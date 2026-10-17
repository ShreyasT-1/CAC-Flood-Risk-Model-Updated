"""Phase1b step 2a: facilities within 40 km of the 3-county boundary.
Hospitals: CMS Hospital General Information (all NC+SC records) geocoded with the Census geocoder (cached), kept if within 40 km of the boundary; ED flag = CMS 'Emergency Services'. Source recorded per row.
Fire stations: (a) OSM amenity=fire_station from the Geofabrik NC + SC extracts, (b) USGS National Map 'Fire Stations/EMS Stations' layer (carto.nationalmap.gov structures/MapServer/51, 2021-vintage).
Both kept, source recorded; stations from different sources within 150 m are merged (source = 'osm+usgs'). Reports how many were added vs the Phase 1 sets."""
import os, time, json, requests, numpy as np, pandas as pd, geopandas as gpd, osmium
O = "data/phase1b/"; os.makedirs(O, exist_ok=True); U = 32617
cs = gpd.read_file("data/phase0/counties.geojson").to_crs(U); bnd = cs.union_all(); zone = bnd.buffer(40000)
zll = gpd.GeoSeries([zone], crs=U).to_crs(4326).iloc[0]; x0, y0, x1, y1 = zll.bounds
# ---- hospitals
H = pd.read_csv("data/phase1/raw/Hospital_General_Information.csv", dtype=str); H = H[H.State.isin(["NC", "SC"])].copy(); cache = O + "hospital_geocode_cache.csv"
G = pd.read_csv(cache, dtype={"facility_id": str}) if os.path.exists(cache) else pd.DataFrame(columns=["facility_id", "lat", "lon", "geocode_match"])
prev = pd.read_csv("data/phase1/hospitals_geocoded.csv", dtype={"facility_id": str})[["facility_id", "lat", "lon", "geocode_match"]]
G = pd.concat([G, prev]).drop_duplicates("facility_id"); todo = H[~H["Facility ID"].isin(G.facility_id)]
print("hospitals NC+SC", len(H), "already geocoded", len(H) - len(todo), "to geocode", len(todo), flush=True); new = []
for _, r in todo.iterrows():
    a = f'{r["Address"]}, {r["City/Town"]}, {r["State"]} {r["ZIP Code"]}'; x = y = np.nan; m = ""
    try:
        j = requests.get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress", params=dict(address=a, benchmark="Public_AR_Current", format="json"), timeout=60).json()["result"]["addressMatches"]
        if j: x, y, m = j[0]["coordinates"]["x"], j[0]["coordinates"]["y"], j[0]["matchedAddress"]
    except Exception as e: m = f"error:{type(e).__name__}"
    new.append(dict(facility_id=r["Facility ID"], lat=y, lon=x, geocode_match=m)); time.sleep(.15)
G = pd.concat([G, pd.DataFrame(new)]).drop_duplicates("facility_id"); G.to_csv(cache, index=False)
H = H.merge(G, left_on="Facility ID", right_on="facility_id", how="left")
Hg = gpd.GeoDataFrame(H, geometry=gpd.points_from_xy(H.lon, H.lat), crs=4326).to_crs(U)
Hg["dist_to_boundary_km"] = Hg.geometry.distance(bnd) / 1000; ungeo = Hg[Hg.lat.isna()]
Hk = Hg[Hg.lat.notna() & (Hg.dist_to_boundary_km <= 40)].copy()
Hk = Hk.rename(columns={"Facility Name": "name", "Emergency Services": "ed_cms", "Hospital Type": "hospital_type", "County/Parish": "county"})
Hk["ed"] = Hk.ed_cms.eq("Yes"); Hk["source"] = "CMS Hospital General Information (geocoded: Census geocoder)"
Hk["is_behavioral_or_nonacute"] = ~Hk.hospital_type.fillna("").str.contains("Acute Care|Critical Access", case=False)
Hk[["facility_id", "name", "county", "State", "hospital_type", "ed", "is_behavioral_or_nonacute", "dist_to_boundary_km", "lat", "lon", "source", "geocode_match"]].to_csv(O + "hospitals_40km.csv", index=False)
print("hospitals within 40 km of boundary:", len(Hk), "| ED=yes:", int(Hk.ed.sum()), "| ED=yes & acute/critical-access:", int((Hk.ed & ~Hk.is_behavioral_or_nonacute).sum()), "| not geocoded (all NC+SC):", len(ungeo),
      "| of those not geocoded, names:", ungeo["Facility Name"].head(12).tolist())
print("added vs Phase 1 (4 ED hospitals inside the 10 km buffer):", int((Hk.ed & ~Hk.is_behavioral_or_nonacute).sum()) - 4, "acute ED hospitals")
# ---- fire stations
fs = []
for pbf in ("data/raw/nc.osm.pbf", "data/phase1b/raw/south-carolina-latest.osm.pbf"):
    if not os.path.exists(pbf): print("MISSING", pbf, "(SC stations not included)"); continue
    for o in osmium.FileProcessor(pbf).with_locations().with_filter(osmium.filter.KeyFilter("amenity")):
        if o.tags.get("amenity") != "fire_station": continue
        try:
            if o.is_node(): p = (o.location.lon, o.location.lat)
            elif o.is_way(): ns = [(n.lon, n.lat) for n in o.nodes]; p = (float(np.mean([a for a, b in ns])), float(np.mean([b for a, b in ns])))
            else: continue
        except Exception: continue
        if x0 < p[0] < x1 and y0 < p[1] < y1: fs.append(dict(name=o.tags.get("name"), lon=p[0], lat=p[1], source="OSM", src_id=f"osm_{o.id}"))
B = "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/51/query"
r = requests.get(B, params=dict(where="1=1", geometry=f"{x0},{y0},{x1},{y1}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects", outFields="NAME,FCODE,STATE,ADDRESS,CITY,SOURCE_DATADESC", returnGeometry="true", outSR=4326, f="json", resultRecordCount=2000), timeout=120).json()
for f in r.get("features", []):
    a_ = {k.upper(): v for k, v in f["attributes"].items()}   # service returns lowercase keys
    fs.append(dict(name=a_["NAME"], lon=f["geometry"]["x"], lat=f["geometry"]["y"], source="USGS National Map (HIFLD-derived, 2021)", src_id=f"usgs_{a_['FCODE']}", fcode=a_["FCODE"]))
F = pd.DataFrame(fs); Fg = gpd.GeoDataFrame(F, geometry=gpd.points_from_xy(F.lon, F.lat), crs=4326).to_crs(U); Fg = Fg[Fg.geometry.within(zone)].copy()
print("fire/EMS records inside 40 km zone: OSM", int((Fg.source == "OSM").sum()), "USGS", int(Fg.source.str.startswith("USGS").sum()), "| USGS FCODEs:", Fg[Fg.source.str.startswith("USGS")].fcode.value_counts().to_dict())
# all USGS records kept (FCODE mix printed above; the layer is "Fire Stations/EMS Stations" - EMS-only sites cannot be separated without a verified code table)
Fg["merged"] = False; keep = []
usgs = Fg[Fg.source.str.startswith("USGS")]; osm = Fg[Fg.source == "OSM"]; tree = usgs.sindex
for i, r in osm.iterrows():
    hit = tree.query(r.geometry.buffer(150), predicate="intersects")
    if len(hit): usgs_i = usgs.index[hit[0]]; Fg.loc[usgs_i, "merged"] = True; Fg.loc[i, "merged"] = True
Fg["source_final"] = np.where(Fg.merged, "osm+usgs", Fg.source)
out = Fg[~((Fg.source == "OSM") & Fg.merged)].copy(); out["source"] = out.source_final
out.to_crs(4326)[["name", "source", "src_id", "lon", "lat"]].to_csv(O + "fire_stations_40km.csv", index=False)
print("fire stations after merge:", len(out), out.source.value_counts().to_dict(), "| Phase 1 had 40 OSM stations inside the 10 km buffer")
