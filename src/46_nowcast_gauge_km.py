"""Which gauges the public NOWCAST shows. Usage (repo root): python src/46_nowcast_gauge_km.py   (needs geopandas; run once, commit the csv)
Rule (fixed here, stated on the site): a gauge is shown if it is within 40 km of New Hanover, Brunswick or Pender county (straight-line, EPSG:32119). The other `in_pilot` gauges
(upstream in the Cape Fear basin: Fayetteville, Greensboro, Chapel Hill, ...) stay in nowcast.json under `other_basin_gauges`, not in the public list.
Writes config/nowcast_gauges.csv (nws_lid, pilot_km, public). Inputs: config/reaches.csv, data/derived/gauges_all.csv, data/phase0/counties.geojson."""
import geopandas as gpd, pandas as pd

KM = 40
c = gpd.read_file("data/phase0/counties.geojson").to_crs(32119).union_all()
g = pd.read_csv("data/derived/gauges_all.csv"); R = pd.read_csv("config/reaches.csv")
p = R[R.in_pilot & R.usgs_ids.notna() & R.nws_lid.notna()].merge(g[["nws_lid", "lat", "lon"]], on="nws_lid")
p["pilot_km"] = (gpd.GeoSeries(gpd.points_from_xy(p.lon, p.lat), crs=4326).to_crs(32119).distance(c) / 1000).round(1)
p["public"] = p.pilot_km <= KM
p[["nws_lid", "pilot_km", "public"]].sort_values("pilot_km").to_csv("config/nowcast_gauges.csv", index=False)
print(p.public.sum(), "public of", len(p), "| largest public km", p[p.public].pilot_km.max(), "| smallest excluded km", p[~p.public].pilot_km.min())
