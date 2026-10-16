"""Builds data/v2/README.md (numbers computed from the files, none typed) and data/FloodLens_V2_data_full.zip. Run after v2_fetch.py obs/hourly/rain and check_leakage.py pass.
Usage (repo root): python data/v2/build_pack.py"""
import sys, zipfile, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; V2 = ROOT / "data/v2"
O = pd.read_parquet(V2 / "obs_hourly_ext.parquet"); O0 = pd.read_parquet(ROOT / "data/derived/obs_hourly.parquet", columns=["usgs_id", "time_utc"]); R = pd.read_parquet(V2 / "rain_fcst.parquet")
C = pd.read_csv(V2 / "obs_ext_coverage.csv", dtype={"usgs_id": str}); L = pd.read_csv(V2 / "upstream_pair_lags.csv", dtype={"usgs_id": str, "up_id": str}); cw = pd.read_csv(ROOT / "data/derived/gauge_crosswalk.csv", dtype={"usgs_id": str})
ids = set(C.usgs_id); tg = set(L.usgs_id); up = set(L[L.usable].up_id)
# obs coverage
nq = int(C.has_q.sum()); ns = int(C.has_stage.sum()); t0, t1 = O.time_utc.min(), O.time_utc.max(); nh = C.hours.iloc[0]
lowq = C[C.has_q & (C.q_pct < 80)].sort_values("q_pct"); lows = C[C.has_stage & (C.stage_pct < 80)].sort_values("stage_pct"); noq = C[~C.has_q]; nos = C[~C.has_stage]
allnan = C[(C.q_hours == 0) & (C.stage_hours == 0)]
# gaps: longest run of missing hours for gauges with data (discharge, else stage)
def longest_gap(s):
    m = s.isna().values; best = cur = 0
    for x in m:
        cur = cur + 1 if x else 0; best = max(best, cur)
    return best
P = O.pivot(index="time_utc", columns="usgs_id", values="obs_q_cfs"); S = O.pivot(index="time_utc", columns="usgs_id", values="obs_stage_ft")
gap = pd.Series({u: longest_gap(P[u] if C.set_index("usgs_id").loc[u, "has_q"] else S[u]) for u in P.columns}); gaps_big = gap[gap > 24 * 30]
# rain
rc = R.groupby("model").agg(rows=("usgs_id", "size"), gauges=("usgs_id", "nunique"), first=("time_utc", "min"), last=("time_utc", "max"), d1=("precip_prev_day1", "count"), d2=("precip_prev_day2", "count"), d3=("precip_prev_day3", "count"))
r1 = R[R.model == "gfs_global"].dropna(subset=["precip_prev_day1"]); rfirst = r1.time_utc.min(); rlast = r1.time_utc.max(); exp_h = int((rlast - rfirst) / pd.Timedelta(hours=1)) + 1
rg = R[R.model == "gfs_global"].groupby("usgs_id").precip_prev_day1.count(); rh = R[R.model == "ncep_hrrr_conus"].groupby("usgs_id").precip_prev_day1.count()
pts = pd.read_csv(V2 / "rain_points.csv", dtype={"usgs_id": str}); km = np.hypot((pts.req_lat - pts.grid_lat) * 111.0, (pts.req_lon - pts.grid_lon) * 111.0 * np.cos(np.radians(pts.req_lat)))
missing_rain = sorted(ids - set(R.usgs_id))
# overlap obs x rain (per gauge, hours with a discharge-or-stage value AND a gfs day-1 forecast)
a = O.dropna(subset=["obs_q_cfs", "obs_stage_ft"], how="all").set_index(["usgs_id", "time_utc"]).index; b = r1.set_index(["usgs_id", "time_utc"]).index; both = a.intersection(b)
ov = pd.Series(1, index=both).groupby(level=0).size(); old_ov = int((O0.time_utc >= rfirst).sum())
tg_ov = ov.reindex(sorted(tg)).fillna(0); mx = lambda s: f"{int(s.min()):,} / {int(s.median()):,} / {int(s.max()):,}"
F = lambda t: pd.Timestamp(t).strftime("%Y-%m-%d %H:%M")
txt = f"""# FloodLens V2 data pack (full) - built {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')} UTC

Verified rewrite of the first-draft pack. Everything below was produced by `v2_fetch.py` and checked by `check_leakage.py` in this folder; numbers in this README are computed from the files by `build_pack.py`.

## Contents
| File | What | Rows | Range |
|---|---|---|---|
| `obs_hourly_ext.parquet` | USGS hourly stage (`obs_stage_ft`, hourly MAX) and discharge (`obs_q_cfs`, hourly MEAN); same schema as `data/derived/obs_hourly.parquet`; label = hour START (UTC) | {len(O):,} ({len(ids)} gauges x {nh:,} h) | {F(t0)} .. {F(t1)} UTC |
| `obs_ext_coverage.csv` | per-gauge hours / % with data, first/last valid hour, share of provisional values | {len(C)} | |
| `rain_fcst.parquet` | archived precipitation FORECASTS, mm per hour; columns `time_utc, usgs_id, model, precip_prev_day1, precip_prev_day2, precip_prev_day3`; `time_utc` = START of the accumulation hour (see rules); models `gfs_global`, `ncep_hrrr_conus` | {len(R):,} | {F(R.time_utc.min())} .. {F(R.time_utc.max())} UTC |
| `rain_points.csv` | requested gauge point vs the model grid cell Open-Meteo actually returned | {len(pts)} | |
| `rain_coverage.csv` | per model and gauge: rows, first/last, non-null counts per lead day | | |
| `upstream_pair_lags.csv` | (unchanged input) empirical upstream lag per pair, `usable` flag | {len(L)} | |
| `obs_coverage_2015_2023.csv` | (unchanged input) coverage of the existing 2015-2023 file | | |
| `v2_fetch.py`, `check_leakage.py`, `build_pack.py`, `common.py` (from `src/`), `03_observed.py` (from `src/`, reference for the aggregation) | scripts | | |

Gauges: {len(ids)} = {len(tg)} targets (every `usgs_id` in `upstream_pair_lags.csv`) + {len(up - tg)} extra usable upstream gauges; all {len(ids)} are in `gauge_crosswalk.csv` and in the 2015-2023 file.

## Sources and licences
- **USGS** National Water Information System, OGC API `https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous` (`/v0/` answers too; the repo uses `/v1/`), parameters `00065` stage and `00060` discharge, 15-minute values aggregated to UTC hours. U.S. Government data, public domain; please credit USGS. **Values after the last annual approval are Provisional and can change** (share per gauge in `obs_ext_coverage.csv`; median provisional share of discharge {C.q_provisional_share.median():.2f}). API limits seen: 1,000 requests/hour with an API key; a query window longer than 1,100 days is rejected (HTTP 400).
- **Open-Meteo Previous-Runs API** `https://previous-runs-api.open-meteo.com/v1/forecast` (queried 2026-10-13). Free tier: non-commercial use only, 600 calls/min, 5,000/h, 10,000/day (multi-year multi-location requests are weighted; the fetch hit per-minute and hourly waits and finished). Data CC BY 4.0: **attribute "Weather data by Open-Meteo.com"** and indicate modifications (we relabel timestamps and convert to long format). Commercial use needs a paid Open-Meteo licence. The underlying models are NOAA NCEP GFS and HRRR (U.S. Government work).

## Rules (leakage) - enforced by `check_leakage.py`
1. Time labels are hour STARTS. Open-Meteo reports precipitation as the sum of the PRECEDING hour (timestamp = end of interval); `v2_fetch.py` shifts it back one hour so `time_utc` in `rain_fcst.parquet` matches the obs convention (obs bin `h` covers [h, h+1)).
2. Rain features: only the `precip_prev_dayN` forecast columns. `precip_prev_dayN` for valid hour v is the value forecast N days before v, so it was issued at least N*24 h before v (exact model cycle not published; N*24 h is the safe bound). A prediction at time t may use it only if v - N*24 h <= t. The plain `precipitation` series of the same API (non-null back to 2021) is a best-estimate/analysis-like series and is **never** used or exported.
3. Upstream features: only pairs with `usable=True`; the value used at t must come from an hourly bin that was complete and at least `best_lag_h` old: `bin_label + 1 h + ceil(best_lag_h) <= t` (the draft's lag column is called `best_lag_h` in the file).
4. `python data/v2/check_leakage.py` checks the delivered files and self-tests the validators; `--features ledger.parquet` validates a feature-use ledger (columns `pred_time_utc`, `rain_valid_time_utc`, `rain_lead_day`, `usgs_id`, `up_id`, `up_obs_time_utc`, optional `obs_time_utc`) and exits 1 on any violation.

## Coverage
**Observations ({F(t0)} .. {F(t1)}, {nh:,} hours):** discharge for {nq} of {len(C)} gauges (median {C[C.has_q].q_pct.median():.1f}% of hours, min {C[C.has_q].q_pct.min():.1f}%), stage for {ns} gauges (median {C[C.has_stage].stage_pct.median():.1f}%, min {C[C.has_stage].stage_pct.min():.1f}%).
- Gauges with no discharge series (`has_q` false in the crosswalk): {len(noq)}, all of them targets. In addition {len(C[C.has_q & (C.q_hours == 0)])} gauges that the crosswalk marks `has_q` true returned **no discharge at all** from the API ({list(C[C.has_q & (C.q_hours == 0)].usgs_id)}; the 2015-2023 file has none for them either), so the crosswalk `has_q` flag is wrong for these; they have stage only. Gauges with no stage series: {len(nos)}. Gauges with no data at all in the window: {len(allnan)} {list(allnan.usgs_id)[:10]}.
- Discharge below 80% coverage: {len(lowq)} gauges {list(zip(lowq.usgs_id, lowq.q_pct.round(1)))[:12]}. Stage below 80%: {len(lows)} gauges {list(zip(lows.usgs_id, lows.stage_pct.round(1)))[:12]}.
- Gauges with a gap of more than 30 consecutive days in their main series: {len(gaps_big)} {[(i, int(v)) for i, v in gaps_big.items()][:12]}.
- The current (incomplete) hour is excluded. No gauge was dropped for missing data (unlike `obs_hourly.parquet`, which dropped gauges with >20% missing key variable); filter with `obs_ext_coverage.csv`.
- There is **no overlap** between `obs_hourly.parquet` (ends 2023-01-31 23:00) and `obs_hourly_ext.parquet` (starts 2023-02-01 00:00); concatenating gives one series per gauge, with the same aggregation (stage MAX, Q MEAN).

**Rain forecasts:** {len(pts)} gauge points, requested at the crosswalk lat/lon. Per model: rows / gauges / first / last / non-null day1 / day2 / day3:
{rc.to_string()}
- Archive start: lead-day precipitation is non-null only from **{F(rfirst)} UTC** (probed 2026-10-13: first non-null 2024-01-19). The "GFS archive from ~2021-03" in the first draft is true for temperature only, **not for precipitation**.
- HRRR provides lead day 1 only (the model horizon is 48 h): `precip_prev_day2/3` are NaN for `ncep_hrrr_conus` ({int(rc.loc['ncep_hrrr_conus','d2'])} non-null values). `gfs_global` has days 1-3. Open-Meteo's `gfs_seamless` is not used: its day 1 is HRRR and day 2+ is GFS (a mixture).
- Completeness: gfs_global day-1 non-null hours per gauge, min / median / max {mx(rg)} of {exp_h:,} expected hours in {F(rfirst)}..{F(rlast)}; HRRR day-1 {mx(rh)}.
- Missing from rain: {missing_rain if missing_rain else 'no gauge missing'}.
- Resolution: the returned grid cell is a median {km.median():.1f} km (max {km.max():.1f} km) from the gauge point (GFS is ~0.11-0.25 deg; HRRR 3 km). This is a point value, not a basin average, and is **coarse for small catchments** (and misses convective cells). Gauge-point precipitation is a rough proxy for catchment rain.
- Alternative if point data is too coarse: NWM `forcing_medium_range` / `forcing_short_range` on GCS (`gs://national-water-model`, 1 km CONUS grids, available from at least 2021-04 on GCS). Measured file sizes (HEAD requests, 2026-10-13): short-range forcing ~145 MB per (cycle, lead), medium-range ~170 MB. Short range only reaches 18 h, so lead days 1-3 would need medium range: roughly 72 hourly leads x 170 MB = ~12 GB per cycle, i.e. ~12 TB for one cycle per day over the {int((rlast - rfirst).days)} days of this window (whole-file reads; I did not verify every lead exists hourly). **Not downloaded.** Cheaper options to discuss: GFS/HRRR GRIB2 byte-range subsets from the NOAA AWS open-data buckets (small per-field reads), or basin-averaging Open-Meteo over several points per basin.

**Overlap of observations and rain forecasts** (hours with a gauge value AND a gfs_global day-1 forecast): {int(both.size):,} gauge-hours; per target gauge min / median / max {mx(tg_ov)} hours (window {F(rfirst)} .. {F(min(t1, rlast))}, ~{int((min(t1, rlast) - rfirst).days)} days). **The 2015-2023 observation file overlaps the rain forecasts by {old_ov} hours**: rain-forecast features can only be trained and tested on 2024-01-19 .. 2026-10-12, so anything in the existing 2015-2023 table (including the Florence 2018 test event) has no rain-forecast feature at all.

## Known gaps / things to be blunt about
- Rain-forecast history is only ~2.7 years and contains no Florence-scale event unless 2024-2026 produced one; check the event count in this window before promising any rain-skill result.
- Point rain at a 4-8 km grid, GFS lead-day values are model forecasts with the usual displacement errors; HRRR day-1 only.
- Provisional USGS data after the last approval date may be revised; a model trained on provisional values may shift when they are approved.
- `best_lag_h` is a correlation estimate (3 h resolution), and {int((~L.usable).sum())} of {len(L)} upstream pairs are not usable (`usable=False`) and must not be used.
- Rain-forecast issue times are bounded (N*24 h before valid), not exact.
- Not run / not done: NWM forcing download (needs your decision), HAND/terrain, any model training.
"""
(V2 / "README.md").write_text(txt, encoding="utf-8"); print(txt[:200])
files = [V2 / f for f in ("README.md", "obs_hourly_ext.parquet", "obs_ext_coverage.csv", "rain_fcst.parquet", "rain_points.csv", "rain_coverage.csv", "upstream_pair_lags.csv", "obs_coverage_2015_2023.csv", "v2_fetch.py", "check_leakage.py", "build_pack.py")] + [ROOT / "src/common.py", ROOT / "src/03_observed.py"]
z = ROOT / "data/FloodLens_V2_data_full.zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in files: zf.write(f, f.name)
print("wrote", z, round(z.stat().st_size / 1e6, 1), "MB"); [print(f"  {f.name}: {f.stat().st_size / 1e6:.2f} MB") for f in files]
