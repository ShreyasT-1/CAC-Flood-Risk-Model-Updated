"""T6: build data/export/ (website + ML teammate). Structural consequence ranking uses NO hazard/flow input. Origins: phase-1 snap by default (SNAP=resnap for the phase-2 re-snap; see README).
Env: SNAP=phase1 (default) | resnap, EXPORT_DIR. Usage (repo root): python src/export_data.py   ->  then python src/export_checks.py"""
import os, sys, json, hashlib, subprocess, datetime, importlib.util, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
SNAP = os.environ.get("SNAP", "phase1"); assert SNAP in ("phase1", "resnap"); X = os.environ.get("EXPORT_DIR", "data/export/"); os.makedirs(X, exist_ok=True)
if SNAP == "resnap": os.environ["P2_RESNAP"] = "1"   # default is the phase-1 snap (see README: the re-snap failed the 2026-10-12 check)
RP = "resnap" if SNAP == "resnap" else "base"
sp = importlib.util.spec_from_file_location("eng", "src/22_engine_p2.py"); eng = importlib.util.module_from_spec(sp); sp.loader.exec_module(eng)
net = eng.Net(); _, org, fac = eng.inputs(); org = org.reset_index(drop=True); onode = org.node.values; pop = org.pop20.values.astype(float); NO = len(org)
V = pd.read_parquet("data/phase0/crossings_v2.parquet"); SN = pd.read_parquet("data/phase1b/crossing_snap.parquet")[["crossing_id", "snap_seg", "snap_dist_m"]]
H = pd.read_parquet("data/phase1b/hospitals_snapped.parquet"); H = H[H.ed & ~H.is_behavioral_or_nonacute]; F = pd.read_parquet("data/phase1b/firestations_snapped.parquet")

# ---------- 1. crossings ----------
FA = pd.read_csv("data/phase2/fema_assign_crossings.csv").rename(columns={"id": "crossing_id"}); C = V.merge(SN, on="crossing_id", how="left").merge(FA, on="crossing_id", how="left"); seed = C.src != "osm_secondary"
C["seed_reliable"] = np.where(seed, C.crest_elev_reliable.astype("object"), None)   # defined only for structure-seeded crossings; blank for OSM-derived
C["graph_snapped"] = C.snap_seg.notna()
cols = dict(crossing_id="id", lat="lat", lon="lon", road_carried="road", feature_name="stream", nwm_name="nwm_reach_name", county="county", src="src", structure_type="structure_type", data_quality="data_quality", seed_reliable="seed_reliable",
            flag_tidal_like="tidal_flag", nbi_structure_len_m="nbi_structure_len_m", strm_order="stream_order", feature_id="nwm_feature_id", hazard_threshold_ok="hazard_threshold_ok", hazard_ok_reason="hazard_ok_reason",
            q2_cfs="q2_cfs", q5_cfs="q5_cfs", q10_cfs="q10_cfs", q25_cfs="q25_cfs", q50_cfs="q50_cfs", hwt_cfs="hwt_cfs", graph_snapped="graph_snapped", snap_seg="graph_segment_id", fema_zone="fema_zone", fema_zone_subty="fema_zone_subty", fema_zone_class="fema_zone_class", fema_sfha="fema_sfha", fema_static_bfe="fema_static_bfe", fema_n_overlapping_polygons="fema_n_overlapping_polygons")
E = C[list(cols)].rename(columns=cols).sort_values("id").reset_index(drop=True); E.to_csv(X + "crossings_export.csv", index=False)
gpd.GeoDataFrame(E, geometry=gpd.points_from_xy(E.lon, E.lat), crs=4326).to_file(X + "crossings_export.geojson", driver="GeoJSON")

# ---------- 2. consequence ranking (single-crossing closure; hazard-free) ----------
def tree_segs(d, p):   # segments used by the baseline shortest-path tree (a closure outside it cannot change any distance)
    ok = np.isfinite(d) & (p >= 0); u = np.where(ok)[0]; return {net.arc_seg.get((a, b), net.arc_seg.get((b, a))) for a, b in zip(u, p[u])}
def base(nodes):
    M = net.csr(set()); d, p, s = dijkstra(M, directed=True, indices=list(map(int, nodes)), min_only=True, return_predecessors=True); return d, p, s
Hn, Fn = H.node.unique(), F.node.unique(); dH, pH, sH = base(Hn); dF, pF, sF = base(Fn); tH, tF = tree_segs(dH, pH), tree_segs(dF, pF); bH, bF = dH[onode], dF[onode]
okH, okF = np.isfinite(bH), np.isfinite(bF)
FB = pd.read_csv("data/phase2/fema_assign_blocks.csv", dtype={"geoid20": str}); BL = pd.DataFrame(dict(geoid20=org.geoid20.astype(str).values, county=org.county.values, pop20=org.pop20.values, lat=org.lat.values, lon=org.lon.values, snap_m=org.snap_m.round(1).values,
    baseline_reachable_ed_hospital=okH, baseline_reachable_fire_station=okF)).merge(FB, on="geoid20", how="left"); BL.to_csv(X + "blocks_export.csv", index=False)
segs = sorted(set(C.snap_seg.dropna().astype(int))); TH, TF = {}, {}   # seg -> travel time (s) of every origin with that segment closed
for k, sg in enumerate(segs):
    if sg in tH: TH[sg] = eng.solve(net, {sg}, list(map(int, Hn)), 0)[0][onode].astype(np.float32)
    if sg in tF: TF[sg] = eng.solve(net, {sg}, list(map(int, Fn)), 0)[0][onode].astype(np.float32)
    if k % 200 == 0: print("segments", k, "/", len(segs), flush=True)
def effect(T, b, ok, sg):
    t = T.get(sg); z = np.zeros(NO, bool)
    if t is None: return z, z, np.zeros(NO)
    with np.errstate(invalid="ignore"): det = (t - b) / 60
    lost = ok & ~np.isfinite(t); slow = ok & np.isfinite(t) & (np.nan_to_num(det, nan=0) > 1); return lost, slow, np.where(slow, det, 0.0)
rows = []
for sg in segs:
    lh, sh, dh = effect(TH, bH, okH, sg); lf, sf, df = effect(TF, bF, okF, sg); aff = lh | sh | lf | sf; mx = lambda a: float(a.max()) if a.any() else 0.0
    rows.append(dict(graph_segment_id=sg, hosp_pop_lost_access=int(pop[lh].sum()), hosp_blocks_lost_access=int(lh.sum()), hosp_pop_slowed_gt1min=int(pop[sh].sum()), hosp_added_person_hours=float((pop * dh).sum() / 60),
                     hosp_max_detour_min=round(mx(dh), 2), fire_pop_lost_access=int(pop[lf].sum()), fire_blocks_lost_access=int(lf.sum()), fire_pop_slowed_gt1min=int(pop[sf].sum()), fire_added_person_hours=float((pop * df).sum() / 60),
                     fire_max_detour_min=round(mx(df), 2), people_affected=int(pop[aff].sum()), blocks_affected=int(aff.sum())))
R = pd.DataFrame(rows); R["hosp_added_person_hours"] = R.hosp_added_person_hours.round(2); R["fire_added_person_hours"] = R.fire_added_person_hours.round(2)
K = C[["crossing_id", "snap_seg", "snap_dist_m"]].rename(columns={"crossing_id": "id", "snap_seg": "graph_segment_id", "snap_dist_m": "snap_dist_m"})
K = K.merge(R, on="graph_segment_id", how="left"); K["crossings_on_same_segment"] = K.groupby("graph_segment_id").id.transform("size")
K["consequence_status"] = np.where(K.graph_segment_id.notna(), "assessed", "not assessed: crossing not snapped to a graph segment (<= 50 m)")
K["rank_by_people_affected"] = K.people_affected.rank(method="min", ascending=False)
K = K.sort_values(["rank_by_people_affected", "id"]).reset_index(drop=True); K.to_csv(X + "consequence_ranking.csv", index=False)
print("consequence: assessed", int(K.graph_segment_id.notna().sum()), "of", len(K), "| segments in baseline trees", len(set(TH) | set(TF)), "of", len(segs))

# ---------- 3. address-report sample (25 block centroids; structural, no hazard) ----------
rng = np.random.default_rng(20261011); cand = np.where(okH & okF)[0]; pick = []
for cty, n in (("Brunswick", 8), ("New Hanover", 9), ("Pender", 8)):
    pool = [i for i in cand if org.county.values[i].lower().startswith(cty.lower()[:5])]; pick += list(rng.choice(pool, n, replace=False))
cx = C.dropna(subset=["snap_seg"]).copy(); cx["snap_seg"] = cx.snap_seg.astype(int); seg_x = cx.groupby("snap_seg").apply(lambda g: g.sort_values("crossing_id")[["crossing_id", "road_carried", "feature_name"]].values.tolist(), include_groups=False).to_dict()
Mf = csr_matrix((net.arc_w, (net.arc_a, net.arc_b)), shape=(net.n, net.n))
def path(p, d, node):
    out, cur = [], node
    while p[cur] >= 0 and np.isfinite(d[cur]) and d[cur] > 0: nx = p[cur]; out.append(net.arc_seg.get((cur, nx), net.arc_seg.get((nx, cur)))); cur = nx
    return out
def critical(T, b, p, d, i):   # crossing on this block's baseline path whose single closure hurts it most
    best = None
    for sg in path(p, d, int(onode[i])):
        if sg in seg_x and sg in T:
            t = T[sg][i]; delta = np.inf if not np.isfinite(t) else float(t - b[i]) / 60
            if best is None or delta > best[0]: best = (delta, sg)
    if best is None or best[1] is None: return dict(crossing_id=None, note="no inventoried crossing on the baseline path, or closing the crossings on it changes nothing", effect=None)
    cid, road, stream = seg_x[best[1]][0]; ef = "loses all access" if np.isinf(best[0]) else f"+{best[0]:.1f} min"
    return dict(crossing_id=cid, road=None if pd.isna(road) else road, stream=None if pd.isna(stream) else stream, effect_if_closed=ef, crossings_on_segment=len(seg_x[best[1]]))
STAMP = "SAMPLE - block-centroid estimate"; recs = []
for i in pick:
    dd = dijkstra(Mf, directed=True, indices=int(onode[i]))   # forward times from this block's node
    nh = sum(dd[n] <= 1800 for n in Hn); nf = int(sum(dd[n] <= 600 for n in F.node.values)); hi, fi = int(sH[onode[i]]), int(sF[onode[i]])
    recs.append(dict(stamp=STAMP, geoid20=org.geoid20.values[i], county=org.county.values[i], pop20=int(pop[i]), centroid_lat=round(float(org.lat.values[i]), 5), centroid_lon=round(float(org.lon.values[i]), 5),
                     baseline_nearest_ed_hospital=dict(name=H.name.values[H.node.values == hi][0], drive_min=round(float(bH[i]) / 60, 1)), baseline_nearest_fire_station=dict(name=F.name.values[F.node.values == fi][0], drive_min=round(float(bF[i]) / 60, 1)),
                     critical_crossing_for_hospital_access=critical(TH, bH, pH, dH, i), critical_crossing_for_fire_access=critical(TF, bF, pF, dF, i),
                     redundancy=dict(ed_hospitals_within_30_min=int(nh), fire_stations_within_10_min=nf), method="Baseline routing on OSM default speeds, no traffic. Critical crossing = the crossing on the baseline path whose closure alone (whole junction-to-junction segment) hurts this block most. No hazard or flow input."))
json.dump(recs, open(X + "address_report_sample.json", "w"), indent=1)

# ---------- 4. Florence hindcast hourly state (NWM v3.0 retrospective, free-running; scenario levels, not probabilities) ----------
FL = pd.read_parquet("data/phase1b/flows_hindcast.parquet"); cfs = FL * eng.CFS; W = "data/phase2/engine/"
hs = pd.read_parquet(W + "replay_hindcast_" + RP + "_hour_state.parquet"); os_ = pd.read_parquet(W + "replay_hindcast_" + RP + "_origin_state.parquet"); LV = {"RL2": "q2_cfs", "RL5": "q5_cfs", "RL10": "q10_cfs", "RL25": "q25_cfs", "RL50": "q50_cfs"}
lost = os_[~os_.reachable].groupby(["facility_type", "crossing_set", "scenario", "state_id"]).agg(blocks=("geoid20", "size"), people=("pop20", "sum")).reset_index()
Cn = V.merge(SN[["crossing_id"]], on="crossing_id"); base_pop = {}; out = []
for sname, mask in (("seed", Cn.src != "osm_secondary"), ("seed_reliable", (Cn.src != "osm_secondary") & Cn.crest_elev_reliable.fillna(False))):
    Cs = Cn[mask & Cn.hazard_threshold_ok & Cn.feature_id.notna()]; idx = {c: i for i, c in enumerate(cfs.columns.astype(str))}; Q = cfs.values[:, [idx[str(int(f))] for f in Cs.feature_id]]
    for scen, col in LV.items():
        above = (Q > Cs[col].values[None, :]).sum(axis=1); df = pd.DataFrame(dict(hour_utc=cfs.index, crossing_set=sname, scenario=scen, n_crossings_assessed=len(Cs), n_crossings_above_level=above))
        for ft, tag in (("hospital_ED_acute", "ed_hospital"), ("fire_station", "fire_station")):
            if ft == "fire_station" and sname != "seed": df[f"blocks_lost_{tag}_access"] = pd.NA; df[f"people_lost_{tag}_access"] = pd.NA; continue
            h = hs[(hs.facility_type == ft) & (hs.crossing_set == sname) & (hs.scenario == scen)][["hour", "state_id"]]; l = lost[(lost.facility_type == ft) & (lost.crossing_set == sname) & (lost.scenario == scen)]
            m = h.merge(l[["state_id", "blocks", "people"]], on="state_id", how="left").fillna({"blocks": 0, "people": 0}); m = m.set_index("hour")
            df[f"blocks_lost_{tag}_access"] = m.blocks.reindex(df.hour_utc).values; df[f"people_lost_{tag}_access"] = m.people.reindex(df.hour_utc).values
        out.append(df)
FH = pd.concat(out, ignore_index=True)
for c in [c for c in FH.columns if c.startswith(("blocks_lost", "people_lost"))]: FH[c] = FH[c].astype("Int64")
FH["label"] = "hindcast (NWM v3.0 retrospective, free-running); scenario, not a probability"; FH.to_csv(X + "florence_replay_hourly.csv", index=False)

# ---------- README (data dictionary + limitations copied verbatim from phase1_limitations.md) ----------
lim = open("reports/phase1_limitations.md", encoding="utf-8").read()
snapnote = (open("docs/export_snap_sidebyside.md", encoding="utf-8").read() if os.path.exists("docs/export_snap_sidebyside.md") else "(side-by-side table not yet generated)")
README = open("docs/export_readme_head.md", encoding="utf-8").read().replace("{SNAP}", SNAP).replace("{N_ORIGINS}", f"{NO:,}").replace("{SNAP_SECTION}", snapnote) + "\n\n---\n# Known limitations (copied verbatim from `reports/phase1_limitations.md`)\n\n" + lim + "\n"
open(X + "README.md", "w", encoding="utf-8").write(README)

# ---------- manifest ----------
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
try: gh = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
except Exception: gh = "unavailable"
ins = {"crossings": ["data/phase0/crossings_v2.parquet", "data/phase1b/crossing_snap.parquet", "data/phase2/fema_assign_crossings.csv", "data/phase2/fema_nfhl.parquet"], "net": ["data/phase1b/graph_segments.parquet", "data/phase1b/origins_snapped.parquet", "data/phase1b/hospitals_snapped.parquet", "data/phase1b/firestations_snapped.parquet", "data/phase1b/graph_nodes.parquet"]}
replay_in = ["data/phase1b/flows_hindcast.parquet", W + "replay_hindcast_" + RP + "_hour_state.parquet", W + "replay_hindcast_" + RP + "_origin_state.parquet"]
spec = {"crossings_export.csv": ("src/export_data.py", ins["crossings"]), "crossings_export.geojson": ("src/export_data.py", ins["crossings"]), "consequence_ranking.csv": ("src/export_data.py (+src/22_engine_p2.py Net/solve)", ins["crossings"] + ins["net"]),
        "address_report_sample.json": ("src/export_data.py", ins["crossings"] + ins["net"]), "florence_replay_hourly.csv": ("src/export_data.py (+src/22_engine_p2.py replay outputs)", ins["crossings"] + replay_in), "blocks_export.csv": ("src/export_data.py (+src/62_fema_compare.py)", ins["net"] + ["data/phase2/fema_assign_blocks.csv"]), "README.md": ("src/export_data.py + docs/export_readme_head.md", ["reports/phase1_limitations.md", "docs/export_readme_head.md"] + (["docs/export_snap_sidebyside.md"] if os.path.exists("docs/export_snap_sidebyside.md") else []))}
rowcount = lambda f: (len(pd.read_csv(X + f)) if f.endswith(".csv") else len(json.load(open(X + f))) if f.endswith(".json") else len(gpd.read_file(X + f)) if f.endswith(".geojson") else len(open(X + f, encoding="utf-8").read().splitlines()))
man = dict(snap=SNAP, built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), git_head=gh, git_note="most project files are uncommitted, so file sha256 values are the reliable provenance", files=[
    dict(file=f, rows=rowcount(f), row_unit="lines" if f == "README.md" else "records", source_script=s, input_files=i, input_sha256={p: sha(p) for p in i}, sha256=sha(X + f)) for f, (s, i) in spec.items()])
json.dump(man, open(X + "manifest.json", "w"), indent=1); print("wrote", [f for f in spec])
