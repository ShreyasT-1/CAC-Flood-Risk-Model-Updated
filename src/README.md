# src/ map

Run everything from the **repo root** (`python src/<path>`; scripts use relative paths like `data/phase1b/`). `python src/run.py list` shows the stages; `python src/run.py <stage>` prints the commands in order (`--run` executes them). Original script numbers are kept in the file names, so references like "54_t15_test.py" in `docs/claims.md` still resolve (table at the bottom).

| Stage (folder) | What it does | Main inputs | Main outputs |
|---|---|---|---|
| `common.py` | shared paths + USGS client (used by `pipeline/03_gauge_ml` and `legacy/k2_*`) | - | - |
| `pipeline/01_build_world/phase0` | NWM reaches, OSM extract, crossings, structures, elevation/HAND, thresholds (s1a-s9) | USGS/NWM/OSM/NCDOT downloads | `data/phase0/` (`crossings_v2.parquet`, `reach_thresholds.parquet`) |
| `pipeline/01_build_world/phase1` | origins, facilities, road graph, snapping (p3a-p3e), flags, calibration bridge, label negatives | `data/phase0/` | `data/phase1b/` (`graph_segments`, `origins_snapped`, `hospitals_snapped`, `crossing_snap`...) |
| `pipeline/01_build_world/inventory` | inventory and download scripts for hospitals, fire stations, FEMA, storm reports, DEM manifests (run by hand) | public APIs | `data/inventory/`, `data/derived_new/`, `data/raw_new/` |
| `pipeline/02_routing` | flows (p5a/p5b), recurrence (p7), shortest-path engine and closures (`22_engine_p2.py`, `engine2.py`), connectivity (`23_p8_p2.py`) | `data/phase1b/`, `data/phase0/`, a flows parquet + label | `data/phase2/engine/replay_<label>_*.parquet`, `p8_*.csv`, `data/phase1b/recurrence_*` |
| `pipeline/03_gauge_ml` | gauge table, splits, kill test, v2 features, sample models (01-16; its own notes in `README.md` there) | USGS, NWM zarr, Stage IV (large) | `data/derived/`, `reports/ml_data_report.md`, `reports/sample_model*.md` |
| `pipeline/04_export` | `export_data.py` builds `data/export/`; `export_checks.py` asserts it | `data/phase1b/`, `data/phase2/`, `22_engine_p2.py` | `data/export/*` + `manifest.json` |
| `validation/` | the run-once tests whose rules were fixed in advance (20-42, 50-58, 60-63, 69-71, 81), `80_repro_headlines.py` (recomputes every number in `docs/claims.md`) | `data/phase2/*`, `docs/validation_protocol*.md` | `data/phase2/<test>/`, `reports/phase2_*.md` |
| `live/` | `43` coastal, `44` forecast preview, `45` nowcast, `46` nowcast gauge list, `72` live conditions, `nwm_*.py` archiver. Keep light: Actions installs only numpy/pandas/pyarrow/requests/netCDF4 | NOAA / USGS / NWPS | `export/sample/{nowcast,coastal,forecast_latest}.json`, `data/export/live_conditions.*`, `data/forecasts/` |
| `legacy/` | superseded: `k2_*` (first closure matcher), `engine.py` (phase1 v1 engine), `p8_connectivity.py` (phase1 copy of `23_p8_p2.py`), `run_nwm_live.cmd` (unused per `docs/archiver_setup.md`) | - | - |

Two files stay at `src/` on purpose: `closures_live.py` and `nwm_backfill.py` are started by name from `src/` by Windows Task Scheduler (`FloodLens_Closures_Live`, `FloodLens_NWM_Archiver`). Re-point those two tasks, then `git mv` them into `live/` (and drop the `sys.path` line in `nwm_backfill.py`).

Not merged (outputs not provably identical): `engine2.py` vs `22_engine_p2.py` (22 adds `P2_RESNAP`/`P2_NOLONG` and writes to `data/phase2/engine/`; 21/36/39 still import `engine2.py`), `09_sample_model.py` vs `13_sample_model_v2.py` (different feature sets).

## Old filename -> new path

| old path | new path |
|---|---|
| `src/phase1/engine.py` | `src/legacy/engine.py` |
| `src/k2_00_crossings.py` | `src/legacy/k2_00_crossings.py` |
| `src/k2_00a_osm_pbf.py` | `src/legacy/k2_00a_osm_pbf.py` |
| `src/k2_01_closures.py` | `src/legacy/k2_01_closures.py` |
| `src/k2_02_match.py` | `src/legacy/k2_02_match.py` |
| `src/phase1/p8_connectivity.py` | `src/legacy/p8_connectivity.py` |
| `src/run_nwm_live.cmd` | `src/legacy/run_nwm_live.cmd` |
| `src/43_coastal_levels.py` | `src/live/43_coastal_levels.py` |
| `src/44_forecast_preview.py` | `src/live/44_forecast_preview.py` |
| `src/45_nowcast.py` | `src/live/45_nowcast.py` |
| `src/46_nowcast_gauge_km.py` | `src/live/46_nowcast_gauge_km.py` |
| `src/72_live_conditions.py` | `src/live/72_live_conditions.py` |
| `src/nwm_audit.py` | `src/live/nwm_audit.py` |
| `src/nwm_check.py` | `src/live/nwm_check.py` |
| `src/nwm_delay.py` | `src/live/nwm_delay.py` |
| `src/nwm_fc.py` | `src/live/nwm_fc.py` |
| `src/nwm_hist.py` | `src/live/nwm_hist.py` |
| `src/nwm_live.py` | `src/live/nwm_live.py` |
| `src/nwm_retro.py` | `src/live/nwm_retro.py` |
| `src/run_hist.sh` | `src/live/run_hist.sh` |
| `src/inventory/agol.py` | `src/pipeline/01_build_world/inventory/agol.py` |
| `src/inventory/audit_existing.py` | `src/pipeline/01_build_world/inventory/audit_existing.py` |
| `src/inventory/build_closure_table.py` | `src/pipeline/01_build_world/inventory/build_closure_table.py` |
| `src/inventory/build_fire_stations.py` | `src/pipeline/01_build_world/inventory/build_fire_stations.py` |
| `src/inventory/build_hospitals.py` | `src/pipeline/01_build_world/inventory/build_hospitals.py` |
| `src/inventory/common_geo.py` | `src/pipeline/01_build_world/inventory/common_geo.py` |
| `src/inventory/fetch_ncdot_nconemap.py` | `src/pipeline/01_build_world/inventory/fetch_ncdot_nconemap.py` |
| `src/inventory/fetch_nfhl.py` | `src/pipeline/01_build_world/inventory/fetch_nfhl.py` |
| `src/inventory/fetch_openfema_pa.py` | `src/pipeline/01_build_world/inventory/fetch_openfema_pa.py` |
| `src/inventory/fetch_storm_reports.py` | `src/pipeline/01_build_world/inventory/fetch_storm_reports.py` |
| `src/inventory/fetch_tims_history.py` | `src/pipeline/01_build_world/inventory/fetch_tims_history.py` |
| `src/inventory/lidar_projects.py` | `src/pipeline/01_build_world/inventory/lidar_projects.py` |
| `src/inventory/make_inventory.py` | `src/pipeline/01_build_world/inventory/make_inventory.py` |
| `src/inventory/osm_extract.py` | `src/pipeline/01_build_world/inventory/osm_extract.py` |
| `src/inventory/road_quality.py` | `src/pipeline/01_build_world/inventory/road_quality.py` |
| `src/inventory/tnm_manifest.py` | `src/pipeline/01_build_world/inventory/tnm_manifest.py` |
| `src/phase0/s1a_fetch_reaches.py` | `src/pipeline/01_build_world/phase0/s1a_fetch_reaches.py` |
| `src/phase0/s1b_osm_extract.py` | `src/pipeline/01_build_world/phase0/s1b_osm_extract.py` |
| `src/phase0/s1c_crossings.py` | `src/pipeline/01_build_world/phase0/s1c_crossings.py` |
| `src/phase0/s2_structures.py` | `src/pipeline/01_build_world/phase0/s2_structures.py` |
| `src/phase0/s3a_fetch_lsr.py` | `src/pipeline/01_build_world/phase0/s3a_fetch_lsr.py` |
| `src/phase0/s3b_tiers.py` | `src/pipeline/01_build_world/phase0/s3b_tiers.py` |
| `src/phase0/s4_elev_hand.py` | `src/pipeline/01_build_world/phase0/s4_elev_hand.py` |
| `src/phase0/s5_routelink_diff.py` | `src/pipeline/01_build_world/phase0/s5_routelink_diff.py` |
| `src/phase0/s6_crossings_v2.py` | `src/pipeline/01_build_world/phase0/s6_crossings_v2.py` |
| `src/phase0/s7_thresholds.py` | `src/pipeline/01_build_world/phase0/s7_thresholds.py` |
| `src/phase0/s8_deck_check.py` | `src/pipeline/01_build_world/phase0/s8_deck_check.py` |
| `src/phase0/s9_label_review.py` | `src/pipeline/01_build_world/phase0/s9_label_review.py` |
| `src/phase1/p1_flags.py` | `src/pipeline/01_build_world/phase1/p1_flags.py` |
| `src/phase1/p2_calibration_bridge.py` | `src/pipeline/01_build_world/phase1/p2_calibration_bridge.py` |
| `src/phase1/p3a_origins_facilities.py` | `src/pipeline/01_build_world/phase1/p3a_origins_facilities.py` |
| `src/phase1/p3b_graph.py` | `src/pipeline/01_build_world/phase1/p3b_graph.py` |
| `src/phase1/p3c_snap.py` | `src/pipeline/01_build_world/phase1/p3c_snap.py` |
| `src/phase1/p3d_facilities40.py` | `src/pipeline/01_build_world/phase1/p3d_facilities40.py` |
| `src/phase1/p3e_graph40.py` | `src/pipeline/01_build_world/phase1/p3e_graph40.py` |
| `src/phase1/p9_label_negatives.py` | `src/pipeline/01_build_world/phase1/p9_label_negatives.py` |
| `src/22_engine_p2.py` | `src/pipeline/02_routing/22_engine_p2.py` |
| `src/23_p8_p2.py` | `src/pipeline/02_routing/23_p8_p2.py` |
| `src/phase1/engine2.py` | `src/pipeline/02_routing/engine2.py` |
| `src/phase1/p5a_fetch_flows.py` | `src/pipeline/02_routing/p5a_fetch_flows.py` |
| `src/phase1/p5b_fetch_forecast_v12.py` | `src/pipeline/02_routing/p5b_fetch_forecast_v12.py` |
| `src/phase1/p6_wilmington.py` | `src/pipeline/02_routing/p6_wilmington.py` |
| `src/phase1/p6b_label_compare.py` | `src/pipeline/02_routing/p6b_label_compare.py` |
| `src/phase1/p7_recurrence.py` | `src/pipeline/02_routing/p7_recurrence.py` |
| `src/01_gauges.py` | `src/pipeline/03_gauge_ml/01_gauges.py` |
| `src/02_crosswalk.py` | `src/pipeline/03_gauge_ml/02_crosswalk.py` |
| `src/03_observed.py` | `src/pipeline/03_gauge_ml/03_observed.py` |
| `src/04_nwm.py` | `src/pipeline/03_gauge_ml/04_nwm.py` |
| `src/05_table.py` | `src/pipeline/03_gauge_ml/05_table.py` |
| `src/06_splits.py` | `src/pipeline/03_gauge_ml/06_splits.py` |
| `src/07_killtest.py` | `src/pipeline/03_gauge_ml/07_killtest.py` |
| `src/08_report.py` | `src/pipeline/03_gauge_ml/08_report.py` |
| `src/09_sample_model.py` | `src/pipeline/03_gauge_ml/09_sample_model.py` |
| `src/10_nldi.py` | `src/pipeline/03_gauge_ml/10_nldi.py` |
| `src/11_stage4_catch.py` | `src/pipeline/03_gauge_ml/11_stage4_catch.py` |
| `src/12_build_v2.py` | `src/pipeline/03_gauge_ml/12_build_v2.py` |
| `src/13_sample_model_v2.py` | `src/pipeline/03_gauge_ml/13_sample_model_v2.py` |
| `src/14_leakage_v2.py` | `src/pipeline/03_gauge_ml/14_leakage_v2.py` |
| `src/15_report_v2.py` | `src/pipeline/03_gauge_ml/15_report_v2.py` |
| `src/16_ensemble_v2.py` | `src/pipeline/03_gauge_ml/16_ensemble_v2.py` |
| `src/ml_example_v2.py` | `src/pipeline/03_gauge_ml/ml_example_v2.py` |
| `src/export_checks.py` | `src/pipeline/04_export/export_checks.py` |
| `src/export_data.py` | `src/pipeline/04_export/export_data.py` |
| `src/20_alt_closure_rules.py` | `src/validation/20_alt_closure_rules.py` |
| `src/21_wilmington_check.py` | `src/validation/21_wilmington_check.py` |
| `src/24_label_suggestions.py` | `src/validation/24_label_suggestions.py` |
| `src/30_t10_reports.py` | `src/validation/30_t10_reports.py` |
| `src/31_t10_review_suggestions.py` | `src/validation/31_t10_review_suggestions.py` |
| `src/32_t10_fetch_records.py` | `src/validation/32_t10_fetch_records.py` |
| `src/33_t10_flow_test.py` | `src/validation/33_t10_flow_test.py` |
| `src/35_t10_gauge_validation.py` | `src/validation/35_t10_gauge_validation.py` |
| `src/36_t10_routing_check.py` | `src/validation/36_t10_routing_check.py` |
| `src/37_t10_documented_closures.py` | `src/validation/37_t10_documented_closures.py` |
| `src/38_t10_documented_test.py` | `src/validation/38_t10_documented_test.py` |
| `src/39_t10_exit_scenario.py` | `src/validation/39_t10_exit_scenario.py` |
| `src/40_t12_hwm_crest.py` | `src/validation/40_t12_hwm_crest.py` |
| `src/41_t13_flood_extent.py` | `src/validation/41_t13_flood_extent.py` |
| `src/42_bcso_florence.py` | `src/validation/42_bcso_florence.py` |
| `src/50_t15_step1_closures.py` | `src/validation/50_t15_step1_closures.py` |
| `src/51_t15_events_a4.py` | `src/validation/51_t15_events_a4.py` |
| `src/52_t15_crossings.py` | `src/validation/52_t15_crossings.py` |
| `src/53_t15_flows.py` | `src/validation/53_t15_flows.py` |
| `src/54_t15_test.py` | `src/validation/54_t15_test.py` |
| `src/55_t15_nine.py` | `src/validation/55_t15_nine.py` |
| `src/56_t16_features.py` | `src/validation/56_t16_features.py` |
| `src/57_t16_model.py` | `src/validation/57_t16_model.py` |
| `src/58_t16_posthoc.py` | `src/validation/58_t16_posthoc.py` |
| `src/60_resnap_check.py` | `src/validation/60_resnap_check.py` |
| `src/61_fema_nfhl.py` | `src/validation/61_fema_nfhl.py` |
| `src/62_fema_compare.py` | `src/validation/62_fema_compare.py` |
| `src/63_snap_sidebyside.py` | `src/validation/63_snap_sidebyside.py` |
| `src/69_build_label_review_sheet.py` | `src/validation/69_build_label_review_sheet.py` |
| `src/70_apply_label_review.py` | `src/validation/70_apply_label_review.py` |
| `src/71_label_sensitivity.py` | `src/validation/71_label_sensitivity.py` |
| `src/73_disclosure_checklist.py` | `src/validation/73_disclosure_checklist.py` |
| `src/80_repro_headlines.py` | `src/validation/80_repro_headlines.py` |
| `src/81_ptc8_test.py` | `src/validation/81_ptc8_test.py` |
| `src/README.md` (ML pipeline notes) | `src/pipeline/03_gauge_ml/README.md` |
