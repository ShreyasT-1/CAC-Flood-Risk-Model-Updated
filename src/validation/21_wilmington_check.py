"""Phase 2 / T2b: is 'Wilmington loses no access' an artifact? Diagnostics + stress tests with the phase1b graph (engine2.Net). Outputs data/phase2/t2b_*.csv.
Stress tests close segments irrespective of any flow (so they are NOT hazard scenarios): they measure whether the graph/crossing inventory CAN express a Wilmington loss at all.
Usage (repo root): python src/validation/21_wilmington_check.py"""
import sys, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, "src/pipeline/02_routing"); import engine2 as E
from scipy.sparse.csgraph import connected_components
O, P2 = "data/phase1b/", "data/phase2/"; pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 50)
net = E.Net(); sets, org, fac = E.inputs(); X = gpd.read_parquet("data/phase0/crossings_v2.parquet")
cs = gpd.read_file("data/phase0/counties.geojson")[["NAME", "geometry"]]; X = gpd.sjoin(X, cs, how="left", predicate="within").drop(columns="index_right").rename(columns={"NAME": "cty"})
snap = pd.read_parquet(O + "crossing_snap.parquet")[["crossing_id", "snap_seg"]]; X = X.merge(snap, on="crossing_id")
S = gpd.read_parquet(O + "graph_segments.parquet").set_index("seg_id"); org["grp"] = np.where(org.county == "New Hanover", np.where(org.lat >= 34.28, "NH north", "NH Wilmington/south"), org.county)
onode = org.node.values; pop = org.pop20.values; hosp = fac["hospital_ED_acute"]["nodes"]; hosp_nodes = list(map(int, hosp))
# (a) baseline-unreachable people and graph components
M0 = net.csr(set()); ncomp, lab = connected_components(M0, directed=True, connection="weak"); sizes = np.bincount(lab)
d0, p0, _ = E.solve(net, set(), hosp_nodes, 0); base_ok = np.isfinite(d0[onode])
u = org[~base_ok].assign(comp_size=sizes[lab[onode[~base_ok]]], nodes=onode[~base_ok])
print("baseline-unreachable to ANY ED hospital:", int(u.pop20.sum()), "people,", len(u), "blocks; by group:\n", u.groupby("grp").pop20.agg(["sum", "count"]))
print("component size of those origins' snapped node (nodes): ", u.comp_size.describe()[["min", "50%", "max"]].to_dict(), "| largest component nodes:", int(sizes.max()), "of", net.n)
big = u[u.comp_size > 1000].groupby("grp").pop20.sum(); print("unreachable origins sitting in a LARGE component (directed/oneway or segment-level isolation, not a small island):", big.to_dict())
u.sort_values("pop20", ascending=False).head(25)[["geoid20", "grp", "pop20", "lat", "lon", "snap_m", "comp_size"]].to_csv(P2 + "t2b_baseline_unreachable_top25.csv", index=False)
print(u.sort_values("pop20", ascending=False).head(10)[["geoid20", "grp", "pop20", "lat", "lon", "snap_m", "comp_size"]].to_string(index=False))
# (b) how much of Wilmington's baseline routing touches a crossing at all
seed_seg = set(sets["seed"].snap_seg.astype(int)); any_seg = set(X[X.src != "osm_secondary"].snap_seg.dropna().astype(int)); osm_seg = set(X.snap_seg.dropna().astype(int))
def path_segs(node):
    ps, cur = [], node
    while p0[cur] >= 0 and np.isfinite(d0[cur]) and d0[cur] > 0: nx = p0[cur]; ps.append(net.arc_seg.get((cur, nx), net.arc_seg.get((nx, cur)))); cur = nx
    return ps
rows = []
for g in ["NH Wilmington/south", "NH north", "Brunswick", "Pender"]:
    sel = np.where((org.grp.values == g) & base_ok)[0]; ps = [set(path_segs(int(onode[i]))) for i in sel]
    f = lambda S_: float(np.average([bool(p & S_) for p in ps], weights=pop[sel]))
    rows.append(dict(group=g, pop=int(pop[sel].sum()), share_baseline_path_crosses_hazard_assessed_seed=round(f(seed_seg), 3), share_crosses_any_seed_incl_unassessed=round(f(any_seg), 3), share_crosses_any_crossing_incl_osm=round(f(osm_seg), 3),
                     share_path_uses_bridge_tagged_segment=round(float(np.average([any(S.bridge.get(s, None) not in (None, "no", "") and pd.notna(S.bridge.get(s, None)) for s in p) for p in ps], weights=pop[sel])), 3)))
R1 = pd.DataFrame(rows); R1.to_csv(P2 + "t2b_path_exposure.csv", index=False); print("\nBaseline shortest path to nearest ED hospital crosses a crossing (pop-weighted share):\n", R1.to_string(index=False))
# (c) stress tests: close segments regardless of flow
bridges = set(S.index[S.bridge.notna() & ~S.bridge.isin(["no", ""])].astype(int))
nh_seed_assessed = set(X[(X.cty == "New Hanover") & X.hazard_threshold_ok & (X.src != "osm_secondary")].snap_seg.dropna().astype(int))
nh_seed_all = set(X[(X.cty == "New Hanover") & (X.src != "osm_secondary")].snap_seg.dropna().astype(int)); nh_all = set(X[X.cty == "New Hanover"].snap_seg.dropna().astype(int))
all_seed = set(X[X.src != "osm_secondary"].snap_seg.dropna().astype(int))
nhb = set(S.index[S.bridge.notna() & ~S.bridge.isin(["no", ""]) & (gpd.GeoSeries(S.geometry.centroid, crs=S.crs).y.reindex(S.index) > 33.9)].astype(int))
tests = {"A. 33 hazard-assessed NH seed crossings": nh_seed_assessed, "B. all 61 NH seed crossings (incl. not assessed)": nh_seed_all, "C. all NH crossings incl. OSM-secondary": nh_all,
         "D. every seed crossing in 3 counties": all_seed, "E. every OSM bridge-tagged segment in graph": bridges}
rows = []
for nm, cl in tests.items():
    cl = {int(c) for c in cl}; d, _, _ = E.solve(net, cl, hosp_nodes, 0); t = d[onode]
    for g in ["NH Wilmington/south", "NH north", "Brunswick", "Pender"]:
        m = (org.grp.values == g) & base_ok; lost = m & ~np.isfinite(t); slow = m & np.isfinite(t) & ((t - d0[onode]) / 60 > 10)
        rows.append(dict(stress_test=nm, n_segments_closed=len(cl), group=g, pop=int(pop[m].sum()), pop_no_path_to_any_ED=int(pop[lost].sum()), share=round(float(pop[lost].sum() / pop[m].sum()), 4), pop_detour_gt10min=int(pop[slow].sum())))
R2 = pd.DataFrame(rows); R2.to_csv(P2 + "t2b_stress_tests.csv", index=False); print("\nStress tests (ED hospital access, 11 hospitals; flow-independent closures):\n", R2.to_string(index=False))
# (d) single-hospital sensitivity: only NHRMC (node 63718) as the Wilmington destination
n_nhrmc = [63718]; dN, _, _ = E.solve(net, set(), n_nhrmc, 0); rows = []
for nm, cl in tests.items():
    cl = {int(c) for c in cl}; d, _, _ = E.solve(net, cl, n_nhrmc, 0); t = d[onode]
    for g in ["NH Wilmington/south", "NH north"]:
        m = (org.grp.values == g) & np.isfinite(dN[onode]); lost = m & ~np.isfinite(t)
        rows.append(dict(stress_test=nm, group=g, to="NHRMC only", pop=int(pop[m].sum()), pop_no_path=int(pop[lost].sum()), share=round(float(pop[lost].sum() / pop[m].sum()), 4)))
R3 = pd.DataFrame(rows); R3.to_csv(P2 + "t2b_stress_nhrmc_only.csv", index=False); print("\nNHRMC-only destination:\n", R3.to_string(index=False))
# (e) the big Cape Fear / tidal crossings: what the hindcast hazard says for them
S1 = pd.read_parquet(O + "recurrence_hindcast_nwm_v30_retro.parquet")
big = X[(X.cty == "New Hanover") & X.feature_name.str.contains("CAPE FEAR|INTRACOASTAL|SMITH CR|FISHING", na=False)][["crossing_id", "feature_name", "road_carried", "hazard_ok_reason", "flag_tidal_like", "nbi_structure_len_m", "snap_seg"]].merge(S1[["crossing_id", "peak_bin", "hours_above_q2", "hours_above_q50"]], on="crossing_id", how="left")
print("\nNH large/tidal-name crossings:\n", big.sort_values("feature_name").to_string(index=False)); big.to_csv(P2 + "t2b_nh_big_crossings.csv", index=False)
print("\nNH assessed seed crossings flagged tidal_like:", int(X[(X.cty == "New Hanover") & X.hazard_threshold_ok & (X.src != "osm_secondary")].flag_tidal_like.fillna(False).sum()), "of", len(nh_seed_assessed))
