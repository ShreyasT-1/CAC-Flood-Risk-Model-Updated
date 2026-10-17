"""Phase 2 / T15 under Amendment 4, Step 1: events from flood-related CLOSED records (Condition == 'Closed' + flood regex), gap > 72 h, >= 30 records and >= 3 counties, start >= 2019-01-01. Counts only; no model output.
Usage (repo root): python src/validation/51_t15_events_a4.py"""
import re, pandas as pd, numpy as np
O = "data/phase2/t15/"; P = pd.read_parquet(O + "history_points.parquet")
for c in ["StartDateTime", "EndDateTime"]: P[c] = pd.to_datetime(P[c], unit="ms", utc=True, errors="coerce")
FLOOD = re.compile(r"flood|high water|water over|water across|water on|wash(ed)? ?out|overtop|submerg|under ?water|inundat|erosion", re.I)
P["txt"] = P.Reason.fillna("") + " | " + P.EventName.fillna("") + " | " + P.EventSubType.fillna("")
P = P.sort_values("Id").drop_duplicates("Id"); P["valid"] = P.StartDateTime.notna() & ~(P.EndDateTime < P.StartDateTime)
Q = P[P.valid & (P.StartDateTime >= "2019-01-01") & (P.Condition == "Closed") & P.txt.map(lambda s: bool(FLOOD.search(s)))].sort_values("StartDateTime").copy()
Q["ev"] = (Q.StartDateTime.diff() > pd.Timedelta(hours=72)).cumsum()
E = Q.groupby("ev").agg(start=("StartDateTime", "min"), last_start=("StartDateTime", "max"), records=("Id", "size"), counties=("CountyName", "nunique"), top_counties=("CountyName", lambda s: ", ".join(s.value_counts().head(5).index))).reset_index(drop=True)
E["candidate"] = (E.records >= 30) & (E.counties >= 3); E.to_csv(O + "t15a4_events_all.csv", index=False)
C = E[E.candidate].sort_values("records", ascending=False); ch = C.head(6).sort_values("start").reset_index(drop=True); ch["event_id"] = ["E%d" % (i + 1) for i in range(len(ch))]
ch["flow_start"] = ch.start - pd.Timedelta(hours=48); ch["flow_end"] = ch.last_start + pd.Timedelta(hours=24); ch.to_csv(O + "t15a4_events_chosen.csv", index=False)
Q.merge(ch[["ev", "event_id"]].rename(columns={"ev": "ev_old"}), left_on="ev", right_on="ev_old", how="inner") if False else None
E2 = E.reset_index().rename(columns={"index": "ev"}); Q = Q.merge(E2[["ev", "candidate"]], on="ev"); Q = Q[Q.candidate]
m = {r.ev if "ev" in ch else None: r.event_id for r in ch.itertuples()}
Q.to_parquet(O + "t15a4_closure_points.parquet")
pd.set_option("display.width", 220); print("events with >= 10 records:\n", E[E.records >= 10].to_string(index=False)); print("\ncandidates", len(C), "\nCHOSEN:\n", ch.to_string(index=False))
