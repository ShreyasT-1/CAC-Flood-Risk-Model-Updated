# Label review: how to fill `data/review/label_review_sheet.csv`

Open the CSV in Excel/LibreOffice (keep it as CSV, UTF-8). It has 790 rows: every closure-report candidate in `data/phase0/florence_label_review.csv` (81, `source=florence`) and `data/phase2/t10/report_candidates.csv` (709, `source=t10`). Rows are sorted with the model's "uncertain" rows first (15 in t10 + 5 in florence = 20), then "accept", then "reject".

**The `model_suggested_*` columns are a model suggestion, not a decision.** They are my reading of each remark. Ignore them if you disagree. Do not edit them or any other column except the three reviewer columns.

## What the decisions mean
A *label* says: "this report is a real flood-related closure (or impassable water) of the road at the listed crossing."

- **accept** - the remark says a road/bridge was closed, impassable or under water from flooding, AND the listed crossing (`nearest_crossing_*`) is on that road/stream near the reported place.
  Example (florence 80): "US-17 IS CLOSED IN BOTH DIRECTIONS AT THE TOWN CREEK BRIDGE ... DUE TO FLOODING", listed crossing V2_0064, US17, Town Creek Overflow, 183 m.
- **reject** - not a flood closure, or the listed crossing is clearly the wrong place/road (trees or power lines down, high water with no closure, a different road than the one closed, surge/tide rather than a river).
  Example (florence 26): "WHISPER CREEK LANE ... IS BLOCKED ON BOTH ENDS BY LARGE TREES DOWN ON ROAD" - a tree closure, not flooding.
- **uncertain** - you cannot tell from the remark and a map (which of two roads is meant, possible surge or drainage flooding, location mismatch).
  Example (t10 529): "BRIDGE UNDER WATER NEAR THE INTERSECTION OF INDIAN GRAVE ROAD AND HIGHWAY 268" - the listed crossing is on SR1514, not obviously either named road.

## How to fill the sheet
1. `reviewer_decision` (required on every row): exactly `accept`, `reject` or `uncertain` (lower case). No blanks.
2. `reviewer_crossing_id` (optional on most rows): leave blank to mean "the listed `nearest_crossing_id` is right". Fill it only to name a different crossing id (must exist: `V2_xxxx` for florence rows, `T10_xxxxx` for t10 rows). **Required** for an `accept` on a row that has no listed crossing (many t10 rows have none).
3. `reviewer_notes` (optional): a few words on why.
4. Save as CSV in place. Then check without changing anything: `python src/validation/70_apply_label_review.py` (dry run; prints counts and every problem). When it reports no errors, `python src/validation/70_apply_label_review.py --apply` writes the decisions into the two source files (originals kept as `*.csv.orig`).
5. Then `python src/validation/71_label_sensitivity.py` for the label sensitivity.

Rows you accept that the model rejected (and the reverse) are the interesting ones; the sensitivity script reports how much the T10 results move.
