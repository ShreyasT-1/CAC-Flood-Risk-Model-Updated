# NWM short-range forecast archive

**Label for all 2018 data: "v1.2 operational forecasts, hindcast replay only."** Do not describe results as forecast skill of the current NWM version
(current operational is v3.x; live cycles carry their own `nwm_version`).

- Source (historical): GCS NetCDF bucket `national-water-model`, first issue date 2018-09-17. BigQuery path not used (no project ID yet).
- Live: AWS `noaa-nwm-pds` -> GCS -> NOMADS; all three publish a cycle ~101-103 min after issue (median, `data/forecasts/live_delay.csv`).
- Layout: `data/forecasts/short_range/issue_date=YYYY-MM-DD/cycle_HHz.parquet`; columns feature_id, issue_time, valid_time, lead_hours (1-18),
  streamflow_cfs (= NWM m3/s x 35.3147), nwm_version (file attr `model_version`). Short range has no lead 0.
- Never filled: masked values stay NaN; missing leads/cycles go to `data/forecasts/manifest.csv` (cycle,status,error,source,missing_leads,...).
  Cycle files are never overwritten; reruns skip existing cycles.
- Reaches: `config/reaches.csv` (all 256 crosswalk reaches, `in_pilot` flag). Add rows to extend; rerun pulls only new cycles, so reach additions
  need a re-pull into a fresh folder.
- Historical cycles pulled: 00/03/...21Z only. Upstream gaps (GCS listing): 2018-10-04T21Z and 2018-11-12T13Z have no files (`gaps_audit.csv`).
- Scripts (src/): `nwm_fc.py` core, `nwm_hist.py START END`, `nwm_audit.py`, `nwm_live.py`, `nwm_delay.py`, `nwm_check.py [compare]`.
- Live schedule: `.github/workflows/nwm_live.yml` (hourly, pushes to branch `nwm-archive`). Not yet run.
