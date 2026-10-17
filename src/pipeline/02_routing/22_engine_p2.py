"""PHASE 2 COPY of src/phase1/engine2.py (reads data/phase1b inputs, writes replays to data/phase2/engine/; variants in inputs()).
Phase1b routing engine (v2). Differences from engine.py: closure SCENARIOS are recurrence levels (closed when flow > the reach's 2/5/10/25/50-yr flow) plus a labelled REFERENCE (3.64 x high_water_threshold,
the median flood-stage/threshold ratio; not a recurrence level, not a probability); facilities = hospitals (40 km set; ED and non-ED), fire stations, and derived EXIT points; inputs/outputs in data/phase1b/.
All results are SCENARIOS. Usage: python engine2.py <flows.parquet m3/s> <label>"""
import os, sys, time, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
O = "data/phase1b/"; W = "data/phase2/engine/"; CFS = 35.3146667
SCEN = [("RL2", "q2_cfs", 1.0), ("RL5", "q5_cfs", 1.0), ("RL10", "q10_cfs", 1.0), ("RL25", "q25_cfs", 1.0), ("RL50", "q50_cfs", 1.0), ("REF_3.64xHWT", "hwt_cfs", 3.64)]

class Net:
    def __init__(self):
        S = gpd.read_parquet(O + "graph_segments.parquet"); self.n = int(max(S.u.max(), S.v.max())) + 1; a, b, w, s = [], [], [], []
        for u, v, t, ow, sid in zip(S.u.values, S.v.values, S.time_s.values, S.oneway.values, S.seg_id.values):
            if u == v: continue
            if ow in ("fwd", "both"): a.append(u); b.append(v); w.append(t); s.append(sid)
            if ow in ("rev", "both"): a.append(v); b.append(u); w.append(t); s.append(sid)
        A = pd.DataFrame(dict(a=a, b=b, w=w, s=s)).sort_values("w").drop_duplicates(["a", "b"], keep="first")
        self.arc_a, self.arc_b, self.arc_w, self.arc_s = A.a.values, A.b.values, A.w.values, A.s.values; self.arc_seg = {(x, y): z for x, y, z in zip(self.arc_a, self.arc_b, self.arc_s)}
    def csr(self, closed):
        k = ~np.isin(self.arc_s, list(closed)) if closed else np.ones(len(self.arc_s), bool)
        return csr_matrix((self.arc_w[k], (self.arc_b[k], self.arc_a[k])), shape=(self.n, self.n))   # transposed: distance from facility = travel time node -> facility

def resnap(org):
    """Re-snap each origin to the nearest node of the LARGEST weakly connected component (phase1b snapped some blocks to 1-10-node fragments = baseline-unreachable). snap_m is recomputed (planar metres via EPSG:5070)."""
    from scipy.sparse.csgraph import connected_components; from scipy.spatial import cKDTree
    net = Net(); _, lab = connected_components(net.csr(set()), directed=True, connection="weak"); big = lab == np.bincount(lab).argmax()
    N = pd.read_parquet(O + "graph_nodes.parquet"); N = N.reset_index() if "node" not in N.columns else N; N = N[big[N.node.values]]
    g = lambda lon, lat: gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs=4326).to_crs(5070); a = g(N.lon.values, N.lat.values); b = g(org.lon.values, org.lat.values)
    d, i = cKDTree(np.c_[a.x, a.y]).query(np.c_[b.x, b.y]); org = org.copy(); org["node"] = N.node.values[i]; org["snap_m"] = d; return org

def inputs():
    X = pd.read_parquet(O + "crossing_snap.parquet"); X = X[X.snap_seg.notna() & X.feature_id.notna() & X.hazard_threshold_ok].copy(); X["snap_seg"] = X.snap_seg.astype(int)
    T = pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "q2_cfs", "q5_cfs", "q10_cfs", "q25_cfs", "q50_cfs", "hwt_cfs"]); X = X.drop(columns=["crest_elev_reliable"], errors="ignore").merge(T, on="crossing_id").merge(
        pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "crest_elev_reliable"]), on="crossing_id")
    seed = X.src != "osm_secondary"; sets = {"seed": X[seed], "seed_reliable": X[seed & X.crest_elev_reliable.fillna(False)], "seed_plus_osm_secondary": X}
    org = pd.read_parquet(O + "origins_snapped.parquet")
    if os.environ.get("P2_RESNAP"): org = resnap(org)
    org = org[org.snap_m < 1500].reset_index(drop=True)
    if os.environ.get("P2_NOLONG"):
        L = pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "nbi_structure_len_m"]); L["len"] = pd.to_numeric(L.nbi_structure_len_m, errors="coerce"); drop = set(L[L.len >= float(os.environ["P2_NOLONG"])].crossing_id)
        sets = {k: v[~v.crossing_id.isin(drop)] for k, v in sets.items()}
    H = pd.read_parquet(O + "hospitals_snapped.parquet"); E = pd.read_csv(O + "exits.csv"); F = pd.read_parquet(O + "firestations_snapped.parquet")
    fac = {"hospital_ED_acute": dict(nodes=H[H.ed & ~H.is_behavioral_or_nonacute].node.unique(), red_s=1800, sets=("seed", "seed_reliable", "seed_plus_osm_secondary")),
           "fire_station": dict(nodes=F.node.unique(), red_s=0, sets=("seed",)),
           "exit_major": dict(nodes=E[E.major].node.unique(), red_s=0, sets=("seed", "seed_reliable", "seed_plus_osm_secondary")),
           "exit_major_plus_secondary": dict(nodes=E.node.unique(), red_s=0, sets=("seed", "seed_reliable"))}
    return sets, org, fac

def seg_ratio(cfs, C, col, mult):
    idx = {c: i for i, c in enumerate(cfs.columns.astype(str))}; q = cfs.values[:, [idx[str(int(f))] for f in C.feature_id]] / (C[col].values[None, :] * mult)   # >1 means flow above the level
    segs = np.sort(C.snap_seg.unique()); out = np.zeros((q.shape[0], len(segs)))
    for j, sg in enumerate(segs): out[:, j] = np.nanmax(np.where(np.isnan(q[:, C.snap_seg.values == sg]), -1, q[:, C.snap_seg.values == sg]), axis=1)   # NaN flow = unknown = not closed
    return segs, out

def solve(net, closed, fnodes, red_s):
    M = net.csr(closed); d, pred, src = dijkstra(M, directed=True, indices=fnodes, min_only=True, return_predecessors=True); red = None
    if red_s:
        red = np.zeros(net.n, int)
        for f in fnodes: red += (dijkstra(M, directed=True, indices=[f], limit=red_s)[0] <= red_s)
    return d, pred, red

def run(flows_path, label):
    t0 = time.time(); net = Net(); sets, org, fac = inputs(); F = pd.read_parquet(flows_path); cfs = F * CFS; onode = org.node.values; pop = org.pop20.values
    seg_cross = {k: C.groupby("snap_seg").crossing_id.apply(list).to_dict() for k, C in sets.items()}; aff_rows, base_rows, hourly, statemap = [], [], [], []
    for ftype, fc in fac.items():
        fnodes = list(map(int, fc["nodes"])); d0, p0, r0 = solve(net, set(), fnodes, fc["red_s"]); base_t = d0[onode]; base_ok = np.isfinite(base_t)
        base_rows.append(pd.DataFrame(dict(facility_type=ftype, geoid20=org.geoid20, county=org.county, lat=org.lat, pop20=pop, baseline_reachable=base_ok, baseline_tt_min=base_t / 60, baseline_redundancy=(r0[onode] if r0 is not None else np.nan))))
        cache = {}
        def path_segs(node):
            if node in cache: return cache[node]
            ps, cur = [], node
            while p0[cur] >= 0 and np.isfinite(d0[cur]) and d0[cur] > 0: nx = p0[cur]; ps.append(net.arc_seg.get((cur, nx), net.arc_seg.get((nx, cur)))); cur = nx
            cache[node] = ps; return ps
        for sname in fc["sets"]:
            C = sets[sname]
            for scen, col, mult in SCEN:
                segs, R = seg_ratio(cfs, C, col, mult); cl = R > 1; _, first, inv = np.unique(np.packbits(cl, axis=1), axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
                for sid, fi in enumerate(first):
                    closed = set(map(int, segs[cl[fi]])); d, pr, red = solve(net, closed, fnodes, fc["red_s"]) if closed else (d0, p0, r0); t = d[onode]
                    with np.errstate(invalid="ignore"): det = (t - base_t) / 60
                    aff = base_ok & (~np.isfinite(t) | (np.nan_to_num(det, nan=0) > 1) | ((red[onode] != r0[onode]) if red is not None else False)); crit = {}
                    for i in np.where(aff)[0]:
                        for sg in path_segs(int(onode[i])):
                            if sg in closed: crit[i] = (seg_cross[sname].get(sg) or [None])[0]; break
                    ai = np.where(aff)[0]
                    aff_rows.append(pd.DataFrame(dict(facility_type=ftype, crossing_set=sname, scenario=scen, state_id=sid, geoid20=org.geoid20.values[ai], county=org.county.values[ai], pop20=pop[ai], reachable=np.isfinite(t[ai]),
                                                      tt_min=np.where(np.isfinite(t[ai]), t[ai] / 60, np.nan), detour_min=np.where(np.isfinite(t[ai]), det[ai], np.nan), critical_crossing_baseline_path=[crit.get(i) for i in ai],
                                                      redundancy=(red[onode][ai] if red is not None else np.nan), baseline_redundancy=(r0[onode][ai] if r0 is not None else np.nan), n_closed_segments=len(closed))))
                    m = inv == sid; unreach = (~np.isfinite(t) & base_ok); slow = (np.isfinite(t) & base_ok & (np.nan_to_num(det, nan=0) > 10))
                    for county in [None] + sorted(org.county.unique()):
                        sel = np.ones(len(org), bool) if county is None else (org.county.values == county); den = pop[sel & base_ok].sum()
                        statemap.append(dict(facility_type=ftype, crossing_set=sname, scenario=scen, state_id=sid, county=county or "ALL", n_hours=int(m.sum()), n_closed_segments=len(closed), pop_unreachable=int(pop[sel & unreach].sum()),
                                             share_unreachable=float(pop[sel & unreach].sum() / den) if den else np.nan, pop_detour_gt10min=int(pop[sel & slow].sum()), pop_base=int(den)))
                    hourly.append(pd.DataFrame(dict(hour=F.index[m], facility_type=ftype, crossing_set=sname, scenario=scen, state_id=sid, n_closed_segments=len(closed))))
            print(ftype, "done", round(time.time() - t0), "s", flush=True)
    pd.concat(aff_rows, ignore_index=True).to_parquet(W + f"replay_{label}_origin_state.parquet"); pd.concat(base_rows, ignore_index=True).to_parquet(W + f"replay_{label}_baseline.parquet")
    pd.concat(hourly, ignore_index=True).to_parquet(W + f"replay_{label}_hour_state.parquet"); pd.DataFrame(statemap).to_parquet(W + f"replay_{label}_state_summary.parquet"); print("saved", label, round(time.time() - t0), "s; origins", len(org))

if __name__ == "__main__": run(sys.argv[1], sys.argv[2])
