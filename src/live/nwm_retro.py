"""Fetch NWM v3.0 retrospective hourly streamflow (m3/s) for given feature_ids over a time-index range, straight from the public S3 bucket over HTTPS (s3fs/zarr cannot resolve DNS here).
chrtout.zarr/streamflow: int32 scale 0.01, fill -999900 -> NaN (never filled), chunks [672 h, 30000 reaches], time axis hourly from 1979-02-01 01:00, 385704 steps (to 2023-01-31 23:00)."""
import time, numpy as np, pandas as pd, requests, zstandard
from concurrent.futures import ThreadPoolExecutor
B = "https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/zarr/chrtout.zarr/"; BASE = pd.Timestamp("1979-02-01 01:00"); NT = 385704
_fid = None
def feature_ids():
    global _fid
    if _fid is None: _fid = np.frombuffer(zstandard.ZstdDecompressor().decompress(open("data/phase0/raw/retro30_feature_id.zst", "rb").read(), max_output_size=2776734 * 8), dtype="<i8")
    return _fid
def fetch(ids, t0=None, t1=None, workers=16):
    """DataFrame (hourly index) x feature_id (str columns), m3/s. t0/t1 Timestamps (inclusive); default whole record."""
    ids = np.asarray(sorted(set(int(i) for i in ids)), dtype="int64"); fid = feature_ids(); pos = np.searchsorted(fid, ids); assert (fid[pos] == ids).all(), "feature_id not in retrospective"
    i0 = 0 if t0 is None else int((pd.Timestamp(t0) - BASE) / pd.Timedelta(hours=1)); i1 = NT - 1 if t1 is None else int((pd.Timestamp(t1) - BASE) / pd.Timedelta(hours=1)); assert 0 <= i0 <= i1 < NT
    out = np.full((i1 - i0 + 1, len(ids)), np.nan, dtype=np.float32); jobs = [(t, f) for t in range(i0 // 672, i1 // 672 + 1) for f in sorted(set(pos // 30000))]
    def one(tf):
        t, f = tf; d = zstandard.ZstdDecompressor()
        for k in range(9):
            try:
                r = requests.get(B + f"streamflow/{t}.{f}", timeout=300); r.raise_for_status(); break
            except Exception:
                if k == 8: raise
                time.sleep(min(120, 2 ** (k + 1)))   # network drops (sleep/wifi) -> back off, up to ~8 min total
        a = np.frombuffer(d.decompress(r.content, max_output_size=672 * 30000 * 4), dtype="<i4").reshape(672, -1)
        sel = np.where(pos // 30000 == f)[0]; lo = max(i0, t * 672); hi = min(i1, t * 672 + 671)
        v = a[lo - t * 672:hi - t * 672 + 1][:, pos[sel] - f * 30000].astype(np.float32); v[v == -999900] = np.nan
        out[lo - i0:hi - i0 + 1, sel] = v * 0.01
    with ThreadPoolExecutor(workers) as ex: list(ex.map(one, jobs))
    return pd.DataFrame(out, index=pd.date_range(BASE, periods=NT, freq="h")[i0:i1 + 1], columns=ids.astype(str))
