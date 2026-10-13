# Freeze summary - technical-freeze-1

Written 2026-10-13. Scope: the technical state of the FloodLens Lifelines pilot (Cape Fear: New Hanover, Brunswick, Pender) as committed locally with tag `technical-freeze-1`. Nothing was pushed (the repo has no remote). The only numbers in the claims tables below are copied verbatim from `docs/claims.md`; the checks in section 5 recompute them from files.

## 1. Final claims (copied from `docs/claims.md`, section 1)
Labels: hindcast = NWM v3.0 retrospective; operational replay = NWM operational analysis; scenario = recurrence-flow level, not a probability. **C10 is marked "not recommended as a headline claim" in `docs/claims.md`.** The claims we do NOT make are in `docs/claims.md` section 2 and apply to everything here.

| # | Claim (exact numbers) | Test | Evidence file | Scope limit (one line) |
|---|---|---|---|---|
| C1 | At the hours when flood-closure road reports were filed, NWM flow on the matched reach was far above the same reach's flow at ordinary hours of the same calendar month: AUC **0.958** (95% CI 0.916-0.992); flow above the 2-year level at 60.8% of reports vs 0.73% of control hours. | T10-B | `data/phase2/t10/t10bc_results.json` (`primary_hour`) | 74 provisional, unreviewed reports at 66 NC crossings (24 storms, 2017-2022); controls are random hours, so this shows "storm vs not storm", not "which crossing". |
| C2 | The flow peak falls within +-24 h of the report in **81.1%** of reports vs **14.0%** of controls (difference +0.671, CI 0.556-0.841). | T10-C | `data/phase2/t10/t10bc_results.json` | Same 74 reports; report time is not closure onset time. |
| C3 | The NWM retrospective matches observed discharge at 43 pilot gauges: peak ratio within 0.5-2.0 in **76.7%** of 73 gauge-events; median absolute peak-time error **4 h**; median NSE 0.55. | T10-D | `data/phase2/t10/t10d_stats.json` | Gauged (larger) streams only; says nothing about small ungauged order-1 reaches. |
| C4 | Engine baseline drive times to the nearest ED hospital are close to OSRM's: median absolute error **15.5%**, **91.3%** within +-30%, MAE 3.22 min, bias -2.72 min (engine faster), n = 150 blocks. | T10-F | `data/phase2/t10/t10f_stats.json` | Default OSM speeds, no traffic; passes the 90% rule with 1.3 points of margin; compares two routers, not real trips. |
| C5 | Across 5 NC storm windows (2023-2025), crossings within 100 m of a recorded flood-related road closure had higher modelled peak-flow ratios than other crossings in the same counties: pooled AUC **0.716** (95% CI 0.655-0.752), six-event set; **0.690** (0.623-0.745) when all nine qualifying events are used. | T15 primary (Amendment 4) | `data/phase2/t15/t15_results.json`; `data/phase2/t15_nine/t15_results.json`; `reports/phase2_validation.md` | Operational-analysis flows (assimilated), 430 / 517 positives; unrecorded closures sit in the negatives; AUC is moderate and uneven by event (0.500-0.819); precision at q10 is about 5% (base rate 2.1%). |
| C6 | Structural consequence of closing one crossing (people and blocks losing or slowed in access to ED hospitals and fire stations): computed for 2,742 of 2,920 crossings with no hazard input; e.g. the top-ranked segment slows 43,394 people (537 blocks) by more than 1 minute with 0 people losing hospital or fire access (phase-1 snap). | export (not a validation test) | `data/export/consequence_ranking.csv` | Routing-model estimate: whole OSM segment removed, OSM default speeds, 2020 block centroids, facilities only those geocoded; not validated against real closures. |
| C7 | Under the Florence **hindcast**, a large share of structure-seeded crossings sit above their 2-year flow at once (241 of 250 at the peak hour in RL2), and the modelled count of blocks without a route to an ED hospital changes hour by hour. | replay | `data/export/florence_replay_hourly.csv` | Saturation: 205 of 250 exceed the 50-year flow, so the scenario levels barely separate; free-running hindcast; no surge/tide. |
| C8 | **Nowcast, not forecast (gauge stage):** with the gauge's own recent stage as an input, a fixed gradient-boosting model finds onsets of flood-stage exceedance far better than persistence of the current stage. Recall at 50% precision, onset hours, seed-averaged model vs best persistence baseline: Florence (test) **0.504** vs 0.005, difference **+0.499 [0.400, 0.584]**; unseen gauges 0.417 vs 0.004 (+0.412 [0.298, 0.507]); validation fold 0.384 vs 0.000 (+0.384 [0.085, 0.496]). | ML example (not pre-registered) | `data/phase2/ml_example_v2_results.csv`; `docs/ML_HANDOFF.md` | Needs live stage at the gauge (and upstream/rain feeds); single-seed models get 0.000 at 50% precision on validation and unseen gauges, so the result depends on seed-averaging (chosen post hoc); operating points are set on the evaluation set; one test event, 26 unseen gauges with usable rows. Gauge exceedance is not road closure. |
| C9 | **FEMA NFHL comparison (descriptive only):** of the 250 hazard-ready seed crossings, **241 (96.4%)** exceed RL10 in the Florence hindcast; **214 of those 241 (88.8%)** lie in a FEMA special flood hazard area (A/AE/AH/AO or V/VE), and 7 of the 9 that do not exceed RL10 are also in an SFHA. | T4 comparison | `data/phase2/fema_vs_rl10_florence_hindcast.csv`; `data/phase2/fema_nfhl.parquet` | FEMA zones are a comparison layer, not ground truth; the hindcast saturates, so RL10 does not separate zones (X minimal 92.6% vs SFHA A/AE 97.3% above RL10); crossings sit on waterways, so most fall in mapped hazard areas by construction; "unmapped" means no polygon, not low hazard. |
| C10 | **Within nine 2023-2025 NC storm windows, a pre-registered model combining hindcast flow features with structure attributes ranked crossings near recorded flood closures better than peak flow ratio alone:** leave-one-storm-out pooled AUC **0.798** (CI 0.759-0.820) vs **0.690** (0.624-0.744) for raw peak/q10; paired difference **+0.108 [0.045, 0.171]** (logistic: 0.757, +0.066 [0.030, 0.102]); within-county AUC 0.708 vs 0.626; Helene (held out, trained without it) 0.719 vs 0.638. | T16 (Amendment 5), verdict PASS | `data/phase2/t16/t16_results.json`; `data/phase2/t16/t16_per_event.csv`; `reports/phase2_validation.md` | **Not recommended as a headline claim.** A post-hoc check shows structure attributes with no flow information alone score 0.716 (flow-only features 0.663), so the gain probably reflects which crossings get closures recorded rather than flood hazard; the model is no better than the raw ratio in 2 of 8 events (E1, E6); features use the whole event (hindcast, not a forecast); rain and HAND features could not be built; CIs hold the fitted models fixed; negatives include unrecorded closures. |

### Tests that failed or showed no signal (copied from `docs/claims.md`, section 3)

| Test | What happened | File |
|---|---|---|
| **T12** HWM above road crest vs modelled peak ratio | **FAIL.** AUC **0.55** (CI 0.37-0.73), n = 32 vs 15; HWM above crest at 35 of 54 (64.8%); even crossings with HWM below crest had modelled peaks ~3x their q10. | `data/phase2/t12/t12_results.json`, `reports/phase2_validation.md` |
| **T13** inside observed Florence flood extent vs modelled max flow ratio | **FAIL.** AUC **0.58** (CI 0.32-0.83); 243 of 250 crossings inside the mapped flood, so the observation saturates too. | `data/phase2/t13/t13_results.json` |
| **E1** NCDOT-listed closed roads vs unlisted | **FAIL.** 78.6% (55/70) vs 65.2% (30/46), one-sided p = 0.085 (needs < 0.05). | `data/phase2/t10/t10e_results.json` |
| **E2** dated closures (I-40, I-95, US-17/NC-87) | 8/8 hit, but passes for any road in a saturated layer; **not evidence of validation**. | `data/phase2/t10/t10e_results.json` |
| **E3** graph reproduces Wilmington's isolation | **MISS.** 1.3% exit loss with every listed structure closed; 0% with the model's own q10 set. | `data/phase2/t10/t10e3_exit_scenario.csv` |
| **T15 event E2** (2024-01-09..13, 41 counties) | AUC **0.500** (CI 0.425-0.594), 140 positives: **no signal**. Also E8 (2025-05) AUC 0.516 (CI 0.14-0.83), 25 positives. | `data/phase2/t15/t15_results_by_event.csv`, `data/phase2/t15_nine/t15_results_by_event.csv` |
| **T15 Helene (E5)**, reported separately | AUC 0.638 (CI 0.556-0.711), but **saturated**: 40.7% of negatives exceed q10 (11.9% in the other events); stream order 1 AUC 0.50. | `data/phase2/t15/t15_results_by_event.csv`, `reports/phase2_validation.md` |
| **T16** structure-only vs flow-only (post hoc, not registered) | Structure attributes with **no flow** reach pooled AUC 0.716; flow-only features 0.663; raw peak/q10 0.690. The T16 pass (0.798) is therefore not evidence of hydrological skill. T16 also failed to beat the raw ratio in events E1 (0.800 vs 0.806) and E6 (0.777 vs 0.801). | `data/phase2/t16/t16_posthoc_feature_families.csv`, `t16_per_event.csv` |
| Phase-1 label comparison (reported vs unreported crossings) | No separation: p = 0.58 (peak bin), 0.78 (earliest 2-yr exceedance); 15 assessable reports. | `reports/phase1_report.md` section 5 |
| T15 under Amendment 3 (isolated `IsFullClosure` field) | Stopped: zero qualifying events, because the field is empty before 2026. Amendment 4 changed the rule before any model output existed. | `reports/phase2_validation.md` |
| Within-county discrimination (post hoc, not registered) | AUC about 0.63 in the six-event set: part of the pooled 0.72 reflects which counties got more flow. | `reports/phase2_validation.md` |

### Live layer
The live layer (`data/export/live_conditions.json/.csv`) is a nowcast / scenario display of NOAA operational NWM output. It adds **no new validation claim** (`docs/claims.md`, section 4).

## 2. Files the app and website read
All under `data/export/` (manifest with row counts and sha256: `manifest.json`; field meanings and caveats: `README.md`, which also carries the full limitation list):
- `crossings_export.csv` / `crossings_export.geojson` - 2,920 crossings with reach, recurrence flows, FEMA zone (join key `id`)
- `consequence_ranking.csv` - structural consequence per crossing (same ids; no hazard input)
- `blocks_export.csv` - Census block origins with baseline reachability
- `florence_replay_hourly.csv` - Florence hindcast, hourly, by crossing set and scenario level
- `address_report_sample.json` - 25 sample block-centroid reports (stamped `SAMPLE - block-centroid estimate`)
- `live_conditions.json` / `live_conditions.csv` - **live layer**, rewritten by `python src/72_live_conditions.py` (sha not pinned; read `available`, `stale`, `age_minutes`, `generated_at` before showing anything, and show the `label` text with it)
- Wording source for app text, CAC answer and video: `docs/claims.md` section 5 (drafts; not yet approved by the project owner)

## 3. Known gaps
- **T5 / HAND was never run.** No terrain/HAND feature or `long_bridge_flag` exists; `nbi_structure_len_m` is the only length information.
- **Stage IV rain is unavailable for T16** (the 2023-2025 events); the T16 model has no rain feature (`docs/claims.md` C10).
- **Fire-station values in `florence_replay_hourly.csv` are blank for the `seed_reliable` set** (all 6,600 rows; not computed). They are present for the `seed` set (0 blanks in 6,600 rows). The brief said the blanks were in the seed set; the file shows the reverse, so this line follows the file.
- **88 blocks (6,921 people) are baseline-unreachable under the phase-1 snap and are "not assessed"** in every loss count; they are not zero-loss.
- **Closure labels are unreviewed.** All reviewer columns are blank in `data/phase0/florence_label_review.csv` and `data/phase2/t10/report_candidates.csv`. The 790-row review sheet is `data/review/label_review_sheet.csv` (instructions: `docs/label_review_instructions.md`; apply with `src/70_apply_label_review.py`; sensitivity with `src/71_label_sensitivity.py`, variants 2 and 3 not yet run). T15 does not depend on these labels (it uses NCDOT closure records); T10-B/C (claims C1, C2) does.
- **One number in `docs/claims.md` does not trace to a file:** section 2 item 3 and section 6 say "120" closure-report candidates (74 accept / 15 uncertain). The files hold 709 T10 candidates (117 assessable: 74 accept / 28 reject / 15 uncertain) plus 81 Florence candidates (27 / 49 / 5): 790 rows. No count of 120 exists in the repo. `docs/claims.md` was not edited for this (earlier results untouched); the wording needs a decision.
- Minor: the claims text "p = 0.78" (phase-1 earliest 2-yr rule) traces to `reports/phase1_report.md`; `data/phase2/t2a_rule_comparison.csv` gives 0.792 for the same rule (different null draw). The base rate "2.1%" in C5 belongs to the six-event set (nine-event: 517 / 25,337 = 2.0%).
- The live layer is a nowcast of the current operational NWM (file version stored in `source.nwm_version`; NOAA's overview page describes v3.0 while the files say 3.1). The AWS registry page documents only the short-range product, so the `analysis_assim` path on that bucket was confirmed by request, not by its registry page. The hourly archiver in `data/forecasts/` covers only the 256 gauge reaches of `config/reaches.csv` (2 of the export's hazard-ready reaches), so the live layer does not use it.
- 103 crossings have a reach but no usable recurrence flows (`not_assessed` in the live layer); 178 crossings are not snapped to the routing graph (consequence not assessed); 1,234 of 2,920 crossings have no matched reach.
- Every validation test is a hindcast or operational-analysis replay; no forecast skill is claimed (`docs/claims.md` section 2).

## 4. Reproduce the headline numbers
Verification from the committed files (minutes; no downloads), from the repo root:
```
python src/80_repro_headlines.py            # 65 quantities: recomputed vs documented in docs/claims.md; exit 1 on any mismatch
python src/export_checks.py data/export/    # export integrity, id joins, NaN handling, banned strings, live-layer fields
python src/71_label_sensitivity.py          # self-check: T15 nine-event 0.690 and T10-B 0.958 (variant 1)
python src/ml_example_v2.py data/derived --out results.csv --boot 200 --seeds 42 43 44   # C8; needs data/derived/ml_full_table_v2/ (not committed, ~1 GB)
```
From scratch, per claim (each script's docstring lists its inputs; network steps need downloads and were **not** re-run for this freeze):
```
C1-C4 (T10):  python src/30_t10_reports.py ; src/31_t10_review_suggestions.py ; src/32_t10_fetch_records.py ; src/33_t10_flow_test.py ; src/35_t10_gauge_validation.py ; src/36_t10_routing_check.py
C5 (T15):     python src/50_t15_step1_closures.py ; 51_t15_events_a4.py ; 52_t15_crossings.py ; 53_t15_flows.py ; 54_t15_test.py   (six events)   then   python src/55_t15_nine.py   (nine events)
C10 (T16):    python src/56_t16_features.py ; 57_t16_model.py ; 58_t16_posthoc.py
C6, C7:       python src/export_data.py   (needs the phase-1/1b/2 engine outputs, see src/22_engine_p2.py and src/23_p8_p2.py)   then   python src/export_checks.py
C8 (ML):      steps 01-08 in src/README.md, then src/10_nldi.py ; 11_stage4_catch.py ; 12_build_v2.py ; ml_example_v2.py
C9 (FEMA):    python src/61_fema_nfhl.py ; src/62_fema_compare.py
live layer:   python src/72_live_conditions.py
```

## 5. Checks run for this freeze (2026-10-13)
- `src/export_checks.py data/export/`: PASS, 0 failures (includes the new live-layer checks).
- `src/80_repro_headlines.py`: 65 quantities, 0 mismatches (recomputed from files where marked `recomputed`; bootstrap CIs and model-run outputs are read from the stored result files and marked `stored`). Table: `data/review/repro_headlines.csv`.
- Clean rerun of `src/ml_example_v2.py` (log `data/review/ml_rerun.log`): all 207 result rows identical to the stored `data/phase2/ml_example_v2_results.csv` (maximum absolute difference 0).
- `src/71_label_sensitivity.py` variant 1 reproduces the T15 nine-event pooled AUC and the T10-B AUC from files.
