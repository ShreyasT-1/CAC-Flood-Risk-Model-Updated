"""Phase 2 / T15 Step 1 (data only, no model): pull the NCDOT TIMS incident history (ArcGIS Online NCDOT_TIMSIncidentsHistory, points + lines), count records per month 2019->, flag flood-related full closures
with the regex fixed in docs/validation_protocol.md Amendment 3, build events (gap > 72 h) and list candidates (>= 30 records, >= 3 counties). Usage (repo root): python src/validation/50_t15_step1_closures.py"""
import os, re, json, time, requests, pandas as pd, numpy as np
O = "data/phase2/t15/"; os.makedirs(O, exist_ok=True); B = "https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_TIMSIncidentsHistory/FeatureServer/"
def pull(layer, geom, name):
    p = O + name
    if os.path.exists(p): return pd.read_parquet(p)
    rows, off = [], 0
    while True:
        for k in range(6):
            try: j = requests.get(B + f"{layer}/query", params=dict(where="1=1", outFields="*", returnGeometry="true" if geom else "false", outSR=4326, f="json", resultOffset=off, resultRecordCount=1000, orderByFields="OBJECTID"), timeout=180).json(); break
            except Exception: time.sleep(15)
        f = j.get("features", [])
        for x in f:
            a = x["attributes"]
            if geom and x.get("geometry"): a["_geom"] = json.dumps(x["geometry"])
            rows.append(a)
        off += len(f)
        if not f or not j.get("exceededTransferLimit", False): break
    d = pd.DataFrame(rows); d.to_parquet(p); return d
P = pull(0, True, "history_points.parquet"); L = pull(1, True, "history_lines.parquet"); print("points", len(P), "lines", len(L))
for c in ["StartDateTime", "EndDateTime", "CreationDate", "LastUpdateDateTime"]: P[c] = pd.to_datetime(P[c], unit="ms", utc=True, errors="coerce")
FLOOD = re.compile(r"flood|high water|water over|water across|water on|wash(ed)? ?out|overtop|submerg|under ?water|inundat|erosion", re.I)
P["txt"] = P.Reason.fillna("") + " | " + P.EventName.fillna("") + " | " + P.EventSubType.fillna("")
P["flood_text"] = P.txt.map(lambda s: bool(FLOOD.search(s))); P["full_closure"] = P.IsFullClosure.astype(str).str.lower().eq("true")
P["valid"] = P.StartDateTime.notna() & ~(P.EndDateTime < P.StartDateTime); P = P.sort_values("Id").drop_duplicates("Id")
Q = P[P.valid & (P.StartDateTime >= "2019-01-01")].copy(); Q["month"] = Q.StartDateTime.dt.strftime("%Y-%m"); Q["flood_closure"] = Q.flood_text & Q.full_closure
M = Q.groupby("month").agg(records=("Id", "size"), full_closures=("full_closure", "sum"), flood_text=("flood_text", "sum"), flood_full_closures=("flood_closure", "sum"), counties_flood_closures=("CountyName", lambda s: s[Q.loc[s.index, "flood_closure"]].nunique())).reset_index()
M.to_csv(O + "t15_records_per_month.csv", index=False); pd.set_option("display.width", 200, "display.max_rows", 200); print(M.to_string(index=False))
print("\nfield summary (post-2019 points): EventType", Q.EventType.value_counts(dropna=False).head(8).to_dict(), "| IsFullClosure", Q.IsFullClosure.value_counts(dropna=False).to_dict())
print("Condition top:", Q.Condition.value_counts(dropna=False).head(8).to_dict()); print("Reason flood-text top:", Q[Q.flood_text].Reason.value_counts().head(10).to_dict())
# events: gap > 72 h between consecutive flood-related full-closure starts
F = Q[Q.flood_closure].sort_values("StartDateTime").copy(); F["ev"] = (F.StartDateTime.diff() > pd.Timedelta(hours=72)).cumsum()
E = F.groupby("ev").agg(start=("StartDateTime", "min"), last_start=("StartDateTime", "max"), records=("Id", "size"), counties=("CountyName", "nunique"), top_counties=("CountyName", lambda s: ", ".join(s.value_counts().head(4).index))).reset_index(drop=True)
E["candidate"] = (E.records >= 30) & (E.counties >= 3); E.to_csv(O + "t15_events_all.csv", index=False); print("\nevents with >= 5 flood-closure records:\n", E[E.records >= 5].to_string(index=False))
C = E[E.candidate].sort_values("records", ascending=False); chosen = C.head(6).sort_values("start"); chosen.to_csv(O + "t15_events_chosen.csv", index=False); F[F.StartDateTime.isin([])]  # no-op
F.to_parquet(O + "flood_closure_points.parquet"); print("\nCANDIDATES", len(C), "| CHOSEN:\n", chosen.to_string(index=False))
