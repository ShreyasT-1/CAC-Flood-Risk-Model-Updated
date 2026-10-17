"""T16 POST-HOC diagnostic (NOT pre-registered; does not change the verdict): which feature family carries the T16 gain? Same LOSO scheme, same HGB settings, run on (a) flow-only features, (b) structure-only features (no flow at all).
Usage (repo root): python src/validation/58_t16_posthoc.py"""
import numpy as np, pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
O = "data/phase2/t16/"; F = pd.read_parquet(O + "t16_features.parquet").reset_index(drop=True); F["y"] = F.pos100.astype(int)
for c in ("log_r10", "log_r2"): F[c] = F[c].clip(lower=np.log(1e-4))
F = pd.concat([F, pd.get_dummies(F.stype, prefix="stype").astype(float)], axis=1); TYPE = [c for c in F if c.startswith("stype_")]
FAM = {"flow_only": ["log_r10", "log_r2", "hours_above_q2"], "structure_only (no flow)": ["len_m", "len_missing", "stream_order", "tidal_flag"] + TYPE, "stream_order_only": ["stream_order"]}
def auc(p, n): r = rankdata(np.r_[p, n]); return (r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))
EV = sorted(e for e in F.event_id.unique() if e != "E5"); out = []
for name, cols in FAM.items():
    a = {}
    for e in EV + ["E5"]:
        tr = ~F.event_id.isin([e, "E5"]) if e != "E5" else F.event_id != "E5"; te = F.event_id == e
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.1, random_state=0, early_stopping=False).fit(F.loc[tr, cols].astype(float), F.y[tr]); s = m.predict_proba(F.loc[te, cols].astype(float))[:, 1]; y = F.y[te].values; a[e] = auc(s[y == 1], s[y == 0])
    out.append(dict(features=name, pooled_loso_auc=round(float(np.mean([a[e] for e in EV])), 3), helene=round(float(a["E5"]), 3), **{e: round(float(a[e]), 3) for e in EV}))
R = pd.DataFrame(out); R.to_csv(O + "t16_posthoc_feature_families.csv", index=False); print(R.to_string(index=False))
