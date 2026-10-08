"""Shared helpers: paths, USGS OGC API client (paginated, rate-limit aware, cached)."""
import json, os, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW, DER, REP = ROOT / "data/raw", ROOT / "data/derived", ROOT / "reports"
for d in (RAW, DER, REP, RAW / "usgs", RAW / "nwps"):
    d.mkdir(parents=True, exist_ok=True)

USGS = "https://api.waterdata.usgs.gov/ogcapi/v1/"
START, END = "2015-01-01", "2023-12-31"
NWM_END = "2023-01-31 23:00"  # chrtout.zarr ends 2023-02-01 00:00 (verified); truncate everything to this

_S = requests.Session()
if os.environ.get("USGS_API_KEY"):  # never printed
    _S.headers["X-Api-Key"] = os.environ["USGS_API_KEY"]


def get(url, params=None, tries=6):
    """GET with retry; honours X-RateLimit-Remaining and 429 Retry-After."""
    i = 0
    while i < tries:
        i += 1
        try:
            r = _S.get(url, params=params, timeout=180)
        except requests.RequestException:
            time.sleep(2 ** i); continue
        if r.status_code == 429:  # hourly quota: wait it out, not counted as a failure
            i -= 1; time.sleep(max(int(r.headers.get("Retry-After", 60)), 30)); continue
        if r.status_code >= 500:
            time.sleep(2 ** i); continue
        rem = r.headers.get("X-RateLimit-Remaining")
        if rem is not None and int(rem) < 3:
            time.sleep(30)
        r.raise_for_status()
        return r
    raise RuntimeError(f"failed after {tries} tries: {url}")


def ogc_items(collection, **params):
    """All features of an OGC collection query, following `next` links."""
    params = {"f": "json", "limit": 10000, **params}
    url, out = f"{USGS}collections/{collection}/items", []
    while url:
        j = get(url, params).json()
        out += j["features"]
        url = next((l["href"] for l in j.get("links", []) if l["rel"] == "next"), None)
        params = None  # next link already carries the query
    return out
