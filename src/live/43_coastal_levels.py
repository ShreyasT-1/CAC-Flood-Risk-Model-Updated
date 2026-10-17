"""Coastal water levels for the sample area: NOAA CO-OPS observed + predicted water level (NAVD88, metres), tide/surge residual, and a labelled persistence outlook.
Verified 2026-10-14 against the CO-OPS docs (api.tidesandcurrents.noaa.gov/api/prod, mdapi): products water_level / predictions, datum=NAVD (offered at these 3 stations), 6-min observed (<= 1 month per request), predictions interval h.
Station facts (mdapi, 2026-10-14): 8658120 Wilmington (obs+pred; UP the Cape Fear River, so its residual also contains river flow), 8658163 Wrightsville Beach (obs+pred; open coast side), 8659084 Southport (predictions ONLY, no observed water level).
Honesty rules baked in: residual = observed - predicted is a *nowcast anomaly*, not a surge forecast; the outlook just holds the latest residual (persistence, flagged synthetic=true); no official NHC/NOS surge guidance is used here. Nothing here says a road is safe.
This shell cannot reach NOAA: run on a machine with internet (or in the GitHub Action). Offline self-test: python src/live/43_coastal_levels.py selftest
Usage: python src/live/43_coastal_levels.py fetch   -> export/sample/coastal.json"""
import sys, json, math, datetime as dt, urllib.request, urllib.parse
API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
STALE = dt.timedelta(hours=3)   # observations older than this are flagged stale
STATIONS = {"8658120": dict(name="Wilmington", obs=True, riverine=True), "8658163": dict(name="Wrightsville Beach", obs=True, riverine=False), "8659084": dict(name="Southport", obs=False, riverine=False)}
def _get(params):
    q = dict(params, units="metric", time_zone="gmt", format="json", application="floodlens_lifelines")
    with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(q), timeout=30) as r: j = json.load(r)
    if "error" in j: raise RuntimeError(j["error"].get("message", str(j["error"])))
    return j
def parse_series(j, key):   # CO-OPS rows: {"t": "YYYY-MM-DD HH:MM", "v": "1.23", ...}; v can be "" (missing)
    out = {}
    for r in j.get(key, []):
        try: v = float(r["v"])
        except (KeyError, ValueError, TypeError): continue
        if not math.isnan(v): out[dt.datetime.strptime(r["t"], "%Y-%m-%d %H:%M")] = v
    return out
def hourly(series):   # mean of obs in each clock hour (obs are 6-min), keyed by the hour start
    acc = {}
    for t, v in series.items(): acc.setdefault(t.replace(minute=0), []).append(v)
    return {h: sum(v) / len(v) for h, v in acc.items()}
def build_station(sid, obs_json, pred_json, now):
    s = STATIONS[sid]; pred = {t.replace(minute=0): v for t, v in parse_series(pred_json, "predictions").items() if t.minute == 0}
    obs = hourly(parse_series(obs_json, "data")) if obs_json else {}
    res = {h: round(obs[h] - pred[h], 3) for h in obs if h in pred}; hrs = sorted(set(pred) | set(obs)); last_res_t = max(res) if res else None
    rows = []
    for h in hrs:
        r = dict(t=h.strftime("%Y-%m-%dT%H:00Z"), tide_pred_m_navd88=round(pred[h], 3) if h in pred else None)
        if h in obs: r.update(observed_m_navd88=round(obs[h], 3), residual_m=res.get(h), mode="NOWCAST", synthetic=False, stale=(now - h) > STALE)
        elif h > now.replace(minute=0) and h in pred and last_res_t is not None: r.update(outlook_total_m_navd88=round(pred[h] + res[last_res_t], 3), mode="OUTLOOK-PERSISTENCE", synthetic=True)   # persistence
        rows.append(r)
    return dict(id=sid, name=s["name"], has_observations=bool(obs), riverine_influence=s["riverine"], latest_observed_time=max(obs).strftime("%Y-%m-%dT%H:00Z") if obs else None, stale=(not obs) or (now - max(obs)) > STALE, latest_residual_m=res.get(last_res_t), latest_residual_time=last_res_t.strftime("%Y-%m-%dT%H:00Z") if last_res_t else None, hourly=rows)
def exposure(total_m, crest_m, band_m=0.30):
    """Compare a water level with a road crest. band_m = allowance for lidar vertical error + datum + station-to-site tide difference (not measured here). Never returns 'safe'."""
    if crest_m is None or total_m is None: return "no_elevation_data"
    m = crest_m - total_m
    return "water_at_or_above_crest" if m <= 0 else "within_uncertainty_band" if m <= band_m else "crest_above_water_in_this_scenario"
def fetch():
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None); b = (now - dt.timedelta(hours=48)).strftime("%Y%m%d %H:%M"); e = now.strftime("%Y%m%d %H:%M"); pe = (now + dt.timedelta(hours=72)).strftime("%Y%m%d %H:%M"); out = []
    for sid, s in STATIONS.items():
        pj = _get(dict(station=sid, product="predictions", datum="NAVD", interval="h", begin_date=b, end_date=pe)); oj = None
        if s["obs"]:
            try: oj = _get(dict(station=sid, product="water_level", datum="NAVD", begin_date=b, end_date=e))
            except RuntimeError as ex: print("observed unavailable", sid, ex)
        out.append(build_station(sid, oj, pj, now))
    doc = dict(sample=False, mode="NOWCAST", stale=not any(s["has_observations"] and not s["stale"] for s in out), stale_after_hours=3, generated_at=now.strftime("%Y-%m-%dT%H:%MZ"), datum="NAVD88, metres", source="NOAA CO-OPS (api.tidesandcurrents.noaa.gov)",
               caveats=["Residual = observed minus predicted tide. It is a nowcast anomaly, not a surge forecast.", "Outlook holds the latest residual constant (persistence): a placeholder, NOT surge guidance (synthetic: true).", "Wilmington is up the Cape Fear River; its residual includes river flow and is not pure surge.", "Southport has predictions only (no observed water level).", "Does not include wave run-up, rain/drainage flooding, or river-surge interaction.", "Road elevation comparison uses lidar crest with an allowance band; this comparison is never an all-clear for any road."], outlook_synthetic=True, stations=out)
    json.dump(doc, open("export/sample/coastal.json", "w"), indent=1); print("wrote export/sample/coastal.json", [(s["name"], len(s["hourly"]), s["latest_residual_m"]) for s in out])
def selftest():   # fixtures follow the documented CO-OPS JSON shape; NOT real data
    now = dt.datetime(2026, 10, 14, 12, 0); P = {"predictions": [{"t": (now + dt.timedelta(hours=h)).strftime("%Y-%m-%d %H:%M"), "v": f"{0.5 + 0.4 * math.sin(h / 2):.3f}"} for h in range(-6, 7)]}
    O = {"data": [{"t": (now + dt.timedelta(minutes=6 * k)).strftime("%Y-%m-%d %H:%M"), "v": f"{0.5 + 0.4 * math.sin((k / 10) / 2) + 0.25:.3f}", "q": "p"} for k in range(-60, 1)] + [{"t": "2026-10-14 12:00", "v": ""}]}
    st = build_station("8658163", O, P, now); assert st["has_observations"] and abs(st["latest_residual_m"] - 0.25) < 0.02, st["latest_residual_m"]
    assert any("outlook_total_m_navd88" in r for r in st["hourly"]) and not st["riverine_influence"]
    assert build_station("8659084", None, P, now)["latest_residual_m"] is None and not any("outlook_total_m_navd88" in r for r in build_station("8659084", None, P, now)["hourly"])
    assert exposure(1.0, 0.8) == "water_at_or_above_crest" and exposure(1.0, 1.2) == "within_uncertainty_band" and exposure(1.0, 2.0) == "crest_above_water_in_this_scenario" and exposure(1.0, None) == "no_elevation_data"
    # real CO-OPS water_level rows captured 2026-10-14 (station 8658163): extra keys s/f/q, 6-min stamps, no "error"
    R = {"metadata": {"id": "8658163"}, "data": [{"t": "2026-10-14 20:54", "v": "-0.371", "s": "0.011", "f": "1,0,0,0", "q": "p"}, {"t": "2026-10-14 21:00", "v": "-0.368", "s": "0.012", "f": "1,0,0,0", "q": "p"}, {"t": "2026-10-14 21:06", "v": "-0.366", "s": "0.01", "f": "1,0,0,0", "q": "p"}]}
    assert list(parse_series(R, "data").values()) == [-0.371, -0.368, -0.366]
    old = build_station("8658163", R, P, dt.datetime(2026, 10, 15, 3, 0)); assert old["stale"] and not build_station("8658163", R, P, dt.datetime(2026, 10, 14, 21, 30))["stale"]
    print("selftest OK (fixtures, not live data)")
if __name__ == "__main__": dict(fetch=fetch, selftest=selftest)[sys.argv[1]]()
