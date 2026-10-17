"""Phase 2 / T2a: alternative, non-saturating hazard severity rules, tested the same way as p9_label_negatives.py:
percentile of each label-matched reported crossing among the hazard-assessed SEED crossings of its county (mid-rank), vs a random-draw null (one crossing per report, same county), one-sided p for the median.
Rules (higher = more severe): peak recurrence bin (phase1 baseline), earliest q2 exceedance (baseline), hours above q2, hours above q10, peak/q10, peak/q2, REF peak/(3.64 x HWT), REF hours above,
and flow/q10 AT THE REPORT HOUR vs the county pool at that same hour (time-matched). 'seed_reliable only' = pool and reports restricted to seed_reliable crossings.
All numbers are hindcast (NWM v3.0 retro) or v1.2 forecast-replay SCENARIO rankings, not closure probabilities. Usage (repo root): python src/20_alt_closure_rules.py"""
import json, numpy as np, pandas as pd
P1, O = "data/phase1b/", "data/phase2/"; CFS = 35.3146667; NDRAW = 20000
SERIES = {"hindcast_nwm_v30_retro": "flows_hindcast.parquet", "forecast_nwm_v12_shortrange": "flows_forecast.parquet"}
T = pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "q2_cfs", "q10_cfs", "hwt_cfs"])
L = pd.read_csv("data/phase1/p6b_label_vs_replay.csv")[["report_id", "time_utc", "remark", "crossing_id", "crossing_set"]].rename(columns={"crossing_set": "crossing_src"})
L["t"] = pd.to_datetime(L.time_utc).dt.floor("h")

def mid(v, pool):   # share of pool strictly lower + half ties
    pool = np.asarray(pool, float); pool = pool[np.isfinite(pool)]
    return 100 * (np.mean(pool < v) + 0.5 * np.mean(pool == v)) if len(pool) and np.isfinite(v) else np.nan

def test(vals_by_report, county_of, pool_by_county, seed):
    """vals_by_report: value per assessed report (NaN = not rankable); pool_by_county: arrays. Returns summary dict."""
    rng = np.random.default_rng(seed); pct = np.array([mid(v, pool_by_county[c]) for v, c in zip(vals_by_report, county_of)])
    ok = np.isfinite(pct)
    if ok.sum() < 3: return dict(n=int(ok.sum()), median_pct=None, null_mean_median=None, p_one_sided=None)
    null_pools = {c: np.array([mid(x, p) for x in p[np.isfinite(p)]]) for c, p in pool_by_county.items()}
    cs = [c for c, o in zip(county_of, ok) if o]
    sims = np.median([[rng.choice(null_pools[c]) for c in cs] for _ in range(NDRAW)], axis=1); obs = float(np.median(pct[ok]))
    return dict(n=int(ok.sum()), median_pct=round(obs, 1), share_ge_50=round(float((pct[ok] >= 50).mean()), 2), null_mean_median=round(float(sims.mean()), 1), p_one_sided=round(float(np.mean(sims >= obs)), 3))

out, per_report = [], []
for lab, fl in SERIES.items():
    S = pd.read_parquet(P1 + f"recurrence_{lab}.parquet").merge(T, on="crossing_id"); F = pd.read_parquet(P1 + fl) * CFS; F.columns = F.columns.astype(str)
    S["first_q2_h"] = (S.first_q2 - pd.Timestamp("2018-01-01")).dt.total_seconds() / 3600 * -1   # earlier = larger = more severe; NaN (never/left-censored) = not rankable
    S["peak_over_q10"] = S.peak_flow_cfs / S.q10_cfs; S["peak_over_q2"] = S.peak_flow_cfs / S.q2_cfs
    S["hours_above_ref"] = S["REF_hours_above_3.64xhwt"]; S["peak_over_ref"] = S["REF_peak_over_3.64xhwt"]
    # time-matched: flow/q10 at each report's hour, and the county pool at that same hour
    R = L.merge(S, on="crossing_id", how="left"); R["assessed"] = R.peak_bin.notna(); A = R[R.assessed].copy()
    def at_t(row, cid_row=None):
        return float(F.loc[row.t, str(int(row.feature_id))] / row.q10_cfs) if row.t in F.index else np.nan
    A["flow_over_q10_at_report"] = [at_t(r) for r in A.itertuples()]
    rules = {"peak_bin (phase1 baseline)": "peak_bin_idx", "earliest_q2 (phase1 baseline)": "first_q2_h", "hours_above_q2": "hours_above_q2", "hours_above_q10": "hours_above_q10",
             "peak_flow/q10": "peak_over_q10", "peak_flow/q2": "peak_over_q2", "REF peak/(3.64xHWT)": "peak_over_ref", "REF hours_above_3.64xHWT": "hours_above_ref"}
    for pool_name, mask in (("seed", S.in_seed), ("seed_reliable only", S.in_seed_reliable)):
        pool = S[mask]; Ap = A if pool_name == "seed" else A[A.in_seed_reliable]
        for rn, col in rules.items():
            pb = {c: g[col].values.astype(float) for c, g in pool.groupby("county")}
            res = test(Ap[col].values.astype(float), Ap.county.values, pb, 1); res.update(series=lab, pool=pool_name, rule=rn, n_assessed_reports=len(Ap)); out.append(res)
            if pool_name == "seed": A[f"pct__{rn}"] = [mid(v, pb[c]) for v, c in zip(A[col].astype(float), A.county)]
    if lab.startswith("hindcast"):   # time-matched rule needs the whole pool's flow/q10 at each report hour
        for pool_name, mask in (("seed", S.in_seed), ("seed_reliable only", S.in_seed_reliable)):
            pool = S[mask]; Ap = A if pool_name == "seed" else A[A.in_seed_reliable]; vals, cs, pb_t = [], [], []
            for r in Ap.itertuples():
                g = pool[pool.county == r.county]; qs = (F.loc[r.t, g.feature_id.astype(int).astype(str).values].values / g.q10_cfs.values) if r.t in F.index else np.array([np.nan])
                vals.append(r.flow_over_q10_at_report); cs.append(r.county); pb_t.append(qs)
            # per-report pool differs by hour, so run the null per report with its own pool
            rng = np.random.default_rng(2); pct = np.array([mid(v, p) for v, p in zip(vals, pb_t)]); ok = np.isfinite(pct)
            nullp = [np.array([mid(x, p) for x in p[np.isfinite(p)]]) for p in pb_t]
            sims = np.median([[rng.choice(nullp[i]) for i in np.where(ok)[0]] for _ in range(NDRAW)], axis=1) if ok.sum() >= 3 else None; obs = float(np.median(pct[ok])) if ok.sum() else None
            out.append(dict(series=lab, pool=pool_name, rule="flow/q10 at report hour vs county pool same hour", n_assessed_reports=len(Ap), n=int(ok.sum()), median_pct=None if obs is None else round(obs, 1),
                            share_ge_50=round(float((pct[ok] >= 50).mean()), 2) if ok.sum() else None, null_mean_median=None if sims is None else round(float(sims.mean()), 1), p_one_sided=None if sims is None else round(float(np.mean(sims >= obs)), 3)))
            if pool_name == "seed": A["pct__flow/q10 at report hour"] = pct
    A.assign(series=lab).to_csv(O + f"t2a_report_percentiles_{lab}.csv", index=False)
D = pd.DataFrame(out)[["series", "pool", "rule", "n_assessed_reports", "n", "median_pct", "share_ge_50", "null_mean_median", "p_one_sided"]]; D.to_csv(O + "t2a_rule_comparison.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 60); print(D.to_string(index=False))
# saturation of each rule in the pool: share of seed crossings tied at the modal value
for lab in SERIES:
    S = pd.read_parquet(P1 + f"recurrence_{lab}.parquet"); s = S[S.in_seed]
    print(lab, "seed n", len(s), "| modal peak_bin share", round(s.peak_bin.value_counts(normalize=True).iloc[0], 2), "| hours_above_q10 distinct", s.hours_above_q10.nunique(), "| hours_above_q2 distinct", s.hours_above_q2.nunique())
