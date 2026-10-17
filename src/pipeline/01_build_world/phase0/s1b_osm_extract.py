"""Phase0 S1b: one pass over data/raw/nc.osm.pbf (Geofabrik NC extract, read-only) -> roads + waterways inside pilot bbox+buffer. No Overpass."""
import osmium, geopandas as gpd
from shapely.geometry import LineString
cs = gpd.read_file("data/phase0/counties.geojson"); x0, y0, x1, y1 = cs.total_bounds
x0 -= .03; y0 -= .03; x1 += .03; y1 += .03
ROAD = {"motorway","trunk","primary","secondary","tertiary","unclassified","residential","living_street","motorway_link","trunk_link","primary_link","secondary_link","tertiary_link","service"}
WW = {"river","stream","canal","ditch","drain","tidal_channel"}
roads, ww = [], []
for o in osmium.FileProcessor("data/raw/nc.osm.pbf").with_locations().with_filter(osmium.filter.KeyFilter("highway","waterway")):
    if not o.is_way(): continue
    t = o.tags; h, w = t.get("highway"), t.get("waterway")
    if not ((h in ROAD) or (w in WW)): continue
    try: pts = [(n.lon, n.lat) for n in o.nodes]
    except Exception: continue
    if len(pts) < 2 or not (x0 < pts[0][0] < x1 and y0 < pts[0][1] < y1): continue
    g = LineString(pts)
    if h in ROAD:
        roads.append(dict(osm_id=o.id, name=t.get("name"), ref=t.get("ref"), highway=h, bridge=t.get("bridge"), tunnel=t.get("tunnel"), culvert=t.get("culvert"), geometry=g))
    else:
        ww.append(dict(osm_id=o.id, name=t.get("name"), waterway=w, tunnel=t.get("tunnel"), culvert=t.get("culvert"), intermittent=t.get("intermittent"), geometry=g))
gpd.GeoDataFrame(roads, crs=4326).to_parquet("data/phase0/osm_roads.parquet")
gpd.GeoDataFrame(ww, crs=4326).to_parquet("data/phase0/osm_waterways.parquet")
print(len(roads), len(ww))
