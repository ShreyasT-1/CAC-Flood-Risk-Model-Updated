"""Kill Test 2, Step 0a: fallback road source when Overpass is down. Reads the Geofabrik NC extract (data/raw/nc.osm.pbf) and writes the same
per-county files k2_00_crossings.py caches (data/raw/osm_roads_{019,141}.parquet; 129 already came from Overpass)."""
import osmium, geopandas as gpd
from shapely.geometry import LineString
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); from common import *
from k2_00_crossings import CLASS, COUNTIES

cs = gpd.read_file(f"zip://{RAW / 'counties.zip'}")
cs = cs[(cs.STATEFP == "37") & cs.COUNTYFP.isin(COUNTIES.values())].to_crs(32617)
rows = []
for o in osmium.FileProcessor(str(RAW / "nc.osm.pbf")).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
    if o.is_way() and o.tags["highway"] in CLASS:
        try:
            g = LineString([(n.lon, n.lat) for n in o.nodes])
        except Exception:
            continue
        if len(g.coords) > 1 and 33.6 < g.coords[0][1] < 34.8 and -79.2 < g.coords[0][0] < -77.3:
            rows.append({"osm_id": o.id, "name": o.tags.get("name"), "ref": o.tags.get("ref"), "highway": o.tags["highway"],
                         "bridge": o.tags.get("bridge"), "tunnel": o.tags.get("tunnel"), "culvert": o.tags.get("culvert"), "geometry": g})
a = gpd.GeoDataFrame(rows, crs=4326).to_crs(32617)
for name, c in COUNTIES.items():
    f = RAW / f"osm_roads_{c}.parquet"
    if f.exists():
        continue
    poly = cs[cs.COUNTYFP == c].geometry.union_all().buffer(1500)
    a[a.intersects(poly)].to_crs(4326).to_parquet(f)
    print(name, int(a.intersects(poly).sum()), "ways")
