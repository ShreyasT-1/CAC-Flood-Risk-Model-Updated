"""Job 1d: build docs/DISCLOSURE_CHECKLIST.md from the TODO-CONFIRM lines of docs/claims.md (exact sentences copied programmatically) plus the repo evidence for each (typed below
after reading git log, file dates and the files named). Nothing is marked confirmed. Usage (repo root): python src/73_disclosure_checklist.py"""
import re
L = open("docs/claims.md", encoding="utf-8").read().splitlines()
T = [(i + 1, l) for i, l in enumerate(L) if "TODO-CONFIRM" in l]
EV = {  # first 40 chars of the line -> evidence bullets
    "Based on `git log`": ["`git log`: 2 commits, `fcf2a19` 'Add FloodLens ML data pipeline, reports and Kill Test 1' and `74e6614` 'Add untuned sample model and effectiveness write-up', both dated 2026-10-08, author name 'nishaanthjay', both with a `Co-Authored-By: Claude Sonnet 5.5` trailer (checked with `git log --format=%(trailers)`).",
                           "Everything from phase 1 onward (src/10-80, docs/, reports/phase1+, data/export) is uncommitted in the working tree until the freeze commit; the commit count in this sentence will be 3 after the freeze commit (edit the sentence if you keep it).",
                           "No git remote is configured (`git remote -v` is empty), so nothing has been pushed."],
    "- The project concept": ["`fcf2a19` (2026-10-08) and `docs/phase0_sources.md` (2026-10-10) record the pilot area and the data plan; the task labels T1-T16 appear in `docs/validation_protocol.md` and `reports/phase2_validation.md`.",
                             "No file records your own instructions or who proposed the concept; the repo cannot show this."],
    "- Scope and safety rules": ["`reports/phase1_limitations.md` (2026-10-10) and `data/export/README.md` state scenario wording and forbid 'safe'/'no risk' claims; `src/export_checks.py` enforces the banned strings.",
                                "`git remote -v` is empty and there is no push in `git log`; `docs/claims.md` section 2 item 4 states the no-'safe' rule.",
                                "Whether these rules came from you or from the assistant is not recorded."],
    "- The validation approach": ["`docs/validation_protocol.md`: sections A-F (T10) and Amendments 1-5 dated 2026-10-11 and 2026-10-12, each stating it was written before the corresponding results. Amendment 4 (2026-10-11) changes the closure rule to `Condition == 'Closed'`; Helene is handled separately in `src/54_t15_test.py`.",
                                 "The protocol file is written in the first person, but the repo cannot show who made each decision."],
    "- Task order and which tasks": ["No outputs exist for T5/HAND (`data/export/README.md`: 'the terrain/HAND task was not run'; `docs/claims.md` C10 notes HAND features could not be built).",
                                     "Commit trailers name 'Claude Sonnet 5.5' as co-author on both commits; no file records that you chose this model."],
    "- Which claims go into": ["`docs/claims.md` section 5 (app text, CAC answer, video script) are drafts written 2026-10-13 by the assistant; no file records your approval or edits."],
    "- Nothing is recorded in the repo": ["`reviewer_decision` is blank in `data/phase0/florence_label_review.csv` (81 rows) and `data/phase2/t10/report_candidates.csv` (709 rows); `data/review/label_review_sheet.csv` (790 rows, built 2026-10-13) has empty reviewer columns; no review notes exist.",
                                         "Nothing shows which documents you read: no comments, no edited files, no review log."],
    "- Whether you ran or tested": ["`handoff_for_shreyas/`, `handoff_for_shreyas.zip` (2026-10-11 19:24) and `FloodLens_data_for_Shreyas.zip` (2026-10-11 19:27) exist, and `docs/ML_HANDOFF.md` (2026-10-12) is addressed to 'the ML teammate'.",
                                    "Nothing in the repo shows that Shreyas used, changed or reviewed anything, or that you ran the scripts yourself (all logs and result files were written during assistant-run sessions)."],
}
out = ["# Disclosure checklist (from `docs/claims.md`, section 6)", "",
       "Every `TODO-CONFIRM` line in `docs/claims.md`, copied verbatim, with what the repo can and cannot show. **Nothing is confirmed.** Tick one box per item; 'edit' means the sentence must be changed before it goes on the CAC form.", ""]
for n, (ln, t) in enumerate(T, 1):
    k = next(k for k in EV if t.strip().startswith(k) or t.startswith(k)); ev = EV[k]
    out += [f"## {n}. `docs/claims.md` line {ln}", "", "**Exact sentence:**", "", "> " + t.strip(), "", "**Evidence in the repo:**", ""] + [f"- {e}" for e in ev] + ["",
            "**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________", ""]
open("docs/DISCLOSURE_CHECKLIST.md", "w", encoding="utf-8").write("\n".join(out)); print(len(T), "TODO-CONFIRM lines ->", "docs/DISCLOSURE_CHECKLIST.md")
