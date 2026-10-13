# Sources used for the v2 features (checked live on 2026-10-10)

Nothing here was assumed from memory: each layout below was read from the live listing / docs on that date.

## Stage IV hourly precipitation (observed rain) - USED
- Dataset page: https://gdex.ucar.edu/datasets/d507005/ (NCEP/CPC 4 km precipitation, 1995-2025, WMO GRIB1; GRIB2 only from 2020-07-20; Stage IV from 2002; polar-stereographic 1160x880 nominal).
- Open access (no login, via the OSDF/Pelican data federation, `require-token=false`): https://osdf-director.osg-htc.org/ncar/gdex/d507005/ (directory listing). Sub-folders: `stage4/`, `ST2_4km/`, `grib4km/`, `prcp.hrly/`, ... .
- Files used: https://osdf-director.osg-htc.org/ncar/gdex/d507005/stage4/stage4.YYYYMM.tar (e.g. `.../stage4/stage4.201809.tar`, 87 MB). Layout found by opening one: monthly tar -> daily tar `ST4.YYYYMMDD` -> gzipped GRIB1 `ST4.YYYYMMDDHH.01h.gz` (also 06h / 24h / gif files, ignored).
- Time semantics (read from the GRIB headers): `ST4.2018091412.01h` has dataTime 1100, P1=0, P2=1 -> accumulation over (11Z, 12Z]; the file hour is the END of the accumulation. Grid: 1121 x 881, first point 23.117N 119.023W, orientation 105W, LaD 60N, dx 4763 m in the header (NCEP grid 240 nominal 4762.5 m; 4762.5 m on a 6371.2 km sphere was used - eccodes' own lat/lon assume a slightly smaller sphere and drift ~2.8 m per cell, i.e. < 3 km at the far corner), bitmap present, missing = 9999.
- Decoding: ECMWF ecCodes (`pip install eccodes`). No other source was needed.

## NLDI (basin polygon and upstream gauges) - USED
- Service: https://api.water.usgs.gov/nldi/ ; OpenAPI definition: https://api.water.usgs.gov/nldi/docs/openapi.json (paths read from it: `/linked-data/{source}/{id}/basin`, `/linked-data/{source}/{id}/navigation/{nav_mode}/{data_source}` with `distance`).
- Calls: `.../linked-data/nwissite/USGS-<id>/basin?f=json&simplified=false` and `.../nwissite/USGS-<id>/navigation/UT/nwissite?distance=9999&f=json`.
- Already used by the earlier pipeline: `.../navigation/DM/flowlines` (pilot flag).

## NWM / USGS / NWPS (already in the pipeline, no new downloads)
- See `src/README.md` and `reports/ml_data_report.md` section 7.

## MRMS on AWS - CHECKED, NOT USED
- Registry: https://registry.opendata.aws/noaa-mrms-pds/ ; bucket listing (anonymous HTTPS, S3 ListObjectsV2): https://noaa-mrms-pds.s3.amazonaws.com/?list-type=2&delimiter=/&prefix=CONUS/MultiSensor_QPE_01H_Pass2_00.00/ .
- First day folder in `CONUS/MultiSensor_QPE_01H_Pass2_00.00/` is **20201014** (search results also state data for 2019-09-27..2020-10-30 is not backfilled). That is ~2.3 of the 8 study years and none of Matthew (2016) or Florence (2018), so it is skipped for training.

## AORC v1.1 on AWS - CHECKED, NOT USED
- Registry: https://registry.opendata.aws/noaa-nws-aorc/ ; bucket listing: https://noaa-nws-aorc-v1-1-1km.s3.amazonaws.com/?list-type=2&delimiter=/ -> yearly `1979.zarr/` ... `2025.zarr/`; variable `APCP_surface`, 1 h, ~800 m, CONUS 1979-present.
- It is a retrospective analysis (assembled after the fact), so it could only ever be a comparison feature, never evidence of real-time ability. Not built in this pass (optional in the brief; the Stage IV result decides whether it is worth doing).

## Not used (by instruction)
- Forecast rainfall / QPF and operational NWM forecasts (no historical archive in this pipeline).

## Not used (found in `data/` during the run)
- `data/NCDOTStructureLocationsPolygon.gdb.zip`, `data/lsr_*.xlsx`: belong to the road-closure work (`src/k2_*.py`); not inputs to this task. NWS local storm reports are after-the-fact human reports and would be label-adjacent, so they are not features.
