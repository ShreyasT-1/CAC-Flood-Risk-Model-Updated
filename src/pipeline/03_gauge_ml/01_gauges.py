"""Step 1: all NC USGS continuous gauges + NWS flood stage + pilot flag + datum check.
Outputs data/derived/gauges_all.csv, data/derived/datum_check.csv, data/derived/step1_counts.json
"""
import io, json, sys, zipfile
import numpy as np, pandas as pd, requests
from concurrent.futures import ThreadPoolExecutor
from common import *

NC_BBOX = "-84.4,33.8,-75.4,36.7"
NWPS = "https://api.water.noaa.gov/nwps/v1/"
PILOT_COUNTIES = ["New Hanover", "Brunswick", "Pender"]


def usgs_sites():
    f = ogc_items("monitoring-locations", state_code="37", site_type_code="ST")
    sites = pd.DataFrame([{**x["properties"], "lon": x["geometry"]["coordinates"][0],
                           "lat": x["geometry"]["coordinates"][1]} for x in f if x["geometry"]])
    sites = sites[["id", "monitoring_location_name", "county_name", "hydrologic_unit_code",
                   "drainage_area", "lat", "lon"]].rename(columns={"id": "usgs_id"})
    sites["usgs_id"] = sites.usgs_id.str.replace("USGS-", "")
    return sites


def usgs_continuous_meta():
    rows = []
    for pc in ("00060", "00065"):
        for x in ogc_items("time-series-metadata", bbox=NC_BBOX, parameter_code=pc,
                           computation_identifier="Instantaneous"):
            p = x["properties"]
            rows.append({"usgs_id": p["monitoring_location_id"].replace("USGS-", ""), "pc": pc,
                         "begin": p["begin"], "end": p["end"], "primary": p["primary"]})
    m = pd.DataFrame(rows)
    m["begin"], m["end"] = pd.to_datetime(m.begin, utc=True), pd.to_datetime(m.end, utc=True)
    g = m.groupby(["usgs_id", "pc"]).agg(begin=("begin", "min"), end=("end", "max")).unstack("pc")
    g.columns = [f"{'q' if pc == '00060' else 'stage'}_{k}" for k, pc in g.columns]
    return g.reset_index()


def nwps_nc():
    """NWS NWPS gauges in NC -> lid, usgsId, reachId, flood categories, historic crests (cached)."""
    r = get(NWPS + "gauges", {"bbox.xmin": -84.4, "bbox.ymin": 33.8, "bbox.xmax": -75.4,
                              "bbox.ymax": 36.7, "srid": "EPSG_4326"})
    lids = [g["lid"] for g in r.json()["gauges"] if g["state"]["abbreviation"] == "NC"]

    def one(l):
        p = RAW / "nwps" / f"{l}.json"
        if not p.exists():
            p.write_text(json.dumps(get(NWPS + "gauges/" + l).json()))
        return json.loads(p.read_text())
    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(one, lids))


def pilot_flags(sites):
    """in_pilot = gauge inside a pilot county OR its downstream mainstem (NLDI) crosses one."""
    z = RAW / "counties.zip"
    if not z.exists():
        z.write_bytes(requests.get("https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip",
                                   timeout=300).content)
    import geopandas as gpd
    from shapely.geometry import shape
    c = gpd.read_file(f"zip://{z}")
    c = c[(c.STATEFP == "37") & c.NAME.isin(PILOT_COUNTIES)].to_crs(4326)
    poly = c.unary_union
    pts = gpd.GeoSeries(gpd.points_from_xy(sites.lon, sites.lat), crs=4326)
    inside = pts.within(poly).values
    cache = RAW / "nldi_dm"; cache.mkdir(exist_ok=True)

    def downstream(row):
        f = cache / f"{row.usgs_id}.json"
        if not f.exists():
            u = f"https://api.water.usgs.gov/nldi/linked-data/nwissite/USGS-{row.usgs_id}/navigation/DM/flowlines"
            try:
                f.write_text(requests.get(u, params={"distance": 500, "f": "json"}, timeout=120).text)
            except requests.RequestException:
                return None
        try:
            fc = json.loads(f.read_text())["features"]
        except Exception:
            return None  # site not in NLDI
        return any(shape(x["geometry"]).intersects(poly) for x in fc)
    with ThreadPoolExecutor(6) as ex:
        down = list(ex.map(downstream, sites.itertuples()))
    sites["pilot_inside"] = inside
    sites["pilot_downstream"] = down  # None = NLDI lookup failed
    sites["in_pilot"] = inside | pd.Series(down).fillna(False).astype(bool).values
    return sites


def datum_check(g):
    """Compare USGS gage height max within +-3h of up to 5 recent NWPS crests (olddatum=False, 2007+)."""
    rows = []

    def one(r):
        out = []
        crests = [c for c in r["crests"] if not c.get("olddatum") and c["occurredTime"] >= "2007-01-01"
                  and c["occurredTime"] < "2023-12-31" and c.get("stage", -999) > -100]
        for c in sorted(crests, key=lambda c: -c["stage"])[:5]:  # 5 largest = most identifiable events
            t = pd.Timestamp(c["occurredTime"])
            t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
            w = pd.Timedelta(hours=36 if t.hour == 0 and t.minute == 0 else 3)  # date-only crests have no time of day
            try:
                f = ogc_items("continuous", monitoring_location_id=f"USGS-{r['usgs_id']}", parameter_code="00065",
                              time=f"{(t - w):%Y-%m-%dT%H:%M:%SZ}/{(t + w):%Y-%m-%dT%H:%M:%SZ}")
            except Exception:
                continue
            v = [float(x["properties"]["value"]) for x in f if x["properties"]["value"] is not None]
            if v:
                out.append({"usgs_id": r["usgs_id"], "nws_lid": r["lid"], "crest_time": c["occurredTime"],
                            "nws_stage": c["stage"], "usgs_max_gh": max(v)})
        return out
    with ThreadPoolExecutor(4) as ex:
        for o in ex.map(one, g):
            rows += o
    return pd.DataFrame(rows)


if __name__ == "__main__":
    sites, meta = usgs_sites(), usgs_continuous_meta()
    t = sites.merge(meta, on="usgs_id")  # NC stream sites with >=1 continuous instantaneous series
    t["has_q"], t["has_stage"] = t.q_begin.notna(), t.stage_begin.notna()
    lo, hi = pd.Timestamp(START, tz="UTC"), pd.Timestamp("2023-01-31", tz="UTC")
    for k in ("q", "stage"):  # series must overlap the study window
        t[f"{k}_in_window"] = (t[f"{k}_begin"] <= hi) & (t[f"{k}_end"] >= lo)

    nw = nwps_nc()
    nwdf = pd.DataFrame([{"nws_lid": n["lid"], "usgs_id": n.get("usgsId") or None, "nwm_reach_id": n.get("reachId"),
                          "flood_stage_ft": (n.get("flood") or {}).get("categories", {}).get("minor", {}).get("stage"),
                          "action_stage_ft": (n.get("flood") or {}).get("categories", {}).get("action", {}).get("stage")}
                         for n in nw])
    nwdf.loc[nwdf.flood_stage_ft.fillna(-999) <= -900, "flood_stage_ft"] = np.nan
    nwdf = nwdf.dropna(subset=["usgs_id"]).drop_duplicates("usgs_id")
    t = t.merge(nwdf, on="usgs_id", how="left")
    t["has_official_flood_stage"] = t.flood_stage_ft.notna()

    t = pilot_flags(t)

    crest = {n["usgs_id"] if "usgs_id" in n else n.get("usgsId"): n for n in nw}
    cand = [{"usgs_id": r.usgs_id, "lid": r.nws_lid, "crests": (crest[r.usgs_id].get("flood") or {}).get("crests", {}).get("historic", [])}
            for r in t[t.has_official_flood_stage & t.has_stage].itertuples() if r.usgs_id in crest]
    d = datum_check(cand)
    d["diff_ft"] = d.usgs_max_gh - d.nws_stage
    d.to_csv(DER / "datum_check_events.csv", index=False)
    s = d.groupby("usgs_id").agg(n_events=("diff_ft", "size"), median_diff=("diff_ft", "median"),
                                 max_abs_diff=("diff_ft", lambda x: x.abs().max()))
    # ponytail: tolerance 0.5 ft median, >=3 events; datum shifts (e.g. 1-3 ft) are what we want to catch, peak timing noise is not
    s["datum_ok"] = (s.n_events >= 3) & (s.median_diff.abs() <= 0.5)
    s["datum_reason"] = np.where(s.n_events < 3, "fewer than 3 comparable crest events",
                                 np.where(s.median_diff.abs() > 0.5, "median |USGS-NWS| > 0.5 ft", ""))
    t = t.merge(s, on="usgs_id", how="left")
    t.loc[t.has_official_flood_stage & t.has_stage & t.n_events.isna(), ["datum_ok", "datum_reason"]] = [False, "no NWPS crest with USGS gage height"]
    t.to_csv(DER / "gauges_all.csv", index=False)

    cnt = {"nc_stream_sites_total": len(sites), "with_continuous_series": len(t),
           "with_discharge": int(t.has_q.sum()), "with_stage": int(t.has_stage.sum()),
           "with_discharge_in_window": int(t.q_in_window.sum()), "with_stage_in_window": int(t.stage_in_window.sum()),
           "with_official_flood_stage": int(t.has_official_flood_stage.sum()),
           "without_official_flood_stage": int((~t.has_official_flood_stage).sum()),
           "official_stage_and_stage_series": int((t.has_official_flood_stage & t.has_stage).sum()),
           "datum_ok": int((t.datum_ok == True).sum()), "datum_excluded": int((t.datum_ok == False).sum()),
           "in_pilot": int(t.in_pilot.sum()), "pilot_lookup_failed": int(t.pilot_downstream.isna().sum())}
    (DER / "step1_counts.json").write_text(json.dumps(cnt, indent=1))
    print(json.dumps(cnt, indent=1))
