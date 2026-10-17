"""Step 4: NWM v3.0 retrospective hourly streamflow (m3/s) for crosswalk feature_ids, 2015-01-01 .. 2023-01-31 23:00 UTC.
Source: s3://noaa-nwm-retrospective-3-0-pds/CONUS/zarr/chrtout.zarr (anonymous). Approved download: ~14 GB of chunk reads, only the
needed reaches are kept (a few MB). Reads are one 672-h time-chunk at a time, cached to data/raw/nwm/, resumable.
NOTE: the v3.0 retrospective has NO data assimilation (free-running), unlike the operational NWM.
ponytail: plain xarray/zarr (dask not installed; threads over time-chunks give the parallelism).
Output: data/derived/nwm_hourly.parquet (feature_id, time_utc, nwm_flow_cms)
"""
import numpy as np, pandas as pd, xarray as xr
from concurrent.futures import ThreadPoolExecutor
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2])); from common import *

(RAW / "nwm").mkdir(exist_ok=True)
ds = xr.open_zarr("s3://noaa-nwm-retrospective-3-0-pds/CONUS/zarr/chrtout.zarr", storage_options={"anon": True})
c = pd.read_csv(DER / "gauge_crosswalk.csv")
fids = np.sort(c[c.drainage_area_check == "ok"].feature_id.unique())
fpos = np.searchsorted(ds.feature_id.values, fids)
assert (ds.feature_id.values[fpos] == fids).all()
t0, t1 = [int(np.searchsorted(ds.time.values, np.datetime64(t))) for t in ("2015-01-01T00:00", "2023-02-01T00:00")]
assert pd.Timestamp(ds.time.values[t1 - 1]) == pd.Timestamp(NWM_END), ds.time.values[t1 - 1]
TS = 672
starts = list(range(t0, t1, TS))
print(f"{len(fids)} reaches, {t1 - t0} hours, {len(starts)} time chunks", flush=True)


def one(s):
    f = RAW / "nwm" / f"chunk_{s}.parquet"
    if f.exists():
        return
    e = min(s + TS, t1)
    a = ds.streamflow.isel(time=slice(s, e), feature_id=fpos).load()  # masks fill values to NaN, applies scale factor
    df = pd.DataFrame(a.values, index=a.time.values, columns=fids)
    df.columns = df.columns.astype(str)
    df.to_parquet(f.with_suffix(".tmp"))
    f.with_suffix(".tmp").replace(f)
    print("done", s, flush=True)


with ThreadPoolExecutor(3) as ex:
    list(ex.map(one, starts))

d = pd.concat([pd.read_parquet(RAW / "nwm" / f"chunk_{s}.parquet") for s in starts])
d.index = pd.DatetimeIndex(d.index, tz="UTC", name="time_utc")
assert len(d) == t1 - t0 and d.index.is_monotonic_increasing and d.index.is_unique
long = d.rename(columns=int).rename_axis("feature_id", axis=1).stack().rename("nwm_flow_cms").reset_index()
long.to_parquet(DER / "nwm_hourly.parquet", index=False)
print("rows", len(long), "| NaN fraction", round(long.nwm_flow_cms.isna().mean(), 5), "| last hour", d.index[-1])
