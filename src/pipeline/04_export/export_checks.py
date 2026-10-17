"""Assertions for the export folder (T6; default data/export/). Exit code 1 and a list of failures if anything is wrong. Usage (repo root): python src/export_checks.py [export_dir]"""
import os, re, sys, json, hashlib, pandas as pd, geopandas as gpd
X = (sys.argv[1] if len(sys.argv) > 1 else "data/export/").rstrip("/") + "/"; bad = []
def chk(ok, msg):
    if not ok: bad.append(msg)
man = json.load(open(X + "manifest.json")); R = lambda f: pd.read_csv(X + f)
cr, co, hr = R("crossings_export.csv"), R("consequence_ranking.csv"), R("florence_replay_hourly.csv"); bl = pd.read_csv(X + "blocks_export.csv", dtype={"geoid20": str}); smp = json.load(open(X + "address_report_sample.json")); gj = gpd.read_file(X + "crossings_export.geojson")
# 1. row counts and hashes match the manifest
for m in man["files"]:
    if m.get("live"): continue   # live layer: rewritten on every run, checked in section 5 (rows must match the manifest there)
    f = m["file"]; n = (len(R(f)) if f.endswith(".csv") else len(json.load(open(X + f))) if f.endswith(".json") else len(gj) if f.endswith(".geojson") else len(open(X + f, encoding="utf-8").read().splitlines()))
    chk(n == m["rows"], f"{f}: {n} rows, manifest says {m['rows']}"); chk(hashlib.sha256(open(X + f, "rb").read()).hexdigest() == m["sha256"], f"{f}: sha256 differs from manifest")
chk({m["file"] for m in man["files"]} == set(os.listdir(X)) - {"manifest.json", "build.log"}, "files in data/export/ and manifest differ")
# 2. ids unique and joining across files
chk(cr.id.is_unique and cr.id.notna().all(), "crossings_export ids not unique/complete"); chk(co.id.is_unique, "consequence ids not unique")
chk(set(co.id) == set(cr.id), "consequence_ranking ids != crossings_export ids"); chk(set(gj.id) == set(cr.id), "geojson ids != csv ids")
cids = {s[k]["crossing_id"] for s in smp for k in ("critical_crossing_for_hospital_access", "critical_crossing_for_fire_access") if s[k].get("crossing_id")}
chk(cids <= set(cr.id), f"sample crossing ids not in crossings_export: {sorted(cids - set(cr.id))[:5]}")
seg = cr.dropna(subset=["graph_segment_id"]).set_index("id").graph_segment_id; c2 = co.dropna(subset=["graph_segment_id"]).set_index("id").graph_segment_id
chk(seg.equals(c2.reindex(seg.index)) and len(seg) == len(c2), "graph_segment_id differs between crossings_export and consequence_ranking")
chk(bl.geoid20.is_unique, "blocks_export geoid20 not unique"); sg = {s["geoid20"] for s in smp}; chk(sg <= set(bl.geoid20), "sample geoid20 not in blocks_export")
chk(bl[["geoid20", "county", "pop20", "lat", "lon", "snap_m", "fema_zone", "fema_zone_class"]].notna().all().all(), "NaN in blocks_export key/FEMA columns"); chk(cr[["fema_zone", "fema_zone_class"]].notna().all().all(), "NaN FEMA zone in crossings_export (use UNMAPPED, never blank)")
chk(bl.baseline_reachable_ed_hospital.dtype == bool and bl.baseline_reachable_fire_station.dtype == bool, "baseline reachability columns not boolean")
# 3. no NaN where defined
cons = [c for c in co.columns if c.startswith(("hosp_", "fire_")) or c in ("people_affected", "blocks_affected", "rank_by_people_affected", "crossings_on_same_segment", "snap_dist_m")]
a = co.consequence_status == "assessed"; chk(co.loc[a, cons].notna().all().all(), "NaN in consequence columns of assessed crossings"); chk(co.loc[~a, cons].isna().all().all(), "values present for crossings marked not assessed")
chk(a.sum() == co.graph_segment_id.notna().sum(), "assessed count != snapped count"); chk((co.loc[a, cons] >= 0).all().all(), "negative consequence value")
th = ["q2_cfs", "q5_cfs", "q10_cfs", "q25_cfs", "q50_cfs"]; ok = cr.hazard_threshold_ok.astype(str).str.lower() == "true"; chk(cr.loc[ok, th].notna().all().all(), "NaN thresholds on hazard_threshold_ok crossings")
chk(cr[["id", "lat", "lon", "data_quality"]].notna().all().all(), "NaN in id/lat/lon/data_quality")
sc = ["blocks_lost_ed_hospital_access", "people_lost_ed_hospital_access", "n_crossings_above_level", "n_crossings_assessed"]; chk(hr[sc].notna().all().all(), "NaN in hourly hospital/crossing columns")
fire = ["blocks_lost_fire_station_access", "people_lost_fire_station_access"]; chk(hr.loc[hr.crossing_set == "seed", fire].notna().all().all(), "NaN fire columns for crossing_set=seed"); chk(hr.loc[hr.crossing_set != "seed", fire].isna().all().all(), "fire columns present where not computed")
chk((hr.n_crossings_above_level <= hr.n_crossings_assessed).all(), "more crossings above level than assessed")
chk(hr.groupby(["crossing_set", "scenario"]).size().nunique() == 1 and hr.hour_utc.nunique() == 1320, "hourly file is not 1320 hours x each set/scenario")
chk(all(s["stamp"] == "SAMPLE - block-centroid estimate" for s in smp) and len(smp) == 25, "sample must be 25 records each stamped 'SAMPLE - block-centroid estimate'")
# 4. forbidden wording anywhere in the export, and limitations copied in full
for f in os.listdir(X):
    t = open(X + f, encoding="utf-8", errors="replace").read().lower()
    for w in ("safe", "no risk"): chk(w not in t, f"forbidden string '{w}' in {f}")
chk(open("reports/phase1_limitations.md", encoding="utf-8").read() in open(X + "README.md", encoding="utf-8").read(), "README does not contain phase1_limitations.md in full")
# 5. live layer (live_conditions.json / .csv): strict JSON, staleness fields, id joins, NaN handling, scenario wording
def _no_const(c): raise ValueError("non-finite number " + c)
try: lj = json.load(open(X + "live_conditions.json", encoding="utf-8"), parse_constant=_no_const)
except ValueError as e: bad.append(f"live_conditions.json is not strict JSON: {e}"); lj = None
lc = pd.read_csv(X + "live_conditions.csv"); lm = {m["file"]: m for m in man["files"] if m.get("live")}
if lj is not None:
    chk(set(lm) == {"live_conditions.json", "live_conditions.csv"}, "live_conditions.json/.csv not (both) in manifest with live=true")
    chk(all(k in lj for k in ("available", "stale", "generated_at", "source", "age_minutes", "label", "stale_after_minutes", "crossings")), "live_conditions.json missing available/stale/generated_at/source/age_minutes/label/stale_after_minutes/crossings")
    chk("not a closure forecast" in lj.get("label", "").lower() and "scenario" in lj.get("label", "").lower(), "live label must say scenario view / not a closure forecast")
    chk(len(lj["crossings"]) == len(lc), "live json and csv row counts differ")
    for f_, n_ in (("live_conditions.json", len(lj["crossings"])), ("live_conditions.csv", len(lc))): chk(lm.get(f_, {}).get("rows") == n_, f"{f_}: manifest rows {lm.get(f_, {}).get('rows')} != {n_}")
    if lj["available"]:
        lv = {"RL0", "RL2", "RL5", "RL10", "RL25", "RL50", "not_assessed", "no_flow_value"}
        chk(lc.crossing_id.is_unique and set(lc.crossing_id) <= set(cr.id), "live crossing_id not unique / not in crossings_export")
        chk(set(lc.crossing_id) == set(cr.id[cr.nwm_feature_id.notna()]), "live crossings != crossings_export rows that have an nwm_feature_id")
        chk(set(lc.level_reached) <= lv, f"live level_reached values outside {sorted(lv)}")
        chk(lc[["crossing_id", "cycle_time_utc", "valid_time_utc", "age_minutes", "stale", "level_reached"]].notna().all().all(), "NaN in live id/time/age/stale/level columns")
        asd_ = lc.level_reached.isin(["RL0", "RL2", "RL5", "RL10", "RL25", "RL50"]); chk(lc.loc[asd_, ["flow_cfs", "ratio_q2", "ratio_q5", "ratio_q10", "ratio_q25", "ratio_q50"]].notna().all().all(), "NaN flow/ratios on an assessed live row")
        chk(lc.loc[lc.level_reached == "not_assessed", ["ratio_q2", "ratio_q10"]].isna().all().all(), "ratios present on a not_assessed live row"); chk((lc.flow_cfs.dropna() >= 0).all(), "negative live flow")
        chk(isinstance(lj["stale"], bool) and lj["stale"] == (lj["age_minutes"] > lj["stale_after_minutes"]), "live stale flag inconsistent with age_minutes"); chk((lc.stale.astype(str).str.lower() == str(lj["stale"]).lower()).all(), "csv stale differs from json stale")
        chk(set(lc.cycle_time_utc) == {lj["cycle_time_utc"]}, "csv cycle_time_utc differs from json")
        hi = {"RL0": 0, "RL2": 2, "RL5": 5, "RL10": 10, "RL25": 25, "RL50": 50}; a_ = lc[asd_]; r_ = a_.level_reached.map(hi); chk(((r_ >= 2) == (a_.ratio_q2 > 1)).all(), "level_reached inconsistent with ratio_q2")
    else:
        chk(len(lj["crossings"]) == 0 and bool(lj.get("explanation")), "live available=false must have an explanation and no crossings")
print("export_checks:", "FAIL" if bad else "PASS", f"({len(bad)} failures)")
for b in bad: print(" -", b)
sys.exit(1 if bad else 0)
