# Live NWM archiver: local hourly setup (Windows)

Local only. No GitHub Actions, no push. (The old `.github/workflows/nwm_live.yml` is untouched and not used.)

## What runs
- Task action: `pythonw.exe` (no console window), working directory `src/`, argument `nwm_backfill.py 72`. For every hourly short-range cycle in the last 72 h (up to now minus 2 h) it calls `nwm_fc.archive_cycle(..., sources=aws, gcs, nomads, require_complete=True)`.
- **Idempotent.** An existing `data/forecasts/short_range/issue_date=YYYY-MM-DD/cycle_HHz.parquet` returns `exists` and is never rewritten. A cycle is written only when all 18 leads were fetched (write to `.tmp`, then rename). Incomplete cycles are retried on the next run.
- Every new cycle adds a row to `data/forecasts/manifest.csv`; unrecoverable cycles are logged there with `status = failed` or `missing_upstream`.
- Log: `data/forecasts/logs/live_task.log` (`start (pythonw)` and `exit ok` lines per run, one line per cycle processed).
- Each run looks back 72 h, so a machine that was off or asleep for up to ~3 days catches up on the next run (AWS held every cycle back to at least 2026-10-01 when tested).

## One-time setup (PowerShell)
```powershell
$root = "C:\Users\nisha\OneDrive\Desktop\Projects\lifeline"
$py   = "C:\Users\nisha\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
$a = New-ScheduledTaskAction -Execute $py -Argument "nwm_backfill.py 72" -WorkingDirectory "$root\src"
$t = New-ScheduledTaskTrigger -Once -At 00:45 -RepetitionInterval (New-TimeSpan -Hours 1)
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName FloodLens_NWM_Archiver -Action $a -Trigger $t -Settings $s -Force
```
Runs at minute :45 of every hour, local time (the cycle issued 2 h earlier is ~101-119 min old by then, so it is published). Edit `$py` if Python moves.

## Verify
```powershell
Start-ScheduledTask -TaskName FloodLens_NWM_Archiver
Get-ScheduledTaskInfo -TaskName FloodLens_NWM_Archiver | fl LastRunTime,LastTaskResult,NextRunTime
Get-Content data\forecasts\logs\live_task.log -Tail 5      # expect "exit ok"
```
`LastTaskResult : 0` = success. Verified 2026-10-11 13:49 local: result 0, one new cycle (15Z) archived, log shows start and exit.

## Problems seen on 2026-10-11 (and fixes)
- First version ran a `.cmd` wrapper (`src/legacy/run_nwm_live.cmd`, now unused). Launched from a session whose console was torn down, it died with `-1073741510` (Ctrl-C) before doing work (seen on 10:20, 12:50 and 13:45 starts; the 10:45 start happened to succeed). Running `pythonw.exe` directly with its own log fixed it.
- The 11:45 and 12:45 runs did not start, and DNS failed for part of that window: consistent with the laptop sleeping. `-StartWhenAvailable` runs a missed start on wake and the 72 h look-back refills any gap. Default `schtasks /Create` also sets "do not start on battery"; the settings above disable that.
- If the PC is off for more than ~10 days, cycles AWS no longer holds are lost for good.

## Limits and tools
- The PC must be on and the user logged in; the task does not wake the machine.
- Disable: `Unregister-ScheduledTask -TaskName FloodLens_NWM_Archiver -Confirm:$false`. Pause: `Disable-ScheduledTask -TaskName FloodLens_NWM_Archiver`.
- Measure publication delay (Last-Modified of f001/f018 minus issue time, last 12 cycles): `python src/live/nwm_delay.py` -> `data/forecasts/live_delay.csv` (overwrites that CSV each time). Measured 2026-10-11: median 104 min AWS, 104 GCS, 103 NOMADS; max 119 / 113 / 107.
- Manual catch-up: `python src/nwm_backfill.py 2026-10-10T22` (UTC ISO hour) or `python src/nwm_backfill.py 120` (hours back).

# Live NCDOT closures/incidents archiver (T14)

- Script: `src/closures_live.py`. One query per run to NCDOT's public ArcGIS Online layer **NCDOT_TIMS_Incidents** (`https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMS_Incidents/FeatureServer/0`, no token; NCDOT metadata: repackaged from the TIMS feed every 5 min). Saves `data/closures_live/YYYY-MM-DD/incidents_YYYYMMDDTHHMMZ.geojson` with exclusive create (an existing file is never overwritten). Log: `data/closures_live/logs/closures_live.log`.
- Why this endpoint: the documented TIMS API (`eapps.ncdot.gov/services/traffic-prod/v1/incidents`) now returns only a notice that it was retired on 2026-05-27; its replacement (`drivenc.gov/api/v2/get/event`) requires a developer key tied to an account, which we do not use (no access behind a login). Terms found: NCDOT GIS use limitation (not a legal document, NCDOT not liable for errors); no published rate limit, so we make one request (~750 KB) per hour.
- Each snapshot holds all current incidents statewide (roadwork, closures, special events, weather, crashes) with `IsFullClosure`, `StartDateTime`, `EndDateTime`, `Reason`, `Condition`, road and county. First snapshot 2026-10-11 18:36Z: 801 incidents, 290 full closures.
- NCDOT also publishes `NCDOT_TIMSIncidentsHistory` (137,965 records, start dates 2017-09 .. 2026-10) but it holds **no records for 2018-09-10..10-15**, so it cannot replace the Florence records request.

Setup (PowerShell):
```powershell
$root = "C:\Users\nisha\OneDrive\Desktop\Projects\lifeline"; $py = "C:\Users\nisha\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
$a = New-ScheduledTaskAction -Execute $py -Argument "closures_live.py" -WorkingDirectory "$root\src"
$t = New-ScheduledTaskTrigger -Once -At 00:15 -RepetitionInterval (New-TimeSpan -Hours 1)
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName FloodLens_Closures_Live -Action $a -Trigger $t -Settings $s -Force
```
Verified 2026-10-11 14:37 local: `LastTaskResult 0`, snapshot saved. Unlike the NWM archiver this cannot back-fill: an hour the PC is off is lost.
