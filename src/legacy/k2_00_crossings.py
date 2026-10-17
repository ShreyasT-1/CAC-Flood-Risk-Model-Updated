"""Kill Test 2, Step 0: build data/derived/crossings.parquet (not supplied, so built here).
Roads  : OSM via osmnx (Overpass) for New Hanover (37129), Brunswick (37019), Pender (37141); motor-vehicle highway classes only.
Reaches: USGS 'Updated CONUS river network attributes and geometry based on NHDPlusV2, E2NHDPlusV2 and NWMv2.1' (ver 3.0, Nov 2024),
         ScienceBase item 65cbbb98d34ef4b119cb37c9 (public S3 copy): enhd_nhdplus_flowlines.gpkg (geometry, key comid) + enhd_nhdplusatts.parquet (streamorde).
         The NWM v3.0 retrospective uses this same reach network; the join is VERIFIED by requiring COMID to exist in chrtout.zarr feature_id.
Crossing = point where an OSM road line intersects a reach line (EPSG:32617 geometry). One row per (road way, reach, intersection point
cluster within 30 m). Output columns: crossing_id, osm_id, name, ref, highway, road_class, bridge, feature_id, stream_order, lat, lon, county.
"""
import time
import numpy as np, pandas as pd, geopandas as gpd
import osmnx as ox
from shapely.geometry import MultiPoint, Point
from shapely.ops import unary_union
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); from common import *

S3 = "prod-is-usgs-sb-prod-publish/65cbbb98d34ef4b119cb37c9"  # public bucket; lazy reads, nothing is downloaded in full
COUNTIES = {"New Hanover": "129", "Brunswick": "019", "Pender": "141"}
CLASS = {"motorway": "primary", "trunk": "primary", "primary": "primary", "motorway_link": "primary", "trunk_link": "primary",
         "primary_link": "primary", "secondary": "secondary", "secondary_link": "secondary", "tertiary": "tertiary", "tertiary_link": "tertiary",
         "unclassified": "local", "residential": "local", "living_street": "local"}


def roads(cs):
    """OSM ways per county (cached per county; Overpass is flaky so retry, and use a long timeout)."""
    ox.settings.requests_timeout = 180
    ox.settings.max_query_area_size = 2.0e8  # ~14 km x 14 km sub-queries so one slow cell cannot stall the county
    ox.settings.overpass_url = "https://overpass-api.de/api"
    ox.settings.overpass_rate_limit = True
    parts = []
    for name, c in COUNTIES.items():
        f = RAW / f"osm_roads_{c}.parquet"
        if not f.exists():
            poly = gpd.GeoSeries([cs[cs.COUNTYFP == c].geometry.union_all().buffer(1500)], crs=32617).to_crs(4326).iloc[0]
            for attempt in range(6):
                try:
                    g = ox.features_from_polygon(poly, tags={"highway": list(CLASS)}); break
                except Exception as e:
                    print(f"{name}: overpass attempt {attempt + 1} failed: {type(e).__name__}", flush=True)
                    time.sleep(30 * (attempt + 1))
            else:
                raise RuntimeError(f"Overpass failed 6x for {name}")
            g = g[g.geometry.geom_type.isin(["LineString", "MultiLineString"])].reset_index()
            for c_ in ("name", "ref", "bridge", "tunnel", "culvert"):
                if c_ not in g.columns:
                    g[c_] = None
            g = g[["id", "name", "ref", "highway", "bridge", "tunnel", "culvert", "geometry"]].rename(columns={"id": "osm_id"})
            g.to_parquet(f)
        parts.append(gpd.read_parquet(f))
    r = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(r.drop_duplicates("osm_id"), crs=4326)


def main():
    cs = gpd.read_file(f"zip://{RAW / 'counties.zip'}")
    cs = cs[(cs.STATEFP == "37") & cs.COUNTYFP.isin(COUNTIES.values())].to_crs(32617)
    area = cs.geometry.union_all()
    rd = roads(cs).to_crs(32617)
    rd["road_class"] = rd.highway.map(CLASS)
    rd = rd[rd.road_class.notna()].copy()
    print("OSM road ways:", len(rd), rd.road_class.value_counts().to_dict(), flush=True)

    minx, miny, maxx, maxy = gpd.GeoSeries([area.buffer(2000)], crs=32617).to_crs(4326).total_bounds
    fl = gpd.read_file(f"/vsicurl/https://{S3}/enhd_nhdplus_flowlines.gpkg", bbox=(minx, miny, maxx, maxy), engine="pyogrio")
    idc = next(c for c in fl.columns if c.lower() == "comid")
    fl = fl.rename(columns={idc: "feature_id"}).to_crs(32617)
    fl["feature_id"] = fl.feature_id.astype("int64")
    at = pd.read_parquet(f"s3://{S3}/enhd_nhdplusatts.parquet", columns=["comid", "streamorde"], storage_options={"anon": True}).rename(columns={"comid": "feature_id", "streamorde": "stream_order"})
    at["feature_id"] = at.feature_id.astype("int64")
    fl = fl.merge(at, on="feature_id", how="left")
    import xarray as xr
    nwm_ids = xr.open_zarr("s3://noaa-nwm-retrospective-3-0-pds/CONUS/zarr/chrtout.zarr", storage_options={"anon": True}).feature_id.values
    n0 = len(fl)
    fl = fl[fl.feature_id.isin(nwm_ids)]
    print(f"flowlines in bbox: {n0}; with a v3.0 retrospective feature_id: {len(fl)}", flush=True)

    j = gpd.sjoin(rd[["osm_id", "name", "ref", "highway", "road_class", "bridge", "geometry"]], fl[["feature_id", "stream_order", "geometry"]],
                  predicate="intersects").drop(columns="index_right")
    rl = fl.set_index("feature_id").geometry
    rows = []
    for r in j.itertuples():
        g = r.geometry.intersection(rl.loc[r.feature_id])
        if g.is_empty:
            continue
        pts = [p for part in getattr(g, "geoms", [g]) for p in ([part] if part.geom_type == "Point" else
               ([Point(c) for c in part.coords[:1]] if hasattr(part, "coords") else []))]
        if not pts:
            continue
        for k in sorted(set(map(tuple, gpd.GeoSeries(pts).apply(lambda p: (round(p.x / 30), round(p.y / 30))).tolist()))):
            sel = [p for p in pts if (round(p.x / 30), round(p.y / 30)) == k]
            c = MultiPoint(sel).centroid
            rows.append({"osm_id": r.osm_id, "name": r.name, "ref": r.ref, "highway": r.highway, "road_class": r.road_class,
                         "bridge": r.bridge, "feature_id": r.feature_id, "stream_order": r.stream_order, "geometry": c})
    x = gpd.GeoDataFrame(rows, crs=32617)
    x["county"] = ""
    for n, c in COUNTIES.items():
        x.loc[x.within(cs[cs.COUNTYFP == c].geometry.union_all()), "county"] = n
    x = x[x.county != ""].reset_index(drop=True)  # crossings inside the three counties only
    ll = x.to_crs(4326)
    x["lon"], x["lat"] = ll.geometry.x, ll.geometry.y
    x.insert(0, "crossing_id", np.arange(len(x)))
    x.to_parquet(DER / "crossings.parquet")
    print("crossings:", len(x), "| by class:", x.road_class.value_counts().to_dict(), "| by county:", x.county.value_counts().to_dict(),
          "| unique reaches:", x.feature_id.nunique(), "| with name or ref:", int((x.name.notna() | x.ref.notna()).sum()))


if __name__ == "__main__":
    main()

