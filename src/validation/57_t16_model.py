"""T16 step 2 (Amendment 5, docs/validation_protocol.md): leave-one-storm-out logistic regression and one HistGradientBoosting model on the crossing x event table; Helene (E5) never trained on, reported separately.
Nothing is tuned. Pass rule: primary model = HGB; pooled LOSO AUC (mean of the 8 event AUCs) > baseline (raw peak/q10) AND paired bootstrap difference CI excludes 0. Stop rule: any pooled AUC > 0.85 -> exit before writing results.
Usage (repo root): python src/57_t16_model.py"""
import sys, json, numpy as np, pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
O = "data/phase2/t16/"; NB = 10000; rng = np.random.default_rng(20261012)
F = pd.read_parquet(O + "t16_features.parquet").reset_index(drop=True); F["y"] = F.pos100.astype(int); HEL = "E5"; EVS = sorted(e for e in F.event_id.unique() if e != HEL)
for c in ("log_r10", "log_r2"): F[c] = F[c].clip(lower=np.log(1e-4))   # Amendment 5a: ln(max(ratio, 1e-4)); zero-flow rows rank lowest
for c in ("log_r10", "log_r2", "hours_above_q2"): assert np.isfinite(F[c]).all(), f"non-finite {c}"
D = pd.get_dummies(F.stype, prefix="stype").astype(float); TYPE = list(D.columns); F = pd.concat([F, D], axis=1)
GROUPS = {"log_r10": ["log_r10"], "log_r2": ["log_r2"], "hours_above_q2": ["hours_above_q2"], "structure_length": ["len_m", "len_missing"], "stream_order": ["stream_order"], "tidal_flag": ["tidal_flag"], "structure_type": TYPE, "hand": ["hand_clearance_m", "hand_missing"]}
BASEF = ["log_r10", "log_r2", "hours_above_q2", "len_m", "len_missing", "stream_order", "tidal_flag"] + TYPE; HANDF = ["hand_clearance_m", "hand_missing"]
def mats(cols):   # tree gets NaN natively; logistic gets the registered missing indicators with the value column set to 0 (model-input encoding only, data untouched)
    X = F[cols].astype(float); XL = X.copy()
    for c in ("len_m", "hand_clearance_m"):
        if c in XL: XL[c] = XL[c].fillna(0.0)
    return X, XL
def auc(pos, neg):
    if len(pos) == 0 or len(neg) == 0: return np.nan
    r = rankdata(np.r_[pos, neg]); return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
def new_models(): return dict(logistic=make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)), hgb=HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.1, random_state=0, early_stopping=False))
def fit_predict(cols, train_idx, test_idx, perm=None):
    X, XL = mats(cols); out = {}
    for name, m in new_models().items():
        Xm = XL if name == "logistic" else X[[c for c in X.columns if X[c].nunique() > 1]]   # scikit-learn's HGB cannot ingest a constant or all-NaN column (the HAND columns have no coverage); dropping it cannot change the tree
        m.fit(Xm.iloc[train_idx], F.y.values[train_idx]); out[name] = (m, Xm)
    return out
# ---------- leave-one-storm-out ----------
VARIANTS = {"without_hand": BASEF, "with_hand": BASEF + HANDF}; OOF = F[["event_id", "crossing_id", "cty", "y"]].copy(); OOF["base"] = F.log_r10.values; IMP = []
for vn, cols in VARIANTS.items():
    for name in ("logistic", "hgb"): OOF[f"{name}_{vn}"] = np.nan
    for e in EVS:
        tr = np.where(~F.event_id.isin([e, HEL]))[0]; te = np.where(F.event_id == e)[0]; fitted = fit_predict(cols, tr, te)
        for name, (m, Xm) in fitted.items():
            OOF.loc[te, f"{name}_{vn}"] = m.predict_proba(Xm.iloc[te])[:, 1]
            if vn == "without_hand":   # permutation importance on the held-out event (5 repeats)
                base_auc = auc(OOF.loc[te][F.y.values[te] == 1][f"{name}_{vn}"].values, OOF.loc[te][F.y.values[te] == 0][f"{name}_{vn}"].values); r = np.random.default_rng(7)
                for g, gc in GROUPS.items():
                    gc = [c for c in gc if c in Xm.columns]
                    if not gc: continue
                    drops = []
                    for _ in range(5):
                        Xp = Xm.iloc[te].copy(); p = r.permutation(len(te)); Xp[gc] = Xp[gc].values[p]; s = m.predict_proba(Xp)[:, 1]; yy = F.y.values[te]; drops.append(base_auc - auc(s[yy == 1], s[yy == 0]))
                    IMP.append(dict(model=name, event_id=e, group=g, auc_drop=float(np.mean(drops))))
    # Helene: trained on all eight non-Helene events
    tr = np.where(F.event_id != HEL)[0]; te = np.where(F.event_id == HEL)[0]; fitted = fit_predict(cols, tr, te)
    for name, (m, Xm) in fitted.items(): OOF.loc[te, f"{name}_{vn}"] = m.predict_proba(Xm.iloc[te])[:, 1]
SC = ["base", "logistic_without_hand", "hgb_without_hand", "logistic_with_hand", "hgb_with_hand"]
def event_aucs(df, sc, evs): return {e: auc(g[g.y == 1][sc].values, g[g.y == 0][sc].values) for e, g in df[df.event_id.isin(evs)].groupby("event_id")}
pooled = {sc: float(np.mean(list(event_aucs(OOF, sc, EVS).values()))) for sc in SC}; print("pooled LOSO AUC (mean of 8 event AUCs):", {k: round(v, 3) for k, v in pooled.items()})
bad = {k: v for k, v in pooled.items() if k != "base" and v > 0.85}
if bad: print("STOP: pooled AUC above 0.85 ->", bad, "-> leak audit required before reporting. No result tables written."); sys.exit(2)
dif = {k: float(np.max(np.abs(OOF[f"{k}_with_hand"].values - OOF[f"{k}_without_hand"].values))) for k in ("logistic", "hgb")}; print("max |with HAND - without HAND| prediction difference:", dif)
# ---------- bootstrap over (event, county) cells ----------
cells = {k: g.index.values for k, g in OOF[OOF.event_id.isin(EVS)].groupby(["event_id", "cty"])}; keys = list(cells); Y = OOF.y.values
def boot_pooled(scores, nb=NB):
    res = {s: [] for s in scores}; evs = EVS
    for _ in range(nb):
        pick = rng.integers(0, len(keys), len(keys)); per = {e: [] for e in evs}
        for i in pick: per[keys[i][0]].append(cells[keys[i]])
        vals = {s: [] for s in scores}
        for e in evs:
            if not per[e]: continue
            idx = np.concatenate(per[e]); y = Y[idx]
            if y.sum() == 0 or y.sum() == len(y): continue
            for s in scores: v = OOF[s].values[idx]; vals[s].append(auc(v[y == 1], v[y == 0]))
        for s in scores: res[s].append(np.mean(vals[s]) if vals[s] else np.nan)
    return {s: np.array(v) for s, v in res.items()}
BS = ["base", "logistic_without_hand", "hgb_without_hand"]; bt = boot_pooled(BS); ci = lambda a: [round(float(np.nanpercentile(a, 2.5)), 3), round(float(np.nanpercentile(a, 97.5)), 3)]
res = {"pooled_auc": {k: round(v, 3) for k, v in pooled.items()}, "pooled_ci95": {s: ci(bt[s]) for s in BS}, "diff_vs_baseline": {}}
for s in BS[1:]:
    d = bt[s] - bt["base"]; res["diff_vs_baseline"][s] = dict(diff=round(pooled[s] - pooled["base"], 3), ci95=ci(d), excludes_zero=bool(np.nanpercentile(d, 2.5) > 0 or np.nanpercentile(d, 97.5) < 0))
prim = res["diff_vs_baseline"]["hgb_without_hand"]; res["PRIMARY_verdict"] = "PASS" if (pooled["hgb_without_hand"] > pooled["base"] and prim["ci95"][0] > 0) else "FAIL"
# ---------- per event, Helene, within-county ----------
rows = []
for e in EVS + [HEL]:
    g = OOF[OOF.event_id == e]; ks = [k for k in cells if k[0] == e] if e != HEL else list(g.groupby("cty").groups)
    cl = {k: g[g.cty == (k[1] if e != HEL else k)].index.values for k in ks}; r = dict(event_id=e, n_pos=int(g.y.sum()), n_neg=int((1 - g.y).sum()))
    for s in BS:
        r[f"auc_{s}"] = round(auc(g[g.y == 1][s].values, g[g.y == 0][s].values), 3); bb = []
        for _ in range(2000):
            pick = rng.integers(0, len(ks), len(ks)); idx = np.concatenate([cl[ks[i]] for i in pick]); y = Y[idx]
            if 0 < y.sum() < len(y): v = OOF[s].values[idx]; bb.append(auc(v[y == 1], v[y == 0]))
        r[f"ci_{s}"] = ci(bb)
    rows.append(r)
PE = pd.DataFrame(rows); PE.to_csv(O + "t16_per_event.csv", index=False)
def within(sc, evs):   # concordant pairs / pairs, pairs only inside (event, county) cells with >= 5 positives and >= 5 negatives
    c = [];
    for (e, ct), g in OOF[OOF.event_id.isin(evs)].groupby(["event_id", "cty"]):
        p, n = g[g.y == 1][sc].values, g[g.y == 0][sc].values
        if len(p) >= 5 and len(n) >= 5: r = rankdata(np.r_[p, n]); a = (r[:len(p)].sum() - len(p) * (len(p) + 1) / 2); c.append((a, len(p) * len(n)))
    return np.array(c)
wc = {}
for grp, evs in (("loso_non_helene", EVS), ("helene", [HEL])):
    for s in BS:
        c = within(s, evs); pt = c[:, 0].sum() / c[:, 1].sum(); bb = []
        for _ in range(NB): pick = rng.integers(0, len(c), len(c)); bb.append(c[pick, 0].sum() / c[pick, 1].sum())
        wc[f"{grp}|{s}"] = dict(auc=round(float(pt), 3), ci95=ci(bb), cells=len(c))
res["within_county_auc"] = wc
H = OOF[OOF.event_id == HEL]; res["helene"] = {s: dict(auc=round(auc(H[H.y == 1][s].values, H[H.y == 0][s].values), 3)) for s in SC}
IM = pd.DataFrame(IMP).groupby(["model", "group"]).auc_drop.agg(["mean", "std"]).round(4).reset_index().sort_values(["model", "mean"], ascending=[True, False]); IM.to_csv(O + "t16_permutation_importance.csv", index=False)
OOF.to_parquet(O + "t16_oof_predictions.parquet"); json.dump(res, open(O + "t16_results.json", "w"), indent=1, default=str)
pd.set_option("display.width", 230, "display.max_columns", 30); print(json.dumps(res, indent=1, default=str)); print(PE.to_string(index=False)); print(IM.to_string(index=False))
