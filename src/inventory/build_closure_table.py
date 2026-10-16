"""Unified flood-related road event table, tiers kept separate via source_type. Output: data/derived_new/flood_road_events_unified.{csv,parquet}
source_type: confirmed_closure | water_over_road | structure_damage | storm_report.  A storm_report is NOT a closure.  Usage: python -I src/inventory/build_closure_table.py"""
import os, sys, re, glob, json, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT, A_IDS, B_IDS
from shapely.geometry import Point
os.chdir(ROOT); AR = areas()
CTY_A = {v.upper() for v in A_IDS.values()}; CTY_B = {v.upper() for v in B_IDS.values()}


def area_of(county=None, lat=None, lon=None):
    c = (county or "").upper().replace(" COUNTY", "").strip()
    if c in CTY_A: return "A"
    if c in CTY_B: return "B"
    if lat is not None and pd.notna(lat) and pd.notna(lon):
        p = Point(lon, lat)
        for k in "AB":
            if AR[k][0].contains(p): return k
        for k in "AB":
            if AR[k][1].contains(p): return k + "_buffer"
    return None


# label by date window only; NOT verified against storm tracks
EVENTS = [("Matthew", "2016-10-05", "2016-10-25"), ("Florence", "2018-09-10", "2018-10-31"), ("Michael", "2018-10-10", "2018-10-13"), ("Dorian", "2019-09-04", "2019-09-08"),
          ("Isaias", "2020-08-03", "2020-08-05"), ("Fred", "2021-08-17", "2021-08-19"), ("Ian", "2022-09-30", "2022-10-03"), ("Debby", "2024-08-06", "2024-08-11"),
          ("Helene", "2024-09-25", "2024-10-05"), ("Chantal", "2025-07-05", "2025-07-09")]


def event_of(t):
    if pd.isna(t): return "unknown"
    for n, a, b in EVENTS:
        if pd.Timestamp(a, tz="UTC") <= t <= pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1): return n
    return "unnamed/other"


rows = []
FL = re.compile(r"flood|high water|water (?:over|across|on)|washout|wash out|under water|submerg|overtop", re.I)
ROADW = re.compile(r"\b(road|rd|street|st|highway|hwy|bridge|culvert|intersection|lane|ave|drive|dr)\b", re.I)

# 1. TIMS history + Helene archive
t = pd.read_parquet("data/raw_new/ncdot_tims_history/tims_incidents_history_points.parquet"); t["src"] = "ncdot_tims_history"
h = pd.read_parquet("data/raw_new/ncdot_tims_helene/tims_helene_historical_points.parquet")
for c in ("CreationDate", "StartDateTime", "EndDateTime", "LastUpdateDateTime"):
    if c in h: h[c] = pd.to_datetime(h[c], unit="ms", utc=True, errors="coerce") if pd.api.types.is_numeric_dtype(h[c]) else pd.to_datetime(h[c], utc=True, errors="coerce")
h["src"] = "ncdot_tims_helene_hist"; h = h[~h.Id.isin(t.Id)]
t = pd.concat([t, h.drop(columns=["geometry"], errors="ignore")], ignore_index=True)
txt = t[["Reason", "EventSubType", "EventType", "EventName", "Location"]].fillna("").agg(" | ".join, axis=1)
t = t[txt.str.contains(FL)].copy()
t["area"] = [area_of(c, la, lo) for c, la, lo in zip(t.CountyName.fillna(""), t.Latitude, t.Longitude)]
t = t[t.area.notna()]
closed = (t.Condition.fillna("") == "Closed") | (t.IsFullClosure.fillna("").astype(str).str.lower() == "true")
for r, c in zip(t.itertuples(), closed):
    rows.append(dict(source="NCDOT TIMS incident history (" + r.src + ")", source_type="confirmed_closure" if c else "water_over_road", event=event_of(r.StartDateTime),
                     start_time=r.StartDateTime, end_time=r.EndDateTime,
                     end_time_kind="TIMS EndDateTime (clear time as logged; may be an estimate/stale)" if pd.notna(r.EndDateTime) else "none",
                     lat=r.Latitude, lon=r.Longitude, road_name=" ".join(x for x in [str(r.Road or ""), str(r.Location or "")] if x),
                     county=r.CountyName, area=r.area, geometry_quality="point at DriveNC incident location (route+milepost), not surveyed to the crossing",
                     confidence="medium" if c else "low-medium",
                     detail=f"Condition={r.Condition}; IsFullClosure={r.IsFullClosure}; Reason={str(r.Reason)[:200]}", source_id=f"tims:{r.Id}"))

# 2. IEM LSR
for f in sorted(glob.glob("data/raw_new/iem_lsr_nc/lsr_NC_*.geojson")):
    for x in json.load(open(f))["features"]:
        p = x["properties"]; tt = p["typetext"]; rem = p.get("remark") or ""
        if not (tt in ("FLASH FLOOD", "FLOOD") or FL.search(rem)): continue
        a = area_of(p.get("county"), p["lat"], p["lon"])
        if not a: continue
        ts = pd.Timestamp(p["valid"])
        rows.append(dict(source="IEM Local Storm Reports", source_type="storm_report", event=event_of(ts), start_time=ts, end_time=pd.NaT, end_time_kind="none (report)",
                         lat=p["lat"], lon=p["lon"], road_name="", county=p.get("county"), area=a,
                         geometry_quality="LSR point = reporter/WFO location estimate (often rounded, ~1 km)", confidence="low (report, not closure)",
                         detail=f"{tt}; src={p.get('source')}; road_words_in_remark={bool(ROADW.search(rem))}; remark={rem[:200]}", source_id="lsr:" + str(p.get("product_id"))))

# 3. NCEI Storm Events
for f in sorted(glob.glob("data/raw_new/ncei_storm_events/*.csv.gz")):
    d = pd.read_csv(f, low_memory=False)
    d = d[(d.STATE == "NORTH CAROLINA") & d.EVENT_TYPE.isin(["Flash Flood", "Flood"])]
    for r in d.itertuples():
        a = area_of(r.CZ_NAME if r.CZ_TYPE == "C" else None, r.BEGIN_LAT, r.BEGIN_LON)
        if not a: continue
        m = re.search(r"(-?\d+)$", str(r.CZ_TIMEZONE)); off = int(m.group(1)) if m else -5  # old years: bare "EST"; NC assumed UTC-5 (DST ignored -> up to 1 h error)
        s = pd.to_datetime(r.BEGIN_DATE_TIME, format="%d-%b-%y %H:%M:%S", errors="coerce"); e = pd.to_datetime(r.END_DATE_TIME, format="%d-%b-%y %H:%M:%S", errors="coerce")
        s = (s - pd.Timedelta(hours=off)).tz_localize("UTC") if pd.notna(s) else pd.NaT
        e = (e - pd.Timedelta(hours=off)).tz_localize("UTC") if pd.notna(e) else pd.NaT
        nar = str(r.EVENT_NARRATIVE or "")
        rows.append(dict(source="NCEI Storm Events Database", source_type="storm_report", event=event_of(s), start_time=s, end_time=e,
                         end_time_kind="event end (flood duration), NOT road reopening", lat=r.BEGIN_LAT, lon=r.BEGIN_LON, road_name=str(r.BEGIN_LOCATION or ""),
                         county=r.CZ_NAME, area=a, geometry_quality="point if BEGIN_LAT/LON present else county-wide" if pd.notna(r.BEGIN_LAT) else "county only",
                         confidence="low-medium (report, not closure)",
                         detail=f"{r.EVENT_TYPE}; cause={r.FLOOD_CAUSE}; src={r.SOURCE}; road_words_in_narrative={bool(ROADW.search(nar))}; narrative={nar[:250]}", source_id=f"ncei:{r.EVENT_ID}"))

# 4. OpenFEMA PA (structure_damage; county level, no coordinates, no damage date)
pa = pd.read_csv("data/raw_new/openfema_pa/pa_projects_CD_areasAB.csv")
for r in pa.itertuples():
    rows.append(dict(source="OpenFEMA PA Funded Projects v2", source_type="structure_damage", event=f"DR-{r.disasterNumber} {r.incidentType}",
                     start_time=pd.to_datetime(r.declarationDate, utc=True), end_time=pd.NaT, end_time_kind="none", lat=None, lon=None, road_name=str(r.applicationTitle),
                     county=r.county, area=area_of(r.county), geometry_quality="none (county + applicant only)", confidence="medium that damage occurred; no date/location",
                     detail=f"cat={r.damageCategoryCode} {r.damageCategoryDescrip}; obligated=${r.totalObligated:,.0f}; start_time is DECLARATION date, not damage date", source_id=f"pa:{r.gmProjectId}"))

u = pd.DataFrame(rows)
for c in ("start_time", "end_time"): u[c] = pd.to_datetime(u[c], utc=True, errors="coerce")
u = u.sort_values(["source_type", "start_time"]).reset_index(drop=True)
os.makedirs("data/derived_new", exist_ok=True)
u.to_csv("data/derived_new/flood_road_events_unified.csv", index=False); u.to_parquet("data/derived_new/flood_road_events_unified.parquet")
pd.set_option("display.width", 220)
print(len(u)); print(u.groupby(["source_type", "area"]).size().unstack(fill_value=0))
cc = u[u.source_type == "confirmed_closure"]
print("confirmed closures w/ end_time:", cc.end_time.notna().mean().round(3)); print(cc.groupby(["event", "area"]).size().unstack(fill_value=0))
print(u[u.source_type == "storm_report"].groupby(["event", "area"]).size().unstack(fill_value=0).sort_values("A", ascending=False).head(15))
