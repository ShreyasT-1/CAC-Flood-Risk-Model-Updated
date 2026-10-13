# NWM forecast sources (Step 1 verification, 2026-10-10)

## URLs consulted
- https://github.com/CIROH-UA/api-nwm-gcp (repo tree via api.github.com/repos/CIROH-UA/api-nwm-gcp/git/trees/main)
- https://raw.githubusercontent.com/CIROH-UA/api-nwm-gcp/main/src/app/main.py  (SOURCE OF TRUTH for table names/columns/params)
- https://raw.githubusercontent.com/CIROH-UA/api-nwm-gcp/main/examples/notebooks/nwm_usgs_streamflow_plot.ipynb
- https://raw.githubusercontent.com/CIROH-UA/api-nwm-gcp/main/examples/scripts/nwm_data_beam_export.py
- https://nwm-api.ciroh.org/openapi.json (and /docs)
- https://hub.ciroh.org/docs/products/data-management/bigquery-api/
- https://repository.library.noaa.gov/view/noaa/66525/noaa_66525_DS1.pdf  (Markert et al. 2024, Env. Model. & Software 179:106123, doi 10.1016/j.envsoft.2024.106123)
- https://goo.gle/nwm-on-bq (cited by paper; marketplace page itself could NOT be fetched)
- https://www.weather.gov/media/notification/pdf_2026/scn26-64_National_Water_Model_V3.1.pdf (search hit, not read)
- https://ciroh.ua.edu/abstracts/ciroh-nwm-api-2-0-retrospective-data-flow-statistics-and-geographic-query/ (search hit, not read)

## BigQuery public dataset: `bigquery-public-data.national_water_model`
| Table | Source | Columns confirmed in API code |
|---|---|---|
| short_range_channel_rt | main.py | feature_id, reference_time, time, ensemble, streamflow, velocity |
| medium_range_channel_rt | main.py | same |
| long_range_channel_rt | main.py | same |
| analysis_assim_channel_rt | main.py | feature_id, time, streamflow, velocity, forecast_offset |
| stream_network | main.py | reach geometry/attributes (columns not enumerated) |
| flood_return_periods | main.py | feature_id, return_period_{2,5,10,25,50,100} |

- Ensemble: short=0; medium=0-5 (paper: member 1 = 10 d, 2-6 = 8.5 d, 3-h step); long=0-3 (30 d, 6-h step). Short = 18 h hourly, init hourly; medium/long init every 6 h. All members in one long table, one row per reach x timestep x member.
- Tables are clustered/partitioned; paper says queries scan "a few MB". $6.25/TiB, 1 TiB/mo free.
- Table is `channel_rt` only (CONUS reach streamflow). Hawaii/PR/AK domains not confirmed.
- Analysis-assim `forecast_offset` 1-3 (API param `run_offset`).

## CIROH REST API: https://nwm-api.ciroh.org
- Needs `x-api-key` header; free only for CIROH members/partners with active project (request via GitHub issue form linked from hub.ciroh.org page; ciroh-it-support@ua.edu).
- GET /forecast: forecast_type (short_range|medium_range|long_range, required), reference_time (default latest), comids, ensemble (default = AVERAGE across members), output_format json|csv
- GET /analysis-assim: start_time (default 2018-09-17), end_time, comids, run_offset 1-3
- GET /geometry, GET /return-period
- Limits: 10 MB per interactive query (paper).

## Coverage
- Paper: archive "since 2018" for the operational NWM. Exact first reference_time per table NOT verified.

## UNVERIFIED / needs a live query (no GCP credentials or google-cloud-bigquery here)
1. Is the dataset still ingesting in 2026? Latest reference_time per table. Note NWM v3.1 went operational 2026-08-18 (search snippet) - ingest may have gaps or schema changes.
2. Real partition/clustering columns, row counts, earliest reference_time, whether Florence (Sep 2018) is present.
3. Whether feature_id (COMID) values match our reach IDs.
4. Live archiving alternative (independent of the BQ ingest): NOAA NWM on AWS `s3://noaa-nwm-pds` / GCS `national-water-model` (not yet fetched/verified).

---
# Addendum: probes run 2026-10-10 (anonymous HTTP, no GCP account)

## Additional URLs
- https://storage.googleapis.com/storage/v1/b/national-water-model/o (GCS NetCDF bucket listing; probed directly)
- https://storage.googleapis.com/storage/v1/b/national-water-model-parq/o (parquet bucket the BigQuery table is built from; probed)
- https://noaa-nwm-pds.s3.amazonaws.com/ (AWS bucket listing; probed)
- https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/ (NOMADS; probed)
- https://pypi.org/pypi/hydrotools.nwm-client-new/json  (v8.0.0, py>=3.8) ; docs https://noaa-owp.github.io/hydrotools/hydrotools.nwm_client_new.html
- https://pypi.org/pypi/hydrotools.nwm-client/json (old client, v9.2.1)
- https://www.weather.gov/media/notification/pdf_2023_24/scn23-76_national_water_model_v3.0_aab.pdf (v3.0; search hit)
- https://www.weather.gov/media/notification/pdf2/scn20-119nwm_v2.1_aad.pdf (v2.1; search hit)

## Verified coverage (listing/test, not guesses)
| Source | First issue date | Last | Notes |
|---|---|---|---|
| GCS `national-water-model` (NetCDF) | **2018-09-17** (first prefix nwm.20180917) | 2026-10-09 present (checked 10 dates, all present) | short_range/ has 24 cycles x 18 leads = 432 channel_rt files/day |
| GCS `national-water-model-parq` (parquet; source of BQ) | 2018-09-17 t00z | not checked | channel_rt/{short,medium,long}_range, analysis_assim* ; files updated 2024-08 |
| BigQuery public dataset | **UNVERIFIED** (no creds). Probably 2018-09-17 (built from parq) | UNVERIFIED | cannot dry-run |
| AWS `noaa-nwm-pds` | 2025-01-01 | 2026-10-10 | **NOT a rolling 4-week archive anymore**: 648 daily prefixes. Has all domains (CONUS, AK, HI, PR, coastal) |
| NOMADS /pub/data/nccf/com/nwm/prod/ | nwm.20261009, nwm.20261010 only | live | ~2 days retention; true "live" fallback |

## Florence / Matthew
- Matthew (Oct 2016): **NOT covered by any operational forecast archive found.** GCS/BQ start 2018-09-17. Only hindcast/retrospective flow exists for it.
- Florence (landfall 2018-09-14): **PARTIAL.** Archive starts 2018-09-17 (3 days after landfall). Requested window 2018-09-06..2018-11-13 -> 2018-09-06..16 has NO forecasts (0 files on 0906, 0916). Covered: 09-17..11-13.
- Test of short_range channel_rt file counts for 2018-09-17..2018-11-13: complete (432/day) except **2018-10-04 (414)** and **2018-11-12 (414)** = 18 missing files (one cycle each, probably).
- NetCDF global attr `model_version` is present (2018-09-17 file = "NWM 1.2"), so nwm_version can be read from the file; BQ rows likely don't carry it.
- Units: streamflow m3/s ("m3 s-1"), valid_range 0-5e7 int-scaled. cfs = m3/s * 35.3147.
- Reach 10479801 (from our crosswalk) exists in the 2018-09-17 file.

## NWM operational versions (partly UNVERIFIED)
- v1.0 Aug 2016 (search); v1.1 2017-05-04/08 (search); v1.2 2018-03-06 (search; file attr confirms v1.2 in Sep 2018); v2.0 ~2019-06 (from memory, NOT verified; adds Hawaii, medium-range ensemble); v2.1 2021-04-20 (search); v3.0 2023-09-20 (search); v3.1 2026-08-18 (search snippet, not read).
- Within the usable archive (2018-09-17 on): v1.2 -> v2.0 (2019) -> v2.1 (2021) -> v3.0 (2023) -> v3.1 (2026). Florence window is entirely v1.2.

## hydrotools nwm-client-new (v8.0.0)
- Sources: Google Cloud (default; "largest amount of operational data"), NOMADS, local dir, generic web-server listing, Azure Blob. Reads the NetCDF files above (so same 2018-09-17 start on GCS). Returns SI units (m3/s) unless unit_system=US; columns reference_time, nwm_feature_id, value_time, value, measurement_unit, configuration, usgs_site_code.
- Per-source date ranges not documented in README; GCS range is what I measured above.
- Configurations include short_range, medium_range_mem1-7, long_range_mem1-4, analysis_assim*.

## Cost / account (BigQuery)
- Needs: free Google account -> Cloud project (billing NOT required for BigQuery sandbox: 1 TiB/mo query free, no card, tables expire 60 d; querying a public dataset needs no billing). Auth: `gcloud auth application-default login`, `pip install google-cloud-bigquery`.
- Paper: clustered+partitioned so a reach-limited query scans MB. Dry run (`QueryJobConfig(dry_run=True)`) gives exact bytes before each run.
- RECOMMENDATION: the GCS NetCDF bucket needs NO account at all and was verifiable; downside ~10 MB per file x 432/day (~4.5 GB/day to read, ~260 GB for the Florence window), unless we use range requests / the parquet bucket (19 MB per file, per lead hour, whole CONUS). BigQuery is far cheaper in bytes for 262 reaches.
