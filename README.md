# FloodLens Lifelines

**Can you still get to help when the roads flood?**

Most flood tools answer *"is this road underwater?"* FloodLens Lifelines answers the question that decides whether people live: **"if the water rises, can this neighbourhood still reach a hospital or fire station, and when does that change?"**

Pilot region: **Cape Fear, North Carolina** (New Hanover, Brunswick and Pender counties, plus a 40 km road-network buffer). Live app: https://lifelines-flax.vercel.app

Built by Nishaanth Jay and Shreyas Thota for the Congressional App Challenge.

> **Scenarios, not predictions.** Everything here is a river-flow scenario, a nowcast or a structural estimate. It never says a road is safe, and a road that is not flagged is "not flagged in this scenario", never an all-clear. See [What we do not claim](#what-we-do-not-claim).

---

## Why this is different

Flood maps colour the ground. This project connects four layers that are normally separate:

1. **Water**: NOAA National Water Model (NWM) streamflow, USGS and NWS river gauges, and NOAA tide stations.
2. **Crossings**: 2,920 bridges, culverts and road-stream intersections, each tied to the stream reach it crosses.
3. **A routing network**: about 246,000 road segments, 6,940 Census block origins, 11 emergency-department hospitals and 220 fire stations.
4. **Consequence**: for every crossing, how many people lose or slow their access to a hospital or fire station if that crossing closes.

The result is the part that matters to an emergency manager: not only *which crossing is under water first*, but **which one hurts most when it goes** ("What Breaks First?").

## What it does

| Feature | What you get |
|---|---|
| **Address check** | Type a Cape Fear street address and see the nearest hospitals and fire stations, drive times, which stream crossings each route uses, and how a replayed storm would have affected them hour by hour. |
| **Florence 2018 replay** | Steps through 18 hours of Hurricane Florence on a map. A crossing closes in the scenario while its stream runs above the 10-year flow. The replay states what it misses: surge, tide and street flooding. |
| **Nowcast** | Observed river gauges (USGS + NWS flood categories) and coastal water levels (NOAA CO-OPS), each stamped with its age and a stale flag. |
| **Forecast preview** | The latest NWM short-range forecast (18 hourly leads), shown as a share of the 10-year flow. Explicitly unvalidated and not a closure probability. |
| **What Breaks First?** | Crossings ranked by when their streams first exceed the 10-year flow, alongside what closing each would do to access. |
| **Honest by design** | Every view carries a mode label (REPLAY / NOWCAST / FORECAST), a source, a generated-at time and its caveats. No user data is stored. |

## Results we can stand behind

Every number below is copied from [`docs/claims.md`](docs/claims.md) and traces to a file in this repo. Methods, protocols and thresholds were written down **before** the data was pulled ([`docs/validation_protocol.md`](docs/validation_protocol.md)).

- **The water signal is real.** At the hours when flooded-road reports were filed, NWM flow on the matched stream was far above the same stream's ordinary flow: **AUC 0.958** (95% CI 0.916 to 0.992). The flow peaked within 24 hours of the report in **81%** of cases versus 14% by chance.
- **The hydrology matches reality.** Against 43 pilot-area USGS gauges, the model's peak flow was within a factor of 2 for **76.7%** of gauge-storms, with a median peak-time error of **4 hours**.
- **The routing engine is sound.** Baseline drive times to the nearest hospital land within 30% of OSRM for **91.3%** of 150 test blocks.
- **Nowcast skill.** For gauge stage, a fixed, untuned gradient-boosting model catches flood-stage onsets far better than persistence: recall at 50% precision of **0.504 vs 0.005** on Florence, a held-out test storm.
- **Across nine 2023 to 2025 NC storm windows**, crossings near recorded flood closures had higher modelled peak-flow ratios than other crossings in the same counties (pooled **AUC 0.69 to 0.72**).

## What we do not claim

We publish our failures alongside our wins ([`docs/claims.md`](docs/claims.md), sections 2 and 3).

- We do **not** claim to predict which roads will close. Crossing-level tests were weak or failed (for example, AUC 0.55 against high-water marks and 0.58 against the observed Florence flood extent). The nine-storm result above is a ranking result with low precision, not a closure predictor.
- We do **not** claim forecast skill. Every validation test is a hindcast or an operational-analysis replay.
- We do **not** say any road, block or address is safe or protected.
- Scenarios use river flow only: no storm surge, tide, street flooding, deck height, scour or debris. The coastal layer is shown separately and is not combined with the crossing scenarios.
- Closure labels are positives only (there are no records of roads confirmed open) and are partly unreviewed.
- In the Florence replay the hazard layer saturates (241 of 250 seed crossings exceed their 2-year flow at once), so scenario levels barely separate. The graph also did not reproduce Wilmington's documented isolation.

If you want a project that overclaims, this is the wrong repo. If you want one that tells you where it breaks, keep reading.

## How it works

```
USGS / NWS gauges ----+
NOAA NWM forecast ----+--> hazard by stream reach --> crossing status (scenario)
NOAA tide stations ---+                                       |
NCDOT structures + NBI + OSM roads --> 2,920 crossings -------+
Census blocks + CMS hospitals + fire stations --> routing graph
                                                              |
                          hourly shortest-path routing from hospitals and fire stations
                                                              |
        address / block access, time to isolation, critical crossing, detour, redundancy
                                                              |
                               Next.js + MapLibre website (web/)
```

1. **Hazard.** NWM channel flow is compared with each reach's recurrence flows (2-year and 10-year). A crossing is "closed in the scenario" while its stream runs above the 10-year flow.
2. **Crossings.** Built from NCDOT structure locations, the National Bridge Inventory and OpenStreetMap road-stream intersections, joined to NWM reaches.
3. **Network.** OSM drive network, snapped Census block origins, and hospital and fire-station destinations.
4. **Consequence.** Remove a closed crossing from the graph, re-run multi-source shortest paths and count who loses or slows access.
5. **App.** A static Next.js site reads exported JSON; routes come from the public Valhalla router and geocoding from OpenStreetMap Nominatim.

## Repository map

| Path | What is in it |
|---|---|
| `src/` | The pipeline. Numbered scripts run in order (see [`src/README.md`](src/README.md)): gauges, NWM crosswalk, observed data, ML tables and splits, routing engine, validation tests, live nowcast and forecast jobs. `src/inventory/` builds the data inventory. |
| `web/` | The website: Next.js 15, React 19, TypeScript, Tailwind, MapLibre. Reads `web/public/data/sample/*.json`. |
| `export/sample/`, `data/export/` | Exported tables the app reads: crossings, consequence ranking, blocks, Florence replay, live conditions. Field meanings in [`data/export/README.md`](data/export/README.md). |
| `reports/` | Data cards, validation reports, the untuned sample model write-ups and limitations. |
| `docs/` | The claims register, validation protocols, ML handoff, data sources, freeze summary, setup guides. |
| `data/inventory/` | Dataset inventory (every source: URL, vintage, licence, status, SHA-256). |
| `handoff_for_shreyas/` | Data handoff for the ML teammate. |
| `.github/workflows/` | Hourly jobs that refresh the live layers. |
| `config/` | Reach and gauge lists. |

## Data sources

NOAA National Water Model (retrospective v3.0 and operational), USGS Water Data API, NWS NWPS, NOAA CO-OPS tides, NOAA Stage IV rainfall (via NCAR), NCDOT structure locations, road inundation points and TIMS incident history, National Bridge Inventory, FEMA NFHL, OpenStreetMap, US Census blocks and geocoder, CMS Provider Data, NC OSFM fire stations, IEM Local Storm Reports, NCEI Storm Events, OpenFEMA, Open-Meteo previous-runs. Full list with licences: [`data/inventory/README.md`](data/inventory/README.md).

## Run it

```bash
# website
cd web
npm install
npm run dev            # http://localhost:3000

# refresh live layers (writes export/sample/*.json)
python src/45_nowcast.py
python src/44_forecast_preview.py
cd web && npm run sample:sync

# reproduce the headline numbers from the claims register
python src/80_repro_headlines.py
```

The full pipeline needs a `USGS_API_KEY` and several GB of downloads. Large raw data is not committed; `data/inventory/` and `src/inventory/` document how to recreate it. Hourly refresh setup: [`docs/live_refresh_setup.md`](docs/live_refresh_setup.md).

## Data and privacy

No account, no user data stored. Addresses typed into the app go to OpenStreetMap's Nominatim, and routes to the public Valhalla router. Hospital and fire-station locations are public. Some data received from county agencies is not redistributed here; ask before sharing it.

## Status

Cape Fear pilot, technical freeze 1 (`technical-freeze-1`). A nowcast and scenario tool, not an emergency service. **Not for emergency use. In an emergency, call 911.**

## Acknowledgements

Brunswick County Emergency Management and the Brunswick County Sheriff's Office, for Florence context and service-island maps. NOAA, USGS, NCDOT, FEMA and the OpenStreetMap community, whose open data makes this possible.
