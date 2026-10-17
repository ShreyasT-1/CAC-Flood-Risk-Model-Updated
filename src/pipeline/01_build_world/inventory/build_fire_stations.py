"""Fire stations for Area A (+10 km) and B (+40 km): NC OSFM statewide layer (hosted copy, snapshot 2024-11-04) cross-checked against OSM amenity=fire_station and the earlier OSM-only pilot list.
Output data/derived_new/fire_stations_AB.csv. 'active' = listed by OSFM 9S rating program as of snapshot date (OSFM definition: 'all active fire stations'); OSM-only stations are 'unverified'.
Usage: python -I src/pipeline/01_build_world/inventory/build_fire_stations.py"""
import os, sys, pandas as pd, geopandas as gpd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import areas, ROOT
os.chdir(ROOT); AR = areas()
of = gpd.read_parquet("data/raw_new/nc_fire_stations_osfm/nc_fire_stations_osfm_statewide.parquet")
of = of.set_geometry(gpd.points_from_xy(of.LONGITUDE, of.LATITUDE), crs=4326)
print("OSFM rows", len(of), "null coords", of.LATITUDE.isna().sum(), "exact-duplicate coords", of.duplicated(["LATITUDE", "LONGITUDE"]).sum())
of["area"] = [("A" if AR["A"][1].contains(p) else "B" if AR["B"][1].contains(p) else None) for p in of.geometry]
of = of[of["area"].notna()].copy()
osm = gpd.read_parquet("data/derived_new/osm_extract/osm_firestations_hospitals_AB_buf.parquet"); osm = osm[osm.amenity == "fire_station"].copy()
osm["geometry"] = [g if g.geom_type == "Point" else g.representative_point() for g in osm.geometry]
osm = osm[~(osm.disused.notna() | osm.abandoned.notna() | osm["was:amenity"].notna())]
ou, mu = of.to_crs(32617), osm.to_crs(32617)
rows = []
used = set()
for r, g in zip(of.itertuples(), ou.geometry):
    d = mu.distance(g); j = d.idxmin() if len(d) else None
    near = j is not None and d[j] <= 300
    if near: used.add(j)
    rows.append(dict(name=f"{r.DEPT_NAME.strip()} Sta {r.STATION_NU}", address=r.STATION_AD, city=r.CITY, county=r.COUNTY, lat=r.LATITUDE, lon=r.LONGITUDE, area=r.area, source="OSFM (hosted copy)", source_id=f"fd{r.FD_ID}-{r.STATION_NU}",
                     active="yes (listed by OSFM)", active_source="NC OSFM 9S program layer; hosted copy last edited 2024-11-04", osm_match_within_300m=bool(near)))
for j, r in osm.iterrows():
    if j in used: continue
    rows.append(dict(name=r["name"], address=None, city=r.get("addr:city"), county=None, lat=r.geometry.y, lon=r.geometry.x, area=r.area, source="OSM", source_id=f"osm:{r.osm_id}", active="unverified (OSM only, no OSFM match within 300 m)",
                     active_source="OSM extract 2026-10-09 (disused/abandoned-tagged removed)", osm_match_within_300m=True))
d = pd.DataFrame(rows)
# Wake County GIS (CC BY 4.0, item modified 2026-09-28) = most current source for Wake; flag OSFM Wake stations with no county station within 500 m
wk = gpd.read_parquet("data/raw_new/wake_county_fire_stations/wake_fire_stations.parquet").to_crs(32617)
dd = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(32617)
isw = dd.county.fillna("").str.upper().eq("WAKE") & dd.source.str.startswith("OSFM")
d["wake_gis_match_500m"] = None
d.loc[isw, "wake_gis_match_500m"] = [bool((wk.distance(g) <= 500).any()) for g in dd.geometry[isw]]
wkused = {i for g in dd.geometry[isw] for i in wk.index[wk.distance(g) <= 500]}
wk4 = wk.to_crs(4326)
d = pd.concat([d, pd.DataFrame([dict(name=r.LABEL, address=r.LOCATION, city=r.CITY, county="Wake", lat=r.geometry.y, lon=r.geometry.x, area="A" if AR["A"][1].contains(r.geometry) else None, source="Wake County GIS", source_id=f"wake:{r.STATIONID}",
    active="yes (county-published)", active_source="Wake County open data FireStations, item modified 2026-09-28", osm_match_within_300m=None) for r in wk4.itertuples() if r.Index not in wkused])], ignore_index=True)
print("OSFM Wake stations with NO Wake-GIS station within 500 m (possible closed/moved/merged):", int((d.wake_gis_match_500m == False).sum()), "| Wake-GIS stations with NO OSFM within 500 m (added):", int((d.source == "Wake County GIS").sum()), "of", len(wk))
# duplicate check within 100 m (same station listed twice)
g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(32617)
sj = gpd.sjoin(g, g[["geometry"]].assign(i2=g.index), predicate="dwithin", distance=100).query("index != i2")
d["possible_dup_within_100m"] = d.index.isin(sj.index)
d.to_csv("data/derived_new/fire_stations_AB.csv", index=False)
print(d.groupby(["area", "source"]).size().unstack(fill_value=0))
o_ = d[d.source.str.startswith("OSFM")]; print("OSFM stations with no OSM station within 300 m:", o_[~o_.osm_match_within_300m.astype(bool)].groupby("area").size().to_dict(), "of", o_.groupby("area").size().to_dict())
print("possible duplicates within 100m:", int(d.possible_dup_within_100m.sum()))
prev = pd.read_csv("handoff_for_shreyas/06_facilities/fire_stations_40km.csv"); print("pilot (OSM-based) list rows", len(prev), "vs B total now", int((d.area == "B").sum()))
