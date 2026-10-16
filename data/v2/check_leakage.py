"""FloodLens V2 leakage + integrity checks. Exit code 1 and a list of failures if anything is wrong.
  python data/v2/check_leakage.py                          # checks the delivered data files + self-tests the validators
  python data/v2/check_leakage.py --features ledger.parquet   # also validates a feature-use ledger (csv or parquet), one row per feature value used for a prediction

RULES (the contract any feature builder must satisfy)
 Time labels: every time_utc is the hour START of the interval it describes (obs: [h, h+1); rain: precipitation accumulated over [h, h+1)). A prediction at pred_time_utc = t may use only what is known at t.
 R1 Rain: only archived FORECAST rain (rain_fcst.parquet) may be a rain feature; never observed/analysis rain. precip_prev_dayN for valid hour v was issued at least N*24 h before v (Open-Meteo
    'previous_dayN' = run issued N days before valid time; the exact cycle is not published, so N*24 h is the safe upper bound on issue time). Ledger columns: rain_valid_time_utc, rain_lead_day (1-3).
    VIOLATION if rain_valid_time_utc - rain_lead_day*24h > pred_time_utc (i.e. the forecast could not have been issued yet).
 R2 Upstream obs: only pairs with usable=True in upstream_pair_lags.csv; the value used at pred_time t must come from an hourly bin that was complete and at least best_lag_h older:
    up_obs_time_utc + 1h + ceil(best_lag_h) <= t   (stricter than 't - lag_h or earlier' by the 1 h bin length, the repo's convention that only finished bins are used).
    Ledger columns: usgs_id, up_id, up_obs_time_utc.
 R3 Own-gauge / any other observed feature (optional ledger column obs_time_utc): obs_time_utc + 1h <= pred_time_utc."""
import sys, pathlib
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[2]; V2 = ROOT / "data/v2"; H = pd.Timedelta(hours=1)
bad = []
def chk(ok, msg):
    if not ok: bad.append(msg)

def lag_table():
    L = pd.read_csv(V2 / "upstream_pair_lags.csv", dtype={"usgs_id": str, "up_id": str}); return L.set_index(["usgs_id", "up_id"])

def validate_ledger(F, lags=None):
    """returns a list of violation strings for a feature-use ledger DataFrame"""
    v = []; t = pd.to_datetime(F.pred_time_utc, utc=True)
    if "rain_valid_time_utc" in F:
        m = F.rain_valid_time_utc.notna(); rv = pd.to_datetime(F.rain_valid_time_utc, utc=True); N = F.rain_lead_day
        if (m & ~N.isin([1, 2, 3])).any(): v.append("rain_lead_day must be 1, 2 or 3 where a rain feature is used")
        issue_latest = rv - pd.to_timedelta(N.fillna(0) * 24, unit="h"); n = int((m & (issue_latest > t)).sum())
        if n: v.append(f"R1: {n} rain feature uses with forecast issue time after the prediction time (rain_valid_time - lead*24h > pred_time)")
    if "up_obs_time_utc" in F:
        m = F.up_obs_time_utc.notna(); lags = lags if lags is not None else lag_table(); key = list(zip(F.usgs_id, F.up_id))
        ok_pair = np.array([k in lags.index for k in key]); use = np.array([bool(lags.usable.get(k, False)) if k in lags.index else False for k in key])
        n = int((m & ~pd.Series(use, index=F.index)).sum())
        if n: v.append(f"R2: {n} upstream feature uses from pairs that are not usable=True (or not in upstream_pair_lags.csv)")
        lag = pd.Series([np.ceil(lags.best_lag_h.get(k, np.nan)) if k in lags.index else np.nan for k in key], index=F.index)
        late = pd.to_datetime(F.up_obs_time_utc, utc=True) + H + pd.to_timedelta(lag.fillna(0), unit="h") > t; n = int((m & late).sum())
        if n: v.append(f"R2: {n} upstream feature uses newer than pred_time - lag_h (obs_time + 1h + ceil(lag_h) > pred_time)")
    if "obs_time_utc" in F:
        m = F.obs_time_utc.notna(); n = int((m & (pd.to_datetime(F.obs_time_utc, utc=True) + H > t)).sum())
        if n: v.append(f"R3: {n} observed feature uses from a bin not yet complete at pred_time")
    return v

def self_test():
    t = pd.Timestamp("2025-06-10 12:00", tz="UTC"); L = pd.DataFrame({"best_lag_h": [8.0, 3.0], "usable": [True, False]}, index=pd.MultiIndex.from_tuples([("A", "B"), ("A", "C")], names=["usgs_id", "up_id"]))
    ok = pd.DataFrame(dict(pred_time_utc=[t, t], rain_valid_time_utc=[t + pd.Timedelta(hours=24), t + pd.Timedelta(hours=72)], rain_lead_day=[1, 3], usgs_id="A", up_id="B", up_obs_time_utc=[t - pd.Timedelta(hours=9), t - pd.Timedelta(hours=20)]))
    chk(validate_ledger(ok, L) == [], "self-test: a compliant ledger was flagged")
    bad_rain = ok.assign(rain_valid_time_utc=[t + pd.Timedelta(hours=25), t + pd.Timedelta(hours=72)]); chk(any("R1" in x for x in validate_ledger(bad_rain, L)), "self-test: late-issued rain not flagged")
    bad_up = ok.assign(up_obs_time_utc=[t - pd.Timedelta(hours=8), t - pd.Timedelta(hours=20)]); chk(any("R2" in x for x in validate_ledger(bad_up, L)), "self-test: upstream value newer than lag not flagged")
    bad_pair = ok.assign(up_id=["C", "B"]); chk(any("usable" in x for x in validate_ledger(bad_pair, L)), "self-test: unusable pair not flagged")
    bad_obs = ok.assign(obs_time_utc=[t, t - pd.Timedelta(hours=2)]); chk(any("R3" in x for x in validate_ledger(bad_obs, L)), "self-test: incomplete own-obs bin not flagged")

def data_checks():
    now = pd.Timestamp.now(tz="UTC"); R = pd.read_parquet(V2 / "rain_fcst.parquet"); O = pd.read_parquet(V2 / "obs_hourly_ext.parquet"); O0 = pd.read_parquet(ROOT / "data/derived/obs_hourly.parquet")
    chk(list(R.columns) == ["time_utc", "usgs_id", "model", "precip_prev_day1", "precip_prev_day2", "precip_prev_day3"], f"rain_fcst columns are {list(R.columns)}")
    chk(not any(c in R.columns for c in ("precipitation", "precip", "precip_obs", "precip_analysis")), "rain_fcst contains a non-forecast (analysis/observed) precipitation column")
    chk(str(R.time_utc.dtype).endswith("UTC]"), "rain_fcst time_utc not tz-aware UTC"); chk((R.time_utc == R.time_utc.dt.floor("h")).all(), "rain_fcst time_utc not on the hour")
    chk(not R.duplicated(["time_utc", "usgs_id", "model"]).any(), "rain_fcst duplicate (time_utc, usgs_id, model)"); chk(set(R.model) <= {"gfs_global", "ncep_hrrr_conus"}, f"unexpected models {set(R.model)}")
    p = R[["precip_prev_day1", "precip_prev_day2", "precip_prev_day3"]]; chk(((p.dropna(how="all", axis=0).fillna(0) >= 0) & (p.fillna(0) < 250)).all().all(), "rain values negative or implausible (>=250 mm/h)")
    first = R.dropna(subset=["precip_prev_day1"]).time_utc.min(); chk(first >= pd.Timestamp("2024-01-15", tz="UTC"), f"rain_fcst has lead-day values before the archive start (first {first}); would not be a real forecast")
    chk(R.time_utc.max() < now.floor("h"), "rain_fcst has times at/after now (a forecast issued N days before cannot be matched to observed outcomes yet; would leak nothing but is not archived)")
    h = R[R.model == "ncep_hrrr_conus"]; chk(h.precip_prev_day2.isna().all() and h.precip_prev_day3.isna().all(), "HRRR day2/3 expected all-NaN but are not (archive changed? re-verify the lead semantics)")
    chk(O.dtypes.astype(str).to_dict() == O0.dtypes.astype(str).to_dict(), f"obs_hourly_ext schema {O.dtypes.astype(str).to_dict()} != obs_hourly {O0.dtypes.astype(str).to_dict()}")
    chk(O.time_utc.min() == pd.Timestamp("2023-02-01 00:00", tz="UTC") and O.time_utc.min() > O0.time_utc.max(), "obs_hourly_ext does not start right after obs_hourly (2023-02-01 00:00)")
    chk(O.time_utc.max() <= now.floor("h") - H, "obs_hourly_ext contains the incomplete current hour or the future"); chk(not O.duplicated(["time_utc", "usgs_id"]).any(), "obs_hourly_ext duplicate rows")
    ids = set(O.usgs_id); L = pd.read_csv(V2 / "upstream_pair_lags.csv", dtype={"usgs_id": str, "up_id": str}); need = set(L.usgs_id) | set(L[L.usable].up_id)
    chk(need <= ids, f"gauges missing from obs_hourly_ext: {sorted(need - ids)[:10]}"); chk(set(R.usgs_id) <= ids, "rain gauges not in obs_hourly_ext")
    chk(L.loc[L.usable, "best_lag_h"].between(0, 96).all(), "usable pair with lag outside 0-96 h")

if __name__ == "__main__":
    self_test(); data_checks()
    if "--features" in sys.argv:
        p = sys.argv[sys.argv.index("--features") + 1]; F = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p); chk("pred_time_utc" in F, "ledger has no pred_time_utc"); bad += validate_ledger(F) if "pred_time_utc" in F else []
    print("check_leakage:", "FAIL" if bad else "PASS", f"({len(bad)} failures)"); [print(" -", b) for b in bad]; sys.exit(1 if bad else 0)
