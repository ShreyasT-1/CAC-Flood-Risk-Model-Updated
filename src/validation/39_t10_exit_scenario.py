"""Phase 2 / T10E3: does the road GRAPH reproduce the documented isolation of Wilmington if the documented closures are imposed? Two closure sets at the NCDOT snapshot (2018-09-19 19:00 UTC), snapped to phase1b graph segments (<= 50 m):
 (a) DOCUMENTED-UPPER-BOUND: every statewide seed structure (waterway crossing) on a road/county pair NCDOT listed as "closed in sections" that day (the sections are not located, so this over-closes);
 (b) MODEL: the subset of (a)'s assessed structures whose NWM v3.0 retro flow is above q10 at that hour (the hazard rule, = RL10).
Outcome per group: share of baseline-reachable people with NO path to the derived major exit points / to any ED hospital (same definitions as phase-1 p8). This tests graph + inventory, not the hazard layer alone. Hindcast scenario, not a closure estimate.
Usage (repo root): python src/validation/39_t10_exit_scenario.py"""
import sys, json, numpy as np, pandas as pd, geopandas as gpd
sys.path.insert(0, "src/pipeline/02_routing"); sys.path.insert(0, "src/live"); import engine2 as E; from nwm_retro import fetch
O = "data/phase2/t10/"; U = 32617; CFS = 35.3146667
import re
DOC = pd.read_csv("docs/florence_documented_closures.csv"); DOC = DOC[(DOC.status == "verified") & DOC.time_precision.str.startswith("snapshot")]
cs = gpd.read_file("zip://data/raw/counties.zip"); cs = cs[cs.STATEFP == "37"]; code2name = dict(zip(cs.COUNTYFP, cs.NAME.str.upper()))
St = gpd.read_parquet(O + "structures_nc.parquet"); St["cty"] = [c.upper() if not str(c).isdigit() else code2name.get(str(c).zfill(3)) for c in St.county]
TOK = re.compile(r"\b(I|US|NC)[-\s]?(\d+)")
toks = lambda s: {m.group(1) + m.group(2) for m in TOK.finditer(str(s).upper())}
St["rt"] = St.road_carried.map(toks); pairs = {(r, str(c).upper()) for r_, c in zip(DOC.road, DOC.county) for r in toks(r_)}
St["listed"] = [any((r, c) in pairs for r in rt) for rt, c in zip(St.rt, St.cty)]; L = St[St.listed].copy(); print("statewide structures on NCDOT-listed road/county pairs:", len(L))
RC = pd.read_parquet(O + "e_structure_reaches.parquet"); RC = RC.drop_duplicates("crossing_id"); RC["assessed"] = (RC.reach_dist_m <= 100) & (RC.q2_cfs >= 1); L = L.merge(RC, on="crossing_id", how="left"); L["assessed"] = L.assessed.fillna(False).astype(bool)
t = pd.Timestamp("2018-09-19 19:00"); A = L[L.assessed]; F = fetch(A.feature_id.astype("int64").unique(), t, t); L["flow_cfs"] = [float(F[str(int(f))].iloc[0]) * CFS if a else np.nan for f, a in zip(L.feature_id, L.assessed)]
L["model_closed_q10"] = L.assessed & (L.flow_cfs > L.q10_cfs); print("assessed", int(L.assessed.sum()), "model-closed at snapshot (q10)", int(L.model_closed_q10.sum()))
# snap to graph segments
Sg = gpd.read_parquet("data/phase1b/graph_segments.parquet"); Lg = L.to_crs(U); Lg["g"] = Lg.geometry.buffer(50)
c = gpd.sjoin(Lg[["crossing_id", "g"]].set_geometry("g"), Sg[["seg_id", "bridge", "geometry"]], how="inner", predicate="intersects"); c["d"] = [Lg.set_index("crossing_id").geometry.loc[i].distance(Sg.geometry.iloc[int(s)]) for i, s in zip(c.crossing_id, c.seg_id)]
c["bt"] = c.bridge.fillna("") != ""; c = c.sort_values(["crossing_id", "bt", "d"], ascending=[True, False, True]).groupby("crossing_id").first(); L = L.merge(c[["seg_id"]].rename(columns={"seg_id": "snap_seg"}), left_on="crossing_id", right_index=True, how="left")
print("snapped to the phase-1b graph (40 km zone):", int(L.snap_seg.notna().sum()), "of", len(L))
net = E.Net(); sets, org, fac = E.inputs(); onode = org.node.values; pop = org.pop20.values; org["grp"] = np.where(org.county == "New Hanover", np.where(org.lat >= 34.28, "NH north", "NH Wilmington/south"), org.county)
rows = []
for ftype, key in (("exit_major", "exit_major"), ("hospital_ED_acute", "hospital_ED_acute"), ("exit_major_plus_secondary", "exit_major_plus_secondary")):
    fn = list(map(int, fac[key]["nodes"])); d0 = E.solve(net, set(), fn, 0)[0]; ok = np.isfinite(d0[onode])
    for nm, m in (("a_documented_upper_bound", L.snap_seg.notna()), ("b_model_q10", L.snap_seg.notna() & L.model_closed_q10)):
        cl = set(L[m].snap_seg.astype(int)); d = E.solve(net, cl, fn, 0)[0]; lost = ok & ~np.isfinite(d[onode])
        for g in ["Brunswick", "Pender", "NH Wilmington/south", "NH north"]:
            s = (org.grp.values == g) & ok; rows.append(dict(facility=ftype, closure_set=nm, n_segments_closed=len(cl), group=g, pop_base=int(pop[s].sum()), pop_no_path=int(pop[s & lost].sum()), share=round(float(pop[s & lost].sum() / pop[s].sum()), 4)))
R = pd.DataFrame(rows); R.to_csv(O + "t10e3_exit_scenario.csv", index=False); L.drop(columns="geometry").to_csv(O + "t10e3_structures_snapshot.csv", index=False); pd.set_option("display.width", 200); print(R.to_string(index=False))
