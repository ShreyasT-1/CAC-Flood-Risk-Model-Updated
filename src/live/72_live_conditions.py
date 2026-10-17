"""Job 2b: live NWM conditions for the export crossings -> data/export/live_conditions.json and .csv (overwritten on every run; manifest entries upserted, sha not pinned).
Source: NOAA National Water Model operational "Standard Analysis & Assimilation" channel_rt, tm00 file of the latest hourly cycle (hourly, 3 h look-back; verified 2026-10-13 at
https://water.noaa.gov/about/nwm). Tried newest hour first, going back up to 12 h, sources in order AWS (noaa-nwm-pds), GCS (national-water-model), NOMADS. Not the short-range archive in
data/forecasts: that archive only holds the 256 gauge reaches in config/reaches.csv, which cover 2 of the export's hazard-ready reaches.
This is a SCENARIO VIEW of operational NWM output (flow vs each reach's own recurrence flows), not a closure forecast and not a probability. No value is ever filled: a reach missing from the
file or with a missing value gets null; if no file can be read the output says "available": false with the reason.
Levels: RL0 = flow at or below the reach's 2-year flow; RL2/5/10/25/50 = flow strictly above that recurrence flow (highest one reached). Stale = newest cycle older than 6 h.
Usage (repo root): python src/72_live_conditions.py [--now YYYY-MM-DDTHH] [--out DIR]   (--now/--out are for testing the stale / unavailable paths)"""
import hashlib, json, sys
from datetime import datetime, timedelta, timezone
import netCDF4, numpy as np, pandas as pd, requests
ARG = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
X = ARG("--out", "data/export").rstrip("/") + "/"; CMS_TO_CFS = 35.3146667; STALE_MIN = 360; LOOKBACK_H = 12
SRC = {"aws": "https://noaa-nwm-pds.s3.amazonaws.com/nwm.{d}/analysis_assim/nwm.t{h}z.analysis_assim.channel_rt.tm00.conus.nc",
       "gcs": "https://storage.googleapis.com/national-water-model/nwm.{d}/analysis_assim/nwm.t{h}z.analysis_assim.channel_rt.tm00.conus.nc",
       "nomads": "https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.{d}/analysis_assim/nwm.t{h}z.analysis_assim.channel_rt.tm00.conus.nc"}
LEVELS = [("RL50", "q50_cfs"), ("RL25", "q25_cfs"), ("RL10", "q10_cfs"), ("RL5", "q5_cfs"), ("RL2", "q2_cfs")]
LABEL = ("SCENARIO VIEW of operational National Water Model output (current modelled river flow compared with each reach's own recurrence flows). NOT a closure forecast, not a probability, "
         "and not a statement that any road is open or closed. No surge, tide, drainage flooding, deck height or scour. The model's high-flow skill at small streams is limited (see README).")
now = datetime.strptime(ARG("--now", ""), "%Y-%m-%dT%H").replace(tzinfo=timezone.utc) if "--now" in sys.argv else datetime.now(timezone.utc)
gen = now.isoformat(timespec="seconds"); C = pd.read_csv("data/export/crossings_export.csv"); C = C[C.nwm_feature_id.notna()].copy(); C["fid"] = C.nwm_feature_id.astype("int64")
ids = np.sort(C.fid.unique()); tried = []; got = None


def read(content):
    d = netCDF4.Dataset("x.nc", memory=content); fid = d["feature_id"][:]; o = np.argsort(fid); p = np.searchsorted(fid[o], ids); p[p >= len(fid)] = 0; hit = fid[o][p] == ids
    v = d["streamflow"]; v.set_auto_maskandscale(True); q = np.ma.filled(v[:].astype("float64"), np.nan)[o][p]; q[~hit] = np.nan   # absent reach -> NaN, never filled
    out = dict(q=q * CMS_TO_CFS, cycle=datetime.strptime(d.model_initialization_time, "%Y-%m-%d_%H:%M:%S").replace(tzinfo=timezone.utc), valid=datetime.strptime(d.model_output_valid_time, "%Y-%m-%d_%H:%M:%S").replace(tzinfo=timezone.utc),
               ver=str(getattr(d, "model_version", None) or "NWM " + str(getattr(d, "NWM_version_number", "?")).lstrip("v")), n_absent=int((~hit).sum()), n_file=len(fid)); d.close(); return out


for k in range(LOOKBACK_H + 1):
    t = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=k)
    for s, u in SRC.items():
        url = u.format(d=t.strftime("%Y%m%d"), h=t.strftime("%H"))
        try:
            r = requests.get(url, timeout=120); tried.append(f"{t:%Y-%m-%dT%HZ} {s} HTTP {r.status_code}")
            if r.status_code == 200:
                got = (url, s, read(r.content)); assert got[2]["valid"] == t, f"valid time {got[2]['valid']} != requested cycle {t}"; got[2]["cycle"] = t; break   # tm00: cycle = valid (the file's init time is the 3 h look-back start)
        except Exception as e: tried.append(f"{t:%Y-%m-%dT%HZ} {s} {type(e).__name__}")
    if got: break
cols = ["crossing_id", "nwm_feature_id", "cycle_time_utc", "valid_time_utc", "flow_cfs", "ratio_q2", "ratio_q5", "ratio_q10", "ratio_q25", "ratio_q50", "level_reached", "age_minutes", "stale"]
head = dict(generated_at=gen, label=LABEL, product="NWM operational Standard Analysis & Assimilation, channel_rt, tm00 (hourly)", stale_after_minutes=STALE_MIN,
            level_definitions="RL0 = flow at or below the reach's 2-year recurrence flow; RL2/RL5/RL10/RL25/RL50 = flow strictly above that recurrence flow (highest reached); 'not_assessed' = reach has no usable recurrence flows (hazard_threshold_ok false)")
if not got:
    J = dict(available=False, stale=None, **head, source=None, age_minutes=None, cycle_time_utc=None, valid_time_utc=None, crossings=[],
             explanation=f"No analysis_assim tm00 file could be read for the last {LOOKBACK_H + 1} hourly cycles before {gen} (sources aws, gcs, nomads). No values are shown. Attempts: " + "; ".join(tried[-12:]))
    R = pd.DataFrame(columns=cols); print("UNAVAILABLE:", J["explanation"])
else:
    url, s, g = got; age = round((now - g["cycle"]).total_seconds() / 60); C["flow_cfs"] = pd.Series(g["q"], index=pd.Index(ids)).reindex(C.fid).values
    ok = C.hazard_threshold_ok.astype(str).str.lower() == "true"
    for n in (2, 5, 10, 25, 50): C[f"ratio_q{n}"] = np.where(ok, C.flow_cfs / C[f"q{n}_cfs"], np.nan)
    lv = np.full(len(C), "RL0", dtype=object)
    for name, q in LEVELS[::-1]: lv[(C.flow_cfs > C[q]).values] = name   # ascending so the highest reached wins
    C["level_reached"] = np.where(~ok, "not_assessed", np.where(C.flow_cfs.isna(), "no_flow_value", lv))
    C = C.rename(columns={"id": "crossing_id"}); C["cycle_time_utc"] = g["cycle"].strftime("%Y-%m-%dT%H:%MZ"); C["valid_time_utc"] = g["valid"].strftime("%Y-%m-%dT%H:%MZ"); C["age_minutes"] = age; C["stale"] = age > STALE_MIN
    R = C[cols].round({"flow_cfs": 2, "ratio_q2": 4, "ratio_q5": 4, "ratio_q10": 4, "ratio_q25": 4, "ratio_q50": 4}).reset_index(drop=True)
    cnt = R.level_reached.value_counts().to_dict()
    J = dict(available=True, stale=bool(age > STALE_MIN), **head, source=dict(url=url, network=s, nwm_version=g["ver"], reaches_requested=len(ids), reaches_absent_from_file=g["n_absent"], reaches_in_file=g["n_file"]),
             age_minutes=age, cycle_time_utc=C.cycle_time_utc.iloc[0], valid_time_utc=C.valid_time_utc.iloc[0], n_crossings=len(R), level_counts=cnt, crossings=json.loads(R.to_json(orient="records")))
    print(f"cycle {J['cycle_time_utc']} valid {J['valid_time_utc']} age {age} min stale={J['stale']} via {s} | crossings {len(R)}, reaches {len(ids)} (absent from file: {g['n_absent']}) | levels {cnt}")
open(X + "live_conditions.json", "w", encoding="utf-8").write(json.dumps(J, indent=1, allow_nan=False)); R.to_csv(X + "live_conditions.csv", index=False)
# manifest: upsert the two live files (rows only; sha256 not pinned because the files are rewritten on every run)
mp = X + "manifest.json"; M = json.load(open(mp)); M["files"] = [m for m in M["files"] if m["file"] not in ("live_conditions.json", "live_conditions.csv")]
inp = "data/export/crossings_export.csv"; sha = hashlib.sha256(open(inp, "rb").read()).hexdigest()
for f, n in (("live_conditions.json", len(J["crossings"])), ("live_conditions.csv", len(R))):
    M["files"].append(dict(file=f, rows=n, row_unit="records", live=True, source_script="src/72_live_conditions.py", input_files=[inp, "NOAA NWM analysis_assim channel_rt tm00 (url in the file)"], input_sha256={inp: sha}, generated_at=gen,
                           note="rewritten on every run; sha256 deliberately not pinned; rows are 0 when available is false"))
json.dump(M, open(mp, "w"), indent=1)
