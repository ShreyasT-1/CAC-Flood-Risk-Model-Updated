"""Phase1 step 3a: origins (2020 Census block centroids + population, 3 pilot counties), hospitals (CMS Hospital General Information, geocoded with the Census geocoder), fire stations (OSM; HIFLD not confirmed available)."""
import zipfile, time, json, requests, numpy as np, pandas as pd, geopandas as gpd, osmium
from shapely.geometry import Point
R = "data/phase1/raw/"; O = "data/phase1/"
CTY = {"37129": "New Hanover", "37019": "Brunswick", "37141": "Pender"}
# --- origins: block geo records (SUMLEV 750) joined to P0010001 on LOGRECNO
z = zipfile.ZipFile(R + "nc2020.pl.zip"); geo = {}
pop, lat, lon = {}, {}, {}
for ln in z.open("ncgeo2020.pl"):
    f = ln.decode("latin1").split("|")
    if f[2] == "750" and f[8][-15:-10] in CTY: geo[f[7]] = f[8][-15:]; lat[f[7]] = float(f[-5]); lon[f[7]] = float(f[-4])
for ln in z.open("nc000012020.pl"):
    f = ln.decode("latin1").split("|")
    if f[4] in geo: pop[f[4]] = int(f[5])
B = pd.DataFrame({"geoid20": pd.Series(geo), "pop20": pd.Series(pop), "lat": pd.Series(lat), "lon": pd.Series(lon)}).reset_index(drop=True)
B["county_fp"] = B.geoid20.str[:5]; B["county"] = B.county_fp.map(CTY)
B = gpd.GeoDataFrame(B, geometry=gpd.points_from_xy(B.lon, B.lat), crs=4326); B.to_parquet(O + "origins_blocks.parquet")
print("blocks", len(B), "populated", int((B.pop20 > 0).sum()), "pop", B.groupby("county").pop20.sum().to_dict())
# --- hospitals
H = pd.read_csv(R + "Hospital_General_Information.csv", dtype=str)
near = ["NEW HANOVER", "BRUNSWICK", "PENDER", "COLUMBUS", "BLADEN", "ONSLOW", "DUPLIN", "SAMPSON", "HORRY", "GEORGETOWN", "ROBESON", "CUMBERLAND", "JONES", "CRAVEN"]
H = H[((H.State == "NC") | (H.State == "SC")) & H["County/Parish"].str.upper().isin(near)].copy()
print("candidate hospitals (nearby counties, NC/SC)", len(H), "with emergency services:", int((H["Emergency Services"] == "Yes").sum()))
rows = []
for _, r in H.iterrows():
    a = f'{r["Address"]}, {r["City/Town"]}, {r["State"]} {r["ZIP Code"]}'; x = y = np.nan; matched = ""
    try:
        j = requests.get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress", params=dict(address=a, benchmark="Public_AR_Current", format="json"), timeout=60).json()
        m = j["result"]["addressMatches"]
        if m: x, y, matched = m[0]["coordinates"]["x"], m[0]["coordinates"]["y"], m[0]["matchedAddress"]
    except Exception as e: matched = f"error:{type(e).__name__}"
    rows.append(dict(facility_id=r["Facility ID"], name=r["Facility Name"], address=a, county=r["County/Parish"], state=r.State, hospital_type=r["Hospital Type"], emergency=r["Emergency Services"], lat=y, lon=x, geocode_match=matched)); time.sleep(.2)
Hs = pd.DataFrame(rows); Hs.to_csv(O + "hospitals_geocoded.csv", index=False); print("geocoded", int(Hs.lat.notna().sum()), "of", len(Hs)); print(Hs[Hs.lat.isna()][["name", "address", "geocode_match"]].to_string())
# --- fire stations from OSM pbf
cs = gpd.read_file("data/phase0/counties.geojson"); x0, y0, x1, y1 = cs.total_bounds; x0 -= .15; y0 -= .15; x1 += .15; y1 += .15
fs = []
for o in osmium.FileProcessor("data/raw/nc.osm.pbf").with_locations().with_filter(osmium.filter.KeyFilter("amenity")):
    if o.tags.get("amenity") != "fire_station": continue
    try:
        if o.is_node(): p = (o.location.lon, o.location.lat)
        elif o.is_way(): ns = [(n.lon, n.lat) for n in o.nodes]; p = (np.mean([a for a, b in ns]), np.mean([b for a, b in ns]))
        else: continue
    except Exception: continue
    if x0 < p[0] < x1 and y0 < p[1] < y1: fs.append(dict(osm_id=o.id, kind="node" if o.is_node() else "way", name=o.tags.get("name"), operator=o.tags.get("operator"), lon=p[0], lat=p[1]))
F = pd.DataFrame(fs); F.to_csv(O + "fire_stations_osm.csv", index=False); print("OSM fire stations in pilot bbox +0.15deg", len(F), "named", int(F.name.notna().sum()))
