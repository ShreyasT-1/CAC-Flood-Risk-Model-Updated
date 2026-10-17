"""FORECAST preview (river), one command:  python src/44_forecast_preview.py   (selftest: ... selftest)   -> export/sample/forecast_latest.json
"NWM short-range forecast, unvalidated; river flow only." NOT a closure probability, not a validated forecast; no skill claimed. Not fed into any ML placeholder value.
Source: NOAA operational NWM short-range channel_rt, 18 hourly leads per cycle (AWS -> GCS -> NOMADS, the same fetcher as the hourly archiver, src/nwm_fc.py).
Why not read data/forecasts: the archive holds only the 256 gauge reaches of config/reaches.csv, and only 1 of the 32 sample-crossing reaches is among them, so the sample crossings' reaches are fetched directly for the latest cycle.
Cycle choice: newest cycle (starting 2 h before the current hour; f018 appears ~1h45 after issue) with ALL 18 leads on one source; if the newest is incomplete the previous complete cycle is used and the skipped ones are listed in "fallback".
RL10 scenario state: flow > the crossing's q10_cfs (crossings.json) -> "scenario: flagged". A scenario level, not a probability; "not flagged" is never an assurance.
ML hook: friend's ML outputs (ShreyasT-1/CAC-Flood-Risk-Model-Updated) are not in this repo; nothing is wired. Any future wiring must sit behind a flag with its own synthetic flag and validation status.
If everything fails the previous forecast_latest.json is left untouched and the exit code is 1; the Florence REPLAY files are independent."""
import sys, json
from datetime import datetime, timedelta, timezone
import numpy as np
LABEL = "NWM short-range forecast, unvalidated; river flow only"
MAX_BACK = 12   # cycles to walk back


def state(flow, q10):
    return None if flow is None or q10 is None or not q10 > 0 or flow != flow else "scenario: flagged" if flow > q10 else "scenario: not flagged"


def build(cycle, df, crossings, fallback, now, version):
    """df: long frame feature_id, valid_time, lead_hours, streamflow_cfs for ONE complete cycle."""
    rows = []
    for c in crossings:
        sub = df[df.feature_id == c["nwm_feature_id"]].sort_values("lead_hours"); hourly = []
        for r in sub.itertuples():
            f = None if r.streamflow_cfs != r.streamflow_cfs else round(float(r.streamflow_cfs), 1)   # NaN = model file had no value; never filled
            hourly.append(dict(lead_hours=int(r.lead_hours), valid_time=r.valid_time.strftime("%Y-%m-%dT%H:%MZ"), flow_cfs=f, flow_ratio_q10=round(f / c["q10_cfs"], 3) if f is not None and c["q10_cfs"] else None,
                               scenario_state=state(f, c["q10_cfs"]), synthetic=False))
        rows.append(dict(id=c["id"], name=c["name"], nwm_feature_id=c["nwm_feature_id"], q10_cfs=c["q10_cfs"], in_model_output=len(hourly) > 0, hourly=hourly))
    age_h = round((now - cycle).total_seconds() / 3600, 1)
    return dict(sample=False, mode="FORECAST", label=LABEL, source=f"NOAA National Water Model operational short-range forecast ({version}), channel_rt, 18 hourly leads",
                caveats=["Unvalidated: no forecast skill is claimed for this layer.", "River flow only: no storm surge, tide, wave run-up, or rain/drainage flooding.", "Not a closure probability. 'Scenario: flagged' means modelled flow above the reach's 10-year flow; 'not flagged' is never an all-clear.", "The 10-year flows are recurrence flows of unverified provenance; the replay uses a different model version (v3.0 retrospective), so ratios are not directly comparable."], not_a_closure_probability=True, validated=False, river_flow_only=True, nwm_version=version,
                cycle_issue_time=cycle.strftime("%Y-%m-%dT%H:00Z"), cycle_age_hours=age_h, stale=age_h > 6, generated_at=now.strftime("%Y-%m-%dT%H:%MZ"), leads=18, fallback=fallback,
                scenario_rule="RL10: flow > q10_cfs of the crossing's reach => 'scenario: flagged'. A flow level, not a probability; excludes surge, tide, wave run-up, rain/drainage flooding.",
                ml=dict(enabled=False, reason="no ML outputs in this repo; any wiring needs its own synthetic flag and validation status"), crossings=rows)


def latest_complete(ids, now):
    import pandas as pd
    sys.path.insert(0, "src"); import nwm_fc
    top = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2); skipped = []
    for k in range(MAX_BACK):
        cyc = top - timedelta(hours=k); why = "lead 18 not available on any source"
        for s in ("aws", "gcs", "nomads"):
            last, ver, err = nwm_fc.fetch_lead(s, cyc, 18, ids, tries=2)   # f018 first: cheapest completeness probe
            if last is None: continue
            got = {18: last}; miss = []
            for f in range(1, 18):
                d, v, e = nwm_fc.fetch_lead(s, cyc, f, ids)
                if d is None: miss.append(f)
                else: got[f] = d
            if not miss: return cyc, pd.concat(got.values(), ignore_index=True), ver, skipped
            why = f"{s}: leads {miss} missing"
        skipped.append(dict(cycle=cyc.strftime("%Y-%m-%dT%HZ"), reason=why))
    return None, None, None, skipped


def run():
    now = datetime.now(timezone.utc); C = json.load(open("export/sample/crossings.json"))["crossings"]
    ids = np.sort(np.unique([c["nwm_feature_id"] for c in C])).astype("int64")
    cyc, df, ver, skipped = latest_complete(ids, now)
    if cyc is None: print("no complete cycle in the last", MAX_BACK, "cycles; forecast_latest.json NOT updated:", skipped); sys.exit(1)
    fb = dict(used=bool(skipped), skipped_newer_cycles=skipped, note="newest cycle(s) incomplete; the previous complete cycle is shown" if skipped else "")
    doc = build(cyc, df, C, fb, now, ver); json.dump(doc, open("export/sample/forecast_latest.json", "w"), indent=1)
    fl = sum(1 for c in doc["crossings"] for h in c["hourly"] if h["scenario_state"] == "scenario: flagged")
    print("wrote export/sample/forecast_latest.json cycle", doc["cycle_issue_time"], "fallback" if fb["used"] else "newest", "| crossings", len(doc["crossings"]), "| flagged crossing-hours", fl)


def selftest():
    import pandas as pd
    cyc = datetime(2026, 10, 14, 12, tzinfo=timezone.utc); rows = [dict(feature_id=1, valid_time=pd.Timestamp(cyc + timedelta(hours=h)), lead_hours=h, streamflow_cfs=100.0 * h) for h in range(1, 19)]
    rows.append(dict(feature_id=2, valid_time=pd.Timestamp(cyc + timedelta(hours=1)), lead_hours=1, streamflow_cfs=float("nan")))
    C = [dict(id="a", name="A", nwm_feature_id=1, q10_cfs=500.0), dict(id="b", name="B", nwm_feature_id=2, q10_cfs=500.0), dict(id="c", name="C", nwm_feature_id=3, q10_cfs=500.0)]
    d = build(cyc, pd.DataFrame(rows), C, dict(used=False), cyc + timedelta(hours=7), "NWM 3.1"); a, b, c = d["crossings"]
    assert d["mode"] == "FORECAST" and d["stale"] and d["cycle_age_hours"] == 7.0 and len(a["hourly"]) == 18
    assert [h["scenario_state"] for h in a["hourly"]][:5] == ["scenario: not flagged"] * 5 and a["hourly"][5]["flow_ratio_q10"] == 1.2 and a["hourly"][5]["scenario_state"] == "scenario: flagged"   # 600 > 500; 500 not > 500
    assert b["hourly"][0]["flow_cfs"] is None and b["hourly"][0]["scenario_state"] is None and not c["in_model_output"] and all(h["synthetic"] is False for h in a["hourly"])
    print("selftest OK (synthetic fixture)")


if __name__ == "__main__": dict(selftest=selftest)[sys.argv[1]]() if len(sys.argv) > 1 else run()
