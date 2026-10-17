"""Phase 2 / T10D (= T9): gauge validation of the NWM v3.0 retrospective flow the hazard layer is built on, at the 43 pilot gauges (pilot-flag crosswalk gauges with observed hourly discharge),
for Matthew (2016-10-05..25) and Florence (2018-09-10..10-31). Definitions and the pre-declared verdict: docs/validation_protocol.md section D. Hindcast only; no tuning.
Usage (repo root): python src/validation/35_t10_gauge_validation.py"""
import json, requests, numpy as np, pandas as pd
O = "data/phase2/t10/"; CFS = 35.3146667
c = pd.read_csv("data/derived/gauge_crosswalk.csv", dtype={"usgs_id": str}); c = c[c.in_pilot].drop_duplicates("usgs_id")
o = pd.read_parquet("data/derived/obs_hourly.parquet", columns=["time_utc", "usgs_id", "obs_q_cfs"]); o = o[o.usgs_id.isin(c.usgs_id)]
n = pd.read_parquet("data/derived/nwm_hourly.parquet"); n = n[n.feature_id.isin(c.feature_id)]
gauges = c[c.usgs_id.isin(o.usgs_id.unique())]; print("pilot gauges with obs series:", len(gauges), "of", len(c))
FS = "https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0/query"; ids = gauges.feature_id.astype("int64").tolist()
import time
for _k in range(8):
    try: r = requests.post(FS, data=dict(where="feature_id IN (%s)" % ",".join("'%d'" % x for x in ids), outFields="feature_id,rf_2_0_17c,rf_10_0_17c", returnGeometry="false", f="json"), timeout=120).json(); break
    except Exception: time.sleep(10)
Q = pd.DataFrame([f["attributes"] for f in r["features"]]).drop_duplicates("feature_id").assign(feature_id=lambda d: d.feature_id.astype("int64")).rename(columns={"rf_2_0_17c": "q2_cfs", "rf_10_0_17c": "q10_cfs"})
EV = {"Matthew": ("2016-10-05", "2016-10-25 23:00"), "Florence": ("2018-09-10", "2018-10-31 23:00")}
def kge(s, m):
    r_ = np.corrcoef(s, m)[0, 1]; a = m.std() / s.std(); b = m.mean() / s.mean(); return 1 - np.sqrt((r_ - 1) ** 2 + (a - 1) ** 2 + (b - 1) ** 2)
rows = []
for g in gauges.itertuples():
    ob = o[o.usgs_id == g.usgs_id].set_index("time_utc").obs_q_cfs; nw = n[n.feature_id == g.feature_id].set_index("time_utc").nwm_flow_cms * CFS; q = Q[Q.feature_id == int(g.feature_id)]
    q2 = float(q.q2_cfs.iloc[0]) if len(q) else np.nan
    for ev, (a, b) in EV.items():
        idx = pd.date_range(a, b, freq="h", tz="UTC"); x = pd.DataFrame({"obs": ob.reindex(idx), "nwm": nw.reindex(idx)}); cov = float(x.obs.notna().mean())
        if cov < .8 or x.nwm.notna().mean() < .8: rows.append(dict(usgs_id=g.usgs_id, feature_id=int(g.feature_id), event=ev, scored=False, obs_coverage=round(cov, 2))); continue
        v = x.dropna(); nse = 1 - ((v.nwm - v.obs) ** 2).sum() / ((v.obs - v.obs.mean()) ** 2).sum()
        rows.append(dict(usgs_id=g.usgs_id, feature_id=int(g.feature_id), event=ev, scored=True, obs_coverage=round(cov, 2), nse=float(nse), kge=float(kge(v.obs, v.nwm)), obs_peak_cfs=float(v.obs.max()), nwm_peak_cfs=float(v.nwm.max()),
                         peak_ratio=float(v.nwm.max() / v.obs.max()), peak_time_err_h=float((v.nwm.idxmax() - v.obs.idxmax()) / pd.Timedelta(hours=1)), q2_cfs=q2,
                         h_both_gt_q2=int(((v.obs > q2) & (v.nwm > q2)).sum()), h_obs_only_gt_q2=int(((v.obs > q2) & ~(v.nwm > q2)).sum()), h_nwm_only_gt_q2=int((~(v.obs > q2) & (v.nwm > q2)).sum())))
R = pd.DataFrame(rows); R.to_csv(O + "t10d_gauge_event_metrics.csv", index=False); v = R[R.scored]
st = dict(gauges=len(gauges), gauge_events_scored=len(v), gauge_events_total=len(R), by_event=v.groupby("event").size().to_dict(),
          median_nse=round(float(v.nse.median()), 2), median_kge=round(float(v.kge.median()), 2), share_nse_gt0=round(float((v.nse > 0).mean()), 2),
          share_peak_ratio_0p5_to_2=round(float(v.peak_ratio.between(.5, 2).mean()), 3), median_peak_ratio=round(float(v.peak_ratio.median()), 2), median_abs_peak_time_err_h=float(v.peak_time_err_h.abs().median()),
          exceed_q2_hours=dict(both=int(v.h_both_gt_q2.sum()), obs_only=int(v.h_obs_only_gt_q2.sum()), nwm_only=int(v.h_nwm_only_gt_q2.sum())))
st["q2_hit_rate_of_observed_hours"] = round(st["exceed_q2_hours"]["both"] / max(1, st["exceed_q2_hours"]["both"] + st["exceed_q2_hours"]["obs_only"]), 3)
st["q2_precision_of_nwm_hours"] = round(st["exceed_q2_hours"]["both"] / max(1, st["exceed_q2_hours"]["both"] + st["exceed_q2_hours"]["nwm_only"]), 3)
st["verdict_pass"] = bool(st["share_peak_ratio_0p5_to_2"] >= .70 and st["median_abs_peak_time_err_h"] <= 12)
json.dump(st, open(O + "t10d_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
print(v.groupby("event")[["nse", "kge", "peak_ratio", "peak_time_err_h"]].median().round(2))
