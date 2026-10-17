"""Kill Test 2, Step 1: Florence flood-closure table from the IEM LSR export. Rule-based; every row gets a keep/exclude reason.
Input : data/raw/lsr_201809132029_201810212029.xlsx (only reports 2018-09-13 .. 2018-09-22 UTC; Michael excluded by date)
Output: data/derived/florence_closures.csv
Rules are fixed here and applied mechanically (order = precedence of exclusion reason):
 1 out_of_window | 2 county_not_target (County column not NEW HANOVER/BRUNSWICK/PENDER) | 3 county_coord_mismatch (point not inside the
 County-column county, 2 km tolerance) | 4 duplicate (same UTC time, lat, lon, remark) | 5 downed_tree_or_powerline (no water word)
 | 6 no_water_indicator | 7 area_wide | 8 no_specific_road | else KEEP (broad). strict = broad AND remark names a water feature or water
 crossing the road (bridge|creek|branch|run|river|canal|swamp|stream|culvert|water across/over/flowing/rushing).
"""
import re
import numpy as np, pandas as pd, geopandas as gpd
from common import *

SRC = RAW / "lsr_201809132029_201810212029.xlsx"
COUNTIES = {"NEW HANOVER": "129", "BRUNSWICK": "019", "PENDER": "141"}

WATER = re.compile(r"FLOOD|HIGH WATER|WASH(?:ED)?[ -]?OUT|OVERTOP|OVERWASH|WATER (?:ACROSS|OVER|FLOWING|RUSHING|CROSSING|CAUSED)|"
                   r"STANDING WATER|WATER[S]? (?:REPORTED|ON|IN)|SURROUNDED BY WATER|WATER[ -]COVERED")
TREEPOWER = re.compile(r"TREE|POWER ?LINE|POWERLINE|TRANSFORMER|UTILITY POLE|POLE DOWN")
AREA = re.compile(r"NUMEROUS|SEVERAL ROADS|MULTIPLE ROADS|MANY ROADS|RESIDENTIAL AREA|NEIGHBORHOOD|RESCUE|THROUGHOUT|COUNTY-?WIDE|"
                  r"MULTIPLE LOCATIONS IN|SE WILMINGTON|HOMES")
STRICT = re.compile(r"\bBRIDGE|\bCREEK|\bBRANCH\b|\bRUN\b|\bRIVER|\bCANAL|\bSWAMP|\bSTREAM|\bCULVERT|"
                    r"WATER (?:ACROSS|OVER|FLOWING|RUSHING|CROSSING)|HIGH WATER ACROSS|WATER CROSSING")
CLOSURE = re.compile(r"CLOSED|IMPASS|IPASS|WASHED OUT|WASHOUT|BLOCKED|OVERWASH|STRANDED|ROAD FAILURE|SINK ?HOLE")

# ---- road identifier parsing -------------------------------------------------------------
SUFFIX = {"ROAD": "RD", "RD": "RD", "STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "DRIVE": "DR", "DR": "DR", "LANE": "LN",
          "LN": "LN", "BOULEVARD": "BLVD", "BLVD": "BLVD", "HIGHWAY": "HWY", "HWY": "HWY", "LOOP": "LOOP", "CUTOFF": "CUTOFF",
          "CUTTOFF": "CUTOFF", "PLACE": "PL", "PL": "PL", "WAY": "WAY", "CIRCLE": "CIR", "TRAIL": "TRL", "PARKWAY": "PKWY", "BYP": "BYP"}
STOP = set("THE A AN AT ON OF IN NEAR AND BY TO FROM AS IS ARE WAS WERE BETWEEN INTERSECTION CLOSED IMPASSABLE IPASSABLE DUE WITH FLOODED "
           "FLOODING ACROSS OVER ALONG BOTH DIRECTIONS EASTBOUND WESTBOUND SOUTHBOUND NORTHBOUND ROADWAY MAKING HAS CROSSING "
           "HAD HAVE BEEN BECOME BECAME ROAD FAILURE WASHED OUT REPORTED CAUSED CAUSING OFF BENEATH THROUGH AREA FOR FLOOD HIGH WATER NWS "
           "EMPLOYEE REPORTS REPORT BLOCKED TRAINED SPOTTER ABOUT MILES SOUTH HIGHWAYS HIGHWAY EXIT".split())
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
ROUTE = re.compile(r"\b(I|US|NC|SR)[- ]?(\d{1,4})\b")


def parse_roads(rem):
    out = []
    for sent in re.split(r"\.(?:\s|$)", rem.upper()):  # sentence-wise, so "...FLOODING. ROAD IS..." never forms a road name
        t = re.sub(r"[()]", " ", sent.replace("/", " / ").replace(",", " "))
        t = re.sub(r"US[- ]?(\d+)\s*/\s*(\d+)", r"US- US-", t)  # US-74/76 -> US-74 US-76
        routes = [f"{a} {n}" for a, n in ROUTE.findall(t)]
        toks = re.findall(r"[A-Z0-9'&-]+", t)
        names = []
        for i, w in enumerate(toks):
            if w in SUFFIX and i > 0:
                j, parts = i - 1, []
                while j >= 0 and len(parts) < 3 and toks[j] not in STOP and not ROUTE.fullmatch(toks[j]) and toks[j] != "/":
                    parts.insert(0, toks[j]); j -= 1
                if parts and not (len(parts) == 1 and parts[0] in DIRS):
                    names.append(" ".join(parts + [SUFFIX[w]]))
        out += routes + names
    return list(dict.fromkeys(out))


def main():
    d = pd.read_excel(SRC)
    d["time_utc"] = pd.to_datetime(d["Report Time (UTC Timezone)"], format="%Y/%m/%d %H:%M")
    d = d.rename(columns={"Lat": "lat", "Lon": "lon", "Remark": "remark", "County": "county", "Event Type": "event_type", "Location": "location"})
    d["remark"] = d.remark.fillna("").astype(str).str.upper().str.strip()
    d["county"] = d.county.astype(str).str.upper().str.strip()
    d["report_id"] = d.index
    cs = gpd.read_file(f"zip://{RAW / 'counties.zip'}")
    cs = cs[(cs.STATEFP == "37")].to_crs(32617)
    pts = gpd.GeoSeries(gpd.points_from_xy(d.lon, d.lat), crs=4326).to_crs(32617)
    poly = {n: cs[cs.COUNTYFP == c].geometry.union_all() for n, c in COUNTIES.items()}
    d["coord_county"] = [next((n for n, g in poly.items() if g.contains(p)), "") for p in pts]
    d["coord_ok"] = [(c in poly and poly[c].buffer(2000).contains(p)) for c, p in zip(d.county, pts)]
    d["roads"] = d.remark.map(parse_roads)

    reason = pd.Series("", index=d.index)
    def mark(mask, r):
        m = mask & (reason == "")
        reason[m] = r
    mark(~((d.time_utc >= "2018-09-13") & (d.time_utc < "2018-09-23")), "out_of_window")
    mark(~d.county.isin(COUNTIES), "county_not_target")
    mark(~d.coord_ok, "county_coord_mismatch")
    mark(d.duplicated(["time_utc", "lat", "lon", "remark"], keep="first"), "duplicate")
    water = d.remark.str.contains(WATER)
    mark(d.remark.str.contains(TREEPOWER) & ~water, "downed_tree_or_powerline")
    mark(~water, "no_water_indicator")
    mark(d.remark.str.contains(AREA), "area_wide")
    mark(d.roads.map(len) == 0, "no_specific_road")
    d["status"] = np.where(reason == "", "keep", "exclude")
    d["reason"] = np.where(reason == "", "kept_broad", reason)
    d["strict"] = (d.status == "keep") & d.remark.str.contains(STRICT)
    d["explicit_closure_word"] = d.remark.str.contains(CLOSURE)
    d["cause_surge"] = d.remark.str.contains("SURGE|TIDE")
    d["roads"] = d.roads.map(" | ".join)
    keep = ["report_id", "time_utc", "county", "coord_county", "event_type", "lat", "lon", "location", "remark", "roads", "status", "reason",
            "strict", "explicit_closure_word", "cause_surge"]
    d[keep].to_csv(DER / "florence_closures.csv", index=False)

    t3 = d[d.county.isin(COUNTIES) & (d.time_utc >= "2018-09-13") & (d.time_utc < "2018-09-23")]
    print(f"reports in window (all NC): {((d.time_utc >= '2018-09-13') & (d.time_utc < '2018-09-23')).sum()} | in 3 counties by County column: {len(t3)}")
    print(f"kept BROAD: {(d.status == 'keep').sum()} | kept STRICT: {int(d.strict.sum())}")
    print("excluded by reason (3-county, in-window reports only):")
    print(d.loc[t3.index][d.loc[t3.index].status == 'exclude'].reason.value_counts().to_string())
    print("\nCounty column vs coordinate county disagreements in the 3 counties (in-window):")
    print(t3[~t3.coord_ok][["report_id", "county", "coord_county", "lat", "lon", "remark"]].assign(remark=lambda x: x.remark.str[:90]).to_string())
    k = d[d.status == "keep"]
    print(f"\nFULL KEPT LIST ({len(k)})")
    for r in k.itertuples():
        print(f"{r.report_id:4d} {r.time_utc:%m%d %H:%M} {r.county[:3]} {'S' if r.strict else '-'} {r.lat:.3f},{r.lon:.3f} roads=[{r.roads}] | {r.remark[:150]}")


if __name__ == "__main__":
    main()
