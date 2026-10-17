"""Sample model v2: does adding observed stage / upstream gauges / observed catchment rain create ONSET skill?
HistGradientBoosting, fixed settings as in 09_sample_model.py (200 trees, lr 0.1, 31 leaves, no early stopping, NO tuning).
Train: split==trainval, cv_fold 0..3, exceed_next_12h known, all positives + 10% of negatives; 3 seeds (42,43,44: the seed changes the
negative subsample AND the model random_state). Eval sets (never trained on): VAL = fold 4, UNSEEN gauges (non-Florence), TEST = Florence, PILOT subsets.
All scores are computed on the SAME rows: label known, baseline_ratio / nwm_flow_pctile / own stage at the cutoff all non-NaN.
Metrics: onset only (is_exceed_now False): recall at 50% and 20% precision, PR-AUC; all hours: PR-AUC. 95% CI = cluster bootstrap
(event_id; gauge for Florence/TEST) with paired draws across all scores; median lead time.
Outputs: data/derived/sample_model_v2.csv, sample_model_v2_lead.csv, sample_model_v2_boots.pkl (report: 14_report_v2.py)
"""
import sys, pickle, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from common import *

V2 = DER / "ml_full_table_v2"
Y = "exceed_next_12h"
NWM = ["nwm_flow", "nwm_chg_1h", "nwm_chg_3h", "nwm_chg_6h", "nwm_chg_12h", "nwm_chg_24h", "nwm_lag_1h", "nwm_lag_3h", "nwm_lag_6h",
       "nwm_lag_12h", "nwm_lag_24h", "nwm_flow_pctile", "baseline_ratio", "stream_order", "month"]
LAGS = (1, 3, 6, 12, 24)
OWN = ["own_stage_ft", "own_stage_frac_fs", "own_hrs_since_obs", "own_extrap12h_frac"] + [f"own_stage_chg_{h}h" for h in LAGS]
UP = ["has_upstream", "n_upstream"] + [f"up{k}_{c}" for k in (1, 2, 3) for c in
      ["dist_km", "da_ratio", "stage_ft", "stage_frac_fs", "q_cfs", "hrs_since_obs"] + [f"{a}_chg_{h}h" for a in ("stage", "q") for h in LAGS]]
RAIN = [f"rain_catch_{w}h" for w in (1, 3, 6, 12, 24, 48, 72)]
CONFIGS = {"NWM only": NWM, "+own stage": NWM + OWN, "+upstream gauges": NWM + UP, "+rain": NWM + RAIN,
           "+own+upstream": NWM + OWN + UP, "+all": NWM + OWN + UP + RAIN}
BASE = {"baseline_ratio": "baseline_ratio", "nwm_flow_pctile": "nwm_flow_pctile",
        "persist_stage_frac": "own_stage_frac_fs", "persist_extrap12h": "own_extrap12h_frac"}
SEEDS = (42, 43, 44)
CACHE = DER / "_v2_preds"; CACHE.mkdir(exist_ok=True)
B = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def load():
    allf = sorted(set(sum(CONFIGS.values(), []) + list(BASE.values())))
    meta = ["usgs_id", "time_utc", "event_id", "split", "cv_fold", "in_pilot", "is_exceed_now", Y]
    ev, tr = [], []
    t0 = pd.Timestamp(START, tz="UTC")
    for gi, p in enumerate(sorted(V2.glob("usgs_id=*/part.parquet"))):
        d = pd.read_parquet(p, columns=meta + allf)
        d = d[d[Y].notna()]
        if not len(d):
            continue
        d["tidx"] = ((d.time_utc - t0) // pd.Timedelta(hours=1)).astype("int32"); d["gid"] = gi
        d = d.drop(columns="time_utc"); d["is_exceed_now"] = d.is_exceed_now.astype(bool)
        for c in allf:
            d[c] = d[c].astype("float32")
        t = d[(d.split == "trainval") & (d.cv_fold <= 3)]
        keep = (t[Y] == 1).values.copy(); masks = []
        for s in SEEDS:
            m = np.random.default_rng(s * 100003 + gi).random(len(t)) < 0.10
            masks.append(m); keep |= m
        t = t[keep].copy()
        for s, m in zip(SEEDS, masks):
            t[f"sub{s}"] = m[keep] | (t[Y] == 1).values
        tr.append(t)
        e = d[(d.split.isin(["test", "unseen"])) | ((d.split == "trainval") & (d.cv_fold == 4))]
        ev.append(e[e.baseline_ratio.notna() & e.nwm_flow_pctile.notna() & e.own_stage_ft.notna()])  # same rows for every score
    return pd.concat(tr, ignore_index=True), pd.concat(ev, ignore_index=True)


def fit_predict(tr, ev):
    P = {}
    for s in SEEDS:
        t = tr[tr[f"sub{s}"]]
        for name, feats in CONFIGS.items():
            cf = CACHE / f"{s}_{name.replace('+', 'p').replace(' ', '_')}.npy"  # resume after a crash; delete the folder to refit
            if cf.exists() and len(np.load(cf, mmap_mode="r")) == len(ev):
                P[(name, s)] = np.load(cf); continue
            t0 = time.time()
            m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, random_state=s, early_stopping=False)
            m.fit(t[feats], t[Y]); P[(name, s)] = m.predict_proba(ev[feats])[:, 1].astype("float32")
            np.save(cf, P[(name, s)])
            print(f"seed {s} {name}: {len(t)} rows, {int(t[Y].sum())} pos, {time.time() - t0:.0f}s", flush=True)
    return P


def metrics(ys, w, last, ps=(0.5, 0.2)):
    """ys, w sorted by descending score. -> [recall@50%prec, recall@20%prec, PR-AUC]; cut points only at ends of tie groups"""
    tp = np.cumsum(ys * w); n = np.cumsum(w); P = tp[-1]
    if P <= 0:
        return [np.nan] * (len(ps) + 1)
    tpk, nk = tp[last], n[last]
    prec = tpk / nk
    ap = float(np.sum(np.diff(np.r_[0, tpk]) / P * prec))
    return [float(tpk[prec >= p].max() / P) if (prec >= p).any() else 0.0 for p in ps] + [ap]


def thr_at(y, sc, p):
    """score threshold of the largest alert set (score >= thr) with precision >= p; None if unreachable"""
    o = np.argsort(-sc, kind="stable"); s = sc[o]; tp = np.cumsum(y[o]); n = np.arange(1, len(s) + 1)
    ok = np.r_[s[1:] != s[:-1], True] & (tp / n >= p)
    return s[np.flatnonzero(ok).max()] if ok.any() else None


def lead_times(d, y, sc, thr, strict=False):
    """d, y, sc: ALL rows of the eval set (exceed_now rows included, so the crossing hour c is visible); thr from the onset-only population.
    True onset = crossing bin c (row c has is_exceed_now) preceded by 12 consecutive rows c-12..c-1 with y == 1 and not exceed_now.
    Lead = c - (earliest of those 12 rows with score >= thr). Returns (n onsets, leads of detected onsets)."""
    if thr is None:
        return 0, np.array([])
    order = np.lexsort((d.tidx.values, d.gid.values))
    g, t, ex, yy, ss = d.gid.values[order], d.tidx.values[order], d.is_exceed_now.values[order], y[order], sc[order]
    cand = (yy == 1) & (~ex)
    if strict:  # also require the stage known at the cutoff to be below flood stage (no recession rows)
        cand &= d.own_stage_frac_fs.values[order] < 1.0
    # run ends: cand row followed by a row at t+1 that is exceed_now (same gauge)
    nxt_ok = np.r_[(g[1:] == g[:-1]) & (t[1:] == t[:-1] + 1) & ex[1:], False] & cand
    leads, total = [], 0
    for j in np.flatnonzero(nxt_ok):
        w = slice(j - 11, j + 1)
        if j < 11 or not (cand[w].all() and (g[w] == g[j]).all() and (t[j] - t[j - 11] == 11)):
            continue
        total += 1
        fired = np.flatnonzero(ss[w] >= thr)
        if len(fired):
            leads.append(12 - fired[0])
    return total, np.array(leads)


def main():
    tr, ev = load()
    print("train rows", len(tr), "eval rows", len(ev), flush=True)
    P = fit_predict(tr, ev)
    SC = {name: [P[(name, s)] for s in SEEDS] for name in CONFIGS}
    for b, c in BASE.items():
        SC[b] = [ev[c].values.astype("float64")]
    y_all = ev[Y].values.astype(float)
    ip = ev.in_pilot.values.astype(bool)
    sets = {"VAL (held-out events, trained gauges)": ((ev.split == "trainval") & (ev.cv_fold == 4)).values,
            "UNSEEN gauges (non-Florence)": (ev.split == "unseen").values, "TEST (Florence)": (ev.split == "test").values,
            "PILOT non-Florence (VAL+UNSEEN)": ip & (((ev.split == "trainval") & (ev.cv_fold == 4)) | (ev.split == "unseen")).values,
            "PILOT Florence (TEST)": ip & (ev.split == "test").values}
    rng = np.random.default_rng(0)
    rows, boots, leadrows = [], {}, []
    for sname, sm in sets.items():
        for pop, pm in (("onset only", ~ev.is_exceed_now.values),
                        ("strict onset (stage at cutoff < flood stage)", ~ev.is_exceed_now.values & (ev.own_stage_frac_fs.values < 1.0)),
                        ("all hours", np.ones(len(ev), bool))):
            m = sm & pm
            d = ev[m]; y = y_all[m]
            if y.sum() == 0:
                continue
            cl = d.gid.values if "Florence" in sname or sname.startswith("TEST") else d.event_id.values
            cu, ci = np.unique(cl, return_inverse=True)
            draws = [np.bincount(rng.integers(0, len(cu), len(cu)), minlength=len(cu)) for _ in range(B)]
            for sc_name, lst in SC.items():
                per = []
                for sc in lst:
                    sc = sc[m] if len(sc) == len(ev) else sc
                    o = np.argsort(-sc, kind="stable"); s_ = sc[o]
                    last = np.r_[s_[1:] != s_[:-1], True]; ys, cs = y[o], ci[o]
                    per.append((metrics(ys, np.ones(len(ys)), last), np.array([metrics(ys, dr[cs].astype(float), last) for dr in draws])))
                pt = np.mean([p for p, _ in per], 0); bs = np.mean([b for _, b in per], 0)
                sd = np.std([p for p, _ in per], 0) if len(per) > 1 else np.zeros(3)
                boots[(sname, pop, sc_name)] = bs
                lo, hi = np.nanpercentile(bs, [2.5, 97.5], axis=0)
                rows.append({"eval_set": sname, "population": pop, "score": sc_name, "gauges": d.usgs_id.nunique(), "rows": len(d), "positives": int(y.sum()),
                             "base_rate": y.mean(), "recall50": pt[0], "recall50_lo": lo[0], "recall50_hi": hi[0], "recall50_seed_sd": sd[0],
                             "recall20": pt[1], "recall20_lo": lo[1], "recall20_hi": hi[1], "recall20_seed_sd": sd[1],
                             "pr_auc": pt[2], "pr_auc_lo": lo[2], "pr_auc_hi": hi[2], "pr_auc_seed_sd": sd[2], "x_base": pt[2] / y.mean()})
            if pop != "all hours":  # lead time: seed-mean probability for models, thresholds set on the eval set itself (oracle operating point)
                for sc_name, lst in SC.items():
                    scall = np.mean([l[sm] if len(l) == len(ev) else l for l in lst], 0)  # all rows of the set
                    sc = scall[pm[sm]]  # this onset population
                    r = {"eval_set": sname, "population": pop, "score": sc_name}
                    for p in (0.5, 0.2):
                        tot, ld = lead_times(ev[sm], y_all[sm], scall, thr_at(y, sc, p), strict=pop.startswith("strict"))
                        r[f"onsets_p{int(p * 100)}"] = tot; r[f"detected_p{int(p * 100)}"] = len(ld)
                        r[f"median_lead_h_p{int(p * 100)}"] = float(np.median(ld)) if len(ld) else np.nan
                    leadrows.append(r)
            print(sname, pop, "done", flush=True)
    out = pd.DataFrame(rows); out.to_csv(DER / "sample_model_v2.csv", index=False)
    pd.DataFrame(leadrows).to_csv(DER / "sample_model_v2_lead.csv", index=False)
    pickle.dump(boots, open(DER / "sample_model_v2_boots.pkl", "wb"))
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(out[["eval_set", "population", "score", "rows", "positives", "recall50", "recall20", "pr_auc"]].round(3).to_string())


if __name__ == "__main__":
    main()
