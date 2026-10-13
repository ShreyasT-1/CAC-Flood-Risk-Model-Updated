# Disclosure checklist (from `docs/claims.md`, section 6)

Every `TODO-CONFIRM` line in `docs/claims.md`, copied verbatim, with what the repo can and cannot show. **Nothing is confirmed.** Tick one box per item; 'edit' means the sentence must be changed before it goes on the CAC form.

## 1. `docs/claims.md` line 77

**Exact sentence:**

> Based on `git log` (2 commits, both carrying a `Co-Authored-By: Claude Sonnet 5.5` line, author = the project owner's account), the files in this repo, and the working sessions. The record cannot show who typed what; every line that depends on the owner's own actions is marked **TODO-CONFIRM** and must be confirmed or deleted before it goes on the form.

**Evidence in the repo:**

- `git log`: 2 commits, `fcf2a19` 'Add FloodLens ML data pipeline, reports and Kill Test 1' and `74e6614` 'Add untuned sample model and effectiveness write-up', both dated 2026-10-08, author name 'nishaanthjay', both with a `Co-Authored-By: Claude Sonnet 5.5` trailer (checked with `git log --format=%(trailers)`).
- Everything from phase 1 onward (src/10-80, docs/, reports/phase1+, data/export) is uncommitted in the working tree until the freeze commit; the commit count in this sentence will be 3 after the freeze commit (edit the sentence if you keep it).
- No git remote is configured (`git remote -v` is empty), so nothing has been pushed.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 2. `docs/claims.md` line 87

**Exact sentence:**

> - The project concept (flooded crossings to lifeline access), the study area (New Hanover, Brunswick, Pender) and the task list T1-T15. TODO-CONFIRM

**Evidence in the repo:**

- `fcf2a19` (2026-10-08) and `docs/phase0_sources.md` (2026-10-10) record the pilot area and the data plan; the task labels T1-T16 appear in `docs/validation_protocol.md` and `reports/phase2_validation.md`.
- No file records your own instructions or who proposed the concept; the repo cannot show this.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 3. `docs/claims.md` line 88

**Exact sentence:**

> - Scope and safety rules: lifeline folder only, no website changes, no git push, no deletion of data, no filling of missing values, probabilistic/scenario wording, hindcast/forecast labelling, no "safe" claims. TODO-CONFIRM

**Evidence in the repo:**

- `reports/phase1_limitations.md` (2026-10-10) and `data/export/README.md` state scenario wording and forbid 'safe'/'no risk' claims; `src/export_checks.py` enforces the banned strings.
- `git remote -v` is empty and there is no push in `git log`; `docs/claims.md` section 2 item 4 states the no-'safe' rule.
- Whether these rules came from you or from the assistant is not recorded.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 4. `docs/claims.md` line 89

**Exact sentence:**

> - The validation approach: pre-register tests, run once, report failures, no threshold changes after results; the specific tests T10 A-F, T12, T13, T15; the rule change to `Condition == 'Closed'` (Amendment 4) and treating Helene separately. TODO-CONFIRM

**Evidence in the repo:**

- `docs/validation_protocol.md`: sections A-F (T10) and Amendments 1-5 dated 2026-10-11 and 2026-10-12, each stating it was written before the corresponding results. Amendment 4 (2026-10-11) changes the closure rule to `Condition == 'Closed'`; Helene is handled separately in `src/54_t15_test.py`.
- The protocol file is written in the first person, but the repo cannot show who made each decision.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 5. `docs/claims.md` line 90

**Exact sentence:**

> - Task order and which tasks to skip (e.g. T5 skipped for now), and the choice of the model used for coding sessions. TODO-CONFIRM

**Evidence in the repo:**

- No outputs exist for T5/HAND (`data/export/README.md`: 'the terrain/HAND task was not run'; `docs/claims.md` C10 notes HAND features could not be built).
- Commit trailers name 'Claude Sonnet 5.5' as co-author on both commits; no file records that you chose this model.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 6. `docs/claims.md` line 91

**Exact sentence:**

> - Which claims go into the app, the CAC form and the video. TODO-CONFIRM

**Evidence in the repo:**

- `docs/claims.md` section 5 (app text, CAC answer, video script) are drafts written 2026-10-13 by the assistant; no file records your approval or edits.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 7. `docs/claims.md` line 94

**Exact sentence:**

> - Nothing is recorded in the repo: `reviewer_decision` columns in the label files are blank, and no review notes exist. TODO-CONFIRM which of these you actually read and checked: the label decisions; the validation protocol and amendments; the pass/fail results; the export; this claims document.

**Evidence in the repo:**

- `reviewer_decision` is blank in `data/phase0/florence_label_review.csv` (81 rows) and `data/phase2/t10/report_candidates.csv` (709 rows); `data/review/label_review_sheet.csv` (790 rows, built 2026-10-13) has empty reviewer columns; no review notes exist.
- Nothing shows which documents you read: no comments, no edited files, no review log.

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________

## 8. `docs/claims.md` line 95

**Exact sentence:**

> - Whether you ran or tested the code yourself (TODO-CONFIRM), and whether anyone else (for example the ML teammate Shreyas, who received `handoff_for_shreyas/`) contributed or reviewed (TODO-CONFIRM).

**Evidence in the repo:**

- `handoff_for_shreyas/`, `handoff_for_shreyas.zip` (2026-10-11 19:24) and `FloodLens_data_for_Shreyas.zip` (2026-10-11 19:27) exist, and `docs/ML_HANDOFF.md` (2026-10-12) is addressed to 'the ML teammate'.
- Nothing in the repo shows that Shreyas used, changed or reviewed anything, or that you ran the scripts yourself (all logs and result files were written during assistant-run sessions).

**Your answer:**  [ ] yes, accurate   [ ] no, delete   [ ] edit (write the corrected sentence here): ______________________
