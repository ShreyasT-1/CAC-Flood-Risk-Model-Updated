# src/ refactor report (branch `refactor-src`, from c1132cd; tag `technical-freeze-1` untouched)

## What moved
117 files by `git mv` (history kept), commit "Step 1": `src/pipeline/{01_build_world,02_routing,03_gauge_ml,04_export}`, `src/validation`, `src/live`, `src/legacy`. Full old -> new table: `src/README.md`.
Path-only edits ("Step 3"): all `src/<old>` references (scripts, docs/*.md, both workflows, `web/lib/live.ts`, `.gitignore`, root README, `run_hist.sh`) plus hand fixes to `sys.path`/`__file__` roots:
- `from common import *` in `03_gauge_ml/*` and `legacy/k2_*` now put `src/` on `sys.path` first (cwd-independent, as before).
- validation 21, 32, 36, 38, 39, 40, 42, 71: `sys.path.insert` target only. No logic touched; 20-42, 50-58, 60-63, 69-71, 81 are otherwise only `src/<old>` -> `src/<new>` string swaps.
- `live/nwm_fc.py` ROOT `parents[1]` -> `parents[2]`; `live/44_forecast_preview.py` sys.path; inventory `ROOT`/`chdir` ".." x2 -> x4; `run_hist.sh` now runs from repo root.
- Check done: reverse-mapping every changed file back to old names reproduces the freeze text exactly except those hand-fixed lines.

## Merged: nothing (proof they differ)
- `phase1/engine2.py` vs `22_engine_p2.py` (`diff --strip-trailing-cr`): 22 adds `resnap()`, env flags `P2_RESNAP` / `P2_NOLONG`, and writes replays to `data/phase2/engine/` instead of `data/phase1b/`. `Net`, `seg_ratio`, `solve`, `SCEN` identical. Validation 21/36/39 import `engine2` and write via it, so folding them together means editing validation code. Kept separate; `engine2.py` sits in `02_routing/` (not legacy) because it is a live dependency.
- `phase1/engine.py` is a different engine (ratio scenarios, `data/phase1`), no importers -> `legacy/`.
- `phase1/p8_connectivity.py` vs `23_p8_p2.py`: differ only in input/output dir (`W`). Original -> `legacy/`; 23 canonical.
- `09_sample_model.py` vs `13_sample_model_v2.py`: different feature sets/outputs. Left both.
- Repeated `CFS = 35.3146667` (20 files) not moved to `common.py`: would edit validation lines, and `common` has import-time side effects (mkdirs, requests).

## Left alone / decisions for you
- `closures_live.py`, `nwm_backfill.py` stay in `src/`: Windows Task Scheduler tasks `FloodLens_Closures_Live` and `FloodLens_NWM_Archiver` run them by name with working dir `src/`. `nwm_backfill.py` got one `sys.path` line so it still finds `live/nwm_fc.py`. To finish: re-point both tasks to `src\live`, then `git mv` them.
- Not in your list, my placement: `73_disclosure_checklist.py` -> validation; `ml_example_v2.py` -> 03_gauge_ml; phase1 `p1_flags`, `p2_calibration_bridge`, `p9_label_negatives` -> 01_build_world/phase1; `p5a`, `p5b`, `p6`, `p6b` -> 02_routing; `run_nwm_live.cmd` (docs say unused) -> legacy.
- Old path text left unchanged in: `docs/freeze_commit_files.txt`, `docs/FREEZE_SUMMARY.md`, `reports/*.md`, `handoff_for_shreyas/`, `export/sample/README.md` and `export/sample/build_sample.py` (a docstring path). The last two are hashed under `export/sample/`, so editing them broke the "identical hashes" rule; reverted. Use the mapping table.
- `docs/validation_protocol*.md` had path strings updated (6 + 2 lines, paths only), as you asked for docs/*.md. Revert those two files if you want the pre-registered text byte-identical.
- Nothing deleted. `src/cache/` (11 tracked json) and `export/sample/{build_sample,make_stress}.py` are outside src scripts; untouched.
- Root `README.md` is untracked in git; I edited it but it is in no commit.
- `docs/nwm_forecast_sources.md` mentions `src/app/main.py`, which never existed.

## Checks, before vs after (outputs in the session scratchpad)
| check | before | after |
|---|---|---|
| `80_repro_headlines.py` | 65 quantities, 0 mismatches | byte-identical output |
| `export_checks.py` | PASS (0 failures) | byte-identical output |
| `45_nowcast.py selftest`, `44_forecast_preview.py selftest` | OK, OK | byte-identical output |
| sha256 of 34 files in `data/export` + `export/sample` | baseline | identical |
| `export_data.py` full regeneration into a temp dir (new layout, loads moved `22_engine_p2.py`, ~9 min) | - | 6 data files byte-identical to committed `data/export`; only `README.md` text differs (script paths) |
| `compileall src`, `python -I` ast parse of 118 files | - | OK |
| `cd web && npm run build` | - | passes |
| workflow python lines (`src/live/nwm_live.py`, `45_nowcast.py`, `44_forecast_preview.py`) | - | files exist and parse; 43/44/45 import without running; `nwm_live.py` not executed (it hits the network, no main guard) |

Side effects to know about: (1) regenerating `data/export` will change `manifest.json` `source_script` strings and the `README.md` path text (data files stay identical), because those strings now name the new paths. (2) While dry-running imports I accidentally executed `72_live_conditions.py` (no main guard); it rewrote `data/export/live_conditions.*` and `manifest.json`; I restored them with `git checkout` and re-hashed (identical to baseline). Note `72` and `nwm_live.py` run on import.
