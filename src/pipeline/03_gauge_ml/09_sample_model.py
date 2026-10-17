"""Sample model (quick sanity check, NOT tuned): HistGradientBoosting on NWM-only features -> exceed_next_12h, official-stage gauges.
Train: split == trainval, cv_fold in 0..3 (negatives subsampled 10%, all positives kept). Fixed hyperparameters, no search, no early stopping.
Eval (never trained on): VAL = trainval fold 4 (held-out events), UNSEEN gauges (non-Florence), TEST = Florence. Same rows scored by the
Kill Test 1 baselines (baseline_ratio, nwm_flow_pctile). Observed stage/discharge are NOT features (they would trivialise the task).
Output: data/derived/sample_model.csv, reports/sample_model.md
"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve
from common import *

FEATS = ["nwm_flow", "nwm_chg_1h", "nwm_chg_3h", "nwm_chg_6h", "nwm_chg_12h", "nwm_chg_24h", "nwm_lag_1h", "nwm_lag_3h", "nwm_lag_6h",
         "nwm_lag_12h", "nwm_lag_24h", "nwm_flow_pctile", "baseline_ratio", "stream_order", "month"]
Y = "exceed_next_12h"
cols = ["usgs_id", "event_id", "split", "cv_fold", "in_pilot", "is_exceed_now", Y] + FEATS
df = pd.concat([pd.read_parquet(p, columns=cols) for p in sorted((DER / "ml_full_table").glob("usgs_id=*/part.parquet"))], ignore_index=True)
df = df[df[Y].notna()]  # primary-label gauges, label known

tr = df[(df.split == "trainval") & (df.cv_fold <= 3)]
rng = np.random.default_rng(42)
tr = tr[(tr[Y] == 1) | (rng.random(len(tr)) < 0.10)]
print("train rows", len(tr), "positives", int(tr[Y].sum()), flush=True)
m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, random_state=42, early_stopping=False)
m.fit(tr[FEATS], tr[Y])

EV = {"VAL (held-out events, trained gauges)": (df.split == "trainval") & (df.cv_fold == 4),
      "UNSEEN gauges (non-Florence)": df.split == "unseen", "TEST (Florence)": df.split == "test"}
rows = []
for name, mk in EV.items():
    for pop, pm in (("all hours", df.index == df.index), ("onset only", ~df.is_exceed_now.astype(bool))):
        d = df[mk & pm & df.baseline_ratio.notna() & df.nwm_flow_pctile.notna()]  # same rows as Kill Test 1
        y = d[Y].values.astype(float)
        if y.sum() == 0:
            continue
        d = d.assign(model=m.predict_proba(d[FEATS])[:, 1])
        for sc in ("model", "baseline_ratio", "nwm_flow_pctile"):
            ap = average_precision_score(y, d[sc]); pr, rc, _ = precision_recall_curve(y, d[sc])
            # event-cluster bootstrap of PR-AUC (B=200; TEST is one event -> gauge clusters), exact AP on resampled rows' cluster sums
            cl = d.usgs_id.values if name.startswith("TEST") else d.event_id.values
            cu, ci = np.unique(cl, return_inverse=True)
            o = np.argsort(-d[sc].values, kind="stable"); ys, cs = y[o], ci[o]
            bs = []
            for _ in range(200):
                w = np.bincount(rng.integers(0, len(cu), len(cu)), minlength=len(cu))[cs]
                tp = np.cumsum(ys * w); n = np.cumsum(w); P = tp[-1]
                bs.append(np.sum(ys * w / P * tp / np.maximum(n, 1)) if P > 0 else np.nan)
            lo, hi = np.nanpercentile(bs, [2.5, 97.5])
            rows.append({"eval_set": name, "population": pop, "score": sc, "gauges": d.usgs_id.nunique(), "rows": len(d), "positives": int(y.sum()),
                         "base_rate": y.mean(), "pr_auc": ap, "x_base": ap / y.mean(), "ci_lo": lo, "ci_hi": hi,
                         "recall_at_50pct_precision": float(rc[pr >= 0.5].max()) if (pr >= 0.5).any() else 0.0})
res = pd.DataFrame(rows)
res.to_csv(DER / "sample_model.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(res.round(4).to_string())
