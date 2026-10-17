"""Phase1 step 1: add crest_elev_reliable + hazard_threshold_ok to crossings_v2 and tighten data_quality=good.
PROVISIONAL crest cutoffs, based only on 14 NGS marks (s8_deck_check.csv): the bridges with |crest - mark| >= 1.0 m had NBI length >= 39 m or order >= 4 / tidal-like; all bridges
under 32 m long were within 0.75 m. Rule: length < 35 m AND order <= 3 AND not tidal-like AND reach matched. Of the 14 marks only 7 pass (others lack a matched reach order); the 7 that pass
have max |crest - mark| = 0.75 m. hazard_threshold_ok: reach matched, q2 >= 1 cfs (my minimum; order-1 median q2 is 6.4 cfs) and high_water_threshold > 0."""
import json, numpy as np, pandas as pd, geopandas as gpd
P = "data/phase0/"
LEN_MAX_M, ORDER_MAX, Q2_MIN_CFS = 35.0, 3, 1.0
X = gpd.read_parquet(P + "crossings_v2.parquet")
if "data_quality_v1" not in X: X["data_quality_v1"] = X.data_quality
seed = X.src != "osm_secondary"; ln = pd.to_numeric(X.nbi_structure_len_m, errors="coerce")
why = np.select([~seed, ln.isna(), ln >= LEN_MAX_M, X.strm_order.isna(), X.strm_order > ORDER_MAX, X.flag_tidal_like.fillna(False)],
                ["secondary_osm", "no_structure_length", "length>=35m", "no_reach_order", "order>3", "tidal_like"], "ok")
X["crest_elev_reliable"] = why == "ok"; X["crest_reliable_reason"] = why
X["hazard_threshold_ok"] = X.feature_id.notna() & (X.q2_cfs >= Q2_MIN_CFS) & (X.hwt_cfs > 0)
X["hazard_ok_reason"] = np.select([X.feature_id.isna(), X.q2_cfs.isna(), X.q2_cfs <= 0, X.q2_cfs < Q2_MIN_CFS, ~(X.hwt_cfs > 0)], ["no_reach", "no_threshold", "q2_zero", "q2<1cfs", "hwt<=0"], "ok")
dq = X.data_quality_v1.copy(); g = (dq == "good") & ~(X.crest_elev_reliable & X.hazard_threshold_ok); dq[g] = "fair"; X["data_quality"] = dq
X.to_parquet(P + "crossings_v2.parquet"); X.to_file(P + "crossings_v2.geojson", driver="GeoJSON")
st = dict(cutoffs=dict(structure_len_m_lt=LEN_MAX_M, order_le=ORDER_MAX, q2_min_cfs=Q2_MIN_CFS, status="provisional, 14 NGS marks"),
          crest_reliable=int(X.crest_elev_reliable.sum()), crest_reason=X.crest_reliable_reason.value_counts().to_dict(), hazard_ok=int(X.hazard_threshold_ok.sum()), hazard_reason=X.hazard_ok_reason.value_counts().to_dict(),
          quality_before=X.data_quality_v1.value_counts().to_dict(), quality_after=X.data_quality.value_counts().to_dict(), good_downgraded=int(g.sum()),
          seed_quality_after=X[seed].data_quality.value_counts().to_dict(), seed_hazard_ok=int(X[seed].hazard_threshold_ok.sum()), seed_n=int(seed.sum()))
# retro check on the 14 marks
D = pd.read_csv(P + "s8_deck_check.csv").merge(X[["crossing_id", "crest_elev_reliable"]], on="crossing_id")
st["marks_reliable_n"] = int(D.crest_elev_reliable.sum()); st["marks_reliable_max_abs_crest_minus_mark"] = float(D[D.crest_elev_reliable].crest_minus_mark.abs().max()); st["marks_unreliable_min_abs"] = float(D[~D.crest_elev_reliable].crest_minus_mark.abs().min())
json.dump(st, open(P + "p1_flags_stats.json", "w"), indent=1); print(json.dumps(st, indent=1))
