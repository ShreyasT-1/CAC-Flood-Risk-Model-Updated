"""New features step B: NCEP Stage IV hourly precipitation (NCAR GDEX d507005, OSDF mirror) -> area-mean rain over each gauge's NLDI basin.
Source layout (verified from the directory listing, see reports/new_features_sources.md):
  https://osdf-director.osg-htc.org/ncar/gdex/d507005/stage4/stage4.YYYYMM.tar  (monthly tar of daily tars ST4.YYYYMMDD,
  each holding gzipped GRIB1 files ST4.YYYYMMDDHH.01h.gz = precip accumulated over the hour ENDING at HH UTC, mm; also 06h/24h files, ignored).
Method: basin polygons (NLDI, EPSG:4326) are projected to the Stage IV polar stereographic grid; weight of a cell = area of (cell square ∩ basin).
  Area-mean = sum(w*v)/sum(w) over cells with valid values; NaN if < 90% of basin area has valid cells or the hour's file is missing (never filled).
Per month output: data/derived/stage4_catch/YYYYMM.npz with hour_end (ISO str), gauges, rain_mm [hours x gauges].
Run: python 11_stage4_catch.py   (resumable; tars are deleted after processing)
"""
import gzip, io, json, tarfile, re, sys
import numpy as np, pandas as pd, requests
import eccodes as ec
from concurrent.futures import ProcessPoolExecutor
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
from shapely import STRtree
import pyproj, scipy.sparse as sp
from common import *

BASE = "https://osdf-director.osg-htc.org/ncar/gdex/d507005/stage4/"
OUT = DER / "stage4_catch"; OUT.mkdir(exist_ok=True)
TMP = RAW / "stage4"; TMP.mkdir(exist_ok=True)
PROJ = "+proj=stere +lat_0=90 +lat_ts=60 +lon_0=-105 +x_0=0 +y_0=0 +R=6371200 +units=m"
NX, NY, DX = 1121, 881, 4762.5  # NCEP grid 240: 4762.5 m at 60N, sphere R=6371.2 km (GRIB header rounds to 4763)
MONTHS = [f"{y}{m:02d}" for y in range(2014, 2024) for m in range(1, 13) if "201412" <= f"{y}{m:02d}" <= "202301"]


def weights():
    f = DER / "stage4_weights.npz"
    miss = pd.read_csv(DER / "obs_missing.csv", dtype={"usgs_id": str}); uids = miss[~miss.dropped].usgs_id.tolist()
    if f.exists():
        z = np.load(f, allow_pickle=True); return list(z["uids"]), sp.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"])), z["info"]
    tr = pyproj.Transformer.from_crs(4326, PROJ, always_xy=True)
    x0, y0 = tr.transform(-119.023, 23.117)  # first grid point (verified in GRIB: lat 23.117, lon -119.023)
    xs, ys = x0 + DX * np.arange(NX), y0 + DX * np.arange(NY)
    rows, cols, vals, info = [], [], [], []
    for gi, u in enumerate(uids):
        fc = json.loads((RAW / "nldi_basin" / f"{u}.json").read_text())["features"]
        if not fc:  # gauge not in NLDI: no basin, rain stays NaN
            info.append((u, 0.0, 0)); continue
        poly = unary_union([transform(tr.transform, shape(x["geometry"])) for x in fc])
        if not poly.is_valid: poly = poly.buffer(0)
        minx, miny, maxx, maxy = poly.bounds
        ix = np.flatnonzero((xs + DX / 2 >= minx) & (xs - DX / 2 <= maxx)); iy = np.flatnonzero((ys + DX / 2 >= miny) & (ys - DX / 2 <= maxy))
        n = 0
        for j in iy:
            for i in ix:
                a = poly.intersection(box(xs[i] - DX / 2, ys[j] - DX / 2, xs[i] + DX / 2, ys[j] + DX / 2)).area
                if a > 0: rows.append(gi); cols.append(j * NX + i); vals.append(a); n += 1
        info.append((u, poly.area / 1e6, n))
    W = sp.csr_matrix((vals, (rows, cols)), shape=(len(uids), NX * NY))
    np.savez(f, uids=np.array(uids), data=W.data, indices=W.indices, indptr=W.indptr, shape=np.array(W.shape), info=np.array(info, dtype=object))
    return uids, W, np.array(info, dtype=object)


def decode(tarf, Wc, cols):
    """monthly tar holds either daily tars of hourly .gz (<=2018) or the hourly .gz files directly (2019+, plus an ignored daily file)"""
    ends, series, seen = [], [], set()
    tot = np.asarray(Wc.sum(1)).ravel()

    def proc(name, data):
        mm = re.fullmatch(r"ST4\.(\d{10})\.01h\.gz", name)  # GRIB1, gzipped (<= 2020-07)
        g2 = re.fullmatch(r"st4_conus\.(\d{10})\.01h\.grb2", name)  # GRIB2, plain (2020-08 on); st4_ak / st4_pr ignored
        mm = mm or g2
        if not mm or mm.group(1) in seen: return
        seen.add(mm.group(1))
        h = ec.codes_new_from_message(data if g2 else gzip.decompress(data))
        try:
            assert ec.codes_get(h, "Ni") == NX and ec.codes_get(h, "Nj") == NY
            assert (ec.codes_get(h, "lengthOfTimeRange") == 1) if g2 else (ec.codes_get(h, "P2") - ec.codes_get(h, "P1") == 1)
            v = ec.codes_get_values(h).astype("float64")
        finally:
            ec.codes_release(h)
        v = v[cols]; ok = (v < 9998) & np.isfinite(v) & (v >= 0)
        num = Wc @ np.where(ok, v, 0.0); den = Wc @ ok.astype(float)
        with np.errstate(all="ignore"):
            r_ = np.where(den / tot >= 0.9, num / np.maximum(den, 1e-9), np.nan)
        ends.append(pd.to_datetime(mm.group(1), format="%Y%m%d%H").isoformat()); series.append(r_.astype("float32"))

    with tarfile.open(tarf) as outer:
        for m in outer:
            if not m.isfile(): continue
            if m.name.endswith((".01h.gz", ".01h.grb2")):
                proc(m.name, outer.extractfile(m).read())
            elif re.fullmatch(r"ST4\.\d{8}", m.name):  # daily tar (nested layout, all years)
                try:
                    with tarfile.open(fileobj=outer.extractfile(m)) as inner:
                        for im in inner: proc(im.name, inner.extractfile(im).read())
                except tarfile.ReadError:
                    pass  # not a tar: hourly files are at top level
    ny, nm = int(tarf.name[7:11]), int(tarf.name[11:13])
    if len(ends) < 0.5 * 24 * __import__("calendar").monthrange(ny, nm)[1]:
        raise IOError(f"only {len(ends)} hourly files decoded")  # never write an empty month silently
    return ends, series


def month(ym):
    out = OUT / f"{ym}.npz"
    if out.exists(): return ym, "cached"
    uids, W, _ = weights()
    cols = np.unique(W.indices); Wc = W[:, cols].tocsr()
    tarf = TMP / f"stage4.{ym}.tar"
    for attempt in range(4):  # download (size checked against Content-Length) + decode; retry the whole month on any failure
        try:
            with requests.get(BASE + f"stage4.{ym}.tar", stream=True, timeout=300) as r:
                r.raise_for_status(); want = int(r.headers.get("Content-Length", -1))
                with open(tarf, "wb") as fh:
                    for ch in r.iter_content(1 << 20): fh.write(ch)
            if want >= 0 and tarf.stat().st_size != want: raise IOError("short download")
            ends, series = decode(tarf, Wc, cols)
            break
        except Exception as e:
            err = repr(e)[:200]
            if attempt == 3: return ym, f"FAILED {err}"
    np.savez(out, hour_end=np.array(ends), gauges=np.array(uids), rain_mm=np.array(series))
    tarf.unlink()
    return ym, f"{len(ends)} hours"


if __name__ == "__main__":
    weights()
    with ProcessPoolExecutor(4) as ex:
        for ym, s in ex.map(month, MONTHS):
            print(ym, s, flush=True)
