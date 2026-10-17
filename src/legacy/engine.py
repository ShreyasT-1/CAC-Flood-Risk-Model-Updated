"""Phase1 routing engine. Multi-source shortest path from facilities over the OSM drive graph; edge (segment) closures from a hazard function.
Hazard = flow(cfs) / reach high_water_threshold(cfs); a crossing is CLOSED when ratio > scenario ratio. Scenario ratios are SCENARIOS, not probabilities: the ratio->closure mapping is uncalibrated
(see data/phase0/p2_stats.json: official flood stage is a median 3.6 x high_water_threshold, so ratio 1.0 closes roads well below flood stage).
Usage: python engine.py <flows.parquet (hours x feature_id, m3/s)> <label e.g. hindcast_nwm_v30_retro>"""
import sys, json, time, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
O = "data/phase1/"; CFS = 35.3146667
SCEN_REQUESTED = (0.5, 0.75, 1.0, 1.5)
SCEN_EXTENDED = (3.64, 10.0, 30.0, 60.0, 100.0)   # added because Florence peak flow/hwt is 9-143x on every seed crossing, so the requested ratios saturate; 3.64 = median q_fs/hwt (p2)
SCEN = SCEN_REQUESTED + SCEN_EXTENDED
FAC = {"hospital": dict(file="hospitals_snapped.parquet", red_limit_s=1800), "fire_station": dict(file="firestations_snapped.parquet", red_limit_s=600)}   # redundancy = facilities reachable within this time

class Net:
    def __init__(self):
        S = gpd.read_parquet(O + "graph_segments.parquet"); self.S = S; n = int(max(S.u.max(), S.v.max())) + 1; self.n = n
        a, b, w, s = [], [], [], []
        for u, v, t, ow, sid in zip(S.u.values, S.v.values, S.time_s.values, S.oneway.values, S.seg_id.values):
            if u == v: continue
            if ow in ("fwd", "both"): a.append(u); b.append(v); w.append(t); s.append(sid)
            if ow in ("rev", "both"): a.append(v); b.append(u); w.append(t); s.append(sid)
        A = pd.DataFrame(dict(a=a, b=b, w=w, s=s)).sort_values("w").drop_duplicates(["a", "b"], keep="first")   # parallel arcs: keep the fastest (small approximation)
        self.arc_a, self.arc_b, self.arc_w, self.arc_s = A.a.values, A.b.values, A.w.values, A.s.values
        self.arc_seg = {(x, y): z for x, y, z in zip(self.arc_a, self.arc_b, self.arc_s)}
    def csr(self, closed):
        k = ~np.isin(self.arc_s, list(closed)) if closed else np.ones(len(self.arc_s), bool)
        return csr_matrix((self.arc_w[k], (self.arc_b[k], self.arc_a[k])), shape=(self.n, self.n))   # TRANSPOSED: distances from facilities = travel time node -> facility

def load_inputs():
    X = pd.read_parquet(O + "crossing_snap.parquet"); X = X[X.snap_seg.notna() & X.feature_id.notna() & X.hazard_threshold_ok].copy(); X["snap_seg"] = X.snap_seg.astype(int)
    T = pd.read_parquet("data/phase0/reach_thresholds.parquet").set_index("feature_id").hwt_cfs
    X["hwt_cfs"] = X.feature_id.astype("int64").map(T).values
    X = X.drop(columns=["crest_elev_reliable"], errors="ignore").merge(pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "crest_elev_reliable"]), on="crossing_id", how="left")
    # seed_reliable: structure crossings whose crest elevation passed the provisional short/low-order/non-tidal test; long, high-level or tidal bridges are NOT closed by a flow ratio (their deck clearance is unknown)
    sets = {"seed": X[X.src != "osm_secondary"], "seed_reliable": X[(X.src != "osm_secondary") & X.crest_elev_reliable.fillna(False)], "seed_plus_osm_secondary": X}
    org = pd.read_parquet(O + "origins_snapped.parquet"); org = org[org.snap_m < 1500].reset_index(drop=True)   # origins >1.5 km from any graph node are dropped and counted, not filled
    return sets, org

def seg_ratio(flows_cfs, C):
    """hours x segments ratio = max over crossings on the segment of flow/hwt"""
    cols = flows_cfs.columns.astype(str); idx = {c: i for i, c in enumerate(cols)}
    r = flows_cfs.values[:, [idx[str(int(f))] for f in C.feature_id]] / C.hwt_cfs.values[None, :]
    segs = np.sort(C.snap_seg.unique()); out = np.zeros((r.shape[0], len(segs)))
    for j, sg in enumerate(segs): out[:, j] = r[:, (C.snap_seg.values == sg)].max(axis=1)
    return segs, out

def solve(net, closed, fac_nodes, red_nodes_list, red_limit):
    M = net.csr(closed)
    d, pred, src = dijkstra(M, directed=True, indices=fac_nodes, min_only=True, return_predecessors=True)
    red = np.zeros(net.n, int)
    for f in red_nodes_list:
        dd = dijkstra(M, directed=True, indices=[f], limit=red_limit); red += (dd[0] <= red_limit)
    return d, pred, red

def run(flows_path, label):
    t0 = time.time(); net = Net(); sets, org = load_inputs(); F = pd.read_parquet(flows_path); cfs = F * CFS
    onode = org.node.values; pop = org.pop20.values
    seg_cross = {k: C.groupby("snap_seg").crossing_id.apply(list).to_dict() for k, C in sets.items()}
    rows_aff, rows_base, hourly, statemap = [], [], [], []
    for ftype, fc in FAC.items():
        fn = pd.read_parquet(O + fc["file"]).node.unique(); fnodes = list(map(int, fn))
        d0, p0, r0 = solve(net, set(), fnodes, fnodes, fc["red_limit_s"]); base_t = d0[onode]; base_ok = np.isfinite(base_t)
        rows_base.append(pd.DataFrame(dict(facility_type=ftype, geoid20=org.geoid20, county=org.county, pop20=pop, baseline_reachable=base_ok, baseline_tt_min=base_t / 60, baseline_redundancy=r0[onode])))
        pathcache = {}
        def path_segs(node):
            if node in pathcache: return pathcache[node]
            ps, cur = [], node
            while p0[cur] >= 0 and np.isfinite(d0[cur]) and d0[cur] > 0:
                nx = p0[cur]; ps.append(net.arc_seg.get((cur, nx), net.arc_seg.get((nx, cur)))); cur = nx
            pathcache[node] = ps; return ps
        for sname, C in sets.items():
            if ftype == "fire_station" and sname != "seed": continue   # runtime: fire stations on the primary crossing set only
            segs, R = seg_ratio(cfs, C)
            for sc in SCEN:
                cl = R > sc; key = np.packbits(cl, axis=1); _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
                for sid, fi in enumerate(first):
                    closed = set(map(int, segs[cl[fi]]))
                    d, pr, red = solve(net, closed, fnodes, fnodes, fc["red_limit_s"]) if closed else (d0, p0, r0)
                    t = d[onode]; ok = np.isfinite(t) & base_ok; det = (t - base_t) / 60
                    aff = base_ok & (~np.isfinite(t) | (np.nan_to_num(t - base_t, nan=0) > 60) | (red[onode] != r0[onode]))   # >1 min slower, unreachable, or fewer facilities in range
                    crit = [None] * len(onode)
                    for i in np.where(aff)[0]:
                        for sg in path_segs(int(onode[i])):
                            if sg in closed: crit[i] = (seg_cross[sname].get(sg) or [None])[0]; break
                    rows_aff.append(pd.DataFrame(dict(facility_type=ftype, crossing_set=sname, scenario_ratio=sc, state_id=sid, geoid20=org.geoid20.values[aff], county=org.county.values[aff], pop20=pop[aff],
                                                      reachable=np.isfinite(t[aff]), tt_min=np.where(np.isfinite(t[aff]), t[aff] / 60, np.nan), detour_min=np.where(np.isfinite(t[aff]), det[aff], np.nan),
                                                      critical_crossing_baseline_path=[crit[i] for i in np.where(aff)[0]], redundancy=red[onode][aff], baseline_redundancy=r0[onode][aff], n_closed_segments=len(closed))))
                    m = (inv == sid); hrs = F.index[m]
                    unreach = (~np.isfinite(t) & base_ok); slow = (np.isfinite(t) & base_ok & (det > 10))
                    for county in [None] + sorted(org.county.unique()):
                        sel = np.ones(len(org), bool) if county is None else (org.county.values == county); den = pop[sel & base_ok].sum()
                        statemap.append(dict(facility_type=ftype, crossing_set=sname, scenario_ratio=sc, state_id=sid, county=county or "ALL", n_hours=int(m.sum()), n_closed_segments=len(closed),
                                             pop_unreachable=int(pop[sel & unreach].sum()), share_unreachable=float(pop[sel & unreach].sum() / den) if den else np.nan, pop_detour_gt10min=int(pop[sel & slow].sum()), pop_base=int(den)))
                    hourly.append(pd.DataFrame(dict(hour=hrs, facility_type=ftype, crossing_set=sname, scenario_ratio=sc, state_id=sid, n_closed_segments=len(closed))))
            print(ftype, sname, "done", round(time.time() - t0), "s", flush=True)
    tag = label
    pd.concat(rows_aff, ignore_index=True).to_parquet(O + f"replay_{tag}_origin_state.parquet"); pd.concat(rows_base, ignore_index=True).to_parquet(O + f"replay_{tag}_baseline.parquet")
    pd.concat(hourly, ignore_index=True).to_parquet(O + f"replay_{tag}_hour_state.parquet"); pd.DataFrame(statemap).to_parquet(O + f"replay_{tag}_state_summary.parquet")
    print("saved", tag, "elapsed", round(time.time() - t0), "s; origins used", len(org), "of snapped (dropped >1.5 km)", )

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
