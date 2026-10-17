"""NWM operational short-range forecast archive (CONUS channel_rt) for our reaches.

Archive label: "v1.2 operational forecasts, hindcast replay only" for 2018 cycles - NOT forecast skill of the current model.
One parquet per issue cycle: data/forecasts/short_range/issue_date=YYYY-MM-DD/cycle_HHz.parquet (never overwritten).
Columns: feature_id, issue_time, valid_time, lead_hours, streamflow_cfs (= m3/s * 35.3147), nwm_version.
Missing leads/cycles are never filled; they are logged in data/forecasts/manifest.csv.
ponytail: reads whole ~10 MB NetCDF per lead (netCDF4 from memory); BigQuery path not built until a project ID exists.
"""
import csv, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import netCDF4, numpy as np, pandas as pd, requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/forecasts"
MANIFEST = OUT / "manifest.csv"
CMS_TO_CFS = 35.3147
LEADS = range(1, 19)
SOURCES = {  # live priority order: aws, gcs, nomads
    "aws": "https://noaa-nwm-pds.s3.amazonaws.com/nwm.{d}/short_range/nwm.t{h}z.short_range.channel_rt.f{f:03d}.conus.nc",
    "gcs": "https://storage.googleapis.com/national-water-model/nwm.{d}/short_range/nwm.t{h}z.short_range.channel_rt.f{f:03d}.conus.nc",
    "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.{d}/short_range/nwm.t{h}z.short_range.channel_rt.f{f:03d}.conus.nc",
}
FIELDS = ["cycle", "status", "error", "source", "missing_leads", "nwm_version", "n_rows", "fetched_utc"]
_S = requests.Session()
_NC = threading.Lock()


def reach_ids():
    return np.sort(pd.read_csv(ROOT / "config/reaches.csv").feature_id.unique())


def url(source, issue, lead):
    return SOURCES[source].format(d=issue.strftime("%Y%m%d"), h=issue.strftime("%H"), f=lead)


def cycle_path(issue):
    return OUT / "short_range" / f"issue_date={issue:%Y-%m-%d}" / f"cycle_{issue:%H}z.parquet"


def _parse(content, lead, ids):
    d = netCDF4.Dataset("x.nc", memory=content)
    ver = str(getattr(d, "model_version", None) or "NWM " + str(d.NWM_version_number).lstrip("v"))  # v1.2 files: model_version; v3.x: NWM_version_number
    fid = d["feature_id"][:]
    pos = np.searchsorted(fid, ids)
    ok = pos < len(fid)
    ok[ok] = fid[pos[ok]] == ids[ok]  # reaches absent from the file are dropped, not filled
    v = d["streamflow"]; v.set_auto_maskandscale(True)
    q = np.ma.filled(v[:][pos[ok]].astype("float64"), np.nan)  # read whole array then index: netCDF fancy indexing is ~100x slower  # masked fill (-999900) -> NaN, kept as NaN
    valid = datetime.strptime(d.model_output_valid_time, "%Y-%m-%d_%H:%M:%S")
    init = datetime.strptime(d.model_initialization_time, "%Y-%m-%d_%H:%M:%S")
    df = pd.DataFrame({"feature_id": ids[ok].astype("int64"), "issue_time": pd.Timestamp(init, tz="UTC"),
                       "valid_time": pd.Timestamp(valid, tz="UTC"), "lead_hours": lead,
                       "streamflow_cfs": q * CMS_TO_CFS, "nwm_version": ver})
    d.close()
    return df, ver, ""


def fetch_lead(source, issue, lead, ids, tries=4):
    """-> (DataFrame | None, version, error). 404 = missing upstream (no retry); other errors retried."""
    err = ""
    for i in range(tries):
        try:
            r = _S.get(url(source, issue, lead), timeout=120)
            if r.status_code in (403, 404):
                return None, None, f"HTTP {r.status_code}"
            r.raise_for_status()
            with _NC:  # netCDF-C is not thread-safe: parse under a lock, download in parallel
                return _parse(r.content, lead, ids)
        except Exception as e:  # network / truncated file
            err = f"{type(e).__name__}: {e}"[:200]; time.sleep(2 ** i)
    return None, None, err


def log(row):
    OUT.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    with open(MANIFEST, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new: w.writeheader()
        w.writerow({k: row.get(k, "") for k in FIELDS})


def archive_cycle(issue, sources=("gcs",), workers=6, require_complete=False):
    """Fetch leads 1-18 of one cycle, write parquet once. Returns status. Idempotent: existing cycle file = skipped."""
    p = cycle_path(issue)
    cyc = issue.strftime("%Y-%m-%dT%HZ")
    if p.exists():
        return "exists"
    ids = reach_ids()
    got, missing, err, used = {}, list(LEADS), "", []
    for s in sources:  # first source that yields every lead wins; otherwise keep the best partial and try the next
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(lambda f: fetch_lead(s, issue, f, ids), [f for f in LEADS if f in missing]))
        for f, (df, ver, e) in zip([f for f in LEADS if f in missing], res):
            if df is not None: got[f] = df; used.append(s) if s not in used else None
            else: err = e
        missing = [f for f in LEADS if f not in got]
        if not missing: break
    if require_complete and missing:  # live: cycle still publishing; write nothing, retry next run
        return "incomplete"
    if not got:
        log(dict(cycle=cyc, status="failed" if "HTTP" not in err else "missing_upstream", error=err, source=",".join(sources),
                 missing_leads="1-18", fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        return "failed"
    df = pd.concat(got.values(), ignore_index=True)
    assert ((df.valid_time - df.issue_time) / pd.Timedelta(hours=1) == df.lead_hours).all(), "valid_time != issue_time + lead"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp"); df.to_parquet(tmp, index=False); tmp.replace(p)
    st = "ok" if not missing else "partial"
    log(dict(cycle=cyc, status=st, error=err if missing else "", source="+".join(used), nwm_version=";".join(sorted(df.nwm_version.unique())),
             missing_leads=",".join(map(str, missing)), n_rows=len(df), fetched_utc=datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return st
