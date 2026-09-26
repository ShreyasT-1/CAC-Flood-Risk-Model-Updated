# Coastal Flood Risk Model

A predictive model for coastal flood insurance risk, covering tracts within 30 miles of the coastline from Maine to Florida (14 East Coast states).

## What it does

`floodData.py` has two modes:

- **`build`** — downloads and assembles the training data: NFIP claims and policy history, Census demographics, coastline distance, elevation, rainfall, and FEMA flood zone coverage for every qualifying coastal tract.
- **`lookup <address>`** — geocodes a single address and returns a plain-language flood risk report using the same underlying data sources. This is the backend for the address-lookup app.

## What the model predicts

Each row is one coastal tract in one time window. The model predicts flood insurance claims in a later period using only information available earlier — no leakage from the future.

- **Targets:** claim counts, and claims occurring outside FEMA-designated high-risk zones, over the target window (with policy-years as exposure).
- **Train:** features from 2009–2013 → claims in 2014–2017.
- **Test:** features from 2013–2017 → claims from 2018 onward (includes Hurricanes Florence, Dorian, and Helene).
- **Val:** a held-out set of whole counties, excluded from training.
- **Predict:** current tracts scored with no known target (production inference).

## Data sources

| Source | Provides |
|---|---|
| OpenFEMA NFIP claims | Claim counts, payments, and zones by tract and year |
| OpenFEMA NFIP policies | Policy-years by tract and year, in and out of flood zones |
| Census ACS / Gazetteer | Housing units, land/water area, tract centroids |
| Natural Earth coastline | Distance to coast |
| USGS elevation service | Elevation at tract centroid |
| NOAA Atlas 14 | 100-year, 24-hour rainfall |
| FEMA NFHL map service | Share of tract area in high-risk flood zones |
| USGS high-water marks | Historical flood marks near each tract |

## Input features

**Claims history:** `claimRateFeat`, `outsideClaimRateFeat`, `paidPerPolicyYearFeat`, `claimRateSlope`, `claimsHistPerHousingUnit`

**Insurance & coverage:** `sfhaPolicyShare`, `takeUpRate`

**Flood zone map:** `sfhaAreaShare`, `moderateAreaShare`

**Historical flooding:** `hwmMarksBefore`

**Geography:** `lat`, `lon`, `landSqmi`, `waterShare`, `distToCoastMi`

**Physical:** `elevMeanFt`, `elevMinFt`, `elevRangeFt`, `rain100yr24hrIn`

`model_ready.parquet` adds missing-value indicator flags per feature, applies log/arcsinh transforms to skewed columns, and standardizes using train-set statistics only. `model_scaler.json` stores that fit so new addresses can be scored on the same scale at inference time.


```

## Model

- PyTorch regression model, trained on `model_ready.parquet`.
- Poisson loss with exposure, to handle count data weighted by policy-years.
- Scored against baseline models (state average, past claim rate, zone-only, Poisson GLM) using a single shared scoring function (deviance + top-decile capture) to keep comparisons fair.

## Status

Data pipeline in progress — see in-repo notes for current source completion status.
