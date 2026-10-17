"""Phase 2 / T15 Step 3: peak NWM streamflow per assessed reach over each event's flow window (Amendment 4). Source: NWM operational analysis_assim channel_rt tm00, hourly, from NOAA's public Google Cloud mirror
gs://national-water-model (the noaa-nwm-pds S3 bucket only starts 2025-01-01). Records the model version stored in the files. Missing hours are listed, never filled. Usage (repo root): python src/53_t15_flows.py"""
import io, os, time, json, requests, numpy as np, pandas as pd, netCDF4
from concurrent.futures import ThreadPoolExecutor
import threading; LOCK = threading.Lock()   # HDF5/netCDF4 is not thread-safe: downloads run in parallel, parsing is serialised
O = "data/phase2/t15/"; G = "https://storage.googleapis.com/national-water-model/"; CFS = 35.3146667
A = pd.read_parquet(O + "t15_crossing_sets.parquet"); ev = pd.read_csv(O + "t15a4_events_chosen.csv", parse_dates=["flow_start", "flow_end"])
def read(t, ids_sorted, idx_pos):
    url = G + f"nwm.{t:%Y%m%d}/analysis_assim/nwm.t{t:%H}z.analysis_assim.channel_rt.tm00.conus.nc"
    for k in range(5):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 404: return t, None, None
            r.raise_for_status()
            with LOCK:
                d = netCDF4.Dataset("m.nc", memory=r.content); d.set_auto_maskandscale(False)
                fid = d["feature_id"][:]; v = d["streamflow"][:].astype(np.float64); ver = d.getncattr("NWM_version_number") if "NWM_version_number" in d.ncattrs() else "NA"; d.close()
            o = np.argsort(fid); pos = o[np.searchsorted(fid[o], ids_sorted)]; x = v[pos]; x[x == -999900] = np.nan; return t, x * 0.01, ver
        except Exception:
            time.sleep(5 * (k + 1))
    return t, "ERR", None
res = {}
for e in ev.itertuples():
    ids = np.sort(A[A.event_id == e.event_id].feature_id.dropna().astype("int64").unique()); hours = pd.date_range(e.flow_start.floor("h").tz_localize(None), e.flow_end.ceil("h").tz_localize(None), freq="h")
    mx = np.full(len(ids), -np.inf); mx[:] = np.nan; got, miss, vers = 0, [], set(); t0 = time.time()
    with ThreadPoolExecutor(10) as ex:
        for t, x, ver in ex.map(lambda t: read(t, ids, None), hours):
            if x is None or isinstance(x, str): miss.append(str(t)); continue
            got += 1; vers.add(ver); mx = np.fmax(mx, x)
    res[e.event_id] = dict(ids=ids, peak_cfs=mx * CFS, hours_expected=len(hours), hours_read=got, missing=miss, versions=sorted(vers))
    print(e.event_id, "reaches", len(ids), "hours", got, "/", len(hours), "missing", len(miss), "versions", sorted(vers), "s", round(time.time() - t0), flush=True)
rows = [dict(event_id=k, feature_id=int(f), peak_cfs=float(p)) for k, v in res.items() for f, p in zip(v["ids"], v["peak_cfs"])]; pd.DataFrame(rows).to_parquet(O + "t15_peaks.parquet")
json.dump({k: {kk: vv for kk, vv in v.items() if kk not in ("ids", "peak_cfs")} for k, v in res.items()}, open(O + "t15_flow_meta.json", "w"), indent=1)
