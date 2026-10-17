"""T16 step 1 (Amendment 5): build the crossing x event feature table. Same rows/labels as data/phase2/t15_nine/t15_crossing_sets.parquet.
New here: hours above q2 per reach and event (hourly NWM analysis_assim channel_rt tm00 from the GCS mirror, same windows as T15; peaks recomputed and checked against t15_peaks.parquet), structure length (NBI, as 52_t15_crossings.py), structure type.
Missing stays NaN. No rain feature (not assessable, Amendment 5 item 2) and no HAND (0 coverage). Usage (repo root): python src/56_t16_features.py"""
import os, time, threading, numpy as np, pandas as pd, geopandas as gpd, requests, netCDF4
from concurrent.futures import ThreadPoolExecutor
LOCK = threading.Lock(); N = "data/phase2/t15_nine/"; O = "data/phase2/t16/"; os.makedirs(O, exist_ok=True); G = "https://storage.googleapis.com/national-water-model/"; CFS = 35.3146667; U = 32119
A = pd.read_parquet(N + "t15_crossing_sets.parquet"); ev = pd.read_csv(N + "t15a4_events_chosen.csv", parse_dates=["flow_start", "flow_end"]); PK = pd.read_parquet(N + "t15_peaks.parquet")
q2 = A.drop_duplicates("feature_id").set_index("feature_id").q2_cfs   # q2 is a property of the reach
def read(t, ids, tmp):
    url = G + f"nwm.{t:%Y%m%d}/analysis_assim/nwm.t{t:%H}z.analysis_assim.channel_rt.tm00.conus.nc"
    for k in range(5):
        try:
            r = requests.get(url, timeout=300)
            if r.status_code == 404: return None
            r.raise_for_status()
            with LOCK:
                d = netCDF4.Dataset(tmp, memory=r.content); d.set_auto_maskandscale(False); fid = d["feature_id"][:]; v = d["streamflow"][:].astype(np.float64); d.close()
            o = np.argsort(fid); x = v[o[np.searchsorted(fid[o], ids)]]; x[x == -999900] = np.nan; return x * 0.01 * CFS
        except Exception: time.sleep(5 * (k + 1))
    return "ERR"
if not os.path.exists(O + "hours_above_q2.parquet"):
    rows = []
    for e in ev.itertuples():
        ids = np.sort(A[A.event_id == e.event_id].feature_id.dropna().astype("int64").unique()); thr = q2.reindex(ids).values; hours = pd.date_range(e.flow_start.floor("h").tz_localize(None), e.flow_end.ceil("h").tz_localize(None), freq="h")
        cnt = np.zeros(len(ids), int); mx = np.full(len(ids), np.nan); n_ok = 0; bad = 0; t0 = time.time()
        with ThreadPoolExecutor(10) as ex:
            for x in ex.map(lambda t: read(t, ids, "m.nc"), hours):
                if x is None or isinstance(x, str): bad += 1; continue
                n_ok += 1; cnt += (x > thr); mx = np.fmax(mx, x)
        rows += [dict(event_id=e.event_id, feature_id=int(f), hours_above_q2=int(c), peak_cfs_check=float(p), hours_read=n_ok, hours_expected=len(hours)) for f, c, p in zip(ids, cnt, mx)]
        print(e.event_id, "reaches", len(ids), "hours", n_ok, "/", len(hours), "bad", bad, "s", round(time.time() - t0), flush=True)
    pd.DataFrame(rows).to_parquet(O + "hours_above_q2.parquet")
H = pd.read_parquet(O + "hours_above_q2.parquet"); M = H.merge(PK, on=["event_id", "feature_id"]); rel = (M.peak_cfs_check - M.peak_cfs).abs() / M.peak_cfs.clip(lower=1e-9)
print("peak recomputed vs T15 stored: max rel diff", float(rel.max()), "| rows", len(M), "of", len(H)); assert rel.max() < 1e-6, "flow download differs from T15 flows"
# structure features (as in 52_t15_crossings.py)
S = gpd.read_parquet("data/phase2/t10/structures_nc.parquet").to_crs(U)
n = pd.read_csv("data/phase0/raw/NBI_NC25.txt", dtype=str, quotechar="'", encoding="latin1", low_memory=False)
def dms(v, lon):
    v = str(v).strip()
    if not v.isdigit(): return np.nan
    d, rest = (int(v[:3]), v[3:]) if lon else (int(v[:2]), v[2:]); return d + int(rest[:2]) / 60 + int(rest[2:]) / 100 / 3600
n["lat"] = n.LAT_016.map(lambda v: dms(v, False)); n["lon"] = -n.LONG_017.map(lambda v: dms(v, True)); n = n.dropna(subset=["lat", "lon"])
nb = gpd.GeoDataFrame({"nbi_len": pd.to_numeric(n.STRUCTURE_LEN_MT_049, errors="coerce").values}, geometry=gpd.points_from_xy(n.lon, n.lat), crs=4326).to_crs(U)
j = gpd.sjoin_nearest(S[["crossing_id", "geometry"]], nb, how="left", max_distance=50); j = j[~j.index.duplicated()]
S["len_m"] = np.where(S.src == "nbi_only", S.nbi_len_m, j.nbi_len.reindex(S.index).values)
st = S.structure_type.fillna("").str.upper(); S["stype"] = np.where(st.str.contains("BRIDGE"), "bridge", np.where(st.str.contains("CULVERT"), "culvert", np.where(st.str.contains("PIPE"), "pipe", "other")))
F = A.merge(H[["event_id", "feature_id", "hours_above_q2"]], on=["event_id", "feature_id"], how="left").merge(pd.DataFrame(S[["crossing_id", "len_m", "stype"]]), on="crossing_id", how="left")
F["log_r10"] = np.log(F.merge(PK, on=["event_id", "feature_id"], how="left").peak_cfs.values / F.q10_cfs.values); F["log_r2"] = np.log(F.merge(PK, on=["event_id", "feature_id"], how="left").peak_cfs.values / F.q2_cfs.values)
F["stream_order"] = F.strm_order.astype(float); F["tidal_flag"] = F.tidal.astype(float); F["len_missing"] = F.len_m.isna().astype(float)
F["hand_clearance_m"] = np.nan; F["hand_missing"] = 1.0   # T5 not run: coverage 0
F = F.reset_index(drop=True); F.to_parquet(O + "t16_features.parquet")
print(len(F), "rows;", int(F.pos100.sum()), "positives; NaN per feature:", F[["log_r10", "log_r2", "hours_above_q2", "len_m", "stream_order", "tidal_flag", "stype"]].isna().sum().to_dict()); print(F.stype.value_counts().to_dict())
tmp = F.merge(pd.read_parquet(N + "t15_crossing_sets.parquet")[["event_id", "crossing_id", "pos100"]], on=["event_id", "crossing_id"], suffixes=("", "_t15")); assert (tmp.pos100 == tmp.pos100_t15).all() and len(tmp) == len(F), "labels differ from T15"
print("labels identical to T15 nine-event sets")
