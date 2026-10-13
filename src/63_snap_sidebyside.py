"""Side-by-side of the two origin snaps (phase-1 snap = published export in data/export/, phase-2 re-snap = alternative build in data/phase2/export_resnap_alt/) plus the 2026-10-12 re-snap check (src/60_resnap_check.py).
Writes docs/export_snap_sidebyside.md (included in the export README by src/export_data.py) and data/phase2/resnap_check/sidebyside.json. Usage (repo root): python src/63_snap_sidebyside.py"""
import json, pandas as pd
A, B = "data/export/", "data/phase2/export_resnap_alt/"; C = pd.read_csv("data/phase2/resnap_check/resnap_check.csv")
def stats(d):
    bl = pd.read_csv(d + "blocks_export.csv", dtype={"geoid20": str}); co = pd.read_csv(d + "consequence_ranking.csv"); hr = pd.read_csv(d + "florence_replay_hourly.csv"); man = json.load(open(d + "manifest.json"))
    top = co.dropna(subset=["people_affected"]).sort_values("people_affected", ascending=False).head(3)
    s = hr[hr.crossing_set == "seed"]; pk = lambda sc, c: int(s[s.scenario == sc][c].max())
    return dict(snap=man["snap"], origin_blocks=len(bl), origin_people=int(bl.pop20.sum()), unreachable_blocks_ed=int((~bl.baseline_reachable_ed_hospital).sum()), unreachable_people_ed=int(bl.pop20[~bl.baseline_reachable_ed_hospital].sum()),
                median_snap_m=float(bl.snap_m.median()), blocks_snap_gt500m=int((bl.snap_m > 500).sum()), crossings_with_effect=int((co.people_affected > 0).sum()), top3_people_affected=[int(v) for v in top.people_affected], top3_ids=list(top.id),
                peak_blocks_lost_ed_RL2=pk("RL2", "blocks_lost_ed_hospital_access"), peak_people_lost_ed_RL2=pk("RL2", "people_lost_ed_hospital_access"), peak_blocks_lost_ed_RL10=pk("RL10", "blocks_lost_ed_hospital_access"), peak_people_lost_ed_RL10=pk("RL10", "people_lost_ed_hospital_access"),
                peak_people_lost_fire_RL10=pk("RL10", "people_lost_fire_station_access"))
P, R = stats(A), stats(B); s30 = C[C.group == "sample_30_now_reachable"]; dr = C[C.group == "dropped_21"]
rank = pd.read_csv(A + "consequence_ranking.csv").set_index("id").people_affected.rank(); rk2 = pd.read_csv(B + "consequence_ranking.csv").set_index("id").people_affected.rank(); both = pd.concat([rank, rk2], axis=1).dropna()
chk = dict(sample_n=len(s30), flagged_service_only=int(s30.new_only_ramp_or_service.sum()), flagged_ramp=int(s30.new_has_ramp.sum()), flagged_across_water=int(s30.new_line_crosses_water.sum()), flagged_any_user_criterion=int((s30.new_only_ramp_or_service | s30.new_has_ramp | s30.new_line_crosses_water).sum()),
           new_snap_gt500m=int((s30.new_snap_m > 500).sum()), median_old_snap_m=float(s30.old_snap_m.median()), median_new_snap_m=float(s30.new_snap_m.median()), dropped_n=len(dr), dropped_people=int(dr.pop20.sum()), dropped_cross_water=int(dr.new_line_crosses_water.sum()), dropped_all_old_unreachable=bool(dr.old_was_unreachable.all()),
           spearman_people_affected_rank=round(float(both.corr(method="spearman").iloc[0, 1]), 3))
json.dump(dict(phase1_snap=P, resnap=R, check=chk), open("data/phase2/resnap_check/sidebyside.json", "w"), indent=1)
md = f"""## Origin snap: phase-1 snap vs phase-2 re-snap (checked 2026-10-12)
The phase-2 re-snap moved blocks that the phase-1 snap had left on tiny disconnected road fragments onto the largest connected part of the graph. It cut baseline-unreachable people but **failed a manual check**, so **this export uses the phase-1 snap**. Check (`src/60_resnap_check.py`, `data/phase2/resnap_check/resnap_check.csv`): 30 random blocks that were unreachable under the phase-1 snap and reachable under the re-snap, plus all {chk['dropped_n']} blocks the re-snap dropped.
- **{chk['flagged_service_only']} of {chk['sample_n']}** sampled blocks were snapped to a node whose only roads are service roads (flagged as wrong); 0 to ramps ({chk['flagged_ramp']}); {chk['flagged_across_water']} had the straight line to the snapped node crossing an OSM river/canal/tidal channel (a crude test: streams and ditches were not counted). A further {chk['new_snap_gt500m']} of {chk['sample_n']} moved more than 500 m (median snap distance {chk['median_old_snap_m']:.0f} m with the phase-1 snap, {chk['median_new_snap_m']:.0f} m after the re-snap); that criterion is mine, not counted in the flag. More than 3 flagged, so the re-snap is not used.
- The {chk['dropped_n']} dropped blocks ({chk['dropped_people']} people) were all unreachable under the phase-1 snap; their nearest node on the main network is 1.6-6.2 km away, and {chk['dropped_cross_water']} of {chk['dropped_n']} would cross water to reach it (Caswell Beach / Oak Island blocks). They are dropped under the re-snap and kept (as baseline-unreachable) under the phase-1 snap.

| | Phase-1 snap (this export) | Phase-2 re-snap (alternative build) |
|---|---|---|
| origin blocks / people | {P['origin_blocks']:,} / {P['origin_people']:,} | {R['origin_blocks']:,} / {R['origin_people']:,} |
| blocks / people with no baseline route to an ED hospital (excluded from loss counts) | {P['unreachable_blocks_ed']} / {P['unreachable_people_ed']:,} | {R['unreachable_blocks_ed']} / {R['unreachable_people_ed']:,} |
| median / blocks over 500 m snap distance | {P['median_snap_m']:.0f} m / {P['blocks_snap_gt500m']} | {R['median_snap_m']:.0f} m / {R['blocks_snap_gt500m']} |
| crossings whose single closure changes access or time for any block | {P['crossings_with_effect']} | {R['crossings_with_effect']} |
| top 3 `people_affected` (people) | {P['top3_people_affected']} | {R['top3_people_affected']} |
| Florence hindcast seed set, RL2: peak people / blocks losing ED-hospital access | {P['peak_people_lost_ed_RL2']:,} / {P['peak_blocks_lost_ed_RL2']} | {R['peak_people_lost_ed_RL2']:,} / {R['peak_blocks_lost_ed_RL2']} |
| same, RL10 | {P['peak_people_lost_ed_RL10']:,} / {P['peak_blocks_lost_ed_RL10']} | {R['peak_people_lost_ed_RL10']:,} / {R['peak_blocks_lost_ed_RL10']} |
| same, RL10, fire-station access (people) | {P['peak_people_lost_fire_RL10']:,} | {R['peak_people_lost_fire_RL10']:,} |

The choice barely moves the headline numbers (RL2 peak people losing ED-hospital access differs by {abs(R['peak_people_lost_ed_RL2'] - P['peak_people_lost_ed_RL2'])} people, {100 * abs(R['peak_people_lost_ed_RL2'] - P['peak_people_lost_ed_RL2']) / P['peak_people_lost_ed_RL2']:.1f}%); it matters for the {P['unreachable_blocks_ed']} blocks left on fragments. Rank agreement of `people_affected` between the two builds (Spearman, crossings in both): {chk['spearman_people_affected_rank']}. The phase-1 snap has its own weakness: the {P['unreachable_blocks_ed']} baseline-unreachable blocks sit on isolated fragments, so their access is **not assessed** (not zero), and people there are missing from every loss count.
"""
open("docs/export_snap_sidebyside.md", "w", encoding="utf-8").write(md); print(md); print(json.dumps(chk, indent=1))
