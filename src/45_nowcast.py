"""NOWCAST (observed now), one command:  python src/45_nowcast.py   (selftest: python src/45_nowcast.py selftest)
Writes export/sample/nowcast.json (river gauges) and refreshes export/sample/coastal.json (via 43_coastal_levels.fetch). A failure in one part keeps that part's previous file and is logged in nowcast.json "errors".
River sources (verified 2026-10-14):
  USGS Water Data API (api.waterdata.usgs.gov/ogcapi/v0, collection latest-continuous; the legacy WaterServices is NOT used): latest 00060 discharge (cfs) and 00065 gage height (ft, USGS gauge datum).
  NWS NWPS (api.water.noaa.gov/nwps/v1/gauges/{lid}): observed stage in the NWS stage datum, the NWS flood thresholds, and NWS's own flood category.
  The USGS gage height and the NWS stage are on DIFFERENT datums (e.g. STPN7: USGS 1.40 ft vs NWS 33.49 ft): they are never compared or subtracted. The flood status is NWS's category for NWS's stage.
Gauges: `gauges` = the in_pilot rows of config/reaches.csv that lie within 40 km of New Hanover/Brunswick/Pender (config/nowcast_gauges.csv, made by src/46_nowcast_gauge_km.py); the other in_pilot gauges (upstream basin: Fayetteville, Greensboro, Chapel Hill ...) are kept under `other_basin_gauges` and not shown. Every value carries synthetic:false (real observations), a UTC time and stale (> 3 h old). A gauge category of no_flooding / below action is NOT an all-clear for any road."""
import sys, json, importlib.util, datetime as dt, urllib.request, urllib.parse
import pandas as pd
STALE = dt.timedelta(hours=3)
USGS = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/latest-continuous/items"
NWPS = "https://api.water.noaa.gov/nwps/v1/gauges/"
CATS = ("no_flooding", "action", "minor", "moderate", "major")   # NWPS floodCategory values; others (not_defined, obs_not_current, low_threshold, out_of_service) are passed through as-is


def get(url, params=None):
    if params: url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "floodlens_lifelines"}), timeout=30) as r: return json.load(r)


def usgs_ids(raw):   # config stores ids without leading zeros: 8-digit site numbers (2106500 -> 02106500); longer ids are 15-digit-style, tried zero-padded to 10 then 15
    s = str(int(raw)); return [s.zfill(8)] if len(s) <= 8 else [s.zfill(10), s.zfill(15)]


def parse_usgs(j):   # -> {site_no: {param_code: (value, time_str, approval)}}; null/blank values dropped, newest per (site, parameter) kept
    out = {}
    for f in j.get("features", []):
        p = f["properties"]
        try: v = float(p["value"])
        except (TypeError, ValueError, KeyError): continue
        site = p["monitoring_location_id"].split("-", 1)[1]; cur = out.setdefault(site, {}).get(p["parameter_code"])
        if cur is None or p["time"] > cur[1]: out[site][p["parameter_code"]] = (v, p["time"], p.get("approval_status"))
    return out


def iso(t): return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def stamp(t, now):   # -> (UTC string, stale flag)
    d = iso(t); return d.strftime("%Y-%m-%dT%H:%MZ"), (now - d) > STALE


def build_gauge(g, usgs, nws, now):
    rec = dict(lid=g["lid"], usgs_site=g["site"], mode="NOWCAST", synthetic=False, name=nws.get("name") if nws else None)
    u = (usgs or {}); q, h = u.get("00060"), u.get("00065")
    rec["usgs"] = dict(discharge_cfs=q[0] if q else None, discharge_time=stamp(q[1], now)[0] if q else None, discharge_stale=stamp(q[1], now)[1] if q else True,
                       gage_height_ft_usgs_datum=h[0] if h else None, gage_height_time=stamp(h[1], now)[0] if h else None, gage_height_stale=stamp(h[1], now)[1] if h else True,
                       approval=(q or h or (None, None, None))[2])
    o = ((nws or {}).get("status") or {}).get("observed") or {}; th = ((nws or {}).get("flood") or {}).get("categories") or {}
    ok = o.get("primary") is not None and o.get("validTime") and o["primary"] > -900   # NWPS uses -999 for missing
    t, st = stamp(o["validTime"], now) if ok else (None, True)
    rec["nws"] = dict(stage_ft_nws_datum=o["primary"] if ok else None, stage_time=t, stage_stale=st, flood_category=o.get("floodCategory") if ok else "no_observation",
                      thresholds_ft={k: v["stage"] for k, v in th.items() if v.get("stage") is not None and v["stage"] > -900})
    rec["stale"] = rec["nws"]["stage_stale"] and rec["usgs"]["discharge_stale"] and rec["usgs"]["gage_height_stale"]
    return rec


def river(now):
    R = pd.read_csv("config/reaches.csv"); R = R[R.in_pilot & R.usgs_ids.notna() & R.nws_lid.notna()]; gauges, errors = [], []; pub = set(pd.read_csv("config/nowcast_gauges.csv").query("public").nws_lid)
    cand = {}; [cand.setdefault(sid, r.nws_lid) for r in R.itertuples() for sid in usgs_ids(r.usgs_ids)]
    uj = {}
    try:
        for i in range(0, len(cand), 25):   # batched: comma-separated monitoring_location_id
            chunk = list(cand)[i:i + 25]
            uj.update(parse_usgs(get(USGS, dict(monitoring_location_id=",".join("USGS-" + s for s in chunk), parameter_code="00060,00065", limit=500, f="json"))))
    except Exception as e: errors.append(f"USGS: {type(e).__name__}: {e}"[:200])
    for r in R.itertuples():
        site = next((s for s in usgs_ids(r.usgs_ids) if s in uj), usgs_ids(r.usgs_ids)[0])
        try: nws = get(NWPS + r.nws_lid)
        except Exception as e: nws = None; errors.append(f"NWPS {r.nws_lid}: {type(e).__name__}: {e}"[:200])
        gauges.append(dict(build_gauge(dict(lid=r.nws_lid, site=site), uj.get(site), nws, now), pilot_area=r.nws_lid in pub))
    return gauges, errors


def run():
    now = dt.datetime.now(dt.timezone.utc); gauges, errors = [], []
    try: gauges, errors = river(now)
    except Exception as e: errors.append(f"river: {type(e).__name__}: {e}"[:200])
    other = [g for g in gauges if not g["pilot_area"]]; gauges = [g for g in gauges if g["pilot_area"]]
    if gauges:
        doc = dict(sample=False, mode="NOWCAST", stale=all(g["stale"] for g in gauges), generated_at=now.strftime("%Y-%m-%dT%H:%MZ"), stale_after_hours=3, sources=["USGS Water Data API (latest-continuous, 00060/00065)", "NWS NWPS (observed stage, flood thresholds, flood category)"],
                   caveats=["Observed gauge readings, provisional. Not a forecast and not a closure probability.", "USGS gage height and NWS stage use different datums and are not compared.", "A gauge below flood stage says nothing about whether any road is open or passable; it does not capture drainage flooding, surge, or small streams.", "Flood category is NWS's, for the gauge's own stage."],
                   gauge_rule="Gauges within 40 km of New Hanover, Brunswick or Pender county. Other Cape Fear basin gauges further upstream are kept in other_basin_gauges and not shown.",
                   n_pilot_area=len(gauges), n_other_basin=len(other), errors=errors, gauges=gauges, other_basin_gauges=other)
        json.dump(doc, open("export/sample/nowcast.json", "w"), indent=1); print("wrote export/sample/nowcast.json", len(gauges), "gauges;", sum(g["stale"] for g in gauges), "stale;", len(errors), "errors")
    else: print("river nowcast failed; previous nowcast.json kept:", errors)
    try:
        spec = importlib.util.spec_from_file_location("coastal", "src/43_coastal_levels.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.fetch()
    except Exception as e: print("coastal failed; previous coastal.json kept:", type(e).__name__, e)


def selftest():   # fixtures are trimmed REAL responses captured 2026-10-14
    now = dt.datetime(2026, 10, 14, 21, 0, tzinfo=dt.timezone.utc)
    U = {"features": [{"properties": {"monitoring_location_id": "USGS-02105500", "parameter_code": "00065", "time": "2026-10-14T20:00:00+00:00", "value": "1.40", "approval_status": "Provisional"}},
                      {"properties": {"monitoring_location_id": "USGS-02105500", "parameter_code": "00060", "time": "2026-10-14T20:00:00+00:00", "value": "1100", "approval_status": "Provisional"}},
                      {"properties": {"monitoring_location_id": "USGS-02105500", "parameter_code": "00045", "time": "2026-10-14T20:30:00+00:00", "value": "0.00"}},
                      {"properties": {"monitoring_location_id": "USGS-02105500", "parameter_code": "00060", "time": "2026-10-14T19:00:00+00:00", "value": None}}]}
    N = {"lid": "STPN7", "name": "Cape Fear River at W.O. Huske Lock", "status": {"observed": {"primary": 33.49, "validTime": "2026-10-14T20:00:00Z", "floodCategory": "no_flooding"}},
         "flood": {"categories": {"major": {"stage": 65, "flow": -9999}, "minor": {"stage": 42, "flow": -9999}, "action": {"stage": 41, "flow": -9999}}}}
    u = parse_usgs(U)["02105500"]; assert u["00060"][0] == 1100.0 and u["00065"][0] == 1.4 and "00045" in u
    g = build_gauge(dict(lid="STPN7", site="02105500"), u, N, now); assert not g["stale"] and g["nws"]["flood_category"] == "no_flooding" and g["nws"]["thresholds_ft"] == dict(major=65, minor=42, action=41) and g["usgs"]["discharge_cfs"] == 1100.0
    assert build_gauge(dict(lid="X", site="1"), None, None, now)["stale"] and build_gauge(dict(lid="X", site="1"), None, None, now)["nws"]["flood_category"] == "no_observation"
    assert build_gauge(dict(lid="STPN7", site="02105500"), u, N, now + dt.timedelta(hours=5))["stale"]
    assert usgs_ids(2106500) == ["02106500"] and usgs_ids(210382325)[0] == "0210382325"
    print("selftest OK (trimmed real responses, 2026-10-14)")


if __name__ == "__main__": dict(selftest=selftest)[sys.argv[1]]() if len(sys.argv) > 1 else run()
