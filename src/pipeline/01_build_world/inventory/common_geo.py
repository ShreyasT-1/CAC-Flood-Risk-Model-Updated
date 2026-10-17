import os, geopandas as gpd
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
A_IDS = {"37183": "Wake", "37063": "Durham", "37135": "Orange"}
B_IDS = {"37129": "New Hanover", "37019": "Brunswick", "37141": "Pender"}
def areas():
    """-> dict name -> (county_union, buffered) in EPSG:4326. A buffer 10 km, B buffer 40 km (UTM17N)."""
    c = gpd.read_file("zip://" + os.path.join(ROOT, "data/raw_new/census_counties/cb_2024_us_county_500k.zip")).to_crs(32617)
    o = {}
    for n, ids, b in (("A", A_IDS, 10_000), ("B", B_IDS, 40_000)):
        u = c[c.GEOID.isin(ids)].geometry.union_all()
        f = lambda g: gpd.GeoSeries([g], crs=32617).to_crs(4326).iloc[0]
        o[n] = (f(u), f(u.buffer(b)))
    return o
