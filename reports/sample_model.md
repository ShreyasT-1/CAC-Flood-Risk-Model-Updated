# Sample model - is ML worth it on this data?

One untuned HistGradientBoosting model (200 trees, fixed settings, seed 42) on the 15 NWM-only features (`nwm_flow`, changes, lags, `nwm_flow_pctile`, `baseline_ratio`, stream order, month) predicting `exceed_next_12h` at official-stage gauges. Trained on trainval folds 0-3 (902k rows, 58.8k positives, negatives subsampled 10%). Scored on events/gauges it never saw, against the two no-model Kill Test 1 scores on the *same rows*. Script: `src/09_sample_model.py`; numbers: `data/derived/sample_model.csv`.

PR-AUC (base rate in brackets; higher is better; 95% CI by event cluster, gauge cluster for Florence):

| eval set | population | model | baseline_ratio | nwm_flow_pctile |
|---|---|---|---|---|
| VAL: held-out events, 83 trained gauges (0.0112) | all hours | 0.38 | **0.53** | 0.21 |
| | onset only (0.0018) | 0.029 | 0.028 | **0.040** |
| UNSEEN gauges, non-Florence, 17 gauges (0.0075) | all hours | 0.30 | **0.57** | 0.27 |
| | onset only (0.0017) | 0.033 | **0.072** | 0.046 |
| TEST: Florence, 100 gauges (0.051) | all hours | **0.72** | 0.70 | 0.56 |
| | onset only (0.010) | 0.166 | 0.148 | **0.231** |

Recall at 50% precision, onset only: **0.00 for the model on all three sets** (baselines: 0.00-0.15).

## Verdict
- **The model does not beat the one-line baseline** (`nwm_flow / flood-stage discharge`). It wins only on Florence all-hours, by 0.02 (inside the noise: the confidence intervals overlap heavily), and loses clearly on held-out events and unseen gauges.
- **At onset, nothing here is usable**: every score, model included, is ~15-50x base rate but with absolute PR-AUC of 0.03-0.23 and essentially no recall at 50% precision. The "pass" in Kill Test 1 is mostly the model ranking already-flooding hours.
- **Why**: the only inputs are the NWM retrospective flow and its recent history. That is a hindcast with no assimilation and no rainfall forecast, so it carries little information about *when a gauge will cross flood stage that the flood-stage ratio doesn't already have*.

## What this means for time spent
- Don't spend time on tuning or bigger models with these features; the signal is the ratio, and a model adds nothing.
- Gains would have to come from new information: recent observed stage/discharge at the gauge (strong, but it makes this a nowcast), upstream gauge observations (routing lead time), and rainfall/QPF forecasts. Predicting *onset* needs those.
- Evaluate on onset hours and report recall at fixed precision, not PR-AUC vs base rate.

Caveats: one seed, no hyperparameter search, 17 unseen gauges and one test event. A single run, so small gaps are not evidence either way.
