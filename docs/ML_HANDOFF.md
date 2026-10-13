# ML handoff - FloodLens gauge nowcast (`ml_full_table_v2`)

For the ML teammate. Written 2026-10-12. Do not edit or push to anyone else's repo from this; copy the table and `src/ml_example_v2.py` into your own work. Every number below comes from `data/phase2/ml_example_v2_results.csv` (made by `src/ml_example_v2.py`, log `data/phase2/ml_example_v2.log`) unless another file is named.

## Read first
1. **This is a nowcast, not a forecast.** The v2 features include the gauge's own observed stage (up to one hour before the row time), upstream gauges' observed stage/discharge, and observed (Stage IV) rain over the catchment. A deployed system would need live feeds of all three. Nothing here forecasts rain or the NWM. The 12 h label horizon is the only "lead".
2. **Use `data/derived/ml_full_table_v2/` only. The v1 table `ml_full_table/` is superseded** (kept unmodified; v2 has all v1 columns plus 66 new ones). Neither table may be modified.
3. **Florence is the TEST set. Do not tune, select features, pick thresholds or choose a model on it.** Look at it once at the end.
4. **34 gauges are "unseen"** (`split == "unseen"`, about 15%, seed 42, stratified by HUC4 and pilot status): never in training, evaluated on non-Florence events. In the example run only **26 of the 34** have any evaluation row after the common-row filter (own stage and its 6 h extrapolation known at the cutoff); the other 8 contribute nothing.
5. **7-day buffer**: rows with `split == "buffer"` (the 7 days before and after the Florence window) are used for nothing, not for training, statistics or evaluation.
6. All statistics (percentile, flood-stage discharge, scalers, calibration) must come from `split == "trainval"` hours only. Missing values stay NaN; do not fill them.

## Table, split rules, labels
- Layout and columns: `reports/DATA_CARD.md` (v1 columns, labels, split rules) and `reports/DATA_CARD_v2.md` (66 new nowcast columns, timing convention). Partitioned by `usgs_id`: `ml_full_table_v2/usgs_id=*/part.parquet`, 236 gauges, hourly 2015-01-01..2023-01-31 UTC.
- Label: `exceed_next_12h` (1 if observed stage reaches the NWS minor flood stage in the next 12 h; NaN if hours are missing and none exceeds). Only official-stage gauges that passed the datum check have it.
- `splits.csv` (event level): `event_id -> split, cv_fold`. The table's row-level `split` / `cv_fold` columns follow it; `ml_example_v2.py` asserts they agree and that each event lies in one fold. `cv_fold` is assigned per `event_id` (storm event, or quiet stretch when `event_id < 0`), never per random hour. Folds 0-3 are for training/cross-validation; fold 4 is the validation set in the example; `test` = Florence.
- **Onset** = `is_exceed_now == False` (the gauge is not yet at flood stage in the current hour). Most positives are already-flooding hours, so judge any model on onset, not only on all hours. Because the features stop one hour earlier than `is_exceed_now`, "onset" still includes some recession rows; the example also reports a **strict onset** (stage at the cutoff < flood stage).

## Example script
`src/ml_example_v2.py` is self-contained (pandas, numpy, scikit-learn, pyarrow); no hardcoded paths.
```
python src/ml_example_v2.py <DATA_ROOT> [--out results.csv] [--boot 200] [--seeds 42 43 44]
# DATA_ROOT contains ml_full_table_v2/ and splits.csv; in this repo it is data/derived
```
It trains one HistGradientBoosting model (200 trees, learning rate 0.1, 31 leaves, no early stopping, **no tuning**) on all v2 feature groups (NWM + own stage + upstream + rain; 81 columns) using trainval folds 0-3, all positives plus a 10% negative subsample per seed, 3 seeds. The seed-averaged probability is the score. It scores validation (fold 4), unseen gauges and Florence on the same rows, and reports recall at 50% and 20% precision and PR-AUC with 95% cluster-bootstrap intervals (events; gauges for Florence), paired across scores.

Baselines, scored on the same rows with the same bootstrap draws:
- `persist_stage_frac` = stage at the cutoff / flood stage;
- `persist_extrap12h` = (stage + 12 h x 6 h rise rate) / flood stage;
- `calibrated_persistence` = logistic regression on those two columns, fit on the same training rows as the model;
- `calibrated_persistence_below_fs` = the same, fit only on training rows with stage < flood stage. **Added after the first calibrated variant looked weak at onset** (it is dominated by already-flooding hours); both are reported.

## Results of the example run (nothing tuned; Florence looked at once)
Train: 2,346,695 rows, 58,773 positives, 151 gauges. Evaluation rows 3,890,055. **Onset only**, recall at 50% / 20% precision and PR-AUC; `[ ]` = 95% CI.

| Eval set (onset positives, gauges) | Score | Recall @50% prec | Recall @20% prec | PR-AUC |
|---|---|---|---|---|
| **VAL fold 4** (2,407 onset positives, 151 gauges) | HGB seed-avg | **0.384** [0.085, 0.496] | 0.536 | 0.378 [0.265, 0.483] |
| | persist_stage_frac | 0.000 | 0.110 | 0.054 |
| | persist_extrap12h | 0.000 | 0.000 | 0.046 |
| | calibrated_persistence | 0.000 | 0.184 | 0.065 |
| | calibrated_persistence_below_fs | 0.000 | 0.000 | 0.064 |
| **UNSEEN gauges** (2,165, 26 gauges) | HGB seed-avg | **0.417** [0.300, 0.510] | 0.597 | 0.395 [0.313, 0.459] |
| | persist_stage_frac | 0.004 | 0.200 | 0.088 |
| | persist_extrap12h | 0.000 | 0.000 | 0.082 |
| | calibrated_persistence | 0.003 | 0.341 | 0.119 |
| | calibrated_persistence_below_fs | 0.000 | 0.462 | 0.121 |
| **TEST Florence** (1,362, 177 gauges) | HGB seed-avg | **0.504** [0.403, 0.592] | 0.710 | 0.467 [0.408, 0.528] |
| | persist_stage_frac | 0.005 | 0.053 | 0.059 |
| | persist_extrap12h | 0.001 | 0.488 | 0.165 |
| | calibrated_persistence | 0.005 | 0.183 | 0.110 |
| | calibrated_persistence_below_fs | 0.004 | 0.351 | 0.163 |

**Onset skill versus persistence: the model beats every persistence baseline at onset on all three sets, and the paired 95% intervals exclude zero.** Recall at 50% precision, model minus best baseline: VAL +0.384 [0.085, 0.496]; UNSEEN +0.412 [0.298, 0.507]; Florence +0.499 [0.400, 0.584]. At 20% precision the model beats the strongest baseline on each set (UNSEEN vs `calibrated_persistence_below_fs`: +0.135 [0.099, 0.182]; Florence vs `persist_extrap12h`: +0.222 [0.104, 0.320]). Strict onset gives the same picture (`ml_example_v2_results.csv`, `population` column), as do all hours (smaller gaps: Florence all-hours PR-AUC 0.965 vs 0.906 for the best baseline).

**Caveats that matter more than the headline:**
1. **The YES depends on seed-averaging.** Single-seed models have recall at 50% precision of **0.000 on VAL and UNSEEN** (and 0.000 / 0.371 / 0.283 on Florence for seeds 42/43/44): each single seed puts about a thousand held-out rows at probability exactly 1.0 that are mostly false alarms, so the precision never reaches 50%. Averaging three seeds breaks the ties. This was found in an earlier run (`reports/sample_model_v2.md`) and is a post-hoc choice, not a pre-specified one.
2. Recall at 50% precision on VAL has a wide interval (0.085-0.496).
3. **Operating points are chosen on the evaluation set itself**, an upper bound; a deployed threshold would be set on training data and could miss the target precision.
4. Much of the skill is the gauge's own recent stage; upstream gauges and rain add little that can be shown beyond it (`reports/sample_model_v2.md`).
5. Florence is one event (a 54-day chain with Michael). The unseen-gauge result rests on 26 gauges. 108 of 236 gauges have an upstream gauge.
6. Stage IV is the final QC'd archive; a live system would see preliminary rain with latency.

## Do / don't
- Do keep a gauge-clustered or event-clustered bootstrap; hours are heavily autocorrelated.
- Do report onset and strict onset next to all-hours; all-hours metrics mostly reward ranking already-flooding rows.
- Do not use `obs_stage_ft`, `obs_q_cfs` or the `exceed_next_*` columns as features (labels and observations).
- Do not use the `proxy_*` columns together with the primary label; they are a separate secondary label.
- Do not describe any output as a forecast, a probability of road closure, or as safe/unsafe for a place: gauge exceedance is not road closure.
