"""Seed-averaged ('ensemble') scores for the 6 model configs, scored exactly like 13_sample_model_v2.py (same rows, same bootstrap draws:
rng(0) consumed in the same set/population order), paired with the baselines' draws stored in sample_model_v2_boots.pkl.
Why: single-seed HGB models saturate at p=1.0 on ~10^3 rows (ties at the top that are mostly false alarms), which zeroes recall@50% precision for
the single-seed metric; averaging three seeds breaks those ties. Output: sample_model_v2_ens.csv, sample_model_v2_ens_boots.pkl"""
import importlib.util, pickle, numpy as np, pandas as pd
from pathlib import Path
spec = importlib.util.spec_from_file_location("m", Path(__file__).parent / "13_sample_model_v2.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tr, ev = m.load(); del tr
y_all = ev[m.Y].values.astype(float); ip = ev.in_pilot.values.astype(bool); ex = ev.is_exceed_now.values
ENS = {"ens " + n: np.mean([np.load(m.CACHE / f"{s}_{n.replace('+', 'p').replace(' ', '_')}.npy") for s in m.SEEDS], 0) for n in m.CONFIGS}
sets = {"VAL (held-out events, trained gauges)": ((ev.split == "trainval") & (ev.cv_fold == 4)).values, "UNSEEN gauges (non-Florence)": (ev.split == "unseen").values,
        "TEST (Florence)": (ev.split == "test").values,
        "PILOT non-Florence (VAL+UNSEEN)": ip & (((ev.split == "trainval") & (ev.cv_fold == 4)) | (ev.split == "unseen")).values,
        "PILOT Florence (TEST)": ip & (ev.split == "test").values}
pops = (("onset only", ~ex), ("strict onset (stage at cutoff < flood stage)", ~ex & (ev.own_stage_frac_fs.values < 1.0)), ("all hours", np.ones(len(ev), bool)))
rng = np.random.default_rng(0); B = 200; rows, boots = [], {}
for sname, sm in sets.items():
    for pop, pm in pops:
        mk = sm & pm; d = ev[mk]; y = y_all[mk]
        if y.sum() == 0: continue
        cl = d.gid.values if "Florence" in sname or sname.startswith("TEST") else d.event_id.values
        cu, ci = np.unique(cl, return_inverse=True)
        draws = [np.bincount(rng.integers(0, len(cu), len(cu)), minlength=len(cu)) for _ in range(B)]  # identical to 13_
        for n, sc in ENS.items():
            sc = sc[mk]; o = np.argsort(-sc, kind="stable"); s_ = sc[o]; last = np.r_[s_[1:] != s_[:-1], True]; ys, cs = y[o], ci[o]
            pt = m.metrics(ys, np.ones(len(ys)), last); bs = np.array([m.metrics(ys, dr[cs].astype(float), last) for dr in draws])
            boots[(sname, pop, n)] = bs; lo, hi = np.nanpercentile(bs, [2.5, 97.5], axis=0)
            rows.append({"eval_set": sname, "population": pop, "score": n, "rows": len(d), "positives": int(y.sum()),
                         "recall50": pt[0], "recall50_lo": lo[0], "recall50_hi": hi[0], "recall20": pt[1], "recall20_lo": lo[1], "recall20_hi": hi[1],
                         "pr_auc": pt[2], "pr_auc_lo": lo[2], "pr_auc_hi": hi[2]})
        print(sname, pop, flush=True)
pd.DataFrame(rows).to_csv(m.DER / "sample_model_v2_ens.csv", index=False); pickle.dump(boots, open(m.DER / "sample_model_v2_ens_boots.pkl", "wb"))
