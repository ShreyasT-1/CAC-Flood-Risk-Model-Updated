"""Phase 2 / T10B + T10C: self-controlled flow test of the hazard layer. For each accepted flood-closure report: NWM v3.0 retro flow of the crossing's reach at the report hour, its percentile in the reach's own
1979-2023 hourly record, ratios to q2 / q10 (fixed in advance), vs 200 same-reach same-calendar-month control hours (>72 h from any candidate report on that reach); matched AUC; storm-cluster bootstrap (gap > 48 h = new storm);
timing: does the flow peak within +-24 h of the report (window +-72 h) more often than at control hours. All definitions, thresholds and pass rules are in docs/validation_protocol.md (fixed before running). No tuning.
reviewer_decision (if non-blank) overrides suggested_decision. Usage (repo root): python src/33_t10_flow_test.py"""
import json, numpy as np, pandas as pd
O = "data/phase2/t10/"; NCTRL = 200; NBOOT = 10000; W = 72; HIT = 24
D = pd.read_csv(O + "report_candidates.csv", dtype={"reviewer_decision": str}).fillna({"reviewer_decision": ""}); D["decision"] = np.where(D.reviewer_decision.str.strip() != "", D.reviewer_decision.str.strip().str.lower(), D.suggested_decision)
D = D[D.assessed & D.feature_id.notna()].copy(); D["t"] = pd.to_datetime(D.time_utc).dt.tz_localize(None).dt.floor("h"); D["feature_id"] = D.feature_id.astype("int64").astype(str)
F = pd.read_parquet(O + "nwm_full_record.parquet"); H = {c: F[c].values.astype(np.float64) for c in F.columns}; idx = F.index; pos = {t: i for i, t in enumerate(idx)}; NT = len(idx)
month = idx.month.values
def cluster(t):   # storm clusters: gap > 48 h starts a new one
    o = np.argsort(t.values); tt = t.values[o]; g = np.r_[0, np.cumsum(np.diff(tt) > np.timedelta64(48, "h"))]; out = np.empty(len(t), int); out[o] = g; return out
def pct(sorted_v, x):   # strictly below + half ties, share of valid reference hours
    return (np.searchsorted(sorted_v, x, "left") + .5 * (np.searchsorted(sorted_v, x, "right") - np.searchsorted(sorted_v, x, "left"))) / len(sorted_v)
def roll_max(v, k=6):   # centered max over h-k..h+k, NaN-aware (all-NaN -> NaN)
    s = pd.Series(v); return s.rolling(2 * k + 1, center=True, min_periods=1).max().values
def run(R, label, stat="hour", min_order=None, seed=20261011):
    R = R.copy()
    if min_order: R = R[R.strm_order >= min_order]
    if len(R) < 5: return dict(label=label, n=len(R), note="too few reports")
    rng = np.random.default_rng(seed); R["cl"] = cluster(R.t); allrep = D.groupby("feature_id").t.apply(lambda s: [pos[x] for x in s if x in pos]).to_dict()
    ser = {}; rows = []
    for r in R.itertuples():
        if r.feature_id not in ser:
            v = H[r.feature_id]; s = v if stat == "hour" else roll_max(v, 6); ok = np.isfinite(s); ser[r.feature_id] = (s, ok, np.sort(s[ok]))
        s, ok, ref = ser[r.feature_id]; v = H[r.feature_id]; i = pos.get(r.t)
        if i is None or not ok[i]: continue
        ban = np.zeros(NT, bool)
        for j in allrep[r.feature_id]: ban[max(0, j - W):j + W + 1] = True
        elig = np.where(ok & (month == month[i]) & ~ban & (np.arange(NT) >= W) & (np.arange(NT) < NT - W))[0]
        if len(elig) < NCTRL: continue
        ci = rng.choice(elig, NCTRL, replace=False); x = s[i]; cx = s[ci]; q2, q10 = r.q2_cfs / 35.3146667, r.q10_cfs / 35.3146667   # OWP cfs -> m3/s
        auc = float((x > cx).mean() + .5 * (x == cx).mean())
        def peak_hit(j):   # |argmax(v[j-W:j+W]) - j| <= 24 h, and window max > q2
            w = v[j - W:j + W + 1]
            if not np.isfinite(w).any(): return np.nan, np.nan
            k = int(np.nanargmax(w)); return float(abs(k - W) <= HIT), float(np.nanmax(w) > q2)
        ph = peak_hit(i); pc = np.array([peak_hit(j) for j in ci], float)
        rows.append(dict(report_id=r.report_id, cl=r.cl, crossing_id=r.crossing_id, county=r.county, order=r.strm_order, feature_id=r.feature_id, t=r.t, flow_cms=float(x), pct=float(pct(ref, x)), ratio_q2=float(x / q2), ratio_q10=float(x / q10),
                         ctrl_pct_med=float(np.median([pct(ref, c) for c in cx])), rep_gt_q2=float(x > q2), rep_gt_q10=float(x > q10), ctrl_gt_q2=float((cx > q2).mean()), ctrl_gt_q10=float((cx > q10).mean()), auc=auc,
                         hit_rep=ph[0], big_rep=ph[1], hit_ctrl=float(np.nanmean(pc[:, 0])), big_ctrl=float(np.nanmean(pc[:, 1])), hit_ctrl_given_big=float(np.nanmean(pc[pc[:, 1] == 1, 0])) if (pc[:, 1] == 1).any() else np.nan))
    X = pd.DataFrame(rows); X.attrs["label"] = label
    cls = X.cl.unique(); by = {c: X[X.cl == c] for c in cls}
    def stats(df):
        d = dict(auc=df.auc.mean(), d_gt_q2=df.rep_gt_q2.mean() - df.ctrl_gt_q2.mean(), d_gt_q10=df.rep_gt_q10.mean() - df.ctrl_gt_q10.mean(), d_hit=np.nanmean(df.hit_rep) - np.nanmean(df.hit_ctrl))
        b = df[df.big_rep == 1]; d["d_hit_given_big"] = (b.hit_rep.mean() - b.hit_ctrl_given_big.mean()) if len(b) else np.nan; return d
    point = stats(X); boots = []
    for _ in range(NBOOT): boots.append(stats(pd.concat([by[c] for c in rng.choice(cls, len(cls))])))
    B = pd.DataFrame(boots); ci = {k: [round(float(B[k].quantile(.025)), 3), round(float(B[k].quantile(.975)), 3)] for k in point}
    loo = {int(c): round(float(X[X.cl != c].auc.mean()), 3) for c in cls}; big = X.groupby("cl").size(); big = big[big >= 5].index
    out = dict(label=label, stat=stat, n_reports=len(X), n_crossings=int(X.crossing_id.nunique()), n_storm_clusters=len(cls), median_pct_reports=round(float(X.pct.median()), 3), median_pct_controls=round(float(X.ctrl_pct_med.median()), 3),
               share_gt_q2_reports=round(float(X.rep_gt_q2.mean()), 3), share_gt_q2_controls=round(float(X.ctrl_gt_q2.mean()), 4), share_gt_q10_reports=round(float(X.rep_gt_q10.mean()), 3), share_gt_q10_controls=round(float(X.ctrl_gt_q10.mean()), 4),
               median_ratio_q2=round(float(X.ratio_q2.median()), 2), median_ratio_q10=round(float(X.ratio_q10.median()), 2),
               auc=round(float(point["auc"]), 3), auc_ci95=ci["auc"], d_share_gt_q2=round(float(point["d_gt_q2"]), 3), d_share_gt_q2_ci95=ci["d_gt_q2"], d_share_gt_q10=round(float(point["d_gt_q10"]), 3), d_share_gt_q10_ci95=ci["d_gt_q10"],
               timing_hit_reports=round(float(np.nanmean(X.hit_rep)), 3), timing_hit_controls=round(float(np.nanmean(X.hit_ctrl)), 3), timing_diff=round(float(point["d_hit"]), 3), timing_diff_ci95=ci["d_hit"],
               timing_diff_given_window_gt_q2=None if np.isnan(point["d_hit_given_big"]) else round(float(point["d_hit_given_big"]), 3), timing_diff_given_window_gt_q2_ci95=ci["d_hit_given_big"],
               loo_auc_range=[min(loo.values()), max(loo.values())], loo_auc_clusters_ge5={int(c): loo[int(c)] for c in big})
    out["pass_B"] = bool(out["auc_ci95"][0] > .5 and out["d_share_gt_q2_ci95"][0] > 0); out["pass_C"] = bool(out["timing_diff_ci95"][0] > 0); X.to_csv(O + f"t10bc_per_report_{label}.csv", index=False); return out
res = []
P = D[D.decision == "accept"]
res.append(run(P, "primary_hour")); res.append(run(P, "sens_window_max_pm6h", stat="win6")); res.append(run(P, "sens_order_ge2", min_order=2)); res.append(run(D[D.decision.isin(["accept", "uncertain"])], "sens_accept_plus_uncertain"))
json.dump(res, open(O + "t10bc_results.json", "w"), indent=1, default=str)
for r in res: print(json.dumps(r, default=str))
