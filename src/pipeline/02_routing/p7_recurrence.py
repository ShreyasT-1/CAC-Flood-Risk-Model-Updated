"""Phase1b step 1: per-crossing recurrence-bin summary of a flow series (hindcast or forecast), replacing arbitrary hwt ratios.
Bins (flow vs the reach's NOAA-OWP recurrence flows q2<q5<q10<q25<q50, cfs): 'below_2yr', '2-5', '5-10', '10-25', '25-50', 'above_50'.
3.64 x high_water_threshold is kept as a labelled REFERENCE (median q_fs/hwt from the calibration bridge); it is not a probability and not a recurrence level.
Only crossings with hazard_threshold_ok are summarised (q2 >= 1 cfs, reach matched); the rest are listed as not_assessed, never filled.
First-exceedance times: if the series is ALREADY above the level at its first valid hour the exceedance is LEFT-CENSORED (onset unobservable), flagged, and time is left blank.
Usage: python p7_recurrence.py <flows.parquet m3/s> <label> <crossing_set_name or 'all'>"""
import sys, numpy as np, pandas as pd, geopandas as gpd
O = "data/phase1b/"; CFS = 35.3146667
LV = [("q2", "q2_cfs"), ("q5", "q5_cfs"), ("q10", "q10_cfs"), ("q25", "q25_cfs"), ("q50", "q50_cfs")]
BINS = ["below_2yr", "2-5", "5-10", "10-25", "25-50", "above_50"]

def county_of(X):
    cs = gpd.read_file("data/phase0/counties.geojson")[["NAME", "geometry"]]
    j = gpd.sjoin(X[["crossing_id", "geometry"]], cs, how="left", predicate="within"); return j[~j.index.duplicated()].NAME.reindex(X.index)

def summarise(flows_path, label):
    F = pd.read_parquet(flows_path) * CFS; F.columns = F.columns.astype(str)
    X = gpd.read_parquet("data/phase0/crossings_v2.parquet"); X["county"] = county_of(X)
    X["crossing_set_seed"] = X.src != "osm_secondary"; X["in_seed_reliable"] = X.crossing_set_seed & X.crest_elev_reliable.fillna(False)
    ok = X.feature_id.notna() & X.hazard_threshold_ok & X.feature_id.astype("Int64").astype(str).isin(F.columns)
    rows = []
    for i, r in X[ok].iterrows():
        q = F[str(int(r.feature_id))]; v = q.values; first_valid = q.first_valid_index(); n_valid = int(np.isfinite(v).sum())
        rec = dict(crossing_id=r.crossing_id, src=r.src, in_seed=bool(r.crossing_set_seed), in_seed_reliable=bool(r.in_seed_reliable), county=r.county, data_quality=r.data_quality, strm_order=r.strm_order, feature_id=int(r.feature_id),
                   peak_flow_cfs=float(np.nanmax(v)), n_valid_hours=n_valid, series=label)
        peak = np.nanmax(v); b = sum(peak > r[c] for _, c in LV); rec["peak_bin"] = BINS[b]; rec["peak_bin_idx"] = b
        for nm, c in LV:
            above = v > r[c]; rec[f"hours_above_{nm}"] = int(np.nansum(above))
            if nm in ("q2", "q10", "q50"):
                if above.any():
                    k = int(np.argmax(above)); rec[f"first_{nm}"] = q.index[k] if k > 0 or not np.isnan(v[0]) else pd.NaT
                    rec[f"left_censored_{nm}"] = bool(k == 0 or (np.isnan(v[:k]).all() and np.isfinite(v[k])))   # above at the first valid hour -> onset not observable
                    if rec[f"left_censored_{nm}"]: rec[f"first_{nm}"] = pd.NaT
                else: rec[f"first_{nm}"] = pd.NaT; rec[f"left_censored_{nm}"] = False
        ref = 3.64 * r.hwt_cfs; rec["REF_hours_above_3.64xhwt"] = int(np.nansum(v > ref)); rec["REF_peak_over_3.64xhwt"] = float(peak / ref)
        rows.append(rec)
    S = pd.DataFrame(rows)
    # rank within county among seed crossings by earliest q2 exceedance (rank 1 = earliest); censored/never-exceeded crossings are ranked after observed ones, ties share a rank
    S["rank_first_q2_in_county_seed"] = np.nan
    for cty, g in S[S.in_seed].groupby("county"):
        obs = g.dropna(subset=["first_q2"]); S.loc[obs.index, "rank_first_q2_in_county_seed"] = obs.first_q2.rank(method="min")
    S.to_parquet(O + f"recurrence_{label}.parquet"); S.to_csv(O + f"recurrence_{label}.csv", index=False)
    notass = X[~X.crossing_id.isin(S.crossing_id)]; notass[["crossing_id", "src", "county", "hazard_ok_reason"]].to_csv(O + f"recurrence_{label}_not_assessed.csv", index=False)
    return S, X, notass

if __name__ == "__main__":
    S, X, na = summarise(sys.argv[1], sys.argv[2]); pd.set_option("display.width", 250)
    print(sys.argv[2], "assessed", len(S), "not assessed", len(na), na.hazard_ok_reason.value_counts().to_dict())
    for nm, d in (("seed", S[S.in_seed]), ("seed_reliable", S[S.in_seed_reliable]), ("seed_plus_osm_secondary (sensitivity)", S)):
        print("\ncrossing set:", nm, "n =", len(d)); print(pd.crosstab(d.county, d.peak_bin).reindex(columns=BINS, fill_value=0).to_string())
        print("median hours above q2 / q10 / q50:", d.hours_above_q2.median(), d.hours_above_q10.median(), d.hours_above_q50.median(), "| left-censored q2:", int(d.left_censored_q2.sum()))
