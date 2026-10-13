# Sample model v2 - does new INFORMATION create onset skill?

**This is a NOWCAST, not a forecast.** The new features include observed stage at the gauge (and at upstream gauges) up to one hour before the row time, plus observed (Stage IV) rain over the catchment. A deployed system would need live gauge and radar-gauge rain feeds; nothing here forecasts rain or the NWM. Scripts: `src/10`-`16` (`src/README.md`); numbers: `data/derived/sample_model_v2*.csv`; sources: `reports/new_features_sources.md`; table: `data/derived/ml_full_table_v2/` (`reports/DATA_CARD_v2.md`); leakage tests: `data/derived/leakage_tests_v2.txt` (all PASS).

## Setup (as specified, nothing tuned)
- HistGradientBoosting, same fixed settings as `sample_model.md` (200 trees, lr 0.1, 31 leaves, no early stopping). Train: trainval folds 0-3, all positives + 10% of negatives (903k rows, 58.8k positives). **3 seeds** (42/43/44; the seed changes the negative subsample and the model).
- Feature sets (ablation): NWM only (15 old features); +own stage (9); +upstream gauges (50); +rain (7); +own+upstream; **+all** (the primary model, named before looking at results).
- Baselines, all scored on the same rows: `baseline_ratio`, `nwm_flow_pctile`, **`persist_stage_frac`** (stage / flood stage), **`persist_extrap12h`** ((stage + 12 h x 6 h rise rate) / flood stage).
- Eval sets never trained on: VAL (fold 4), UNSEEN gauges (non-Florence), TEST (Florence), PILOT non-Florence (pilot gauges in VAL+UNSEEN), PILOT Florence. Rows are common to every score (label known; baseline_ratio, nwm_flow_pctile and the stage at the cutoff all present), so populations are slightly smaller than in `sample_model.md`.
- Onset = `is_exceed_now == False` (as specified). Because the features stop at bin t-1 while `is_exceed_now` is bin t, this "onset" still contains recession hours where the gauge was above flood stage at the cutoff. I therefore also report a **strict onset** (cutoff stage < flood stage). Conclusions are the same under both.
- 95% CIs: cluster bootstrap (event_id; gauge for Florence), 200 draws, **paired** across scores (differences use the same draws).

## Verdict
**Does the best model beat the best baseline at onset? YES on the seed-averaged score, NO on single seeds at 50% precision. The seed-averaged score was chosen after seeing the single-seed numbers (post-hoc).**

1. **Seed-averaged probability of the 3 seeds (same settings, no tuning).** `+all` beats the best baseline on every eval set, under both onset definitions, at both precision levels, with 95% CIs excluding 0. Recall at 50% precision, onset only, difference to the best baseline [CI]: VAL +0.41 [+0.10, +0.52]; UNSEEN +0.41 [+0.20, +0.63]; TEST (Florence) +0.42 [+0.28, +0.53]; PILOT non-Florence +0.21 [+0.05, +0.35]; PILOT Florence +0.36 [+0.15, +0.53]. Absolute recall at 50% precision: 0.42-0.50 on VAL/UNSEEN/Florence (best baseline <= 0.08), 0.22 on the non-Florence pilot gauges.
2. **Single-seed models (the pre-specified analysis): recall at 50% precision for `+all` is 0.000 on 3 of 5 sets and 0.25 on the two Florence sets (CIs include 0), so the single-seed verdict is NO on all five. Each seed puts about 1,000 held-out rows at probability exactly 1.0 that are all false alarms (588 of them at 03441000, Davidson River: stage ~0.8 ft vs flood stage 6 ft). Ties at the top stop recall at 50% precision from ever starting; averaging seeds breaks the ties. At 20% precision single-seed models are already ahead (Florence 0.80 vs best baseline 0.48), but VAL/UNSEEN CIs overlap the baselines. Both tables are in the appendix.
3. **Limits on that YES**: the ensemble was added after seeing the single-seed zeros; the models are overconfident (p = 1.0 false alarms), so any precision-based operating point is fragile; the false alarms concentrate in a few gauges that the event-cluster bootstrap does not resample as clusters.

## Which information helps (seed-averaged, onset only, recall at 50% / 20% precision)
| set | NWM only | +own stage | +upstream | +rain | +own+upstream | +all |
|---|---|---|---|---|---|---|
| VAL | 0.00 / 0.06 | 0.35 / 0.49 | 0.01 / 0.21 | 0.00 / 0.13 | 0.39 / 0.51 | **0.42 / 0.57** |
| UNSEEN | 0.01 / 0.05 | 0.44 / 0.57 | 0.00 / 0.28 | 0.01 / 0.19 | 0.43 / 0.56 | **0.43 / 0.60** |
| TEST (Florence) | 0.01 / 0.11 | 0.37 / 0.63 | 0.02 / 0.38 | 0.02 / 0.38 | 0.41 / 0.66 | **0.50 / 0.79** |
| PILOT non-Florence | 0.01 / 0.02 | 0.17 / 0.36 | 0.05 / 0.10 | 0.00 / 0.01 | 0.18 / 0.38 | **0.22 / 0.41** |
| PILOT Florence | 0.00 / 0.02 | 0.38 / 0.68 | 0.02 / 0.40 | 0.01 / 0.18 | 0.45 / 0.73 | **0.49 / 0.80** |

- **The skill comes from the gauge's own recent stage.** NWM-only stays at ~0 (the earlier finding replicates). Adding own stage moves recall at 50% precision from ~0 to 0.35-0.44 on held-out events and unseen gauges.
- **Upstream gauges and observed rain help only a little and not provably.** Alone they lift recall at 20% precision from ~0.05 to 0.1-0.4 but rarely at 50%. On top of own stage, +all minus +own stage at 50% precision ranges from -0.02 (UNSEEN) to +0.13 (Florence) with heavily overlapping CIs (Florence 0.50 [0.37, 0.59] vs 0.37 [0.27, 0.48]). I cannot say rain or upstream gauges add onset skill beyond own stage. Only 108 of 236 gauges have any upstream gauge.
- **Much of "own stage" is learned persistence.** On all-hours PR-AUC the plain `persist_stage_frac` baseline (0.86-0.89 on VAL/UNSEEN/Florence) is as good as or better than every model (+all: 0.74 / 0.63 / 0.89), as expected when most positives are already-flooding hours. The model's advantage is at onset, and it is plausibly a calibrated-persistence effect (the cross-gauge ratio stage/flood-stage is uncalibrated; a small per-gauge logistic model on stage and rate might get close). I did not run that stronger baseline.

## Lead time (onset only, seed-averaged score, thresholds set on the eval set itself)
A "true onset" is an observed first crossing of flood stage whose preceding 12 rows are all positive and not yet flooding. Lead = hours between the first alert in that 12 h window and the crossing (max 12). Median lead of detected onsets for `+all` at the 50% / 20% precision thresholds: VAL 9 h / 12 h (81 / 86 of 91 onsets detected); UNSEEN 7 h / 10 h (124 / 136 of 155); Florence 7 h / 11 h (84 / 89 of 89); PILOT non-Florence 6 h / 8.5 h (35 / 40 of 58); PILOT Florence 6 h / 10.5 h (33 / 36 of 36). Baselines detect almost nothing at 50% precision (`persist_stage_frac` 0 on all sets; `persist_extrap12h` 9 of 89 on Florence, lead 2 h). Full table in the appendix. The 12 h label horizon caps the lead, and thresholds chosen on the eval set make these optimistic.

## Caveats that make these results optimistic or fragile
1. **Nowcast, not forecast.** Needs live stage at the gauge and upstream gauges (and live rain). Lead is bounded by the 12 h label.
2. **Post-hoc ensemble.** The headline YES uses a seed-averaged score chosen after the single-seed metric degenerated. Single-seed recall at 50% precision is 0.
3. **Overconfident false alarms** (p = 1.0 on rows that never flood), concentrated in a few gauges; the bootstrap clusters by event, not gauge, so VAL/UNSEEN CIs are probably too narrow. Absolute stage in feet can act as a gauge identifier, so a model can memorise per-gauge levels (hence the unseen-gauge test, whose CIs are wide with 17 gauges).
4. **Operating points come from the eval set** (recall at fixed precision, lead-time thresholds). A deployed threshold would be chosen on training data and could miss the target precision.
5. **Unseen-gauge `baseline_ratio`/`q_fs_cfs` still use that gauge's own observed stage-discharge pairs** (flagged `own_nontest_hours`), and its `nwm_flow_pctile` reference is its own unseen-split NWM hours. These NWM-side features feed every model including NWM only.
6. **Florence is one event** (a 54-day chain with Michael); its CI is a gauge bootstrap. True onsets: 91 (VAL), 155 (UNSEEN), 58 (pilot non-Florence), so a few storms dominate.
7. **Stage IV is the final, QC'd archive** (a real-time feed would carry latency and preliminary-version error); 108 hours are missing in the window (2019-04: 24, 2020-07: 84) and gauge 0208732534 has no NLDI basin; those features are NaN. Weighting uses a spherical 6371.2 km earth and 4762.5 m spacing; NLDI basin polygons are used as given.
8. **"Nearest upstream" is by great-circle distance** among NLDI upstream sites, not along-network distance, and limited to the 236 usable gauges. Upstream gauges may be in training while the target gauge is unseen (their observations are inputs, not labels).
9. **Timing is one hour stricter than the v1 table**, and the specified onset definition includes some rows whose cutoff stage was already above flood stage (see strict onset). The common-row restriction changes populations vs `sample_model.md`.
10. **Leakage tests** cover truncation recompute for each group, rain window end-times, split structure, old columns identical, and a raw-GRIB re-derivation of basin means. That re-derivation covered only 11 gauge-hours from the GRIB1 era (2016-09, 2018-09); the GRIB2-era months (2020-08 on) were checked by plausibility only.
11. **Not done**: MRMS (starts 2020-10-14), the AORC comparison feature, any forecast rainfall or NWM forecast, a stronger calibrated persistence baseline, hyperparameter tuning (by instruction).

## Task list (final state)
1. Observed-stage and upstream-gauge features - done (`12_build_v2.py`)
2. Stage IV rain + sources note - done (`11_stage4_catch.py`; MRMS and AORC checked, skipped)
3. Table v2 + extended leakage tests - done, all PASS
4. Baselines incl. persistence - done
5. Models and ablations x 3 seeds - done
6. Evaluation, verdict, report - done

---
# Appendix: full tables (auto-generated by `src/15_report_v2.py`)

## Verdict table (auto)

| eval set | onset population | metric | best baseline | +all minus baseline [95% CI] | beats it? |
|---|---|---|---|---|---|
| VAL (held-out events, trained gauges) | onset only [ensemble] | recall @50% precision | nwm_flow_pctile | +0.410 [+0.098, +0.523] | **YES** |
| VAL (held-out events, trained gauges) | onset only [ensemble] | recall @20% precision | persist_stage_frac | +0.422 [+0.186, +0.622] | **YES** |
| VAL (held-out events, trained gauges) | onset only | recall @50% precision | nwm_flow_pctile | -0.014 [-0.044, +0.000] | **NO** |
| VAL (held-out events, trained gauges) | onset only | recall @20% precision | persist_stage_frac | +0.395 [-0.181, +0.607] | **NO** |
| VAL (held-out events, trained gauges) | strict onset [ensemble] | recall @50% precision | nwm_flow_pctile | +0.416 [+0.121, +0.528] | **YES** |
| VAL (held-out events, trained gauges) | strict onset [ensemble] | recall @20% precision | persist_stage_frac | +0.407 [+0.174, +0.538] | **YES** |
| VAL (held-out events, trained gauges) | strict onset | recall @50% precision | nwm_flow_pctile | -0.014 [-0.041, +0.064] | **NO** |
| VAL (held-out events, trained gauges) | strict onset | recall @20% precision | persist_stage_frac | +0.384 [-0.218, +0.577] | **NO** |
| UNSEEN gauges (non-Florence) | onset only [ensemble] | recall @50% precision | baseline_ratio | +0.408 [+0.198, +0.629] | **YES** |
| UNSEEN gauges (non-Florence) | onset only [ensemble] | recall @20% precision | persist_stage_frac | +0.396 [+0.296, +0.569] | **YES** |
| UNSEEN gauges (non-Florence) | onset only | recall @50% precision | baseline_ratio | -0.017 [-0.037, +0.143] | **NO** |
| UNSEEN gauges (non-Florence) | onset only | recall @20% precision | persist_stage_frac | +0.186 [-0.035, +0.492] | **NO** |
| UNSEEN gauges (non-Florence) | strict onset [ensemble] | recall @50% precision | baseline_ratio | +0.416 [+0.215, +0.625] | **YES** |
| UNSEEN gauges (non-Florence) | strict onset [ensemble] | recall @20% precision | persist_stage_frac | +0.384 [+0.241, +0.505] | **YES** |
| UNSEEN gauges (non-Florence) | strict onset | recall @50% precision | baseline_ratio | -0.016 [-0.040, +0.126] | **NO** |
| UNSEEN gauges (non-Florence) | strict onset | recall @20% precision | persist_stage_frac | +0.176 [-0.092, +0.449] | **NO** |
| TEST (Florence) | onset only [ensemble] | recall @50% precision | nwm_flow_pctile | +0.415 [+0.276, +0.534] | **YES** |
| TEST (Florence) | onset only [ensemble] | recall @20% precision | persist_extrap12h | +0.308 [+0.239, +0.368] | **YES** |
| TEST (Florence) | onset only | recall @50% precision | nwm_flow_pctile | +0.166 [-0.091, +0.455] | **NO** |
| TEST (Florence) | onset only | recall @20% precision | persist_extrap12h | +0.316 [+0.251, +0.380] | **YES** |
| TEST (Florence) | strict onset [ensemble] | recall @50% precision | nwm_flow_pctile | +0.426 [+0.305, +0.532] | **YES** |
| TEST (Florence) | strict onset [ensemble] | recall @20% precision | persist_extrap12h | +0.310 [+0.214, +0.380] | **YES** |
| TEST (Florence) | strict onset | recall @50% precision | nwm_flow_pctile | +0.189 [-0.079, +0.433] | **NO** |
| TEST (Florence) | strict onset | recall @20% precision | persist_extrap12h | +0.317 [+0.241, +0.394] | **YES** |
| PILOT non-Florence (VAL+UNSEEN) | onset only [ensemble] | recall @50% precision | baseline_ratio | +0.209 [+0.045, +0.351] | **YES** |
| PILOT non-Florence (VAL+UNSEEN) | onset only [ensemble] | recall @20% precision | persist_stage_frac | +0.343 [+0.185, +0.475] | **YES** |
| PILOT non-Florence (VAL+UNSEEN) | onset only | recall @50% precision | baseline_ratio | -0.010 [-0.034, +0.000] | **NO** |
| PILOT non-Florence (VAL+UNSEEN) | onset only | recall @20% precision | persist_stage_frac | +0.137 [-0.095, +0.433] | **NO** |
| PILOT non-Florence (VAL+UNSEEN) | strict onset [ensemble] | recall @50% precision | baseline_ratio | +0.208 [+0.085, +0.384] | **YES** |
| PILOT non-Florence (VAL+UNSEEN) | strict onset [ensemble] | recall @20% precision | persist_stage_frac | +0.329 [+0.174, +0.473] | **YES** |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | recall @50% precision | baseline_ratio | -0.010 [-0.038, +0.000] | **NO** |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | recall @20% precision | persist_stage_frac | +0.145 [-0.090, +0.472] | **NO** |
| PILOT Florence (TEST) | onset only [ensemble] | recall @50% precision | nwm_flow_pctile | +0.362 [+0.147, +0.527] | **YES** |
| PILOT Florence (TEST) | onset only [ensemble] | recall @20% precision | persist_extrap12h | +0.331 [+0.233, +0.444] | **YES** |
| PILOT Florence (TEST) | onset only | recall @50% precision | nwm_flow_pctile | +0.124 [-0.158, +0.456] | **NO** |
| PILOT Florence (TEST) | onset only | recall @20% precision | persist_extrap12h | +0.377 [+0.252, +0.464] | **YES** |
| PILOT Florence (TEST) | strict onset [ensemble] | recall @50% precision | nwm_flow_pctile | +0.384 [+0.242, +0.606] | **YES** |
| PILOT Florence (TEST) | strict onset [ensemble] | recall @20% precision | persist_extrap12h | +0.335 [+0.235, +0.449] | **YES** |
| PILOT Florence (TEST) | strict onset | recall @50% precision | nwm_flow_pctile | +0.138 [-0.107, +0.526] | **NO** |
| PILOT Florence (TEST) | strict onset | recall @20% precision | persist_extrap12h | +0.379 [+0.267, +0.478] | **YES** |

## Per eval set

### VAL (held-out events, trained gauges)
**onset only**: 83 gauges; rows 1,026,603, positives 1829 (base rate 0.0018); all-hours positives 11649.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.005 [0.000, 0.013] | 0.005 [0.000, 0.039] | 0.028 [0.022, 0.043] | 0.527 [0.427, 0.587] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.014 [0.000, 0.044] | 0.033 [0.000, 0.092] | 0.040 [0.018, 0.079] | 0.213 [0.113, 0.336] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.000] | 0.146 [0.000, 0.313] | 0.063 [0.009, 0.112] | 0.893 [0.694, 0.935] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.537] | 0.058 [0.010, 0.097] | 0.527 [0.300, 0.642] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.033 [0.010, 0.054] | 0.443 [0.209, 0.570] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.000] | 0.417 [0.000, 0.614] | 0.116 [0.020, 0.206] | 0.741 [0.480, 0.859] | 0.000 / 0.035 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.077] | 0.059 [0.015, 0.095] | 0.552 [0.299, 0.666] | 0.000 / 0.000 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.048 [0.013, 0.075] | 0.474 [0.230, 0.596] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.440 [0.000, 0.648] | 0.122 [0.025, 0.211] | 0.736 [0.489, 0.850] | 0.000 / 0.021 |
| +all | 0.000 [0.000, 0.000] | 0.541 [0.000, 0.704] | 0.149 [0.034, 0.245] | 0.741 [0.468, 0.846] | 0.000 / 0.013 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.000 [0.000, 0.064] | 0.064 [0.000, 0.137] | 0.054 [0.026, 0.102] |
| ens +own stage | 0.346 [0.062, 0.475] | 0.487 [0.112, 0.594] | 0.316 [0.198, 0.412] |
| ens +upstream gauges | 0.007 [0.005, 0.134] | 0.210 [0.021, 0.417] | 0.104 [0.063, 0.167] |
| ens +rain | 0.004 [0.000, 0.091] | 0.132 [0.014, 0.227] | 0.092 [0.045, 0.138] |
| ens +own+upstream | 0.388 [0.080, 0.509] | 0.505 [0.143, 0.621] | 0.353 [0.088, 0.462] |
| ens +all | 0.424 [0.101, 0.546] | 0.568 [0.251, 0.673] | 0.407 [0.276, 0.505] |

**strict onset (stage at cutoff < flood stage)**: 83 gauges; rows 1,026,463, positives 1822 (base rate 0.0018); all-hours positives 11649.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.005 [0.000, 0.015] | 0.005 [0.000, 0.044] | 0.027 [0.021, 0.044] | 0.527 [0.427, 0.587] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.014 [0.000, 0.044] | 0.037 [0.000, 0.093] | 0.041 [0.015, 0.080] | 0.213 [0.113, 0.336] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.000] | 0.159 [0.000, 0.330] | 0.071 [0.035, 0.125] | 0.893 [0.694, 0.935] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.527] | 0.059 [0.045, 0.114] | 0.527 [0.300, 0.642] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.033 [0.012, 0.053] | 0.443 [0.209, 0.570] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.000] | 0.422 [0.000, 0.614] | 0.117 [0.022, 0.211] | 0.741 [0.480, 0.859] | 0.000 / 0.033 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.153] | 0.059 [0.019, 0.098] | 0.552 [0.299, 0.666] | 0.000 / 0.000 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.048 [0.016, 0.078] | 0.474 [0.230, 0.596] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.443 [0.000, 0.660] | 0.123 [0.025, 0.218] | 0.736 [0.489, 0.850] | 0.000 / 0.024 |
| +all | 0.000 [0.000, 0.108] | 0.543 [0.000, 0.722] | 0.150 [0.040, 0.246] | 0.741 [0.468, 0.846] | 0.000 / 0.012 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.000 [0.000, 0.067] | 0.071 [0.000, 0.134] | 0.055 [0.031, 0.108] |
| ens +own stage | 0.359 [0.094, 0.479] | 0.485 [0.148, 0.595] | 0.342 [0.102, 0.458] |
| ens +upstream gauges | 0.007 [0.005, 0.110] | 0.213 [0.027, 0.428] | 0.105 [0.063, 0.159] |
| ens +rain | 0.004 [0.000, 0.096] | 0.139 [0.010, 0.225] | 0.093 [0.050, 0.148] |
| ens +own+upstream | 0.388 [0.099, 0.512] | 0.503 [0.162, 0.624] | 0.374 [0.114, 0.478] |
| ens +all | 0.430 [0.128, 0.559] | 0.566 [0.277, 0.678] | 0.435 [0.360, 0.565] |

### UNSEEN gauges (non-Florence)
**onset only**: 17 gauges; rows 1,162,634, positives 1926 (base rate 0.0017); all-hours positives 8689.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.017 [0.002, 0.044] | 0.049 [0.006, 0.171] | 0.054 [0.047, 0.109] | 0.568 [0.321, 0.709] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.001 [0.000, 0.020] | 0.017 [0.000, 0.117] | 0.038 [0.017, 0.084] | 0.264 [0.183, 0.363] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.005 [0.002, 0.008] | 0.207 [0.003, 0.361] | 0.096 [0.067, 0.146] | 0.860 [0.813, 0.944] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.001 [0.000, 0.002] | 0.001 [0.000, 0.718] | 0.099 [0.052, 0.163] | 0.514 [0.235, 0.730] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.036 [0.024, 0.055] | 0.344 [0.122, 0.530] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.201] | 0.554 [0.113, 0.761] | 0.166 [0.084, 0.292] | 0.719 [0.409, 0.864] | 0.000 / 0.017 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.054 [0.000, 0.127] | 0.062 [0.036, 0.103] | 0.451 [0.162, 0.658] | 0.000 / 0.076 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.049 [0.034, 0.084] | 0.352 [0.142, 0.547] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.153 [0.000, 0.505] | 0.081 [0.046, 0.159] | 0.497 [0.215, 0.693] | 0.000 / 0.217 |
| +all | 0.000 [0.000, 0.165] | 0.393 [0.106, 0.774] | 0.141 [0.077, 0.270] | 0.633 [0.310, 0.824] | 0.000 / 0.279 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.007 [0.000, 0.042] | 0.048 [0.007, 0.169] | 0.071 [0.042, 0.112] |
| ens +own stage | 0.440 [0.168, 0.651] | 0.565 [0.382, 0.748] | 0.392 [0.244, 0.574] |
| ens +upstream gauges | 0.003 [0.000, 0.111] | 0.278 [0.078, 0.436] | 0.128 [0.089, 0.202] |
| ens +rain | 0.010 [0.001, 0.036] | 0.194 [0.017, 0.374] | 0.107 [0.077, 0.153] |
| ens +own+upstream | 0.430 [0.166, 0.640] | 0.560 [0.382, 0.737] | 0.386 [0.285, 0.589] |
| ens +all | 0.425 [0.207, 0.646] | 0.603 [0.424, 0.773] | 0.422 [0.327, 0.616] |

**strict onset (stage at cutoff < flood stage)**: 17 gauges; rows 1,162,456, positives 1912 (base rate 0.0016); all-hours positives 8689.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.016 [0.001, 0.040] | 0.046 [0.001, 0.166] | 0.051 [0.044, 0.105] | 0.568 [0.321, 0.709] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.001 [0.000, 0.021] | 0.014 [0.000, 0.092] | 0.037 [0.016, 0.079] | 0.264 [0.183, 0.363] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.007] | 0.217 [0.021, 0.360] | 0.104 [0.066, 0.152] | 0.860 [0.813, 0.944] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.000 [0.000, 0.005] | 0.000 [0.000, 0.686] | 0.099 [0.045, 0.171] | 0.514 [0.235, 0.730] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.036 [0.021, 0.054] | 0.344 [0.122, 0.530] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.187] | 0.553 [0.111, 0.729] | 0.168 [0.079, 0.278] | 0.719 [0.409, 0.864] | 0.000 / 0.016 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.053 [0.000, 0.140] | 0.062 [0.031, 0.106] | 0.451 [0.162, 0.658] | 0.000 / 0.075 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.049 [0.028, 0.088] | 0.352 [0.142, 0.547] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.154 [0.000, 0.496] | 0.081 [0.042, 0.160] | 0.497 [0.215, 0.693] | 0.000 / 0.218 |
| +all | 0.000 [0.000, 0.140] | 0.393 [0.094, 0.771] | 0.141 [0.069, 0.261] | 0.633 [0.310, 0.824] | 0.000 / 0.278 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.006 [0.000, 0.030] | 0.045 [0.003, 0.169] | 0.069 [0.043, 0.109] |
| ens +own stage | 0.445 [0.187, 0.620] | 0.562 [0.361, 0.711] | 0.409 [0.298, 0.573] |
| ens +upstream gauges | 0.002 [0.000, 0.109] | 0.277 [0.069, 0.427] | 0.126 [0.057, 0.182] |
| ens +rain | 0.007 [0.000, 0.037] | 0.192 [0.009, 0.371] | 0.104 [0.068, 0.154] |
| ens +own+upstream | 0.437 [0.175, 0.599] | 0.556 [0.346, 0.695] | 0.398 [0.235, 0.558] |
| ens +all | 0.431 [0.231, 0.640] | 0.601 [0.384, 0.753] | 0.431 [0.247, 0.581] |

### TEST (Florence)
**onset only**: 100 gauges; rows 121,277, positives 1108 (base rate 0.0091); all-hours positives 6335.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.000 [0.000, 0.112] | 0.098 [0.000, 0.180] | 0.060 [0.036, 0.087] | 0.691 [0.550, 0.776] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.079 [0.000, 0.149] | 0.168 [0.101, 0.274] | 0.127 [0.084, 0.191] | 0.545 [0.444, 0.661] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.008 [0.002, 0.018] | 0.010 [0.002, 0.140] | 0.070 [0.056, 0.092] | 0.891 [0.807, 0.922] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.018 [0.000, 0.173] | 0.480 [0.412, 0.535] | 0.197 [0.158, 0.252] | 0.775 [0.658, 0.835] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.016] | 0.029 [0.000, 0.211] | 0.092 [0.067, 0.131] | 0.722 [0.626, 0.814] | 0.000 / 0.041 |
| +own stage | 0.109 [0.000, 0.239] | 0.671 [0.551, 0.763] | 0.259 [0.203, 0.335] | 0.872 [0.784, 0.927] | 0.154 / 0.027 |
| +upstream gauges | 0.000 [0.000, 0.036] | 0.289 [0.000, 0.492] | 0.127 [0.092, 0.178] | 0.725 [0.610, 0.822] | 0.000 / 0.045 |
| +rain | 0.000 [0.000, 0.000] | 0.285 [0.000, 0.479] | 0.130 [0.099, 0.176] | 0.705 [0.604, 0.794] | 0.000 / 0.072 |
| +own+upstream | 0.000 [0.000, 0.332] | 0.687 [0.583, 0.768] | 0.262 [0.203, 0.334] | 0.879 [0.788, 0.929] | 0.000 / 0.004 |
| +all | 0.245 [0.000, 0.515] | 0.796 [0.712, 0.863] | 0.329 [0.274, 0.402] | 0.890 [0.813, 0.929] | 0.174 / 0.006 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.005 [0.000, 0.064] | 0.111 [0.010, 0.232] | 0.109 [0.079, 0.168] |
| ens +own stage | 0.370 [0.266, 0.475] | 0.629 [0.475, 0.741] | 0.382 [0.311, 0.468] |
| ens +upstream gauges | 0.015 [0.003, 0.198] | 0.376 [0.181, 0.538] | 0.176 [0.120, 0.251] |
| ens +rain | 0.021 [0.004, 0.072] | 0.377 [0.031, 0.493] | 0.170 [0.133, 0.259] |
| ens +own+upstream | 0.413 [0.312, 0.513] | 0.655 [0.514, 0.755] | 0.413 [0.337, 0.484] |
| ens +all | 0.495 [0.369, 0.589] | 0.788 [0.692, 0.856] | 0.478 [0.398, 0.563] |

**strict onset (stage at cutoff < flood stage)**: 100 gauges; rows 121,175, positives 1094 (base rate 0.0090); all-hours positives 6335.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.000 [0.000, 0.096] | 0.089 [0.000, 0.159] | 0.056 [0.036, 0.083] | 0.691 [0.550, 0.776] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.077 [0.000, 0.137] | 0.160 [0.088, 0.253] | 0.125 [0.081, 0.187] | 0.545 [0.444, 0.661] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.137] | 0.062 [0.047, 0.083] | 0.891 [0.807, 0.922] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.016 [0.000, 0.160] | 0.477 [0.388, 0.545] | 0.196 [0.155, 0.245] | 0.775 [0.658, 0.835] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.010] | 0.026 [0.000, 0.207] | 0.089 [0.068, 0.130] | 0.722 [0.626, 0.814] | 0.000 / 0.036 |
| +own stage | 0.115 [0.000, 0.260] | 0.672 [0.555, 0.757] | 0.264 [0.213, 0.331] | 0.872 [0.784, 0.927] | 0.163 / 0.023 |
| +upstream gauges | 0.000 [0.000, 0.023] | 0.251 [0.000, 0.471] | 0.124 [0.095, 0.180] | 0.725 [0.610, 0.822] | 0.000 / 0.037 |
| +rain | 0.000 [0.000, 0.000] | 0.189 [0.076, 0.472] | 0.128 [0.100, 0.171] | 0.705 [0.604, 0.794] | 0.000 / 0.154 |
| +own+upstream | 0.000 [0.000, 0.328] | 0.684 [0.585, 0.766] | 0.263 [0.214, 0.345] | 0.879 [0.788, 0.929] | 0.000 / 0.004 |
| +all | 0.265 [0.000, 0.518] | 0.794 [0.710, 0.867] | 0.333 [0.273, 0.406] | 0.890 [0.813, 0.929] | 0.188 / 0.007 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.001 [0.000, 0.047] | 0.100 [0.004, 0.221] | 0.101 [0.078, 0.154] |
| ens +own stage | 0.385 [0.277, 0.499] | 0.638 [0.479, 0.742] | 0.398 [0.323, 0.489] |
| ens +upstream gauges | 0.003 [0.000, 0.198] | 0.358 [0.190, 0.514] | 0.168 [0.130, 0.256] |
| ens +rain | 0.019 [0.003, 0.062] | 0.371 [0.205, 0.502] | 0.165 [0.131, 0.242] |
| ens +own+upstream | 0.421 [0.323, 0.524] | 0.654 [0.542, 0.764] | 0.425 [0.360, 0.508] |
| ens +all | 0.503 [0.383, 0.594] | 0.787 [0.682, 0.857] | 0.492 [0.417, 0.574] |

### PILOT non-Florence (VAL+UNSEEN)
**onset only**: 25 gauges; rows 534,446, positives 922 (base rate 0.0017); all-hours positives 2871.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.010 [0.000, 0.034] | 0.011 [0.004, 0.040] | 0.016 [0.013, 0.036] | 0.154 [0.065, 0.242] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.004 [0.000, 0.031] | 0.034 [0.000, 0.087] | 0.027 [0.012, 0.066] | 0.211 [0.091, 0.355] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.004 [0.000, 0.009] | 0.069 [0.000, 0.160] | 0.045 [0.030, 0.089] | 0.727 [0.630, 0.838] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.001 [0.000, 0.003] | 0.001 [0.000, 0.065] | 0.041 [0.017, 0.090] | 0.300 [0.165, 0.456] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.017 [0.010, 0.033] | 0.161 [0.073, 0.288] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.000] | 0.178 [0.000, 0.460] | 0.084 [0.031, 0.153] | 0.564 [0.348, 0.726] | 0.000 / 0.133 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.029 [0.015, 0.058] | 0.196 [0.088, 0.327] | 0.000 / 0.000 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.025 [0.013, 0.051] | 0.158 [0.074, 0.290] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.166] | 0.043 [0.026, 0.087] | 0.323 [0.238, 0.494] | 0.000 / 0.000 |
| +all | 0.000 [0.000, 0.000] | 0.206 [0.000, 0.552] | 0.093 [0.040, 0.167] | 0.511 [0.325, 0.684] | 0.000 / 0.148 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.005 [0.000, 0.027] | 0.015 [0.000, 0.047] | 0.027 [0.014, 0.061] |
| ens +own stage | 0.174 [0.003, 0.346] | 0.356 [0.140, 0.505] | 0.195 [0.108, 0.321] |
| ens +upstream gauges | 0.048 [0.005, 0.160] | 0.103 [0.018, 0.304] | 0.088 [0.063, 0.212] |
| ens +rain | 0.003 [0.000, 0.065] | 0.014 [0.000, 0.208] | 0.054 [0.030, 0.097] |
| ens +own+upstream | 0.176 [0.006, 0.347] | 0.376 [0.150, 0.536] | 0.192 [0.082, 0.302] |
| ens +all | 0.219 [0.050, 0.374] | 0.412 [0.188, 0.568] | 0.242 [0.136, 0.381] |

**strict onset (stage at cutoff < flood stage)**: 25 gauges; rows 534,359, positives 912 (base rate 0.0017); all-hours positives 2871.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.010 [0.000, 0.038] | 0.011 [0.000, 0.042] | 0.015 [0.013, 0.040] | 0.154 [0.065, 0.242] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.004 [0.000, 0.037] | 0.034 [0.000, 0.092] | 0.027 [0.013, 0.063] | 0.211 [0.091, 0.355] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.007] | 0.078 [0.000, 0.164] | 0.046 [0.018, 0.091] | 0.727 [0.630, 0.838] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.082] | 0.040 [0.017, 0.084] | 0.300 [0.165, 0.456] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.017 [0.010, 0.031] | 0.161 [0.073, 0.288] | 0.000 / 0.000 |
| +own stage | 0.000 [0.000, 0.060] | 0.179 [0.000, 0.519] | 0.084 [0.036, 0.169] | 0.564 [0.348, 0.726] | 0.000 / 0.136 |
| +upstream gauges | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.028 [0.015, 0.053] | 0.196 [0.088, 0.327] | 0.000 / 0.000 |
| +rain | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.025 [0.013, 0.052] | 0.158 [0.074, 0.290] | 0.000 / 0.000 |
| +own+upstream | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.242] | 0.042 [0.026, 0.089] | 0.323 [0.238, 0.494] | 0.000 / 0.000 |
| +all | 0.000 [0.000, 0.000] | 0.223 [0.000, 0.573] | 0.093 [0.045, 0.170] | 0.511 [0.325, 0.684] | 0.000 / 0.158 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.000 [0.000, 0.026] | 0.012 [0.000, 0.040] | 0.025 [0.013, 0.056] |
| ens +own stage | 0.196 [0.017, 0.395] | 0.349 [0.164, 0.518] | 0.211 [0.081, 0.349] |
| ens +upstream gauges | 0.046 [0.002, 0.160] | 0.102 [0.020, 0.279] | 0.086 [0.056, 0.178] |
| ens +rain | 0.000 [0.000, 0.064] | 0.012 [0.000, 0.210] | 0.051 [0.030, 0.095] |
| ens +own+upstream | 0.207 [0.068, 0.381] | 0.371 [0.182, 0.545] | 0.204 [0.088, 0.338] |
| ens +all | 0.218 [0.088, 0.406] | 0.407 [0.212, 0.577] | 0.260 [0.145, 0.409] |

### PILOT Florence (TEST)
**onset only**: 25 gauges; rows 29,617, positives 456 (base rate 0.0154); all-hours positives 2163.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.000 [0.000, 0.065] | 0.000 [0.000, 0.122] | 0.041 [0.031, 0.056] | 0.621 [0.451, 0.725] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.129 [0.000, 0.228] | 0.193 [0.120, 0.352] | 0.155 [0.094, 0.259] | 0.712 [0.529, 0.834] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.013 [0.000, 0.028] | 0.018 [0.000, 0.218] | 0.076 [0.060, 0.113] | 0.861 [0.770, 0.922] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.081 [0.000, 0.188] | 0.469 [0.380, 0.574] | 0.207 [0.170, 0.272] | 0.767 [0.666, 0.850] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.020] | 0.008 [0.000, 0.178] | 0.090 [0.069, 0.136] | 0.704 [0.565, 0.815] | 0.000 / 0.011 |
| +own stage | 0.233 [0.000, 0.451] | 0.692 [0.582, 0.789] | 0.303 [0.215, 0.392] | 0.897 [0.799, 0.948] | 0.061 / 0.011 |
| +upstream gauges | 0.000 [0.000, 0.076] | 0.332 [0.009, 0.614] | 0.151 [0.110, 0.245] | 0.728 [0.611, 0.834] | 0.000 / 0.041 |
| +rain | 0.000 [0.000, 0.011] | 0.070 [0.000, 0.568] | 0.124 [0.091, 0.202] | 0.699 [0.565, 0.811] | 0.000 / 0.099 |
| +own+upstream | 0.353 [0.000, 0.550] | 0.736 [0.591, 0.831] | 0.326 [0.220, 0.437] | 0.878 [0.763, 0.937] | 0.045 / 0.024 |
| +all | 0.254 [0.000, 0.565] | 0.846 [0.716, 0.918] | 0.345 [0.250, 0.450] | 0.859 [0.735, 0.930] | 0.180 / 0.005 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.004 [0.000, 0.045] | 0.020 [0.000, 0.330] | 0.100 [0.077, 0.136] |
| ens +own stage | 0.382 [0.222, 0.479] | 0.684 [0.557, 0.776] | 0.388 [0.275, 0.476] |
| ens +upstream gauges | 0.015 [0.002, 0.272] | 0.395 [0.011, 0.601] | 0.172 [0.118, 0.301] |
| ens +rain | 0.013 [0.000, 0.050] | 0.175 [0.000, 0.576] | 0.141 [0.114, 0.195] |
| ens +own+upstream | 0.445 [0.295, 0.556] | 0.732 [0.529, 0.830] | 0.460 [0.337, 0.557] |
| ens +all | 0.491 [0.333, 0.617] | 0.800 [0.686, 0.910] | 0.518 [0.428, 0.623] |

**strict onset (stage at cutoff < flood stage)**: 25 gauges; rows 29,574, positives 448 (base rate 0.0151); all-hours positives 2163.

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC | all-hours PR-AUC | seed sd (r50 / r20) |
|---|---|---|---|---|---|
| **baseline_ratio** | 0.000 [0.000, 0.049] | 0.000 [0.000, 0.074] | 0.037 [0.027, 0.052] | 0.621 [0.451, 0.725] | 0.000 / 0.000 |
| **nwm_flow_pctile** | 0.116 [0.000, 0.211] | 0.181 [0.093, 0.312] | 0.144 [0.082, 0.248] | 0.712 [0.529, 0.834] | 0.000 / 0.000 |
| **persist_stage_frac** | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.247] | 0.060 [0.051, 0.091] | 0.861 [0.770, 0.922] | 0.000 / 0.000 |
| **persist_extrap12h** | 0.067 [0.000, 0.187] | 0.464 [0.370, 0.575] | 0.203 [0.165, 0.259] | 0.767 [0.666, 0.850] | 0.000 / 0.000 |
| NWM only | 0.000 [0.000, 0.012] | 0.000 [0.000, 0.123] | 0.086 [0.065, 0.133] | 0.704 [0.565, 0.815] | 0.000 / 0.000 |
| +own stage | 0.311 [0.000, 0.447] | 0.686 [0.599, 0.783] | 0.308 [0.240, 0.407] | 0.897 [0.799, 0.948] | 0.042 / 0.011 |
| +upstream gauges | 0.000 [0.000, 0.048] | 0.305 [0.010, 0.598] | 0.143 [0.107, 0.247] | 0.728 [0.611, 0.834] | 0.000 / 0.064 |
| +rain | 0.000 [0.000, 0.008] | 0.000 [0.000, 0.537] | 0.120 [0.093, 0.185] | 0.699 [0.565, 0.811] | 0.000 / 0.000 |
| +own+upstream | 0.354 [0.000, 0.545] | 0.732 [0.615, 0.824] | 0.328 [0.259, 0.458] | 0.878 [0.763, 0.937] | 0.045 / 0.024 |
| +all | 0.254 [0.000, 0.584] | 0.844 [0.764, 0.917] | 0.347 [0.284, 0.452] | 0.859 [0.735, 0.930] | 0.180 / 0.005 |

Seed-averaged (ensemble) scores, same rows and paired draws:

| score | onset recall @50% prec | onset recall @20% prec | onset PR-AUC |
|---|---|---|---|
| ens NWM only | 0.002 [0.000, 0.030] | 0.009 [0.000, 0.351] | 0.092 [0.073, 0.132] |
| ens +own stage | 0.377 [0.258, 0.467] | 0.679 [0.588, 0.785] | 0.397 [0.331, 0.493] |
| ens +upstream gauges | 0.009 [0.000, 0.267] | 0.386 [0.009, 0.584] | 0.159 [0.117, 0.300] |
| ens +rain | 0.011 [0.000, 0.043] | 0.011 [0.000, 0.560] | 0.136 [0.114, 0.184] |
| ens +own+upstream | 0.435 [0.315, 0.563] | 0.728 [0.608, 0.825] | 0.466 [0.394, 0.577] |
| ens +all | 0.500 [0.382, 0.622] | 0.799 [0.722, 0.908] | 0.524 [0.456, 0.627] |

## Lead time

| eval set | population | score | onsets | detected @50% (median lead h) | detected @20% (median lead h) |
|---|---|---|---|---|---|
| VAL (held-out events, trained gauges) | onset only | NWM only | 0 | 0 (-) | 17 (7.000) |
| VAL (held-out events, trained gauges) | onset only | +own stage | 91 | 80 (7.500) | 86 (11.000) |
| VAL (held-out events, trained gauges) | onset only | +all | 91 | 81 (9.000) | 86 (12.000) |
| VAL (held-out events, trained gauges) | onset only | baseline_ratio | 91 | 1 (9.000) | 1 (10.000) |
| VAL (held-out events, trained gauges) | onset only | persist_stage_frac | 0 | 0 (-) | 47 (4.000) |
| VAL (held-out events, trained gauges) | onset only | persist_extrap12h | 0 | 0 (-) | 0 (-) |
| VAL (held-out events, trained gauges) | strict onset | NWM only | 0 | 0 (-) | 19 (8.000) |
| VAL (held-out events, trained gauges) | strict onset | +own stage | 91 | 81 (7.000) | 86 (11.000) |
| VAL (held-out events, trained gauges) | strict onset | +all | 91 | 81 (10.000) | 86 (12.000) |
| VAL (held-out events, trained gauges) | strict onset | baseline_ratio | 91 | 1 (9.000) | 1 (10.000) |
| VAL (held-out events, trained gauges) | strict onset | persist_stage_frac | 0 | 0 (-) | 49 (5.000) |
| VAL (held-out events, trained gauges) | strict onset | persist_extrap12h | 0 | 0 (-) | 0 (-) |
| UNSEEN gauges (non-Florence) | onset only | NWM only | 155 | 3 (2.000) | 18 (5.500) |
| UNSEEN gauges (non-Florence) | onset only | +own stage | 155 | 122 (7.000) | 136 (9.000) |
| UNSEEN gauges (non-Florence) | onset only | +all | 155 | 124 (7.000) | 136 (10.000) |
| UNSEEN gauges (non-Florence) | onset only | baseline_ratio | 155 | 6 (4.500) | 18 (5.000) |
| UNSEEN gauges (non-Florence) | onset only | persist_stage_frac | 155 | 0 (-) | 83 (2.000) |
| UNSEEN gauges (non-Florence) | onset only | persist_extrap12h | 155 | 0 (-) | 0 (-) |
| UNSEEN gauges (non-Florence) | strict onset | NWM only | 155 | 3 (2.000) | 18 (5.500) |
| UNSEEN gauges (non-Florence) | strict onset | +own stage | 155 | 122 (7.000) | 136 (9.000) |
| UNSEEN gauges (non-Florence) | strict onset | +all | 155 | 124 (7.000) | 136 (10.000) |
| UNSEEN gauges (non-Florence) | strict onset | baseline_ratio | 155 | 6 (4.500) | 17 (6.000) |
| UNSEEN gauges (non-Florence) | strict onset | persist_stage_frac | 0 | 0 (-) | 84 (2.000) |
| UNSEEN gauges (non-Florence) | strict onset | persist_extrap12h | 0 | 0 (-) | 0 (-) |
| TEST (Florence) | onset only | NWM only | 89 | 1 (4.000) | 29 (4.000) |
| TEST (Florence) | onset only | +own stage | 89 | 78 (5.000) | 88 (10.000) |
| TEST (Florence) | onset only | +all | 89 | 84 (7.000) | 89 (11.000) |
| TEST (Florence) | onset only | baseline_ratio | 0 | 0 (-) | 24 (4.000) |
| TEST (Florence) | onset only | persist_stage_frac | 89 | 0 (-) | 0 (-) |
| TEST (Florence) | onset only | persist_extrap12h | 89 | 9 (2.000) | 88 (5.000) |
| TEST (Florence) | strict onset | NWM only | 89 | 1 (4.000) | 27 (4.000) |
| TEST (Florence) | strict onset | +own stage | 89 | 79 (5.000) | 88 (10.000) |
| TEST (Florence) | strict onset | +all | 89 | 84 (7.000) | 89 (11.000) |
| TEST (Florence) | strict onset | baseline_ratio | 0 | 0 (-) | 23 (4.000) |
| TEST (Florence) | strict onset | persist_stage_frac | 0 | 0 (-) | 0 (-) |
| TEST (Florence) | strict onset | persist_extrap12h | 89 | 9 (2.000) | 88 (5.000) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | NWM only | 58 | 0 (-) | 1 (3.000) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | +own stage | 58 | 31 (3.000) | 40 (7.000) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | +all | 58 | 35 (6.000) | 40 (8.500) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | baseline_ratio | 58 | 1 (9.000) | 1 (10.000) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | persist_stage_frac | 58 | 0 (-) | 7 (3.000) |
| PILOT non-Florence (VAL+UNSEEN) | onset only | persist_extrap12h | 58 | 0 (-) | 0 (-) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | NWM only | 0 | 0 (-) | 1 (3.000) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | +own stage | 58 | 33 (4.000) | 40 (7.000) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | +all | 58 | 35 (6.000) | 40 (8.500) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | baseline_ratio | 58 | 1 (9.000) | 1 (10.000) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | persist_stage_frac | 0 | 0 (-) | 12 (1.500) |
| PILOT non-Florence (VAL+UNSEEN) | strict onset | persist_extrap12h | 0 | 0 (-) | 0 (-) |
| PILOT Florence (TEST) | onset only | NWM only | 36 | 1 (4.000) | 1 (4.000) |
| PILOT Florence (TEST) | onset only | +own stage | 36 | 32 (5.000) | 36 (8.000) |
| PILOT Florence (TEST) | onset only | +all | 36 | 33 (6.000) | 36 (10.500) |
| PILOT Florence (TEST) | onset only | baseline_ratio | 0 | 0 (-) | 0 (-) |
| PILOT Florence (TEST) | onset only | persist_stage_frac | 36 | 0 (-) | 0 (-) |
| PILOT Florence (TEST) | onset only | persist_extrap12h | 36 | 16 (1.500) | 36 (4.000) |
| PILOT Florence (TEST) | strict onset | NWM only | 36 | 1 (4.000) | 1 (4.000) |
| PILOT Florence (TEST) | strict onset | +own stage | 36 | 34 (5.000) | 36 (8.000) |
| PILOT Florence (TEST) | strict onset | +all | 36 | 33 (6.000) | 36 (11.000) |
| PILOT Florence (TEST) | strict onset | baseline_ratio | 0 | 0 (-) | 0 (-) |
| PILOT Florence (TEST) | strict onset | persist_stage_frac | 0 | 0 (-) | 0 (-) |
| PILOT Florence (TEST) | strict onset | persist_extrap12h | 36 | 16 (1.000) | 36 (4.000) |