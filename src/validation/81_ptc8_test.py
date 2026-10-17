"""PTC8 (Potential Tropical Cyclone Eight, Sept 2024) as a TEST event for the C5 ranking test. Usage (repo root): python src/validation/81_ptc8_test.py   (flow download ~150 hourly files, cached; rerun reads the cache)
Rules fixed here BEFORE the first run (no tuning, no threshold change, no feature selection on this event; metric and pass rule copied from src/validation/54_t15_test.py):
  closures  = data/derived_new/flood_road_events_unified.csv, source_type == confirmed_closure, start 2024-09-14..2024-09-25, area in {B, B_buffer} -> data/derived_new/ptc8_closures.csv.
              duration > 14 days = probable structural damage (flag only): kept as positives in the primary test (they are storm-caused), excluded from timing statistics, and the test is repeated without them.
  crossings = assessed crossings of src/validation/52_t15_crossings.py (same structure->reach match, q2/q10, assessed rule) in the counties that have >= 1 PTC8 closure record; positive = within 100 m of a closure POINT
              (route+milepost point, not surveyed to the crossing; the unified file has no line geometry, unlike 52 which also used lines). 250 m is a sensitivity.
  flows     = NWM operational analysis_assim channel_rt tm00 from gs://national-water-model (same read as src/validation/53_t15_flows.py, NOT the retrospective), window = first start - 2 d .. last start + 1 d (Amendment 4 rule).
  test      = AUC of peak flow / q10 (positives vs negatives), 95% CI by bootstrap over county clusters (10000 resamples); PASS if the lower bound > 0.5, otherwise FAIL (reported either way).
Note: PTC8 is event E4 of the T15 pool already (C5), so this is the same storm re-sliced (TIMS records in New Hanover/Brunswick/Pender + buffer counties only), not an independent held-out storm. See reports/ptc8_test.md."""
import json, time, requests, numpy as np, pandas as pd, geopandas as gpd, netCDF4, threading
from concurrent.futures import ThreadPoolExecutor
from scipy.stats import rankdata
LOCK = threading.Lock(); O = "data/phase2/ptc8/"; G = "https://storage.googleapis.com/national-water-model/"; CFS = 35.3146667; U = 32119; rng = np.random.default_rng(20261016); NB = 10000
import os; os.makedirs(O, exist_ok=True)

# ---- (a) closures ----
d = pd.read_csv("data/derived_new/flood_road_events_unified.csv", low_memory=False)
d["start"] = pd.to_datetime(d.start_time, utc=True); d["end"] = pd.to_datetime(d.end_time, utc=True, errors="coerce")
C = d[(d.source_type == "confirmed_closure") & (d.start >= "2024-09-14") & (d.start < "2024-09-26") & d.area.isin(["B", "B_buffer"])].copy()
C["duration_days"] = ((C.end - C.start).dt.total_seconds() / 86400).round(2); C["probable_structural_damage"] = C.duration_days > 14
C["in_timing_stats"] = ~C.probable_structural_damage & C.end.notna(); C["county_u"] = C.county.str.upper()
C["reason"] = C.detail.str.extract(r"Reason=(.*)")[0].str.replace("\xa0", " ").str.strip()
C.drop(columns=["county_u"]).to_csv("data/derived_new/ptc8_closures.csv", index=False)
print("closures", len(C), "| probable structural damage (> 14 d):", int(C.probable_structural_damage.sum()), list(C[C.probable_structural_damage].road_name.str.split(" ").str[0]))
ctys = sorted(C.county_u.unique())

# ---- (b) crossings + 100 m label (attributes from the T15 crossing sets: same structure -> reach match as src/52) ----
E = pd.read_parquet("data/phase2/t15/t15_crossing_sets.parquet"); E = E[(E.event_id == "E4") & E.cty.isin(ctys)].drop(columns=["event_id", "pos100", "pos250"])
S = gpd.read_parquet("data/phase2/t10/structures_nc.parquet").to_crs(U)[["crossing_id", "geometry"]]
X = gpd.GeoDataFrame(E.merge(S, on="crossing_id", how="left"), geometry="geometry", crs=U).reset_index(drop=True)
assert X.geometry.notna().all() and set(ctys) <= set(X.cty), "a PTC8 county has no assessed crossings in the T15 sets"
pts = gpd.GeoDataFrame(C.reset_index(drop=True), geometry=gpd.points_from_xy(C.lon, C.lat), crs=4326).to_crs(U)
def label(points, rad):
    hit = set(); tree = X.sindex
    for g in points.geometry: hit |= set(X.index[tree.query(g.buffer(rad), predicate="intersects")])
    return X.index.isin(hit)
X["pos100"] = label(pts, 100); X["pos250"] = label(pts, 250); X["pos100_nodamage"] = label(pts[~pts.probable_structural_damage], 100)
# nearest unflagged closure record (<= 100 m) per positive, for the timing statistic
nn = gpd.sjoin_nearest(X[X.pos100][["crossing_id", "geometry"]], pts[~pts.probable_structural_damage][["start", "geometry"]], how="left", max_distance=100); nn = nn[~nn.index.duplicated()]
X["closure_start"] = nn.start.reindex(X.index)
tree0 = X.sindex; pts["has_crossing_100m"] = [len(tree0.query(g.buffer(100), predicate="intersects")) > 0 for g in pts.geometry]
print("closure records with an assessed crossing within 100 m:", int(pts.has_crossing_100m.sum()), "of", len(pts))
print("crossings assessed", len(X), "in counties", ctys, "| positives 100 m", int(X.pos100.sum()), "250 m", int(X.pos250.sum()), "100 m without >14 d rows", int(X.pos100_nodamage.sum()))

# ---- flows: NWM operational analysis (same read as src/validation/53_t15_flows.py) ----
f0, f1 = C.start.min() - pd.Timedelta(days=2), C.start.max() + pd.Timedelta(days=1)
hours = pd.date_range(f0.floor("h").tz_localize(None), f1.ceil("h").tz_localize(None), freq="h"); ids = np.sort(X.feature_id.dropna().astype("int64").unique())
def read(t):
    url = G + f"nwm.{t:%Y%m%d}/analysis_assim/nwm.t{t:%H}z.analysis_assim.channel_rt.tm00.conus.nc"
    for k in range(5):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 404: return t, None, None
            r.raise_for_status()
            with LOCK:
                nc = netCDF4.Dataset("m.nc", memory=r.content); nc.set_auto_maskandscale(False)
                fid = nc["feature_id"][:]; v = nc["streamflow"][:].astype(np.float64); ver = nc.getncattr("NWM_version_number") if "NWM_version_number" in nc.ncattrs() else "NA"; nc.close()
            o = np.argsort(fid); x = v[o[np.searchsorted(fid[o], ids)]]; x[x == -999900] = np.nan; return t, x * 0.01 * CFS, ver
        except Exception: time.sleep(5 * (k + 1))
    return t, "ERR", None
if not os.path.exists(O + "ptc8_flow_hourly.parquet"):
    got, miss, vers, cols = 0, [], set(), {}; t0 = time.time()
    with ThreadPoolExecutor(10) as ex:
        for t, x, ver in ex.map(read, hours):
            if x is None or isinstance(x, str): miss.append(str(t)); continue
            got += 1; vers.add(ver); cols[t] = x
    H = pd.DataFrame(cols, index=ids).sort_index(axis=1); H.columns = H.columns.astype(str); H.to_parquet(O + "ptc8_flow_hourly.parquet")
    json.dump(dict(window_start=str(hours[0]), window_end=str(hours[-1]), hours_expected=len(hours), hours_read=got, missing=miss, versions=sorted(vers), reaches=len(ids), seconds=round(time.time() - t0)), open(O + "ptc8_flow_meta.json", "w"), indent=1)
H = pd.read_parquet(O + "ptc8_flow_hourly.parquet"); meta = json.load(open(O + "ptc8_flow_meta.json")); print("flow meta", meta)
pk = pd.DataFrame({"peak_cfs": H.max(axis=1, skipna=True), "peak_time": pd.to_datetime(H.idxmax(axis=1, skipna=True), utc=True, errors="coerce")}); pk.index.name = "feature_id"
X = X.merge(pk, left_on="feature_id", right_index=True, how="left"); n0 = len(X); X = X[X.peak_cfs.notna()].copy(); print("crossings with a flow peak", len(X), "of", n0)
X["r10"] = X.peak_cfs / X.q10_cfs; X["r2"] = X.peak_cfs / X.q2_cfs

# ---- (c) test ----
def auc(p, n):
    p, n = np.asarray(p, float), np.asarray(n, float)
    if len(p) == 0 or len(n) == 0: return np.nan
    r = rankdata(np.r_[p, n]); return float((r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n)))
def run(D, lab, col="r10"):
    p, n = D[D[lab]][col].values, D[~D[lab]][col].values; a = auc(p, n)
    cells = {k: (g[g[lab]][col].values, g[~g[lab]][col].values) for k, g in D.groupby("cty")}; keys = list(cells); out = []
    for _ in range(NB):
        pick = rng.integers(0, len(keys), len(keys)); v = auc(np.concatenate([cells[keys[i]][0] for i in pick]), np.concatenate([cells[keys[i]][1] for i in pick]))
        if np.isfinite(v): out.append(v)
    ci = [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)] if len(out) > 100 else [None, None]
    hit10, hit2 = D.r10 > 1, D.r2 > 1
    return dict(label=lab, metric=col, n=len(D), n_pos=int(D[lab].sum()), n_neg=int((~D[lab]).sum()), counties=int(D.cty.nunique()), auc=round(a, 3), ci95_county_boot=ci, boot_valid=len(out),
                precision_q10=round(float(D[hit10][lab].mean()), 3) if hit10.any() else None, recall_q10=round(float(hit10[D[lab]].mean()), 3) if D[lab].any() else None,
                precision_q2=round(float(D[hit2][lab].mean()), 3) if hit2.any() else None, recall_q2=round(float(hit2[D[lab]].mean()), 3) if D[lab].any() else None,
                base_rate=round(float(D[lab].mean()), 4), share_gt_q10_pos=round(float((D[D[lab]].r10 > 1).mean()), 3) if D[lab].any() else None, share_gt_q10_neg=round(float((D[~D[lab]].r10 > 1).mean()), 3))
R = {"primary": run(X, "pos100"), "sens_250m": run(X, "pos250"), "sens_no_structural_damage_rows": run(X, "pos100_nodamage"), "sens_r2": run(X, "pos100", "r2")}
lo = R["primary"]["ci95_county_boot"][0]; R["primary"]["verdict"] = "PASS" if lo is not None and lo > 0.5 else "FAIL"
per_county = pd.DataFrame([dict(county=k, n=len(g), n_pos=int(g.pos100.sum()), auc=round(auc(g[g.pos100].r10, g[~g.pos100].r10), 3) if g.pos100.any() and (~g.pos100).any() and g.pos100.sum() >= 3 else None) for k, g in X.groupby("cty")])
strata = []
for col in ("order_class", "reliable_analogue", "tidal"):
    for v, g in X.groupby(col):
        ok = g.pos100.sum() >= 5 and (~g.pos100).sum() >= 5; strata.append(dict(stratum=f"{col}={v}", n=len(g), n_pos=int(g.pos100.sum()), auc=round(auc(g[g.pos100].r10, g[~g.pos100].r10), 3) if ok else None))
tm = X[X.pos100 & X.closure_start.notna() & X.peak_time.notna()]; lag_h = ((tm.closure_start - tm.peak_time).dt.total_seconds() / 3600)
timing = dict(n_positives_with_unflagged_record=int(len(tm)), closure_start_minus_nwm_peak_h_median=round(float(lag_h.median()), 1) if len(tm) else None,
              iqr=[round(float(lag_h.quantile(.25)), 1), round(float(lag_h.quantile(.75)), 1)] if len(tm) else None,
              record_duration_days_median_unflagged=round(float(C[C.in_timing_stats].duration_days.median()), 2), record_duration_days_iqr_unflagged=[round(float(C[C.in_timing_stats].duration_days.quantile(q)), 2) for q in (.25, .75)], n_records_in_timing_stats=int(C.in_timing_stats.sum()))
E4 = pd.read_csv("data/phase2/t15/t15_results_by_event.csv"); E4 = E4[(E4.event_id == "E4") & E4.group.str.startswith("100 m (primary)|all")].iloc[0]
out = dict(results=R, per_county=per_county.to_dict("records"), strata=strata, timing=timing, flow_meta=meta, counties=ctys, closures=dict(n=len(C), records_with_assessed_crossing_100m=int(pts.has_crossing_100m.sum()), structural_damage_flagged=int(C.probable_structural_damage.sum()), by_county=C.county.value_counts().to_dict()),
           t15_E4_for_comparison=dict(n_pos=int(E4.n_pos), n=int(E4.n), auc_r10=float(E4.auc_r10), ci95=E4.auc_r10_ci95_county_boot))
json.dump(out, open(O + "ptc8_results.json", "w"), indent=1, default=str); X.drop(columns="geometry").to_csv(O + "ptc8_crossings_scored.csv", index=False)
print(json.dumps(out, indent=1, default=str))
