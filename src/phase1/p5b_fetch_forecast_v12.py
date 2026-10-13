"""Phase1 step 5b: archived OPERATIONAL NWM (v1.2 era) short-range FORECASTS for the crossing reaches. Source: public GCS bucket gs://national-water-model (https://storage.googleapis.com/national-water-model/),
nwm.YYYYMMDD/short_range/nwm.tHHz.short_range.channel_rt.fNNN.conus.nc, ~10.5 MB each, CONUS 2.7M reaches (we keep only our reaches). The bucket's earliest day is 2018-09-17.
BOUNDED subset (full pull would be ~230 GB): inits 00Z and 12Z, leads f001..f012, 2018-09-17 .. 2018-09-24, ~190 files ~2 GB. Result: for each valid hour the forecast with the LATEST available init and the
shortest lead (issued 00Z/12Z, lead 1-12 h) -> a forecast-driven flow series labelled FORECAST (not hindcast)."""
import os, io, sys, requests, numpy as np, pandas as pd, geopandas as gpd, netCDF4
from concurrent.futures import ThreadPoolExecutor
G = "https://storage.googleapis.com/national-water-model/"; O = "data/phase1/"; D = O + "raw/nwm_fc/"; os.makedirs(D, exist_ok=True)
X = gpd.read_parquet("data/phase0/crossings_v2.parquet"); ids = np.sort(X.feature_id.dropna().astype("int64").unique())
jobs = [(f"{d:%Y%m%d}", h, l) for d in pd.date_range("2018-09-17", "2018-09-24") for h in (0, 12) for l in range(1, 13)]
def one(j):
    day, h, l = j; fn = D + f"{day}_{h:02d}_{l:03d}.parquet"
    if os.path.exists(fn): return fn
    for att in range(4):
        try:
            r = requests.get(G + f"nwm.{day}/short_range/nwm.t{h:02d}z.short_range.channel_rt.f{l:03d}.conus.nc", timeout=180)
            if r.status_code == 404: return None
            r.raise_for_status(); ds = netCDF4.Dataset("mem.nc", mode="r", memory=r.content); fid = ds["feature_id"][:].data.astype("int64"); pos = np.searchsorted(fid, ids)   # feature_id sorted in file (checked below)
            assert (fid[pos] == ids).all(); q = np.ma.filled(ds["streamflow"][:].astype("float64"), np.nan)[pos]   # netCDF4 applies scale_factor/offset; fill stays NaN (m3/s)
            vt = int(ds["time"][0]); pd.DataFrame({"feature_id": ids, "q_m3s": q, "valid": pd.Timestamp("1970-01-01") + pd.Timedelta(minutes=vt), "init": pd.Timestamp(f"{day} {h:02d}:00"), "lead_h": l}).to_parquet(fn); ds.close(); return fn
        except Exception as e: err = e
    print("FAILED", j, type(err).__name__); return None
with ThreadPoolExecutor(6) as ex: res = list(ex.map(one, jobs))
ok = [r for r in res if r]; print("files", len(ok), "of", len(jobs))
A = pd.concat([pd.read_parquet(f) for f in ok]); A.to_parquet(O + "florence_nwm_v12_shortrange_long.parquet")
# per valid hour: latest init, then smallest lead
A = A.sort_values(["valid", "init", "lead_h"], ascending=[True, False, True]); best = A.drop_duplicates(["valid", "feature_id"], keep="first")
W = best.pivot(index="valid", columns="feature_id", values="q_m3s"); W.columns = W.columns.astype(str); W.to_parquet(O + "florence_nwm_v12_shortrange_hourly_m3s.parquet")
print(W.shape, W.index.min(), W.index.max(), "NaN share", float(W.isna().mean().mean()), "lead range used", best.lead_h.min(), best.lead_h.max())
