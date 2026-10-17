"""Phase 2 / T10A step 2: my hand-read corrections to the automatic suggestions in data/phase2/t10/report_candidates.csv (all 120 reports with a structure on a named road within 500 m were read).
Automatic rule over-rejects when the closed road is named after a word like AND/ON/AT; it can also accept a landmark. Writes suggested_decision (accept|reject|uncertain) + reviewer columns left blank.
Runs on 'accept' only; 'uncertain' is excluded from the primary test and used in a sensitivity. Usage (repo root): python src/validation/31_t10_review_suggestions.py"""
import pandas as pd
P = "data/phase2/t10/report_candidates.csv"; d = pd.read_csv(P, dtype={"reviewer_decision": str, "reviewer_notes": str}).fillna({"reviewer_decision": "", "reviewer_notes": ""})
if "auto_suggested_decision" not in d: d["auto_suggested_decision"] = d.suggested_decision
ACC = {4127: "Bowman-Barrier Rd is the closed road (creek flooded it); heuristic cut the remark at 'and'.", 8917: "Roadway under water from Banks Bridge Rd (bridge); named road is the closed road.",
       7573: "Bridge on South Toe River Rd closed by flooding; named road is the closed road.", 10016: "Creek overflowing the bridge on Mangum Dairy Rd, road impassable.",
       13046: "Kool Park Rd closed by flooding near Snow Creek.", 14913: "Clarks Creek Rd itself reported impassable under water (NC-194 also).", 17733: "County Line Creek flooded Race Track Rd, impassable.",
       17730: "South Fork New River over the bridge on Kings Creek Rd, impassable.", 17728: "New River over Martin Gambill Bridge on Farmers Fish Camp Rd, impassable.", 16877: "Road closed at the 7700 block of N Point Blvd by flooding.",
       16880: "NC-67 (Reynolda Rd) closed by flooding; named road is the closed road.", 16945: "NC-73 impassable by flooding west of Ellerbe.", 20383: "Holbert Cove Rd closed by flooding."}
UNC = {529: "Bridge under water at an intersection of two roads; unclear which road.", 2476: "Road closed at an intersection of Avent Ferry Rd and Trailwood Dr; which road, and cause, unclear.", 6593: "Bridge under water at an intersection; unclear which road carries it.",
       5835: "Closure 'near the intersection' of two roads; unclear which.", 10028: "Flooded/closed road reported at an intersection in urban Raleigh; may be pluvial.", 10027: "Four feet of water, rescues, no closure word; urban Raleigh (pluvial?).",
       10032: "Capital Blvd closed under a bridge (underpass, pluvial?).", 8551: "Water across Gordon Rd and College Rd; the matched crossing carries an I-40 ramp.", 9896: "Closure at an intersection of two roads; unclear which.",
       14369: "List of many closed roads in Greensboro; matched road is one of several.", 15579: "Stream flooding at an intersection of two roads, closure; unclear which road.", 16885: "Water rescue and closure at an intersection in Winston-Salem (urban/pluvial?).",
       19199: "Closed at an intersection of two roads; road now passable.", 19197: "I-440 lanes blocked by standing water (pluvial); crossing is on I-440 West.", 22228: "Ramp impassable by flood water (pluvial?); crossing carries Boylan Ave."}
REJ = {18271: "Closed road is Highway 64 near Frozen Creek; Chestnut St is the gauge location, a landmark."}
for k, v in ACC.items(): d.loc[d.report_id == k, ["suggested_decision", "suggested_reason"]] = ["accept", "manual: " + v]
for k, v in UNC.items(): d.loc[d.report_id == k, ["suggested_decision", "suggested_reason"]] = ["uncertain", "manual: " + v]
for k, v in REJ.items(): d.loc[d.report_id == k, ["suggested_decision", "suggested_reason"]] = ["reject", "manual: " + v]
d.to_csv(P, index=False)
print(d.suggested_decision.value_counts().to_dict(), "| accept unique crossings", d[d.suggested_decision == "accept"].crossing_id.nunique(), "| manual changes", len(ACC) + len(UNC) + len(REJ))
