"""Job 1b: validate the filled data/review/label_review_sheet.csv and (only with --apply) write reviewer_decision / reviewer_crossing_id / reviewer_notes into
data/phase0/florence_label_review.csv and data/phase2/t10/report_candidates.csv. Dry run by default. Originals are copied once to <file>.orig (never overwritten).
Rules: reviewer_decision in accept/reject/uncertain on EVERY row (no blanks); reviewer_crossing_id, if given, must exist (V2_* in crossings_v2.parquet, T10_* in structures_nc.parquet);
accept with no listed crossing needs reviewer_crossing_id; (source, report_id) unique and exactly the rows of the source files. Exit 1 on any error. Usage (repo root): python src/validation/70_apply_label_review.py [--apply]"""
import os, shutil, sys, pandas as pd
SHEET = "data/review/label_review_sheet.csv"; SRC = {"florence": "data/phase0/florence_label_review.csv", "t10": "data/phase2/t10/report_candidates.csv"}
S = pd.read_csv(SHEET, dtype=str, keep_default_na=False); bad = []
ids = {"florence": set(pd.read_parquet("data/phase0/crossings_v2.parquet").crossing_id), "t10": set(pd.read_parquet("data/phase2/t10/structures_nc.parquet").crossing_id)}
S["d"] = S.reviewer_decision.str.strip().str.lower(); S["c"] = S.reviewer_crossing_id.str.strip()
nb = (S.d == "").sum()
if nb: bad.append(f"{nb} rows have a blank reviewer_decision (all rows must be filled)")
o = ~S.d.isin(["accept", "reject", "uncertain", ""]); bad += [f"row {i + 2}: reviewer_decision '{v}' not accept/reject/uncertain" for i, v in S.d[o].items()][:20]
if S.duplicated(["source", "report_id"]).any(): bad.append("duplicate (source, report_id) rows")
for k, p in SRC.items():
    want = set(pd.read_csv(p, dtype=str).report_id); got = set(S[S.source == k].report_id)
    if want != got: bad.append(f"{k}: sheet rows differ from {p} (missing {len(want - got)}, extra {len(got - want)})")
for i, r in S.iterrows():
    if r.c and r.c not in ids.get(r.source, set()): bad.append(f"row {i + 2}: reviewer_crossing_id '{r.c}' not found for source {r.source}")
    if r.d == "accept" and not r.c and not r.nearest_crossing_id.strip(): bad.append(f"row {i + 2}: accept with no listed crossing needs reviewer_crossing_id")
print(f"{len(S)} rows; decisions: {S.d.replace('', '(blank)').value_counts().to_dict()}")
if bad:
    print("REFUSED - sheet is not valid:"); [print(" -", b) for b in bad[:40]]; print(f" ({len(bad)} problems)"); sys.exit(1)
print("sheet valid.", {k: S[S.source == k].d.value_counts().to_dict() for k in SRC})
if "--apply" not in sys.argv: print("dry run: nothing written (use --apply)"); sys.exit(0)
for k, p in SRC.items():
    if not os.path.exists(p + ".orig"): shutil.copy(p, p + ".orig")
    D = pd.read_csv(p, dtype={"report_id": str, "reviewer_decision": str, "reviewer_crossing_id": str, "reviewer_notes": str}); s = S[S.source == k].set_index("report_id")
    D["reviewer_decision"] = D.report_id.map(s.d); D["reviewer_crossing_id"] = D.report_id.map(s.c).replace("", pd.NA); D["reviewer_notes"] = D.report_id.map(s.reviewer_notes.str.strip()).replace("", pd.NA)
    D.report_id = pd.to_numeric(D.report_id); D.to_csv(p, index=False); print("wrote", p, D.reviewer_decision.value_counts().to_dict())
