"""Index of the pipeline scripts. No logic of its own: it prints (or, with --run, executes) the existing scripts of a stage in order.
Usage (repo root):  python src/run.py list | python src/run.py <stage> [--run]
Printing is the default because several stages download large files or overwrite committed outputs; read the script docstring first."""
import argparse, glob, subprocess, sys

P = "src/pipeline/"
G = lambda pat: sorted(glob.glob(pat))
STAGES = {
    "build_world": ("crossings, thresholds, road graph, facilities (phase0 s1-s9, then phase1 p1-p3e, p9)", G(P + "01_build_world/phase0/s*.py") + G(P + "01_build_world/phase1/p*.py")),
    "inventory": ("data-source inventory and downloads (run each by hand; they download)", G(P + "01_build_world/inventory/*.py")),
    "routing": ("flows -> engine -> recurrence/connectivity (engine and p8 need args: flows file + label, see docstrings)", [P + "02_routing/" + f for f in
                ("p5a_fetch_flows.py", "p5b_fetch_forecast_v12.py", "p6_wilmington.py", "p6b_label_compare.py", "p7_recurrence.py", "22_engine_p2.py", "23_p8_p2.py")]),
    "gauge_ml": ("gauge table, splits, v2 features, sample models (needs USGS_API_KEY; 03 and 04 are big downloads)", G(P + "03_gauge_ml/[01][0-9]_*.py")),
    "export": ("build data/export, then assert it", [P + "04_export/export_data.py", P + "04_export/export_checks.py"]),
    "validation": ("run-once validation tests, rules fixed in advance (do NOT re-run; 32/53 are large downloads)", G("src/validation/[2-8][0-9]_*.py")),
    "live": ("scripts the GitHub Actions / scheduled tasks call", G("src/live/*.py") + ["src/closures_live.py", "src/nwm_backfill.py"]),
    "checks": ("safe read-only verification: headline recompute, export assertions, live selftests", ["src/validation/80_repro_headlines.py", P + "04_export/export_checks.py", "src/live/45_nowcast.py selftest", "src/live/44_forecast_preview.py selftest"]),
}

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("stage", choices=["list", *STAGES]); ap.add_argument("--run", action="store_true", help="execute instead of print")
a = ap.parse_args()
if a.stage == "list":
    for k, (d, fs) in STAGES.items(): print(f"{k:12s} {len(fs):3d} scripts  {d}")
    sys.exit(0)
for f in STAGES[a.stage][1]:
    cmd = [sys.executable, *f.split()]
    print("python", f)
    if a.run and subprocess.run(cmd).returncode: sys.exit(f"stopped: {f} failed")
