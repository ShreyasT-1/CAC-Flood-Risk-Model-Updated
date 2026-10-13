"""Assemble reports/sample_model_v2.md tables + automatic verdict from sample_model_v2*.csv / .pkl (no network, no training).
Verdict rule (fixed before looking): primary model = '+all'; primary metric = ONSET recall at 50% precision; comparator = the best of the four
baselines on that eval set by the same point metric. 'YES' only if the paired-bootstrap 95% CI of (model - best baseline) lies entirely above 0;
otherwise 'NO' (not distinguishable or worse). Same for recall at 20% precision.
"""
import pickle
import numpy as np, pandas as pd
from common import *

E = pd.read_csv(DER / "sample_model_v2_ens.csv"); eb = pickle.load(open(DER / "sample_model_v2_ens_boots.pkl", "rb"))
R = pd.read_csv(DER / "sample_model_v2.csv"); LD = pd.read_csv(DER / "sample_model_v2_lead.csv")
boots = pickle.load(open(DER / "sample_model_v2_boots.pkl", "rb"))
BASES = ["baseline_ratio", "nwm_flow_pctile", "persist_stage_frac", "persist_extrap12h"]
MODELS = ["NWM only", "+own stage", "+upstream gauges", "+rain", "+own+upstream", "+all"]
SETS = list(dict.fromkeys(R.eval_set))
f = lambda v: "-" if pd.isna(v) else f"{v:.3f}"
ci = lambda r, c: f"{f(r[c])} [{f(r[c + '_lo'])}, {f(r[c + '_hi'])}]"
out, verdict_rows = [], []

POPS = ["onset only", "strict onset (stage at cutoff < flood stage)"]
for s in SETS:
    al = R[(R.eval_set == s) & (R.population == "all hours")]
    out.append(f"### {s}")
    for pop in POPS:
        on = R[(R.eval_set == s) & (R.population == pop)]
        if on.empty: continue
        o0 = on.iloc[0]
        out += [f"**{pop}**: {int(o0.gauges)} gauges; rows {int(o0.rows):,}, positives {int(o0.positives)} (base rate {o0.base_rate:.4f}); "
                f"all-hours positives {int(al.iloc[0].positives) if len(al) else 0}.", "",
                "| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |", "|---|---|---|---|---|---|"]
        for sc in BASES + MODELS:
            r = on[on.score == sc]; a = al[al.score == sc]
            if r.empty: continue
            r = r.iloc[0]
            out.append(f"| {'**' + sc + '**' if sc in BASES else sc} | {ci(r, 'recall50')} | {ci(r, 'recall20')} | {ci(r, 'pr_auc')} | "
                       f"{ci(a.iloc[0], 'pr_auc') if len(a) else '-'} | {f(r.recall50_seed_sd)} / {f(r.recall20_seed_sd)} |")
        out.append("")
        en = E[(E.eval_set == s) & (E.population == pop)]
        out += ["Seed-averaged (ensemble) scores, same rows and paired draws:", "", "| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |", "|---|---|---|---|"]
        for sc in ["ens " + x for x in MODELS]:
            r = en[en.score == sc].iloc[0]
            out.append(f"| {sc} | {ci(r, 'recall50')} | {ci(r, 'recall20')} | {ci(r, 'pr_auc')} |")
        out.append("")
        for k, name in ((0, "recall @50% precision"), (1, "recall @20% precision")):
            col = "recall50" if k == 0 else "recall20"
            bb = max(BASES, key=lambda b: on[on.score == b][col].iloc[0])
            d = eb[(s, pop, "ens +all")][:, k] - boots[(s, pop, bb)][:, k]
            lo, hi = np.nanpercentile(d, [2.5, 97.5])
            pt = en[en.score == "ens +all"][col].iloc[0] - on[on.score == bb][col].iloc[0]
            verdict_rows.append({"eval_set": s, "population": pop + " [ensemble]", "metric": name, "best_baseline": bb, "model_minus_baseline": pt, "lo": lo, "hi": hi,
                                 "beats": "YES" if lo > 0 else "NO"})
        for k, name in ((0, "recall @50% precision"), (1, "recall @20% precision")):
            col = "recall50" if k == 0 else "recall20"
            bb = max(BASES, key=lambda b: on[on.score == b][col].iloc[0])
            d = boots[(s, pop, "+all")][:, k] - boots[(s, pop, bb)][:, k]
            lo, hi = np.nanpercentile(d, [2.5, 97.5])
            pt = on[on.score == "+all"][col].iloc[0] - on[on.score == bb][col].iloc[0]
            verdict_rows.append({"eval_set": s, "population": pop, "metric": name, "best_baseline": bb, "model_minus_baseline": pt, "lo": lo, "hi": hi,
                                 "beats": "YES" if lo > 0 else "NO"})

V = pd.DataFrame(verdict_rows)
V.to_csv(DER / "sample_model_v2_verdict.csv", index=False)
vt = ["| eval set | onset population | metric | best baseline | +all minus baseline [95% CI] | beats it? |", "|---|---|---|---|---|---|"]
for r in V.itertuples():
    vt.append(f"| {r.eval_set} | {r.population.replace(' (stage at cutoff < flood stage)', '')} | {r.metric} | {r.best_baseline} | {r.model_minus_baseline:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}] | **{r.beats}** |")

lead = ["| eval set | population | score | onsets | detected @50% (median lead h) | detected @20% (median lead h) |", "|---|---|---|---|---|---|"]
for r in LD[LD.score.isin(["persist_stage_frac", "persist_extrap12h", "baseline_ratio", "NWM only", "+own stage", "+all"])].itertuples():
    lead.append(f"| {r.eval_set} | {r.population.replace(' (stage at cutoff < flood stage)', '')} | {r.score} | {int(r.onsets_p50)} | {int(r.detected_p50)} ({f(r.median_lead_h_p50)}) | {int(r.detected_p20)} ({f(r.median_lead_h_p20)}) |")

# writes the tables only; reports/sample_model_v2.md = hand-written narrative + this file as its appendix
(REP / "_v2_tables.md").write_text("\n".join(["## Verdict table (auto)", ""] + vt + ["", "## Per eval set", ""] + out + ["## Lead time", ""] + lead))
print("\n".join(vt))
