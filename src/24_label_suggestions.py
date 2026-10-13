"""Phase 2 / T3: add SUGGESTED review columns to data/phase0/florence_label_review.csv. Nothing is auto-accepted: reviewer_decision / reviewer_crossing_id / reviewer_notes stay blank.
Suggestions are my reading of each remark (hand-written below, one line each). Original file is kept as florence_label_review.orig.csv. Usage (repo root): python src/24_label_suggestions.py"""
import os, shutil, numpy as np, pandas as pd
P = "data/phase0/florence_label_review"
if not os.path.exists(P + ".orig.csv"): shutil.copy(P + ".csv", P + ".orig.csv")
d = pd.read_csv(P + ".orig.csv")
A, R, U = "accept", "reject", "uncertain"
# report_id: (decision, flag, crossing override or None, reason)
S = {
152: (A, "", None, "NC-53 closed by water across road; crossing V2_0165 is on NC-53 (Burgaw Creek, 71 m)."),
116: (R, "high_water_not_closure", None, "High water reported at a ramp, no closure stated."),
160: (A, "", None, "US-421 impassable due to flooding; OSM crossing on US-421 at 127 m (poor quality, may be unassessable)."),
37: (A, "duplicate_event_with_82", None, "US-17 impassable by flooding near Old Shallotte Rd; crossing on US-17 (165 m). Same place/time as #82: one event, not two."),
82: (A, "duplicate_event_with_37", None, "US-17 closed both directions by flooding near Shallotte; same crossing and time as #37 (count once)."),
81: (A, "", None, "US-17 impassable by flooding near NC-211; crossing on US-17 (181 m)."),
80: (A, "", None, "US-17 closed at the Town Creek bridge; NCDOT structure V2_0064 on US-17 (183 m): best label in the set."),
26: (R, "tree_powerline_noise", None, "Whisper Creek Lane blocked by fallen trees, not flooding."),
123: (A, "", None, "N Kerr Ave closed by flooding; Spring Branch bridge on N Kerr Ave (199 m)."),
64: (R, "cross_street_landmark", None, "Closed road is Mill Branch Rd NW; the match fired on the landmark Project Rd NW."),
112: (A, "reassigned_to_nearest", "NEAREST", "Dairy Farm Rd impassable by high water; the match used landmark Sidbury Rd, but the crossing on Old Dairy Farm Rd is 35 m away."),
168: (R, "tree_powerline_noise", None, "College Rd blocked by downed power lines and trees."),
58: (R, "cross_street_landmark", None, "Closed road is Jabbertown Rd; the match fired on landmark E Leonard St."),
78: (A, "", None, "US-17 Business closed by flooding in Shallotte; OSM crossing on US-17 Business (269 m)."),
161: (U, "location_check", None, "US-421 closed by flooding but remark says Bladen County near Burgaw; check on a map that crossing V2_1380 (284 m) is the right place."),
149: (R, "cross_street_landmark", None, "Closed road is NC-11; the match fired on landmark Crooked Run Rd (crossing carries SR1324)."),
85: (A, "", None, "Zion Church Rd NE closed by flooding; OSM crossing on that road (296 m)."),
135: (R, "cross_street_landmark;surge_prone", None, "Closed road is USS North Carolina Rd (Battleship Rd); US-421 is the landmark. River/surge-prone location."),
69: (R, "cross_street_landmark", None, "Closed road is NC-211; the match fired on landmark Stone Chimney Rd."),
71: (A, "", None, "NC-906 impassable by flooding; NCDOT structure V2_0021 on NC-906 (361 m)."),
79: (A, "", None, "US-17 impassable by flooding near NC-87; OSM crossing on US-17 (365 m)."),
126: (U, "ramps_not_mainline", None, "I-40/I-140 interchange ramps flooded and impassable; crossing is OSM I-40 at 377 m, not the ramps themselves."),
172: (R, "tree_powerline_noise", None, "Parmele Rd blocked by trees and power lines."),
144: (R, "cross_street_landmark", None, "Closed road is Horse Branch Rd; the match fired on landmark Penderlea Hwy."),
125: (U, "underpass_pluvial?", None, "Gordon Rd flooded beneath I-40 overpass (no closure stated); crossing carries an I-40 ramp, not Gordon Rd."),
136: (U, "two_roads;underpass_pluvial?", None, "Water across Gordon Rd and College Rd, impassable; the matched crossing carries an I-40 ramp, not either road."),
68: (U, "possible_surge_overwash", None, "NC-211/Howe Rd closed by flooding near Dosher Cutoff (Southport), where #56 reports overwash; tide/surge may be the cause; crossing is on NC-211 (429 m)."),
74: (A, "", None, "Old Ocean Hwy impassable by flooding; OSM crossing on that road (443 m)."),
153: (R, "cross_street_landmark", None, "Closed road is NC-53; the match fired on landmark US-117."),
166: (R, "tree_powerline_noise", None, "Carolina Beach Rd blocked by downed power lines and trees."),
63: (A, "dist_499m_borderline", None, "Midway Rd/NC-906 closed by flooding; OSM crossing on that road at 499 m (just inside 500 m; report coordinates are rounded to ~1 km)."),
60: (A, "dist_over_500m", None, "Little Macedonia Rd NW closed by flooding; crossing on that road at 515 m (does not count toward the 500 m rule)."),
150: (A, "dist_over_500m;closure_typo", None, "NC-210 'ipassable' (typo hid it from the closure filter) due to flooding; crossing on NC-210 at 532 m."),
173: (R, "tree_powerline_noise", None, "Princess Place Dr blocked by downed trees."),
73: (A, "dist_over_500m", None, "Old Fayetteville Rd impassable by flooding; crossing on that road at 561 m."),
124: (A, "reassigned_to_nearest;dist_199m", "V2_0102", "Water over the bridge on Kerr Ave; the match fired on landmark Spring View Dr, but the Spring Branch bridge on Kerr Ave (V2_0102) is 199 m away."),
167: (R, "tree_powerline_noise", None, "Castle Hayne Rd closed by downed power lines."),
72: (A, "dist_over_500m", None, "Ocean Isle Beach Rd SW impassable by flooding; crossing on that road at 599 m."),
83: (R, "cross_street_landmark", None, "Closed road is US-17; the match fired on landmark Ocean Isle Beach Rd."),
139: (A, "dist_over_500m", None, "Coras Grove Rd impassable by flooding; crossing on that road at 633 m."),
67: (A, "dist_over_500m", None, "NC-211 closed by flooding near West Trace Dr; OSM crossing on NC-211 at 637 m."),
155: (A, "dist_over_500m", None, "NC-53 impassable by flooding at Bell Williams Rd; crossing on NC-53 at 647 m."),
154: (A, "dist_over_500m", None, "NC-53 closed by flooding near Horse Branch Rd; crossing on NC-53 at 649 m."),
70: (R, "cross_street_landmark", None, "Closed road is NC-211; the match fired on landmark W 9th St."),
34: (R, "storm_surge", None, "County officials attribute the US-421 closure to storm surge in downtown Wilmington; not riverine."),
115: (A, "dist_over_500m", None, "Castle Hayne Rd impassable by high water; OSM crossing on that road at 763 m."),
65: (R, "cross_street_landmark", None, "Closed road is Mt Misery Rd NE; the match fired on landmark Blue Banks Loop Rd."),
143: (R, "cross_street_landmark", None, "Closed road is NC-53; the match fired on landmark NC-50."),
119: (R, "high_water_not_closure;tree_powerline_noise", None, "High waters reported, mixed with downed lines and trees; no closure stated."),
134: (A, "dist_over_500m;infrastructure_failure", None, "US-17 Business washed out at 12th St (flood damage); crossing on US-17 Business (Burnt Mill Creek) at 841 m."),
61: (A, "dist_over_500m", None, "Longwood Rd NW closed by flooding; crossing on that road at 854 m."),
130: (A, "dist_over_500m;infrastructure_failure", None, "N Kerr Ave washed out; crossing on N Kerr Ave at 866 m."),
165: (R, "tree_powerline_noise", None, "Blue Clay Rd blocked by downed power lines."),
164: (R, "tree_powerline_noise", None, "Blue Clay Rd closed by downed power lines."),
138: (R, "cross_street_landmark", None, "Closed road is Burgaw Creek Loop Rd; the match fired on landmark NC-53."),
59: (R, "cross_street_landmark", None, "Closed road is Lancale Rd NE; the match fired on landmark US-74."),
141: (R, "no_crossing_on_named_road", None, "Real flash-flood washout, but no inventory crossing on Deerfield Dr within 1 km."),
111: (R, "not_a_closure", None, "A car stalled on a flooded street; no road closure."),
77: (R, "no_crossing_on_named_road", None, "Real flood closure, but no inventory crossing on Turkey Trot Rd within 1 km."),
113: (R, "not_a_closure", None, "Flooding reported in an area; no closure stated."),
120: (R, "high_water_not_closure", None, "High water at intersections; no closure stated."),
132: (R, "no_crossing_on_named_road", None, "Real flooded/impassable road, but no inventory crossing on Billmark Dr within 1 km."),
147: (R, "no_crossing_on_named_road", None, "Real flood closure of Johnson Ave/SR-1349, but no inventory crossing on it within 1 km."),
114: (R, "not_a_closure", None, "Residential flooding, no road named."),
56: (R, "possible_surge_overwash;no_crossing_on_named_road", None, "Dosher Cutoff closed by overwash; surge/tide mechanism, and no crossing on it."),
62: (R, "no_crossing_on_named_road", None, "Real flood closure of Malmo Loop Rd, but no inventory crossing on it within 1 km."),
140: (R, "no_crossing_on_named_road", None, "Real washout closure of Country Club Rd, but no inventory crossing on it within 1 km."),
128: (R, "no_crossing_on_named_road", None, "Road failure on Shire Lane; no inventory crossing on it."),
170: (R, "tree_powerline_noise", None, "Gordon Rd blocked by downed trees and power lines."),
145: (R, "no_crossing_on_named_road;duplicate_event_with_146", None, "I-40 impassable by flooding (real, useful for the NCDOT request), but no I-40 crossing within 1 km; same time as #146."),
146: (R, "no_crossing_on_named_road;duplicate_event_with_145", None, "I-40 impassable by flooding (real), no I-40 crossing within 1 km; same time as #145."),
159: (R, "no_crossing_on_named_road", None, "US-17 closed by flooding near Hampstead, but no US-17 crossing within 1 km (nearest is Mill Creek on Factory Rd)."),
131: (R, "not_a_closure", None, "Sinkhole report, not a flood closure."),
66: (R, "no_crossing_on_named_road", None, "NC-133 impassable by flooding, but no NC-133 crossing within 1 km."),
76: (R, "location_mismatch;no_crossing_on_named_road", None, "US-17 southbound closed 'in Wilmington' but filed under Brunswick; the nearest crossing is on SR1357, not US-17."),
84: (R, "no_crossing_on_named_road", None, "US-74/76 closed by flash flooding, but no US-74/76 crossing within 1 km."),
110: (R, "no_crossing_on_named_road", None, "16th St collapsed near Greenfield St; no inventory crossing on 16th St (near Greenfield Lake, mechanism unclear)."),
122: (R, "no_crossing_on_named_road", None, "N Kerr Ave washed out at Bavarian Ln, but no crossing on it within 1 km of these coordinates."),
13: (R, "tree_powerline_noise", None, "Large trees in roads, not flooding."),
148: (R, "not_a_closure", None, "Rescue count, no road named."),
142: (R, "no_crossing_on_named_road", None, "SR-1400 impassable at multiple locations; no inventory crossing on it within 1 km."),
}
assert set(d.report_id) == set(S), (set(d.report_id) ^ set(S))
d["suggested_decision"] = d.report_id.map(lambda i: S[i][0]); d["suggested_flag"] = d.report_id.map(lambda i: S[i][1]); d["suggested_reason"] = d.report_id.map(lambda i: S[i][3])
d["suggested_crossing_id"] = [(r.nearest_crossing_id if S[r.report_id][2] == "NEAREST" else (S[r.report_id][2] or r.named_road_crossing_id)) if S[r.report_id][0] != R else None for r in d.itertuples()]
x = pd.read_parquet("data/phase0/crossings_v2.parquet", columns=["crossing_id", "lat", "lon"]).set_index("crossing_id")
def dist(r):   # metres from the (rounded) report point to the suggested crossing, planar approximation
    c = r.suggested_crossing_id
    if c is None or c not in x.index: return np.nan
    return float(np.hypot((x.lat[c] - r.lat) * 111320, (x.lon[c] - r.lon) * 111320 * np.cos(np.radians(r.lat))))
d["suggested_crossing_dist_m"] = d.apply(dist, axis=1).round(0)
d.to_csv(P + ".csv", index=False)
a = d[d.suggested_decision == A]; u = d[d.suggested_decision == U]
print("decisions:", d.suggested_decision.value_counts().to_dict())
print("flags:", d.suggested_flag.str.split(";").explode().replace("", np.nan).value_counts().to_dict())
for nm, g in (("accept only", a), ("accept + uncertain", pd.concat([a, u]))):
    for cut in (500, 1000):
        k = g[g.suggested_crossing_dist_m <= cut]
        print(f"{nm}, suggested crossing <= {cut} m: reports {len(k)}, unique crossings {k.suggested_crossing_id.nunique()}, unique events (#37/#82 and #123/#124 counted once) {len(k) - int(k.report_id.isin([82, 124]).sum())}")
print("auto-matched (named-road crossing <= 500 m) before review:", int((d.named_road_crossing_dist_m <= 500).sum()), "| of those suggested reject:", int(((d.named_road_crossing_dist_m <= 500) & (d.suggested_decision == R)).sum()))
