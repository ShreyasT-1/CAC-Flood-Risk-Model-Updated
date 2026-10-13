# FloodLens Lifelines - ML data pipeline (Steps 1-7)

Run from `src/` in order. Needs `USGS_API_KEY` in the environment (never printed). Python: pandas, numpy, pyarrow, xarray, zarr, s3fs, requests, geopandas, scikit-learn.
Every network step caches to `data/raw/` and resumes on rerun.

| Script | What it does | Main outputs |
|---|---|---|
| `common.py` | paths, USGS OGC client (pagination, 429 wait, X-Api-Key) | - |
| `01_gauges.py` | all NC USGS stream sites with continuous series, NWS flood stage (NWPS minor category), pilot flag (inside pilot county or NLDI downstream path crosses it), datum check vs NWPS crests | `data/derived/gauges_all.csv`, `datum_check_events.csv`, `step1_counts.json` |
| `02_crosswalk.py` | gauge -> NWM v3.0 `feature_id` (RouteLink `gage_id` carried in `chrtout.zarr`; NWPS `reachId` fallback), distance validation, relaxed datum rule | `gauge_crosswalk.csv`, `crosswalk_unmatched.csv` |
| `03_observed.py fetch` / `hourly` | yearly USGS pulls 2015-01-01..2023-01-31 -> UTC hourly (stage max, discharge mean), missing-fraction, drop >20% | `data/raw/usgs/`, `obs_hourly.parquet`, `obs_missing.csv` |
| `04_nwm.py` | lazy chunked read of NWM retrospective streamflow for the needed reaches | `data/raw/nwm/`, `nwm_hourly.parquet` |
| `05_table.py` | gauge-hour table, labels, storm events, proxy thresholds | `ml_full_table/`, `events.csv`, `proxy_thresholds.csv` |
| `06_splits.py` | test/buffer/unseen/trainval splits, CV folds, TRAIN-only pctile + Q_fs + baseline_ratio, leakage tests | adds columns to `ml_full_table/`, `splits.csv`, `holdout_gauges.csv`, `split_summary.csv`, `leakage_tests.txt` |
| `07_killtest.py` | Kill Test 1, no model | `kill_test_1.csv` |
| `08_report.py` | assembles `reports/ml_data_report.md` from the files above (needs no network) | `reports/ml_data_report.md`, `datum_exclusions.csv` |

Notes: `splits.csv` is event-level (event_id -> split/fold). The row-level assignment is the `split` and `cv_fold` columns of the table.
Order for a full rerun: 01, 02, `03 fetch` (hours; USGS quota 1000 req/h), `03 hourly`, 04 (~14 GB of S3 reads), 05, 06, 07, 08.

No model is trained or tuned anywhere.
The NWM retrospective v3.0 ends 2023-02-01, so the whole study window is 2015-01-01 .. 2023-01-31 23:00 UTC.


## v2: new information (observed stage, upstream gauges, observed rain) - nowcast, not forecast
Run after the steps above. Needs `eccodes` (`pip install eccodes`). Sources and URLs: `reports/new_features_sources.md`.

| Script | What it does | Main outputs |
|---|---|---|
| `10_nldi.py` | NLDI basin polygon + upstream (UT) NWIS sites per gauge; nearest 1-3 upstream usable gauges | `data/raw/nldi_basin/`, `nldi_ut/`, `data/derived/upstream_gauges.csv` |
| `11_stage4_catch.py` | NCAR GDEX d507005 Stage IV hourly rain (monthly tars via OSDF, GRIB1 -> 2020-07, GRIB2 from 2020-08) -> area-mean over each basin (fractional-area weights) | `data/derived/stage4_catch/YYYYMM.npz`, `stage4_weights.npz` |
| `12_build_v2.py` | adds own-stage, upstream-gauge and catchment-rain columns to every existing column | `data/derived/ml_full_table_v2/` |
| `14_leakage_v2.py` | truncation recompute for each new group, rain window/end-time checks, raw-GRIB re-derivation | `data/derived/leakage_tests_v2.txt` |
| `13_sample_model_v2.py` | 6 feature-set ablations x 3 seeds (HGB, fixed settings) + 4 baselines, cluster bootstrap, lead time | `sample_model_v2.csv`, `_lead.csv`, `_boots.pkl` |
| `16_ensemble_v2.py` | seed-averaged scores with the same bootstrap draws | `sample_model_v2_ens.csv` |
| `15_report_v2.py` | tables + paired-bootstrap verdict | `the appendix of reports/sample_model_v2.md`, `sample_model_v2_verdict.csv` |

Timing convention (stricter than the v1 table): row time t = start of hour; new features use only stage/discharge bins that ended by t (bin t-1 and earlier) and Stage IV accumulations that END at or before t. Nothing is filled; missing is NaN.
