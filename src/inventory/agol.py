"""Paged ArcGIS REST query helper. Never overwrites outputs."""
import json, time, requests, geopandas as gpd, pandas as pd
S = requests.Session(); S.headers["User-Agent"] = "FloodLens-student-research/1.0"
def _get(url, params, post=False):
    for k in range(6):
        try:
            r = (S.post if post else S.get)(url, **({"data": params} if post else {"params": params}), timeout=180)
            j = r.json()
            if "error" in j: raise RuntimeError(j["error"])
            return j
        except Exception as e:
            if k == 5: raise
            time.sleep(8 * (k + 1))
def fetch(layer_url, where="1=1", poly=None, out_fields="*", out_sr=4326, page=2000, geom=True, order="OBJECTID"):
    """layer_url = .../FeatureServer/N ; poly = shapely polygon in EPSG:4326 (intersects) -> GeoDataFrame (or DataFrame if geom False)."""
    p = dict(where=where, outFields=out_fields, returnGeometry=str(geom).lower(), outSR=out_sr, f="geojson", resultRecordCount=page, orderByFields=order)
    if poly is not None:
        p.update(geometry=json.dumps({"rings": [list(map(list, poly.exterior.coords))], "spatialReference": {"wkid": 4326}}), geometryType="esriGeometryPolygon", inSR=4326, spatialRel="esriSpatialRelIntersects")
    feats, off = [], 0
    while True:
        p["resultOffset"] = off
        j = _get(layer_url + "/query", p, post=True)
        f = j.get("features", []); feats += f; off += len(f)
        if not f or not (j.get("exceededTransferLimit") or j.get("properties", {}).get("exceededTransferLimit")): break
    if not feats: return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(feats, crs=4326)
