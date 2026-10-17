"""Step 7: Kill Test 1 (no model). Score = baseline_ratio (and separately nwm_flow_pctile); target = exceed_next_{1,6,12}h.
Pass bar, fixed in advance: PR-AUC >= 2 x base rate (point estimate; CI reported). Primary-label gauges only (official flood stage).
Subsets: TEST (Florence), UNSEEN gauges (non-Florence), PILOT gauges (non-Florence; and Florence), ALL non-Florence.
Block bootstrap: resample event_id clusters (storm events + quiet stretches) with replacement, B=1000, seed 0, on a 2000-bin
quantile histogram of the score (exact PR-AUC used for the point estimate). TEST is ONE event so event resampling is impossible:
its CI resamples GAUGES instead (labelled). Output: data/derived/kill_test_1.csv
"""
import numpy as np, pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve
from common import *

B, NB = 1000, 2000
rng = np.random.default_rng(0)
cols = ["usgs_id", "event_id", "split", "in_pilot", "is_exceed_now", "baseline_ratio", "nwm_flow_pctile", "exceed_next_1h", "exceed_next_6h", "exceed_next_12h"]
df = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((DER / "ml_full_table").glob("usgs_id=*/part.parquet"))], ignore_index=True)
df = df[df.exceed_next_12h.notna() | df.exceed_next_6h.notna() | df.exceed_next_1h.notna()]  # primary-label gauges only
SUBSETS = {"TEST (Florence)": df.split == "test", "UNSEEN gauges (non-Florence)": df.split == "unseen",
           "PILOT gauges (non-Florence)": df.in_pilot & df.split.isin(["trainval", "unseen"]),
           "PILOT gauges (Florence)": df.in_pilot & (df.split == "test"),
           "ALL non-Florence": df.split.isin(["trainval", "unseen"])}


def ap_binned(pos, neg):
    o = slice(None, None, -1)  # descending score
    tp, fp = np.cumsum(pos[o]), np.cumsum(neg[o])
    P = tp[-1]
    return float(np.sum(pos[o] / P * tp / np.maximum(tp + fp, 1))) if P > 0 else np.nan


def boot(score, y, cl):
    edges = np.unique(np.quantile(score, np.linspace(0, 1, NB + 1)))
    b = np.clip(np.searchsorted(edges, score, side="right") - 1, 0, len(edges) - 2)
    cu, ci = np.unique(cl, return_inverse=True)
    nb = len(edges) - 1
    M = np.stack([np.bincount(ci * nb + b, weights=y, minlength=len(cu) * nb).reshape(len(cu), nb),
                  np.bincount(ci * nb + b, weights=1 - y, minlength=len(cu) * nb).reshape(len(cu), nb)])
    out = []
    for _ in range(B):
        w = np.bincount(rng.integers(0, len(cu), len(cu)), minlength=len(cu))
        out.append(ap_binned(w @ M[0], w @ M[1]))
    return np.nanpercentile(out, [2.5, 97.5]), len(cu)


rows = []
# both scores are always scored on the SAME rows (gauges with a usable Q_fs and a pctile). "all hours" is the pre-registered test;
# "onset only" drops hours where the gauge is already at/above flood stage (persistence makes those positives trivial) -- diagnostic.
for pop, popmask in (("all hours", df.index == df.index), ("onset only (not currently >= flood stage)", ~df.is_exceed_now.astype(bool))):
  for sname, m in SUBSETS.items():
    for target in ("exceed_next_12h", "exceed_next_6h", "exceed_next_1h"):
        common = m & popmask & df[target].notna() & df.baseline_ratio.notna() & df.nwm_flow_pctile.notna()
        for score in ("baseline_ratio", "nwm_flow_pctile"):
            d = df[common]
            r = {"population": pop, "subset": sname, "target": target, "score": score, "rows": len(d), "gauges": d.usgs_id.nunique()}
            if len(d) == 0 or d[target].sum() == 0:
                rows.append({**r, "positives": int(d[target].sum()) if len(d) else 0, "note": "no positives / no rows"}); continue
            y, s = d[target].values.astype(float), d[score].values.astype(float)
            base = y.mean()
            ap = average_precision_score(y, s)
            pr, rc, _ = precision_recall_curve(y, s)
            by_gauge = sname.startswith("TEST")
            ci, ncl = boot(s, y, d.usgs_id.values if by_gauge else d.event_id.values)
            if ncl < 2:
                ci = np.array([np.nan, np.nan])  # single cluster: no resampling variance
            r.update({"positives": int(y.sum()), "events_with_positives": d[d[target] == 1].event_id.nunique(), "base_rate": base,
                      "pr_auc": ap, "pr_auc_over_base": ap / base, "ci_lo": ci[0], "ci_hi": ci[1], "ci_resampled_units": "gauges" if by_gauge else "event_id clusters",
                      "n_clusters": ncl, "recall_at_50pct_precision": float(rc[pr >= 0.5].max()) if (pr >= 0.5).any() else 0.0,
                      "pass_2x_base": bool(ap >= 2 * base)})
            rows.append(r)
res = pd.DataFrame(rows)
res.to_csv(DER / "kill_test_1.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(res[res.target == "exceed_next_12h"].drop(columns=["target", "ci_resampled_units"]).round(4).to_string())
print(res[res.target != "exceed_next_12h"][["population", "subset", "target", "score", "positives", "base_rate", "pr_auc", "pr_auc_over_base", "ci_lo", "ci_hi", "pass_2x_base"]].round(4).to_string())
