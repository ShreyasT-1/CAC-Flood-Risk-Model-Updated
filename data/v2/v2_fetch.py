"""FloodLens V2 fetch (verified rewrite of the untested draft; checked against the live APIs on 2026-10-13). From the repo root:
  python data/v2/v2_fetch.py obs      # USGS continuous stage (00065) + discharge (00060), 2023-02-01 -> now, yearly chunks, cached to data/raw/usgs/{id}_{pc}_ext{chunk}.csv (resumable, atomic)
  python data/v2/v2_fetch.py hourly   # UTC hourly like src/03_observed.py (stage = hourly MAX, Q = hourly MEAN, label = hour START) -> data/v2/obs_hourly_ext.parquet + obs_ext_coverage.csv
  python data/v2/v2_fetch.py rain     # archived precipitation forecasts (Open-Meteo Previous-Runs), lead day 1-3, GFS + HRRR -> data/v2/rain_fcst.parquet + rain_points.csv + rain_coverage.csv
Fixes versus the draft (all found by testing): (1) the OGC API rejects a time window > 1100 days with HTTP 400, so the draft's single 2023->now request failed: now yearly chunks; (2) uses the repo client
common.get() (X-Api-Key, 429 / quota waiting; limit is 1000 req/h with a key) and the /v1/ path the repo uses (/v0/ also answers); (3) no hourly aggregation existed; (4) Open-Meteo: lead-day precipitation is
only archived from 2024-01-19 (NOT 2021-03; that is the temperature archive), 'gfs_seamless' is HRRR for day 1 and GFS after (a mixture), HRRR has lead day 1 only; so models gfs_global and ncep_hrrr_conus are
requested; hourly precipitation is the sum of the PRECEDING hour (timestamp = interval end) so it is relabelled to hour start to match the obs files; the draft's plain 'precipitation' column (analysis-like, non-NULL
back to 2021) is never requested: it is not a forecast. Leakage rules: see data/v2/check_leakage.py."""
import io, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from common import get, RAW, DER, USGS, ROOT   # noqa: E402
V2 = ROOT / "data/v2"; PC = {"stage": "00065", "q": "00060"}; LIMIT = 50000
NOW = pd.Timestamp.now(tz="UTC"); T_FIRST = pd.Timestamp("2023-02-01 00:00", tz="UTC")   # obs_hourly.parquet ends 2023-01-31 23:00
CHUNKS = [("2023", "2023-02-01T00:00:00Z", "2023-12-31T23:59:59Z"), ("2024", "2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"), ("2025", "2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z"),
          ("2026", "2026-01-01T00:00:00Z", NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))]   # open chunk: file name carries the fetch date (see fname)
cw = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str}).set_index("usgs_id"); lags = pd.read_csv(V2 / "upstream_pair_lags.csv", dtype={"usgs_id": str, "up_id": str})
IDS = sorted(set(lags.usgs_id) | set(lags[lags.usable].up_id))   # 108 targets + usable upstreams


def fname(uid, pc, c, fetch=True):
    n = f"{uid}_{pc}_ext{c[0]}" + (f"_thru{NOW:%Y%m%d}" if c[0] == "2026" and fetch else "")
    return RAW / "usgs" / (n + ".csv")


def latest_file(uid, pc, c):
    if c[0] != "2026": return fname(uid, pc, c) if fname(uid, pc, c).exists() else None
    fs = sorted((RAW / "usgs").glob(f"{uid}_{pc}_ext2026_thru*.csv")); return fs[-1] if fs else None


def fetch_one(uid, pc, c):
    f = fname(uid, pc, c)
    if f.exists(): return 0
    parts, off, n = [], 0, 0
    while True:
        r = get(USGS + "collections/continuous/items", {"f": "csv", "monitoring_location_id": f"USGS-{uid}", "parameter_code": pc, "properties": "time,value,approval_status",
                                                       "time": f"{c[1]}/{c[2]}", "limit": LIMIT, "offset": off}); n += 1
        d = pd.read_csv(io.StringIO(r.text)) if r.text.strip() else pd.DataFrame(columns=["time", "value", "approval_status"])
        parts.append(d[["time", "value", "approval_status"]] if len(d) else d)
        if len(d) < LIMIT: break
        off += LIMIT
    tmp = f.with_suffix(".tmp"); pd.concat(parts).to_csv(tmp, index=False); tmp.replace(f); return n   # atomic: a cached file is always complete


def obs():
    todo = [(u, PC[k], c) for u in IDS for k in PC if bool(cw.loc[u, "has_q" if k == "q" else "has_stage"]) for c in CHUNKS]
    todo = [t for t in todo if not fname(*t).exists()]; print(f"{len(todo)} gauge-param-chunks to fetch (quota 1000 req/h)", flush=True)
    def job(a):
        i, t = a
        try: fetch_one(*t)
        except Exception as e: print("FAILED", t[:2], t[2][0], type(e).__name__, str(e)[:120], flush=True)   # not cached -> retried on rerun
        if i % 100 == 0: print(i, "/", len(todo), time_s(), flush=True)
    with ThreadPoolExecutor(6) as ex: list(ex.map(job, enumerate(todo)))


def time_s(): return pd.Timestamp.now().strftime("%H:%M:%S")


def hourly():
    f26 = [latest_file(u, pc, CHUNKS[3]) for u in IDS for pc in PC.values()]; f26 = [f for f in f26 if f is not None]
    fetched_end = min(pd.Timestamp(f.stat().st_mtime, unit="s", tz="UTC") for f in f26)   # the open chunk was requested up to roughly its first file's fetch time (<= mtime)
    last = min(NOW.floor("h"), fetched_end.floor("h")) - pd.Timedelta(hours=1)   # last hour fully covered by the fetch (the hour being fetched is partial)
    idx = pd.date_range(T_FIRST, last, freq="h"); out, cov = [], []
    for u in IDS:
        cols, prov, miss = {}, {}, []
        for k, pc in PC.items():
            if not bool(cw.loc[u, "has_q" if k == "q" else "has_stage"]): cols[k] = pd.Series(np.nan, index=idx); continue
            fs = [latest_file(u, pc, c) for c in CHUNKS]
            if any(f is None for f in fs): miss.append(f"{k}: not fully fetched"); cols[k] = pd.Series(np.nan, index=idx); continue
            d = pd.concat([pd.read_csv(f) for f in fs] + [pd.DataFrame(columns=["time", "value", "approval_status"])]).dropna(how="all")
            if len(d) == 0: cols[k] = pd.Series(np.nan, index=idx); continue
            d["time"] = pd.to_datetime(d.time, utc=True, format="ISO8601"); d["value"] = pd.to_numeric(d.value, errors="coerce"); d = d.dropna(subset=["value"]).set_index("time")
            h = d.value.resample("h").max() if k == "stage" else d.value.resample("h").mean()
            cols[k] = h.reindex(idx); prov[k] = float((d.approval_status == "Provisional").mean()) if len(d) else np.nan
        df = pd.DataFrame(cols, index=idx); df.insert(0, "usgs_id", u); out.append(df.rename_axis("time_utc").reset_index())
        cov.append(dict(usgs_id=u, has_q=bool(cw.loc[u, "has_q"]), has_stage=bool(cw.loc[u, "has_stage"]), hours=len(idx), q_hours=int(df.q.notna().sum()), stage_hours=int(df.stage.notna().sum()),
                        q_pct=round(100 * df.q.notna().mean(), 2), stage_pct=round(100 * df.stage.notna().mean(), 2), q_first=df.q.first_valid_index(), q_last=df.q.last_valid_index(),
                        stage_first=df.stage.first_valid_index(), stage_last=df.stage.last_valid_index(), q_provisional_share=prov.get("q"), stage_provisional_share=prov.get("stage"), note="; ".join(miss)))
    O = pd.concat(out, ignore_index=True).rename(columns={"q": "obs_q_cfs", "stage": "obs_stage_ft"})[["time_utc", "usgs_id", "obs_stage_ft", "obs_q_cfs"]]
    O["time_utc"] = O.time_utc.astype("datetime64[us, UTC]"); O["usgs_id"] = O.usgs_id.astype(str)
    O.to_parquet(V2 / "obs_hourly_ext.parquet", index=False); pd.DataFrame(cov).to_csv(V2 / "obs_ext_coverage.csv", index=False)
    print(f"{len(O):,} rows, {O.usgs_id.nunique()} gauges, {idx[0]} .. {idx[-1]}; q pct median {pd.DataFrame(cov).q_pct.median()}, gauges with notes: {sum(1 for c in cov if c['note'])}")


# ---------------------------------------------------------------- rain
RMODELS = {"gfs_global": "NCEP GFS (Open-Meteo 'gfs_global', same values as gfs013 for lead days 1-3)", "ncep_hrrr_conus": "NCEP HRRR 3 km CONUS (lead day 1 only)"}
OM = "https://previous-runs-api.open-meteo.com/v1/forecast"; R0 = "2024-01-15"   # lead-day precipitation first non-null 2024-01-19 (probed 2026-10-13)
RCH = [("2024", R0, "2024-12-31"), ("2025", "2025-01-01", "2025-12-31"), ("2026", "2026-01-01", (NOW - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))]
BATCH = 8


def om_get(params, tries=8):
    import requests
    for i in range(tries):
        r = requests.get(OM, params=params, timeout=180)
        if r.status_code == 200: return r.json()
        reason = str(r.json().get("reason", "")) if r.headers.get("content-type", "").startswith("application/json") else r.text[:120]
        if r.status_code == 429 and "aily" in reason: raise SystemExit(f"Open-Meteo DAILY limit reached ({reason}); rerun tomorrow, cached chunks are kept")
        if r.status_code == 429: time_sleep(65 if "inute" in reason else 600); continue
        if r.status_code >= 500: time_sleep(5 * (i + 1)); continue
        raise RuntimeError(f"Open-Meteo {r.status_code}: {reason}")
    raise RuntimeError("Open-Meteo failed after retries")


def time_sleep(s):
    import time; print("  waiting", s, "s", flush=True); time.sleep(s)


def rain():
    import json
    d = RAW / "openmeteo"; d.mkdir(exist_ok=True); pts = cw.loc[IDS, ["lat", "lon"]]; ids = list(pts.index); rows, meta = [], {}
    var = ",".join(f"precipitation_previous_day{k}" for k in (1, 2, 3))
    for yr, a, b in RCH:
        for s in range(0, len(ids), BATCH):
            grp = ids[s:s + BATCH]; f = d / f"rain_{yr}_{s:03d}"; f = f.with_suffix(".json" if yr != "2026" else f".thru{NOW:%Y%m%d}.json")
            if not f.exists():
                j = om_get(dict(latitude=",".join(f"{pts.loc[u, 'lat']:.5f}" for u in grp), longitude=",".join(f"{pts.loc[u, 'lon']:.5f}" for u in grp), start_date=a, end_date=b, hourly=var,
                                models=",".join(RMODELS), timezone="UTC"))
                j = j if isinstance(j, list) else [j]; assert len(j) == len(grp), "location count mismatch"
                tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(dict(ids=grp, resp=j))); tmp.replace(f); print(yr, s, "fetched", flush=True)
            z = json.loads(f.read_text())
            for u, r in zip(z["ids"], z["resp"]):
                meta[u] = dict(usgs_id=u, req_lat=pts.loc[u, "lat"], req_lon=pts.loc[u, "lon"], grid_lat=r["latitude"], grid_lon=r["longitude"], grid_elev_m=r.get("elevation"))
                h = pd.DataFrame(r["hourly"]); t_end = pd.to_datetime(h.pop("time"), utc=True)
                for m in RMODELS:
                    x = pd.DataFrame({f"precip_prev_day{k}": h[f"precipitation_previous_day{k}_{m}"].astype(float) for k in (1, 2, 3)}); x = x.dropna(how="all")
                    x.insert(0, "time_utc", (t_end[x.index] - pd.Timedelta(hours=1)).values); x.insert(1, "usgs_id", u); x.insert(2, "model", m); rows.append(x)
    R = pd.concat(rows, ignore_index=True); R["time_utc"] = pd.to_datetime(R.time_utc, utc=True).astype("datetime64[us, UTC]"); R["usgs_id"] = R.usgs_id.astype(str); R["model"] = R.model.astype(str)
    R = R.drop_duplicates(["time_utc", "usgs_id", "model"]).sort_values(["usgs_id", "model", "time_utc"]).reset_index(drop=True)
    R.to_parquet(V2 / "rain_fcst.parquet", index=False); pd.DataFrame(meta.values()).to_csv(V2 / "rain_points.csv", index=False)
    cv = R.groupby(["model", "usgs_id"]).agg(rows=("time_utc", "size"), first=("time_utc", "min"), last=("time_utc", "max"), **{f"n_day{k}": (f"precip_prev_day{k}", "count") for k in (1, 2, 3)}).reset_index()
    cv.to_csv(V2 / "rain_coverage.csv", index=False); print(R.groupby("model").agg(rows=("usgs_id", "size"), gauges=("usgs_id", "nunique"), first=("time_utc", "min"), last=("time_utc", "max")))


if __name__ == "__main__":
    {"obs": obs, "hourly": hourly, "rain": rain}[sys.argv[1]]()
