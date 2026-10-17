"""Phase1 step 6b: qualitative comparison of the replay hazard with the 24 label-matched Florence reports (florence_label_review.csv: closure candidates with a crossing on the NAMED road <= 500 m).
For each report: hindcast flow/high_water_threshold of that crossing's reach at the report hour, and which scenarios would have it closed. NOT validation: labels are unreviewed, positives only, and the set is tiny."""
import json, numpy as np, pandas as pd
O = "data/phase1/"; CFS = 35.3146667
C = pd.read_csv("data/phase0/florence_label_review.csv"); C = C[C.auto_tier_from_phase0.isin(["gold", "silver", "bronze"]) & (C.named_road_crossing_dist_m <= 500)].copy()
X = pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "feature_id", "q2_cfs", "hwt_cfs", "strm_order", "data_quality", "crest_elev_reliable", "hazard_threshold_ok", "src", "feature_name"]).set_index("crossing_id")
F = pd.read_parquet(O + "florence_nwm_v30_retro_hourly_m3s.parquet") * CFS
C["time_utc"] = pd.to_datetime(C.time_utc).dt.tz_localize(None); C["hour"] = C.time_utc.dt.floor("h")
rows = []
for _, r in C.iterrows():
    x = X.loc[r.named_road_crossing_id]; fid = x.feature_id
    q = np.nan if pd.isna(fid) or pd.isna(x.hwt_cfs) else float(F.loc[r.hour, str(int(fid))]); qpk = np.nan if pd.isna(fid) else float(F[str(int(fid))].max())
    rat = q / x.hwt_cfs if pd.notna(q) and x.hwt_cfs and x.hwt_cfs > 0 else np.nan; rpk = qpk / x.hwt_cfs if pd.notna(qpk) and x.hwt_cfs and x.hwt_cfs > 0 else np.nan
    rows.append(dict(report_id=r.report_id, time_utc=r.time_utc, county=r.county, remark=r.remark[:110], crossing_id=r.named_road_crossing_id, dist_m=r.named_road_crossing_dist_m, crossing_set=x.src, quality=x.data_quality, stream=x.feature_name,
                     order=x.strm_order, hazard_ok=x.hazard_threshold_ok, flow_cfs_at_report=q, hwt_cfs=x.hwt_cfs, ratio_at_report=rat, ratio_peak_in_replay=rpk, q_over_q2_at_report=q / x.q2_cfs if pd.notna(q) and x.q2_cfs and x.q2_cfs > 0 else np.nan))
R = pd.DataFrame(rows); R.to_csv(O + "p6b_label_vs_replay.csv", index=False)
v = R.dropna(subset=["ratio_at_report"]); pd.set_option("display.width", 250, "display.max_colwidth", 60)
st = dict(n_reports=len(R), n_with_ratio=len(v), ratio_at_report_quantiles=v.ratio_at_report.quantile([.1, .25, .5, .75, .9]).round(1).to_dict(),
          share_ratio_ge={str(k): round(float((v.ratio_at_report >= k).mean()), 2) for k in (0.5, 1.0, 3.64, 10, 30, 100)}, n_hazard_ok=int(R.hazard_ok.fillna(False).sum()), by_set=R.crossing_set.value_counts().to_dict(),
          report_time_range=[str(R.time_utc.min()), str(R.time_utc.max())], order_dist=R.order.value_counts().sort_index().to_dict(), median_q_over_q2=round(float(v.q_over_q2_at_report.median()), 1))
json.dump(st, open(O + "p6b_stats.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str)); print(R[["time_utc", "remark", "crossing_set", "order", "ratio_at_report", "ratio_peak_in_replay"]].round(1).to_string())
