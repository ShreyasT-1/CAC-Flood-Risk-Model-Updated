# Phase 0 sources (fetched 2026-10-10)

Every URL below was fetched/queried during Phase 0; field names were read from the live service or file, not assumed.

## Spike 1 - crossings / reaches
| What | URL | Notes |
|---|---|---|
| NWM RouteLink (official, NOAA NCO) | https://www.nco.ncep.noaa.gov/pmb/codes/nwprod/nwm.v3.1.6/parm/domain/RouteLink_CONUS.nc | 269,369,766 B. **Only v3.1.6 is listed on the official directory; no v3.0 file found there.** Variables read: link, order, Length, So, NHDWaterbodyComID, gages, lat, lon. It has ONE midpoint per reach, no line geometry. |
| NWM RouteLink v3.0.17 (HydroShare, community repack) | https://www.hydroshare.org/resource/1fe9975004ce4b5097d41939afa14f84/ | RouteLink.h5 is 0.7 MB -> gauge/lake subset only; not used. |
| NWM reach geometry (NOAA OWP map service) | https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0 | Fields: feature_id, name, strm_order, huc6, nwm_vers. Queried by bbox, 3,836 reaches. `nwm_vers` = 3 for all. |
| OSM roads + waterways | data/raw/nc.osm.pbf (Geofabrik NC extract already on disk, dated 2026-10-09, read-only) | Used instead of Overpass. |
| County polygons | data/raw/counties.zip (already on disk, Census cartographic, read-only) | |
| NOT USED | data/raw/nhd/enhd_nhdplus_flowlines.gpkg, enhd_nhdplusatts.parquet | 4,255-byte HTML error pages from an earlier failed download, not data. |

## Spike 2 - structures
| NCDOT StructuresPoint (gdb, Q1 2026, modified 2026-04-27, 3,962,066 B) | https://xfer.services.ncdot.gov/gisdot/DOTBridgeLocations/NCDOTStructureLocationsPoint.gdb.zip | link found on https://connect.ncdot.gov/resources/gis/pages/gis-data-layers.aspx |
|---|---|---|
| NCDOT metadata (field list) | https://xfer.services.ncdot.gov/gisdot/Metadata/QuarterlyPublication/2026_Quarter1/NCDOTStructureLocationsPoint.pdf | saved text: data/phase0/raw/NCDOTStructureLocationsPoint_metadata.txt |
| NCDOT ER FeatureServer (2022 snapshot, only checked) | https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_StructuresER/FeatureServer | same fields, older; not used |
| NBI 2025 NC delimited (7,661,852 B) | https://www.fhwa.dot.gov/bridge/nbi/2025/delimited/NC25.txt (index: https://www.fhwa.dot.gov/Bridge/nbi/ascii2025.cfm ; format: https://www.fhwa.dot.gov/bridge/nbi/format.cfm) | text qualifier is `'`; lat/long are DDMMSSss / DDDMMSSss |

## Spike 3 - closure labels
| IEM LSR API | https://mesonet.agron.iastate.edu/geojson/lsr.py?help= (data: /geojson/lsr.geojson) | bbox + sts/ets used |
|---|---|---|
| IEM VTEC events | https://mesonet.agron.iastate.edu/json/vtec_events.py?wfo=ILM&year=2018 (and 2016) | `locations` is a county text list; no geometry here |
| NCDOT TIMS / DriveNC history (ArcGIS Online) | https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMSIncidentsHistory/FeatureServer (layers 0 points, 1 lines); also ...TIMSIncidentsHistoryEdit_QUERYTABLE | CreationDate min 2024-10-15; StartDateTime min 2017-09-07 but only 2 records start before 2019-01-01 (both Wake County) |
| Searched, nothing found | ArcGIS Online public search for Florence/Matthew closure layers; web search for a Florence closure GIS download | |

## Spike 4 - elevation / HAND
| USGS TNM Access API (1 m DEM listing) | https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Digital Elevation Model (DEM) 1 meter&bbox=... | 172 tiles: 162 NC_HurricaneFlorence_2020_D20 + 10 SC_2023Horry_Processing_D24 |
|---|---|---|
| 1 m tiles read remotely (HTTP range) | https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/... | nothing downloaded in full |
| NOAA OWP HAND (inundation-mapping) | https://github.com/NOAA-OWP/inundation-mapping (README: ESIP S3 `noaa-nws-owp-fim`) | bucket answers "Requester Pays ... authenticate" to anonymous requests -> not accessible without credentials |
| 3DEPElevation ImageServer | https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer | returned "Invalid Token" (498) on 2026-10-10; not used |
| Pre-Florence NC lidar (info only) | https://coast.noaa.gov/slrdata/DEMs/NC/index.html | 2014/2015 NCFMP lidar; not downloaded |

## Follow-up (2026-10-10)
| Use | URL | Notes |
|---|---|---|
| v3.0 retrospective feature_id coordinate | https://noaa-nwm-retrospective-3-0-pds.s3.amazonaws.com/CONUS/zarr/chrtout.zarr/feature_id/0 | single zstd chunk, 2,776,734 int64 ids; fetched with curl because zarr/s3fs fails DNS in this environment (aiodns); decoded with `zstandard` (pip-installed) |
| Recurrence flows / high-water threshold | https://maps.water.noaa.gov/server/rest/services/reference/static_nwm_flowlines/FeatureServer/0 | fields high_water_threshold (cfs), rf_50/25/10/5/2_0_17c (aliases "2%, 4%, 10%, 20%, 50% Streamflow (cfs)"). No other documentation found: layer description is one line; not in NCO RouteLink/parm (https://www.nco.ncep.noaa.gov/pmb/codes/nwprod/nwm.v3.1.6/parm/ lists domain, constants, ...; no recurrence file); https://water.noaa.gov/about/nwm and /about/output_file_contents do not mention them. "17c" = Bulletin 17C is my inference, unverified. |
| NGS marks with NAVD88 ortho heights | https://services2.arcgis.com/C8EMgrsFcRFL6LrL/ArcGIS/rest/services/NGS_Datasheets_Feature_Service/FeatureServer/1 | 2,941 marks in the bbox with ORTHO_HT; datasheets index https://geodesy.noaa.gov/datasheets/index.shtml |
