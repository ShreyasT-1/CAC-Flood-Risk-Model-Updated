# FloodLens Lifelines - Data card

One row per **gauge-hour** for NC USGS stream gauges, 2015-01-01 00:00 to 2023-01-31 23:00 UTC (the NWM v3.0 retrospective ends 2023-02-01). 236 usable gauges, ~16.7M rows, partitioned by `usgs_id` in `data/derived/ml_full_table/` (parquet). Read it with `pd.read_parquet(path)` (the partition column comes back as a column).

## What we predict
Will the gauge's observed stage reach the **official NWS flood stage** (the "minor" category) within the next h hours? Only gauges with an official stage that passed a datum check have these labels (177 of 236). The other 59 gauges only have the *secondary* proxy label. Never mix the two.

## Columns
| group | columns | meaning |
|---|---|---|
| keys | `usgs_id`, `feature_id`, `time_utc`, `in_pilot`, `event_id` | `feature_id` = NWM reach. `in_pilot` = in or upstream of New Hanover / Brunswick / Pender. `event_id` > 0 = storm event, < 0 = quiet stretch between events (both are the unit for CV and bootstrap). |
| NWM features (past only) | `nwm_flow` (cfs), `nwm_chg_{1,3,6,12,24}h`, `nwm_lag_{1,3,6,12,24}h`, `stream_order` (-1 = unknown), `month` | Everything uses data at or before `time_utc`. NWM is the v3.0 *retrospective* (no data assimilation). |
| TRAIN-only features | `nwm_flow_pctile`, `q_fs_cfs`, `q_fs_quality`, `q_fs_source`, `baseline_ratio` | Percentile of `nwm_flow` within the reach's TRAIN hours; `q_fs_cfs` = discharge at flood stage from observed stage-discharge pairs; `baseline_ratio = nwm_flow / q_fs_cfs`. `q_fs_quality`: good (>=10 pairs within 0.25 ft of flood stage), ok (0.5 ft), poor (1 ft), none (NaN ratio). Unseen gauges have no TRAIN hours, see "Caveats". |
| observations (for labels/analysis, **not features**) | `obs_stage_ft` (hourly max), `obs_q_cfs` (hourly mean), `flood_stage_ft`, `is_exceed_now` | Do not feed observations at/after t into a model. |
| PRIMARY labels | `exceed_next_1h` ... `exceed_next_12h` | 1 if max observed stage in (t, t+h] >= flood stage; 0 if all h hours observed and below; **NaN if hours are missing and none exceeds** (we never fill). `exceed_next_12h` is the h=12 column. |
| SECONDARY label | `proxy_exceed_next_12h`, `proxy_q2_cfs` | 1 if observed discharge in the next 12 h >= the gauge's 2-year peak (median of pre-2015 USGS annual peaks, needs >= 10). All gauges with discharge; NaN otherwise. |
| splits | `split`, `cv_fold` | see below |

## Split rules (fixed before looking at any result)
1. **TEST** = the whole Florence event window (2018-09-13 to 2018-11-06 under our 5-day event rule; it chains Florence with Michael and recession), every gauge. The 7 days before and after are **buffer**: used for nothing.
2. **Unseen gauges** (`split == "unseen"`): 34 gauges (about 15%, seed 42, stratified by HUC4 basin and pilot status; at least half of pilot gauges stay in training). Never in training; evaluate them on non-Florence events.
3. **trainval**: remaining gauges, non-Florence hours. `cv_fold` (0-4) is assigned per `event_id`, so no event spans folds; nothing is split by random hour. Folds are balanced on primary positives.
4. All statistics (percentile, scaling, Q_fs) must come from `split == "trainval"` hours only. Test/buffer rows never feed any statistic.
5. Events: statewide exceedance hours chained with gaps < 5 days. See `events.csv` (90 events; Matthew 2016 and Florence 2018 named).

## Caveats you must know
- Hours with no observation have NaN observed values and NaN labels; they stay in the table.
- Most positive hours are *already-flooding* hours. Judge any model on **onset** (`is_exceed_now == False`) as well as all hours.
- `baseline_ratio` for unseen gauges uses a Q_fs from their own non-test observations (flagged `q_fs_source = own_nontest_hours`): optimistic for the "ungauged" claim.
- One gauge (0214244102, below a dam) has no NWM data; its NWM features are NaN.
- NWM here is a hindcast, not a forecast.

Full detail, counts, leakage tests and the Kill Test 1 results: `reports/ml_data_report.md`. Code and run order: `src/README.md`.
