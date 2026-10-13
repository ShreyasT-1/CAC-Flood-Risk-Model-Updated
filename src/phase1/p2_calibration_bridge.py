"""Phase1 step 2: what recurrence level does official flood stage (q_fs_cfs, from observed stage-discharge pairs) roughly correspond to on the NWM reach? NOT a skill claim."""
import json, requests, numpy as np, pandas as pd
D = "data/derived/"; P = "data/phase0/"
q = pd.read_csv(D + "q_fs_estimates.csv", dtype={"usgs_id": str}); q = q[q.q_fs_cfs.notna()]
c = pd.read_csv(D + "gauge_crosswalk.csv", dtype={"usgs_id": str}).drop_duplicates("usgs_id")
m = q.merge(c[["usgs_id", "feature_id", "stream_order", "drainage_area", "in_pilot"]], on="usgs_id", how="left")
U = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"
ids = m.feature_id.astype("int64").unique().tolist(); rows = []
for i in range(0, len(ids), 100):
    r = requests.post(U, data=dict(where="feature_id IN (%s)" % ",".join("'%d'" % x for x in ids[i:i + 100]), outFields="feature_id,high_water_threshold,rf_10_0_17c,rf_5_0_17c,rf_2_0_17c,rf_25_0_17c,rf_50_0_17c", returnGeometry="false", f="json"), timeout=120).json()
    rows += [f["attributes"] for f in r["features"]]
T = pd.DataFrame(rows).rename(columns={"high_water_threshold": "hwt", "rf_2_0_17c": "q2", "rf_5_0_17c": "q5", "rf_10_0_17c": "q10", "rf_25_0_17c": "q25", "rf_50_0_17c": "q50"}); T["feature_id"] = T.feature_id.astype("int64")
m = m.merge(T, on="feature_id", how="left")
for k in ("hwt", "q2", "q5", "q10"): m["r_" + k] = np.where(m[k] > 0, m.q_fs_cfs / m[k], np.nan)   # zero threshold -> NaN, not filled
m.to_csv(P + "p2_calibration_bridge.csv", index=False)
def summ(g, cols=("r_hwt", "r_q2", "r_q5", "r_q10")):
    return {c_: dict(n=int(g[c_].notna().sum()), p10=round(float(g[c_].quantile(.1)), 2), median=round(float(g[c_].median()), 2), p90=round(float(g[c_].quantile(.9)), 2)) for c_ in cols}
st = dict(n=len(m), missing_thresholds=int(m.hwt.isna().sum()), zero_hwt=int((m.hwt <= 0).sum()), overall=summ(m),
          by_quality={k: summ(g) for k, g in m.groupby("q_fs_quality")}, by_order={int(k): dict(n=len(g), **summ(g, ("r_hwt", "r_q2", "r_q5"))) for k, g in m.groupby("stream_order")},
          share_qfs_between_q2_and_q10=round(float(((m.q_fs_cfs >= m.q2) & (m.q_fs_cfs <= m.q10)).mean()), 3), share_qfs_below_q2=round(float((m.q_fs_cfs < m.q2).mean()), 3), share_qfs_above_q10=round(float((m.q_fs_cfs > m.q10).mean()), 3),
          share_qfs_above_q50=round(float((m.q_fs_cfs > m.q50).mean()), 3), corr_log_qfs_log_hwt=round(float(np.corrcoef(np.log(m.q_fs_cfs[m.hwt > 0]), np.log(m.hwt[m.hwt > 0]))[0, 1]), 3),
          good_only_share_between_q2_q10=round(float(((m.q_fs_cfs >= m.q2) & (m.q_fs_cfs <= m.q10))[m.q_fs_quality == "good"].mean()), 3))
json.dump(st, open(P + "p2_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
