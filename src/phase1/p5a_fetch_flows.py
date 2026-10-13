"""Phase1 step 5a: NWM v3.0 retrospective hourly streamflow (HINDCAST, free-running, no DA) for the crossing reaches, 2018-09-13 .. 2018-11-06 UTC.
zarr/s3fs cannot resolve DNS here, so the needed chunks of s3://noaa-nwm-retrospective-3-0-pds/CONUS/zarr/chrtout.zarr/streamflow are fetched over HTTPS with requests and decoded by hand
(zstd, int32, scale 0.01 m3/s, fill -999900, chunks [672 h, 30000 reaches])."""
import os, requests, numpy as np, pandas as pd, geopandas as gpd, zstandard
B = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/zarr/chrtout.zarr/"; O = "data/phase1/"; C = O + "raw/nwm_chunks/"; os.makedirs(C, exist_ok=True)
d = zstandard.ZstdDecompressor()
get = lambda k: requests.get(B + k, timeout=300)
fid = np.frombuffer(d.decompress(open("data/phase0/raw/retro30_feature_id.zst", "rb").read(), max_output_size=2776734 * 8), dtype="<i8")
tt = np.frombuffer(d.decompress(get("time/0").content, max_output_size=672 * 8), dtype="<i8"); print("time units", get("time/.zattrs").text.replace("\n", " ")[:200], "first", tt[:3])
X = gpd.read_parquet("data/phase0/crossings_v2.parquet"); ids = np.sort(X.feature_id.dropna().astype("int64").unique()); pos = np.searchsorted(fid, ids); assert (fid[pos] == ids).all()
# time index: the zarr time axis is hourly from 1979-02-01 01:00 (verified against 'first' above and the old pipeline's NWM_END assert)
t0 = pd.Timestamp("2018-09-13 00:00"); t1 = pd.Timestamp("2018-11-06 23:00"); base = pd.Timestamp("1979-02-01 01:00")
i0 = int((t0 - base) / pd.Timedelta(hours=1)); i1 = int((t1 - base) / pd.Timedelta(hours=1)); print("time idx", i0, i1, "hours", i1 - i0 + 1)
tc = range(i0 // 672, i1 // 672 + 1); fc = sorted(set(pos // 30000)); print("time chunks", list(tc), "feature chunks", fc, "files", len(tc) * len(fc), "(~4 MB each)")
out = np.full((i1 - i0 + 1, len(ids)), np.nan)
for t in tc:
    for f in fc:
        fn = C + f"{t}.{f}"
        if not os.path.exists(fn):
            r = get(f"streamflow/{t}.{f}"); r.raise_for_status(); open(fn, "wb").write(r.content)
        a = np.frombuffer(d.decompress(open(fn, "rb").read(), max_output_size=672 * 30000 * 4), dtype="<i4").reshape(672, -1)
        sel = np.where(pos // 30000 == f)[0]; lo = max(i0, t * 672); hi = min(i1, t * 672 + 671)
        v = a[lo - t * 672:hi - t * 672 + 1][:, pos[sel] - f * 30000].astype(float); v[v == -999900] = np.nan   # missing stays NaN
        out[lo - i0:hi - i0 + 1, sel] = v * 0.01
times = pd.date_range(base, periods=i1 + 1, freq="h")[i0:i1 + 1]; assert times[0] == t0 and times[-1] == t1
F = pd.DataFrame(out, index=times, columns=ids.astype(str)); F.to_parquet(O + "florence_nwm_v30_retro_hourly_m3s.parquet")
print(F.shape, "NaN share", float(np.isnan(out).mean()), "max m3/s", float(np.nanmax(out)), "peak time of median-reach", F.median(axis=1).idxmax())
print("sanity: NE Cape Fear River at Burgaw/Chinquapin region reaches top peaks:", F.max().sort_values(ascending=False).head(3).round(0).to_dict())
