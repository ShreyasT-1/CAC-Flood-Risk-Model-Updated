"""Minimal, runnable example for the ML teammate: NOWCAST of exceed_next_12h on data/derived/ml_full_table_v2 (NOT a forecast; the v1 table is superseded).
Rules enforced here: v2 columns only; split / cv_fold taken from the table and checked against splits.csv (cv_fold is per event_id); Florence = TEST, never trained on, never used to choose anything;
the 7-day buffer rows (split == 'buffer') are dropped everywhere; unseen gauges (34) are never trained on; every fitted statistic comes from trainval folds 0-3 only; one fixed HistGradientBoosting setting, no tuning.
Baselines (same rows, same bootstrap draws): persist_stage_frac, persist_extrap12h, calibrated_persistence (logistic regression on those two columns, fit on the same training rows as the model; plus a variant fit only on rows with stage < flood stage).
Metrics: recall at 50% and 20% precision and PR-AUC, onset only (is_exceed_now == False) and all hours; 95% CI by cluster bootstrap (event_id; gauge for Florence), paired across scores. Operating points are set on the eval set itself (an upper bound).
Usage:  python src/pipeline/03_gauge_ml/ml_example_v2.py <DATA_ROOT> [--out results.csv] [--boot 200] [--seeds 42 43 44]
        DATA_ROOT = folder that contains ml_full_table_v2/ and splits.csv (in this repo: data/derived)."""
import argparse, sys, numpy as np, pandas as pd
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

Y = "exceed_next_12h"; LAGS = (1, 3, 6, 12, 24)
NWM = ["nwm_flow", "nwm_chg_1h", "nwm_chg_3h", "nwm_chg_6h", "nwm_chg_12h", "nwm_chg_24h", "nwm_lag_1h", "nwm_lag_3h", "nwm_lag_6h", "nwm_lag_12h", "nwm_lag_24h", "nwm_flow_pctile", "baseline_ratio", "stream_order", "month"]
OWN = ["own_stage_ft", "own_stage_frac_fs", "own_hrs_since_obs", "own_extrap12h_frac"] + [f"own_stage_chg_{h}h" for h in LAGS]
UP = ["has_upstream", "n_upstream"] + [f"up{k}_{c}" for k in (1, 2, 3) for c in ["dist_km", "da_ratio", "stage_ft", "stage_frac_fs", "q_cfs", "hrs_since_obs"] + [f"{a}_chg_{h}h" for a in ("stage", "q") for h in LAGS]]
RAIN = [f"rain_catch_{w}h" for w in (1, 3, 6, 12, 24, 48, 72)]
FEATS = NWM + OWN + UP + RAIN                      # the "+all" set of reports/sample_model_v2.md
PERSIST = ["own_stage_frac_fs", "own_extrap12h_frac"]; BASE = {"persist_stage_frac": "own_stage_frac_fs", "persist_extrap12h": "own_extrap12h_frac"}


def load(root, seeds):
    meta = ["usgs_id", "event_id", "split", "cv_fold", "is_exceed_now", "in_pilot", Y]
    parts = sorted((root / "ml_full_table_v2").glob("usgs_id=*/part.parquet")); assert parts, f"no parquet under {root / 'ml_full_table_v2'}"
    tr, ev, seen = [], [], set()
    for gi, p in enumerate(parts):
        d = pd.read_parquet(p, columns=sorted(set(meta + FEATS)))
        d = d[(d.split != "buffer") & d[Y].notna()].copy(); d["is_exceed_now"] = d.is_exceed_now.astype(bool); d["gid"] = gi
        for c in FEATS: d[c] = d[c].astype("float32")
        seen |= set(zip(d.event_id, d.split, d.cv_fold))
        t = d[(d.split == "trainval") & (d.cv_fold <= 3)]; keep = (t[Y] == 1).values.copy(); masks = []
        for s in seeds:   # all positives + 10% of negatives; the seed changes the subsample and the model
            m = np.random.default_rng(s * 100003 + gi).random(len(t)) < 0.10; masks.append(m); keep |= m
        t = t[keep].copy()
        for s, m in zip(seeds, masks): t[f"sub{s}"] = m[keep] | (t[Y] == 1).values
        tr.append(t)
        e = d[d.split.isin(["test", "unseen"]) | ((d.split == "trainval") & (d.cv_fold == 4))]
        ev.append(e[e.own_stage_ft.notna() & e.own_stage_frac_fs.notna() & e.own_extrap12h_frac.notna()])   # same rows for every score
    return pd.concat(tr, ignore_index=True), pd.concat(ev, ignore_index=True), seen


def check_splits(root, seen):
    S = pd.read_csv(root / "splits.csv"); S["split"] = S.split.str.replace(r"\(.*\)", "", regex=True); m = S.set_index("event_id")
    bad = [(e, sp, f) for e, sp, f in seen if sp == "trainval" and (e not in m.index or int(m.cv_fold[e]) != int(f) or m.split[e] != "trainval")]
    assert not bad, f"table cv_fold/split disagree with splits.csv for events {bad[:5]}"
    folds = pd.DataFrame(list(seen), columns=["event_id", "split", "cv_fold"]); folds = folds[folds.split == "trainval"]
    assert folds.groupby("event_id").cv_fold.nunique().max() == 1, "an event spans several cv folds"
    print("split check: table split/cv_fold agree with splits.csv; each event lies in exactly one fold; buffer rows dropped")


def metrics(ys, w, last):
    """ys, w sorted by descending score -> [recall at 50% precision, recall at 20% precision, PR-AUC]; cut points only at the ends of tie groups"""
    tp = np.cumsum(ys * w); n = np.cumsum(w); P = tp[-1]
    if P <= 0: return [np.nan] * 3
    tpk, nk = tp[last], n[last]; prec = tpk / nk
    return [float(tpk[prec >= p].max() / P) if (prec >= p).any() else 0.0 for p in (0.5, 0.2)] + [float(np.sum(np.diff(np.r_[0, tpk]) / P * prec))]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--out", default="ml_example_v2_results.csv"); ap.add_argument("--boot", type=int, default=200); ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    a = ap.parse_args(); root = Path(a.root); tr, ev, seen = load(root, a.seeds); check_splits(root, seen)
    assert set(tr.split) == {"trainval"} and tr.cv_fold.max() <= 3, "training rows must be trainval folds 0-3"
    print(f"train rows {len(tr):,} (positives {int(tr[Y].sum()):,}); eval rows {len(ev):,}; gauges: train {tr.usgs_id.nunique()}, unseen {ev[ev.split == 'unseen'].usgs_id.nunique()} with usable rows (34 reserved), Florence {ev[ev.split == 'test'].usgs_id.nunique()}", flush=True)
    SC = {}
    for s in a.seeds:   # HGB, fixed settings, no tuning, no early stopping
        t = tr[tr[f"sub{s}"]]; m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, random_state=s, early_stopping=False).fit(t[FEATS], t[Y])
        SC[f"hgb_seed{s}"] = m.predict_proba(ev[FEATS])[:, 1]; print("fitted seed", s, flush=True)
    SC["hgb_seedavg"] = np.mean([SC[f"hgb_seed{s}"] for s in a.seeds], 0)
    for k, c in BASE.items(): SC[k] = ev[c].values.astype("float64")
    t = tr[tr[PERSIST].notna().all(axis=1)]; lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(t[PERSIST], t[Y])   # fit on trainval folds 0-3 only; negatives are the 10%-subsampled pool
    SC["calibrated_persistence"] = lr.predict_proba(ev[PERSIST])[:, 1]
    # second calibrated variant, added after the first looked weak at onset (it is dominated by already-flooding training hours): same model, fit only on training rows whose stage at the cutoff is below flood stage (known at the cutoff, so deployable)
    tb = t[t.own_stage_frac_fs < 1.0]; lr2 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(tb[PERSIST], tb[Y]); SC["calibrated_persistence_below_fs"] = lr2.predict_proba(ev[PERSIST])[:, 1]
    y = ev[Y].values.astype(float); strict = ev.own_stage_frac_fs.values < 1.0; rng = np.random.default_rng(0); rows = []
    sets = {"VAL (fold 4, trained gauges)": ((ev.split == "trainval") & (ev.cv_fold == 4)).values, "UNSEEN gauges (non-Florence)": (ev.split == "unseen").values, "TEST Florence": (ev.split == "test").values}
    pops = {"onset (is_exceed_now False)": ~ev.is_exceed_now.values, "strict onset (stage at cutoff < flood stage)": ~ev.is_exceed_now.values & strict, "all hours": np.ones(len(ev), bool)}
    for sn, sm in sets.items():
        for pn, pm in pops.items():
            mk = sm & pm; d = ev[mk]; yy = y[mk]
            if yy.sum() == 0: continue
            cl = d.gid.values if sn.startswith("TEST") else d.event_id.values; cu, ci = np.unique(cl, return_inverse=True)
            draws = [np.bincount(rng.integers(0, len(cu), len(cu)), minlength=len(cu)) for _ in range(a.boot)]; B = {}
            for name, sc in SC.items():
                sc = sc[mk]; o = np.argsort(-sc, kind="stable"); s_ = sc[o]; last = np.r_[s_[1:] != s_[:-1], True]; ys, cs = yy[o], ci[o]
                pt = metrics(ys, np.ones(len(ys)), last); bs = np.array([metrics(ys, dr[cs].astype(float), last) for dr in draws]); B[name] = bs; lo, hi = np.nanpercentile(bs, [2.5, 97.5], axis=0)
                rows.append(dict(eval_set=sn, population=pn, score=name, rows=len(d), positives=int(yy.sum()), gauges=d.usgs_id.nunique(), recall50=pt[0], recall50_lo=lo[0], recall50_hi=hi[0], recall20=pt[1], recall20_lo=lo[1], recall20_hi=hi[1], pr_auc=pt[2], pr_auc_lo=lo[2], pr_auc_hi=hi[2]))
            best = max(BASE_NAMES := ["persist_stage_frac", "persist_extrap12h", "calibrated_persistence", "calibrated_persistence_below_fs"], key=lambda k: next(r["recall50"] for r in rows[::-1] if r["score"] == k and r["eval_set"] == sn and r["population"] == pn))
            for k in BASE_NAMES + ["best"]:   # paired difference: model (seed-averaged) minus baseline, same draws
                kk = best if k == "best" else k
                for j, nm in ((0, "recall50"), (1, "recall20"), (2, "pr_auc")):
                    dm = B["hgb_seedavg"][:, j] - B[kk][:, j]; pt = next(r[nm] for r in rows[::-1] if r["score"] == "hgb_seedavg" and r["eval_set"] == sn and r["population"] == pn) - next(r[nm] for r in rows[::-1] if r["score"] == kk and r["eval_set"] == sn and r["population"] == pn)
                    rows.append(dict(eval_set=sn, population=pn, score=f"DIFF hgb_seedavg - {k}" + (f" ({kk})" if k == "best" else ""), metric=nm, diff=pt, diff_lo=float(np.nanpercentile(dm, 2.5)), diff_hi=float(np.nanpercentile(dm, 97.5))))
            print(sn, "|", pn, "done", flush=True)
    R = pd.DataFrame(rows); R.to_csv(a.out, index=False); pd.set_option("display.width", 220, "display.max_columns", 30)
    print(R[~R.score.str.startswith(("DIFF", "hgb_seed4"))][["eval_set", "population", "score", "rows", "positives", "recall50", "recall20", "pr_auc"]].round(3).to_string(index=False))
    print(R[R.score.str.startswith("DIFF")][["eval_set", "population", "score", "metric", "diff", "diff_lo", "diff_hi"]].round(3).to_string(index=False)); print("wrote", a.out)


if __name__ == "__main__": main()
