# FloodLens V2 data pack (full) - built 2026-10-13 UTC

Verified rewrite of the first-draft pack. Everything below was produced by `v2_fetch.py` and checked by `check_leakage.py` in this folder; numbers in this README are computed from the files by `build_pack.py`.

## Contents
| File | What | Rows | Range |
|---|---|---|---|
| `obs_hourly_ext.parquet` | USGS hourly stage (`obs_stage_ft`, hourly MAX) and discharge (`obs_q_cfs`, hourly MEAN); same schema as `data/derived/obs_hourly.parquet`; label = hour START (UTC) | 5,380,724 (166 gauges x 32,414 h) | 2023-02-01 00:00 .. 2026-10-13 13:00 UTC |
| `obs_ext_coverage.csv` | per-gauge hours / % with data, first/last valid hour, share of provisional values | 166 | |
| `rain_fcst.parquet` | archived precipitation FORECASTS, mm per hour; columns `time_utc, usgs_id, model, precip_prev_day1, precip_prev_day2, precip_prev_day3`; `time_utc` = START of the accumulation hour (see rules); models `gfs_global`, `ncep_hrrr_conus` | 7,944,262 | 2024-01-19 11:00 .. 2026-10-12 22:00 UTC |
| `rain_points.csv` | requested gauge point vs the model grid cell Open-Meteo actually returned | 166 | |
| `rain_coverage.csv` | per model and gauge: rows, first/last, non-null counts per lead day | | |
| `upstream_pair_lags.csv` | (unchanged input) empirical upstream lag per pair, `usable` flag | 245 | |
| `obs_coverage_2015_2023.csv` | (unchanged input) coverage of the existing 2015-2023 file | | |
| `v2_fetch.py`, `check_leakage.py`, `build_pack.py`, `common.py` (from `src/`), `03_observed.py` (from `src/`, reference for the aggregation) | scripts | | |

Gauges: 166 = 108 targets (every `usgs_id` in `upstream_pair_lags.csv`) + 58 extra usable upstream gauges; all 166 are in `gauge_crosswalk.csv` and in the 2015-2023 file.

## Sources and licences
- **USGS** National Water Information System, OGC API `https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous` (`/v0/` answers too; the repo uses `/v1/`), parameters `00065` stage and `00060` discharge, 15-minute values aggregated to UTC hours. U.S. Government data, public domain; please credit USGS. **Values after the last annual approval are Provisional and can change** (share per gauge in `obs_ext_coverage.csv`; median provisional share of discharge 0.07). API limits seen: 1,000 requests/hour with an API key; a query window longer than 1,100 days is rejected (HTTP 400).
- **Open-Meteo Previous-Runs API** `https://previous-runs-api.open-meteo.com/v1/forecast` (queried 2026-10-13). Free tier: non-commercial use only, 600 calls/min, 5,000/h, 10,000/day (multi-year multi-location requests are weighted; the fetch hit per-minute and hourly waits and finished). Data CC BY 4.0: **attribute "Weather data by Open-Meteo.com"** and indicate modifications (we relabel timestamps and convert to long format). Commercial use needs a paid Open-Meteo licence. The underlying models are NOAA NCEP GFS and HRRR (U.S. Government work).

## Rules (leakage) - enforced by `check_leakage.py`
1. Time labels are hour STARTS. Open-Meteo reports precipitation as the sum of the PRECEDING hour (timestamp = end of interval); `v2_fetch.py` shifts it back one hour so `time_utc` in `rain_fcst.parquet` matches the obs convention (obs bin `h` covers [h, h+1)).
2. Rain features: only the `precip_prev_dayN` forecast columns. `precip_prev_dayN` for valid hour v is the value forecast N days before v, so it was issued at least N*24 h before v (exact model cycle not published; N*24 h is the safe bound). A prediction at time t may use it only if v - N*24 h <= t. The plain `precipitation` series of the same API (non-null back to 2021) is a best-estimate/analysis-like series and is **never** used or exported.
3. Upstream features: only pairs with `usable=True`; the value used at t must come from an hourly bin that was complete and at least `best_lag_h` old: `bin_label + 1 h + ceil(best_lag_h) <= t` (the draft's lag column is called `best_lag_h` in the file).
4. `python data/v2/check_leakage.py` checks the delivered files and self-tests the validators; `--features ledger.parquet` validates a feature-use ledger (columns `pred_time_utc`, `rain_valid_time_utc`, `rain_lead_day`, `usgs_id`, `up_id`, `up_obs_time_utc`, optional `obs_time_utc`) and exits 1 on any violation.

## Coverage
**Observations (2023-02-01 00:00 .. 2026-10-13 13:00, 32,414 hours):** discharge for 155 of 166 gauges (median 99.3% of hours, min 0.0%), stage for 166 gauges (median 99.9%, min 75.7%).
- Gauges with no discharge series (`has_q` false in the crosswalk): 11, all of them targets. In addition 4 gauges that the crosswalk marks `has_q` true returned **no discharge at all** from the API (['02081054', '02087570', '02092554', '02108566']; the 2015-2023 file has none for them either), so the crosswalk `has_q` flag is wrong for these; they have stage only. Gauges with no stage series: 0. Gauges with no data at all in the window: 0 [].
- Discharge below 80% coverage: 8 gauges [('02081054', 0.0), ('02087570', 0.0), ('02092554', 0.0), ('02108566', 0.0), ('0208524975', 72.6), ('0210166029', 73.7), ('0345577330', 75.7), ('0214244102', 79.4)]. Stage below 80%: 1 gauges [('0345577330', 75.7)].
- Gauges with a gap of more than 30 consecutive days in their main series: 10 [('02081054', 32414), ('02084000', 3193), ('0208524975', 6676), ('0208675010', 2279), ('02087570', 32414), ('02092554', 32414), ('0210166029', 1319), ('02108566', 32414), ('0214244102', 6680), ('0345577330', 7866)].
- The current (incomplete) hour is excluded. No gauge was dropped for missing data (unlike `obs_hourly.parquet`, which dropped gauges with >20% missing key variable); filter with `obs_ext_coverage.csv`.
- There is **no overlap** between `obs_hourly.parquet` (ends 2023-01-31 23:00) and `obs_hourly_ext.parquet` (starts 2023-02-01 00:00); concatenating gives one series per gauge, with the same aggregation (stage MAX, Q MEAN).

**Rain forecasts:** 166 gauge points, requested at the crosswalk lat/lon. Per model: rows / gauges / first / last / non-null day1 / day2 / day3:
                    rows  gauges                     first                      last       d1       d2       d3
model                                                                                                          
gfs_global       3974040     166 2024-01-19 11:00:00+00:00 2026-10-12 22:00:00+00:00  3974040  3970056  3966072
ncep_hrrr_conus  3970222     166 2024-01-19 17:00:00+00:00 2026-10-12 22:00:00+00:00  3970222        0        0
- Archive start: lead-day precipitation is non-null only from **2024-01-19 11:00 UTC** (probed 2026-10-13: first non-null 2024-01-19). The "GFS archive from ~2021-03" in the first draft is true for temperature only, **not for precipitation**.
- HRRR provides lead day 1 only (the model horizon is 48 h): `precip_prev_day2/3` are NaN for `ncep_hrrr_conus` (0 non-null values). `gfs_global` has days 1-3. Open-Meteo's `gfs_seamless` is not used: its day 1 is HRRR and day 2+ is GFS (a mixture).
- Completeness: gfs_global day-1 non-null hours per gauge, min / median / max 23,940 / 23,940 / 23,940 of 23,940 expected hours in 2024-01-19 11:00..2026-10-12 22:00; HRRR day-1 23,917 / 23,917 / 23,917.
- Missing from rain: no gauge missing.
- Resolution: the returned grid cell is a median 4.6 km (max 7.9 km) from the gauge point (GFS is ~0.11-0.25 deg; HRRR 3 km). This is a point value, not a basin average, and is **coarse for small catchments** (and misses convective cells). Gauge-point precipitation is a rough proxy for catchment rain.
- Alternative if point data is too coarse: NWM `forcing_medium_range` / `forcing_short_range` on GCS (`gs://national-water-model`, 1 km CONUS grids, available from at least 2021-04 on GCS). Measured file sizes (HEAD requests, 2026-10-13): short-range forcing ~145 MB per (cycle, lead), medium-range ~170 MB. Short range only reaches 18 h, so lead days 1-3 would need medium range: roughly 72 hourly leads x 170 MB = ~12 GB per cycle, i.e. ~12 TB for one cycle per day over the 997 days of this window (whole-file reads; I did not verify every lead exists hourly). **Not downloaded.** Cheaper options to discuss: GFS/HRRR GRIB2 byte-range subsets from the NOAA AWS open-data buckets (small per-field reads), or basin-averaging Open-Meteo over several points per basin.

**Overlap of observations and rain forecasts** (hours with a gauge value AND a gfs_global day-1 forecast): 3,945,942 gauge-hours; per target gauge min / median / max 16,089 / 23,923 / 23,940 hours (window 2024-01-19 11:00 .. 2026-10-12 22:00, ~997 days). **The 2015-2023 observation file overlaps the rain forecasts by 0 hours**: rain-forecast features can only be trained and tested on 2024-01-19 .. 2026-10-12, so anything in the existing 2015-2023 table (including the Florence 2018 test event) has no rain-forecast feature at all.

## Known gaps / things to be blunt about
- Rain-forecast history is only ~2.7 years and contains no Florence-scale event unless 2024-2026 produced one; check the event count in this window before promising any rain-skill result.
- Point rain at a 4-8 km grid, GFS lead-day values are model forecasts with the usual displacement errors; HRRR day-1 only.
- Provisional USGS data after the last approval date may be revised; a model trained on provisional values may shift when they are approved.
- `best_lag_h` is a correlation estimate (3 h resolution), and 125 of 245 upstream pairs are not usable (`usable=False`) and must not be used.
- Rain-forecast issue times are bounded (N*24 h before valid), not exact.
- Not run / not done: NWM forcing download (needs your decision), HAND/terrain, any model training.
