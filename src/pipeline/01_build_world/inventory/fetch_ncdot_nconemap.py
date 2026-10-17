"""Download (Area A / B clipped) NG911 centerlines, NCDOT state-maintained roads, NCDOT road inundation points, Helene TIMS history. Usage: python -I src/inventory/fetch_ncdot_nconemap.py [name ...]"""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
from agol import fetch
AR = areas()
NG = "https://services.gis.nc.gov/secure/rest/services/NC1Map_Transportation/FeatureServer/0"
SM = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_StateMaintainedRoadsER/FeatureServer/0"
INU = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_Statewide_Inundation_Points/FeatureServer/%d"
HEL = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/State_Maintained_Historical_TIMS_Incidents_Hurricane_Helene/FeatureServer/%d"
def save(gdf, d, name):
    p = os.path.join(ROOT, "data/raw_new", d); os.makedirs(p, exist_ok=True); f = os.path.join(p, name)
    assert not os.path.exists(f), f + " exists"
    gdf["fetched_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    gdf.to_parquet(f); print("saved", f, len(gdf), flush=True)
want = set(sys.argv[1:])
def on(n): return not want or n in want
if on("ng911"):
    for k in "A":  # area B already served by OSM pilot graph; NG911 for B not fetched
        save(fetch(NG, poly=AR[k][1]), "nc_ng911_centerlines", f"ng911_centerlines_area{k}_buf.parquet")
if on("statemaint"):
    for k in "AB": save(fetch(SM, poly=AR[k][1]), "ncdot_state_maintained_roads", f"state_maintained_roads_area{k}_buf.parquet")
if on("inund"):
    for L, ri in enumerate([10, 25, 50, 100, 500]):
        for k in "AB":
            g = fetch(INU % L, poly=AR[k][1]); g["ri_layer"] = ri
            save(g, "ncdot_inundation_points", f"road_inundation_{ri}yr_area{k}_buf.parquet")
if on("helene"):
    for L, n in ((0, "points"), (1, "lines")): save(fetch(HEL % L), "ncdot_tims_helene", f"tims_helene_historical_{n}.parquet")
if on("fire_osfm"):
    g = fetch("https://services1.arcgis.com/aT1T0pU1ZdpuDk1t/ArcGIS/rest/services/Map_test_pp3/FeatureServer/5", order="FID")
    save(g, "nc_fire_stations_osfm", "nc_fire_stations_osfm_statewide.parquet")
if on("hosp_hifld_mirror"):
    g = fetch("https://services.arcgis.com/XG15cJAlne2vxtgt/ArcGIS/rest/services/Hospitals_hifld/FeatureServer/0", where="STATE='NC'", order="OBJECTID_1")
    save(g, "hifld_hospitals_mirror", "hifld_hospitals_mirror_NC_2021snapshot.parquet")
if on("fire_wake"):
    U = "https://services1.arcgis.com/a7CWfuGP5ZnLYE7I/arcgis/rest/services/FireStations/FeatureServer/0"
    save(fetch(U), "wake_county_fire_stations", "wake_fire_stations.parquet")
