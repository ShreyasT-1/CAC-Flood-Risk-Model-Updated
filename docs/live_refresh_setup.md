# Live data refresh (hourly) - manual setup

What runs: `.github/workflows/refresh_live.yml` (GitHub Actions, free tier) runs `src/live/45_nowcast.py` and `src/live/44_forecast_preview.py` every hour at minute 37, copies `nowcast.json`, `coastal.json` and `forecast_latest.json` into `web/public/data/sample/`, and commits them. A commit to the default branch makes Vercel redeploy, so the site shows the new files. `generated_at` inside each file is the time the script ran; nothing is re-stamped.

No secret is needed (the old `SITE_PUSH_TOKEN` and `SITE_REPO` are gone: the website is now in this repo). Things to set by hand, once:

1. **GitHub repo, Settings > Actions > General > Workflow permissions**: choose "Read and write permissions". (The workflow also asks for `contents: write`, but an org/repo default of read-only can override it.)
2. **Scheduled workflows only run on the default branch.** The default branch must contain `.github/workflows/refresh_live.yml` (push it to `main`, or make `master` the default). A repo with no activity for 60 days has its schedules paused by GitHub; open the Actions tab and re-enable.
3. **Vercel project**: Settings > General > Root Directory = `web`; Git > Production Branch = the default branch above. If the project was linked to the old separate website repo, reconnect it to this repo.
4. **First run**: Actions tab > refresh-live > Run workflow, then check that a commit "live data ..." appears and that Vercel builds it.
5. Optional: the hourly commits add ~200 KB each to history. If that bothers you, change the cron to every 3 hours (`37 */3 * * *`); the nowcast `stale` flag flips after 3 hours, so hourly is the cadence that keeps the badge off.

If the cron stops (Actions disabled, token or permission problem), the site does not fake freshness: each file keeps its own `generated_at`, and the badge in the app goes red "Stale" again.

Local one-off refresh (what was done on 2026-10-16): `python src/live/45_nowcast.py`, `python src/live/44_forecast_preview.py`, then `cd web && npm run sample:sync`.
