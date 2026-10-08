"""Step 3: pull USGS continuous stage (00065) + discharge (00060), yearly chunks, cache to data/raw/usgs/, resumable.
Then aggregate to UTC hourly (stage = hourly MAX, discharge = hourly MEAN; hour label = hour START, obs in [h, h+1)).
Usage: python 03_observed.py fetch   (long: ~4-5h at the 1000 req/h quota; rerun resumes)
       python 03_observed.py hourly  (builds data/derived/obs_hourly.parquet + obs_missing.csv)
Outputs: data/raw/usgs/{usgs_id}_{pc}_{year}.csv, data/derived/obs_hourly.parquet, data/derived/obs_missing.csv
"""
import io, sys, time
import numpy as np, pandas as pd
from common import *

PC = {"stage": "00065", "q": "00060"}
LIMIT = 50000
T_FIRST, T_LAST = pd.Timestamp("2015-01-01 00:00"), pd.Timestamp(NWM_END)  # NWM retrospective ends 2023-02-01 -> truncate all
YEARS = range(2015, 2024)


def gauges():
    c = pd.read_csv(DER / "gauge_crosswalk.csv", dtype={"usgs_id": str})
    c = c[c.drainage_area_check == "ok"]  # drops the 1 distance MISMATCH
    return c.sort_values("has_official_flood_stage", ascending=False)  # official-stage gauges first


def fetch_one(uid, pc, yr):
    f = RAW / "usgs" / f"{uid}_{pc}_{yr}.csv"
    if f.exists():
        return 0
    t1 = f"{yr}-12-31T23:59:59Z" if yr < 2023 else "2023-01-31T23:59:59Z"
    parts, off, n = [], 0, 0
    while True:
        r = get(USGS + "collections/continuous/items",
                {"f": "csv", "monitoring_location_id": f"USGS-{uid}", "parameter_code": pc, "properties": "time,value",
                 "time": f"{yr}-01-01T00:00:00Z/{t1}", "limit": LIMIT, "offset": off})
        d = pd.read_csv(io.StringIO(r.text)) if r.text.strip() else pd.DataFrame(columns=["time", "value"])
        n += 1
        parts.append(d[["time", "value"]] if len(d) else d)
        if len(d) < LIMIT:
            break
        off += LIMIT
    pd.concat(parts).to_csv(f.with_suffix(".tmp"), index=False)
    f.with_suffix(".tmp").replace(f)  # atomic: a file in cache is always complete
    return n


def fetch():
    g, todo = gauges(), []
    for r in g.itertuples():
        for k, pc in PC.items():
            if (k == "q" and not r.has_q) or (k == "stage" and not r.has_stage):
                continue
            todo += [(r.usgs_id, pc, y) for y in YEARS]
    todo = [t for t in todo if not (RAW / "usgs" / f"{t[0]}_{t[1]}_{t[2]}.csv").exists()]
    print(f"{len(todo)} gauge-param-year chunks to fetch", flush=True)
    def job(a):
        i, t = a
        try:
            fetch_one(*t)
        except Exception as e:
            print("FAILED", t, type(e).__name__, str(e)[:120], flush=True)  # not cached -> retried on rerun
        if i % 100 == 0:
            print(i, "/", len(todo), time.strftime("%H:%M:%S"), flush=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:  # quota (1000 req/h) is the real limit; get() waits out 429s
        list(ex.map(job, enumerate(todo)))


def hourly():
    g = gauges()
    idx = pd.date_range(T_FIRST, T_LAST, freq="h", tz="UTC")
    out, miss = [], []
    for r in g.itertuples():
        cols = {}
        for k, pc in PC.items():
            fs = [RAW / "usgs" / f"{r.usgs_id}_{pc}_{y}.csv" for y in YEARS]
            if not all(f.exists() for f in fs):
                cols[k] = None; continue  # not fully fetched (or series absent) -> treated as 100% missing
            d = pd.concat([pd.read_csv(f) for f in fs])
            if len(d) == 0:
                cols[k] = None; continue
            d["time"] = pd.to_datetime(d.time, utc=True, format="ISO8601")
            d["value"] = pd.to_numeric(d.value, errors="coerce")
            d = d.dropna().set_index("time").value
            h = d.resample("h").max() if k == "stage" else d.resample("h").mean()
            cols[k] = h.reindex(idx)
        df = pd.DataFrame({k: (v if v is not None else pd.Series(np.nan, index=idx)) for k, v in cols.items()}, index=idx)
        m = df.isna().mean()
        key = "stage" if r.has_official_flood_stage else "q"
        miss.append({"usgs_id": r.usgs_id, "stage_missing": m["stage"], "q_missing": m["q"], "key_var": key,
                     "dropped": bool(m[key] > 0.20)})
        if m[key] > 0.20:
            continue
        for k in ("stage", "q"):  # non-key variable over 20% missing -> null it out (kept visible in obs_missing.csv)
            if m[k] > 0.20:
                df[k] = np.nan
        df.insert(0, "usgs_id", r.usgs_id)
        out.append(df.rename_axis("time_utc").reset_index())
    pd.concat(out).rename(columns={"q": "obs_q_cfs", "stage": "obs_stage_ft"}).to_parquet(DER / "obs_hourly.parquet", index=False)
    mm = pd.DataFrame(miss)
    mm.to_csv(DER / "obs_missing.csv", index=False)
    print(f"gauges kept: {(~mm.dropped).sum()} | dropped (>20% missing key var): {mm.dropped.sum()}")
    print(mm[mm.dropped].to_string())


if __name__ == "__main__":
    {"fetch": fetch, "hourly": hourly}[sys.argv[1]]()
