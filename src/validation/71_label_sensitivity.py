"""Job 1c: label sensitivity. Which results depend on the reviewed labels?
 * T15 (nine-event pooled AUC, 0.690) uses NCDOT closure RECORDS as positives (src/50-54), not the LSR report labels reviewed in data/review/label_review_sheet.csv, so review cannot change it.
   It is recomputed here as a self-check (variant 1 only) and is identical under any review outcome.
 * T10-B/C (claims C1/C2: AUC 0.958 on 74 accepted reports) IS driven by the review labels, so the three variants are run on it with the unchanged code of src/33_t10_flow_test.py
   (executed from a patched copy that writes to data/review/sensitivity/ and never touches data/phase2/t10/):
   (1) all auto-labels as they are now (model-suggested accept);
   (2) only labels the reviewer accepted (reviewer 'accept', including rows the model rejected; reviewer reject/uncertain dropped);
   (3) reviewer accepts that are also model accepts (reviewer-rejected AND reviewer-uncertain removed from the positives, nothing added).
Variants 2 and 3 run only when the sheet is fully filled (same rules as src/70_apply_label_review.py); until then only variant 1 runs. Usage (repo root): python src/71_label_sensitivity.py"""
import importlib, json, os, sys, numpy as np, pandas as pd
O, OUT = "data/phase2/t10/", "data/review/sensitivity/"; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, "src"); a, npos, evs = importlib.import_module("80_repro_headlines").t15_pooled("data/phase2/t15_nine/")
print(f"T15 nine-event pooled AUC recomputed from files: {a:.3f} ({npos} positives; events {','.join(evs)}); unaffected by label review (labels = NCDOT records)")
assert round(a, 3) == 0.690, "T15 self-check failed: expected 0.690"
src = open("src/33_t10_flow_test.py", encoding="utf-8").read()
for x, y in (('O + "report_candidates.csv"', "CAND"), ('X.to_csv(O + f"t10bc_per_report_{label}.csv"', 'X.to_csv(OUTD + f"t10bc_per_report_{label}_{VAR}.csv"')):
    assert x in src, x; src = src.replace(x, y)
src = src[:src.index("res = []")] + 'res = [run(D[D.decision == "accept"], "primary_hour")]\n'
T = pd.read_csv(O + "report_candidates.csv"); S = pd.read_csv("data/review/label_review_sheet.csv", dtype=str, keep_default_na=False); S = S[S.source == "t10"].set_index("report_id")
rev = T.report_id.astype(str).map(S.reviewer_decision.str.strip().str.lower()); filled = rev.isin(["accept", "reject", "uncertain"]).all()
variants = {"1_all_auto_labels": pd.Series("", index=T.index)}
if filled:
    variants["2_reviewer_accepted_only"] = rev
    variants["3_auto_accepts_kept_by_reviewer"] = pd.Series(np.where((T.suggested_decision == "accept") & (rev == "accept"), "accept", "reject"), index=T.index)
else:
    print(f"sheet not fully filled ({int((~rev.isin(['accept', 'reject', 'uncertain'])).sum())} of {len(T)} t10 rows blank): running variant 1 only; variants 2 and 3 NOT run")
rows = []
for v, dec in variants.items():
    p = OUT + f"cand_{v}.csv"; C = T.copy(); C["reviewer_decision"] = dec.values; C.to_csv(p, index=False)
    ns = dict(CAND=p, OUTD=OUT, VAR=v, __name__="t10_variant"); exec(compile(src, "33_t10_flow_test(patched)", "exec"), ns); r = ns["res"][0]
    rows.append(dict(variant=v, n_positive_reports=r["n_reports"], n_crossings=r["n_crossings"], storm_clusters=r["n_storm_clusters"], auc=r["auc"], auc_ci95=r["auc_ci95"], share_gt_q2_reports=r["share_gt_q2_reports"],
                     share_gt_q2_controls=r["share_gt_q2_controls"], timing_hit_reports=r["timing_hit_reports"], timing_diff=r["timing_diff"], pass_B=r["pass_B"], pass_C=r["pass_C"]))
R = pd.DataFrame(rows); pd.set_option("display.width", 250, "display.max_columns", 20); print(R.to_string(index=False)); R.to_csv("data/review/label_sensitivity.csv", index=False)
if not filled: assert abs(R.auc.iloc[0] - 0.958) < 5e-4, "T10-B self-check failed: expected 0.958"
if not filled: print("self-check: variant 1 reproduces T10-B AUC 0.958 and T15 0.690")
