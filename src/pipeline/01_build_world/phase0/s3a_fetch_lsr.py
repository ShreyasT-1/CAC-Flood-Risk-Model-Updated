"""Phase0 S3a: fresh IEM LSR pull (geojson API) for pilot bbox, both events. https://mesonet.agron.iastate.edu/geojson/lsr.py?help="""
import requests, geopandas as gpd, pandas as pd
cs = gpd.read_file("data/phase0/counties.geojson"); x0, y0, x1, y1 = cs.total_bounds
W = {"florence": ("2018-09-10T00:00Z", "2018-10-05T00:00Z"), "matthew": ("2016-10-06T00:00Z", "2016-10-14T00:00Z")}
out = []
for ev, (a, b) in W.items():
    r = requests.get("https://mesonet.agron.iastate.edu/geojson/lsr.geojson", params=dict(west=x0 - .1, east=x1 + .1, south=y0 - .1, north=y1 + .1, sts=a, ets=b), timeout=120)
    print(ev, r.status_code, r.url)
    g = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326); g["event"] = ev; print(len(g), g.columns.tolist()); out.append(g)
g = pd.concat(out, ignore_index=True); g.to_parquet("data/phase0/lsr_raw.parquet")
print(g.groupby("event").typetext.value_counts().to_string())
