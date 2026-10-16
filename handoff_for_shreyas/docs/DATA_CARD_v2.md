# FloodLens Lifelines - Data card addendum: `ml_full_table_v2`

Same rows, split rules and old columns as `reports/DATA_CARD.md` (Florence = TEST, 7-day buffer, 34 unseen gauges, cv_fold by event_id, all statistics from trainval only). Partitioned by `usgs_id` in `data/derived/ml_full_table_v2/`. **66 new columns. These are NOWCAST features (they use observed stage), not forecast features.**

Timing: row time `t` = start of hour. New features use information available at clock time t: observed bins `<= t-1` (bin `t-1` covers [t-1, t)) and Stage IV hourly accumulations whose end time is `<= t`. This is one hour stricter than the v1 `is_exceed_now` (bin t). Missing stays NaN.

| group | columns | meaning |
|---|---|---|
| own stage (9) | `own_stage_ft`, `own_stage_chg_{1,3,6,12,24}h`, `own_stage_frac_fs`, `own_hrs_since_obs`, `own_extrap12h_frac` | stage at the cutoff, changes, stage / flood stage, hours since last observed bin, (stage + 12 h x 6 h-rise-rate) / flood stage |
| upstream gauges (50) | `has_upstream`, `n_upstream`, `up{1,2,3}_{dist_km, da_ratio, stage_ft, stage_frac_fs, q_cfs, hrs_since_obs, stage_chg_{1,3,6,12,24}h, q_chg_{1,3,6,12,24}h}` | nearest 1-3 upstream usable gauges (NLDI UT navigation, nearest by great-circle distance, not along-network); `da_ratio` = upstream / own drainage area; NaN when absent (108 of 236 gauges have >= 1) |
| catchment rain (7) | `rain_catch_{1,3,6,12,24,48,72}h` | Stage IV area-mean rain (mm) over the gauge's NLDI basin, accumulated over the window ending at t; NaN if any hour in the window is missing (108 missing hours in the study window: 2019-04, 2020-07) or the gauge has no basin (0208732534) |

Caveats: Stage IV is the final, quality-controlled archive (a real-time system would see the preliminary version); upstream `stage_frac_fs` uses the NWS flood stage only where the upstream gauge has one; the extrapolation baseline column is derived from stage only. Results and caveats: `reports/sample_model_v2.md`. Leakage tests: `data/derived/leakage_tests_v2.txt`.
