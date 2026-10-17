"""Job 1a: build data/review/label_review_sheet.csv, one row per unreviewed label candidate from data/phase0/florence_label_review.csv (source=florence) and
data/phase2/t10/report_candidates.csv (source=t10). Model suggestions are in model_suggested_* columns (NOT decisions); reviewer_* columns are left EMPTY.
Refuses to overwrite an existing sheet (it may hold the reviewer's work) unless --force. Usage (repo root): python src/validation/69_build_label_review_sheet.py"""
import os, sys, pandas as pd
OUT = "data/review/label_review_sheet.csv"
if os.path.exists(OUT) and "--force" not in sys.argv: sys.exit(f"{OUT} exists; refusing to overwrite (use --force only if it is still empty)")
F = pd.read_csv("data/phase0/florence_label_review.csv"); T = pd.read_csv("data/phase2/t10/report_candidates.csv")
for d in (F, T): assert d.reviewer_decision.isna().all(), "source already has reviewer decisions"
f = pd.DataFrame(dict(source="florence", report_id=F.report_id, date=F.time_utc, county=F.county, remark=F.remark, lat=F.lat, lon=F.lon, nearest_crossing_id=F.nearest_crossing_id,
                      nearest_crossing_name=F.nearest_crossing_stream, nearest_crossing_road=F.nearest_crossing_road, nearest_crossing_dist_m=F.nearest_crossing_dist_m,
                      model_suggested_decision=F.suggested_decision, model_suggested_reason=F.suggested_reason, model_suggested_crossing_id=F.suggested_crossing_id.fillna(F.nearest_crossing_id)))
t = pd.DataFrame(dict(source="t10", report_id=T.report_id, date=T.time_utc, county=T.county, remark=T.remark, lat=T.lat, lon=T.lon, nearest_crossing_id=T.crossing_id,
                      nearest_crossing_name=T.feature_name, nearest_crossing_road=T.road_carried, nearest_crossing_dist_m=T.crossing_dist_m,
                      model_suggested_decision=T.suggested_decision, model_suggested_reason=T.suggested_reason, model_suggested_crossing_id=T.crossing_id))
S = pd.concat([t, f], ignore_index=True); S["model_suggestion_note"] = "model suggestion, not a decision"
S["_o"] = S.model_suggested_decision.map({"uncertain": 0, "accept": 1, "reject": 2}); S["_s"] = (S.source != "t10").astype(int)
S = S.sort_values(["_o", "_s", "date"]).drop(columns=["_o", "_s"]).reset_index(drop=True)
for c in ("reviewer_decision", "reviewer_crossing_id", "reviewer_notes"): S[c] = ""
assert not S.duplicated(["source", "report_id"]).any()
S.to_csv(OUT, index=False); print(len(S), "rows;", S.groupby(["source", "model_suggested_decision"]).size().to_dict())
