"""Phase1b step 4: label check WITH negatives. For each of the 24 label-matched Florence reports (crossing on the named road <= 500 m), the percentile rank of its crossing among ALL seed crossings in the same county
(hazard-assessed ones) for (a) peak recurrence bin and (b) earliest 2-yr exceedance. High percentile = higher bin / earlier exceedance; ties count as not-higher (strictly-lower share + half of ties, i.e. mid-rank).
Reported crossings that are OSM-secondary are ranked against the seed distribution of their county (they are not in it). Null: one random seed crossing per report from the same county, 5000 draws; one-sided permutation p for the median.
If reported crossings do not rank higher, that is what gets reported. Crossings never exceeding 2-yr, or left-censored (already above at series start), have no exceedance time and are left out of the time metric (not filled).
Usage: python p9_label_negatives.py <recurrence_<label>.parquet> <label>"""
import sys, json, numpy as np, pandas as pd
O = "data/phase1b/"; lab = sys.argv[2]; rng = np.random.default_rng(0)
S = pd.read_parquet(O + f"recurrence_{lab}.parquet"); seed = S[S.in_seed].copy()
R = pd.read_csv("data/phase1/p6b_label_vs_replay.csv")[["report_id", "time_utc", "remark", "crossing_id", "crossing_set"]].rename(columns={"crossing_set": "crossing_src"})
R = R.merge(S, on="crossing_id", how="left"); R["assessed"] = R.peak_bin.notna()
def midrank_pct(v, pool):   # share of pool strictly lower + half ties
    pool = np.asarray(pool, float); return 100 * (np.mean(pool < v) + 0.5 * np.mean(pool == v))
bin_pool = {c: g.peak_bin_idx.values for c, g in seed.groupby("county")}
t_pool = {c: ((g.first_q2 - pd.Timestamp("2018-01-01")).dt.total_seconds() / 3600).values for c, g in seed.groupby("county")}   # NaN = never/censored
def pct_time(r):
    if pd.isna(r.first_q2): return np.nan
    p = t_pool[r.county]; v = (r.first_q2 - pd.Timestamp("2018-01-01")).total_seconds() / 3600; ok = p[~np.isnan(p)]
    return 100 * (np.mean(ok > v) + 0.5 * np.mean(ok == v)) if len(ok) else np.nan   # earlier than a larger share of observed times = higher
R["pct_peak_bin"] = [midrank_pct(r.peak_bin_idx, bin_pool[r.county]) if r.assessed else np.nan for _, r in R.iterrows()]
R["pct_earliest_q2"] = [pct_time(r) if r.assessed else np.nan for _, r in R.iterrows()]
R.to_csv(O + f"p9_label_negatives_{lab}.csv", index=False)
def summ(v):
    v = v.dropna(); return dict(n=int(len(v)), median=round(float(v.median()), 1), mean=round(float(v.mean()), 1), share_ge_50=round(float((v >= 50).mean()), 2), share_ge_75=round(float((v >= 75).mean()), 2)) if len(v) else dict(n=0)
a = R[R.assessed]
def null_median(pcts_by_county, counties, fn):
    sims = []
    for _ in range(5000):
        vals = [fn(c) for c in counties]; sims.append(np.nanmedian(vals))
    return np.array(sims)
cs = a.county.tolist()
pb = {c: np.array([midrank_pct(x, bin_pool[c]) for x in bin_pool[c]]) for c in bin_pool}
pt = {}
for c, g in seed.groupby("county"):
    ok = t_pool[c][~np.isnan(t_pool[c])]; pt[c] = np.array([100 * (np.mean(ok > v) + 0.5 * np.mean(ok == v)) for v in ok]) if len(ok) else np.array([np.nan])
sb = null_median(pb, cs, lambda c: rng.choice(pb[c])); st_ = null_median(pt, cs, lambda c: rng.choice(pt[c]))
obs_b, obs_t = a.pct_peak_bin.median(), a.pct_earliest_q2.median()
st = dict(series=lab, n_reports=len(R), assessed=int(R.assessed.sum()), not_assessed_no_reach_or_threshold=int((~R.assessed).sum()), assessed_by_crossing_src=a.crossing_src.value_counts().to_dict(), left_censored_q2_among_assessed=int(a.left_censored_q2.sum()),
          peak_bin_percentile=summ(R.pct_peak_bin), earliest_q2_percentile=summ(R.pct_earliest_q2), peak_bin_percentile_structure_crossings_only=summ(R[R.crossing_src == "ncdot+nbi"].pct_peak_bin),
          earliest_q2_percentile_structure_crossings_only=summ(R[R.crossing_src == "ncdot+nbi"].pct_earliest_q2), reported_peak_bin_counts=a.peak_bin.value_counts().to_dict(), seed_peak_bin_counts=seed.peak_bin.value_counts().to_dict(),
          null_median_peak_bin_pct_mean=round(float(np.nanmean(sb)), 1), perm_p_peak_bin_one_sided=round(float(np.mean(sb >= obs_b)), 3),
          null_median_earliest_q2_pct_mean=round(float(np.nanmean(st_)), 1), perm_p_earliest_q2_one_sided=round(float(np.mean(st_ >= obs_t)), 3) if pd.notna(obs_t) else None)
json.dump(st, open(O + f"p9_label_negatives_{lab}.json", "w"), indent=1, default=str); print(json.dumps(st, indent=1, default=str))
