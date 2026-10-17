"""T15 Step-0 check (2026-10-11): rerun the pooled primary test on ALL nine qualifying events (same code, same rule) beside the six-event result.
Builds data/phase2/t15_nine/ by running text-patched copies of 52/53/54 (only the output dir and the event file differ). E1-E6 keep their ids and reuse the already-downloaded flows (same windows);
E7-E9 (the 3 candidates not in the top 6 by record count) get flows from the same GCS mirror. Usage (repo root): python src/validation/55_t15_nine.py"""
import os, shutil, subprocess, sys, pandas as pd
O, N = "data/phase2/t15/", "data/phase2/t15_nine/"; os.makedirs(N, exist_ok=True)
for f in ("nc_reaches.parquet", "t15a4_closure_points.parquet", "history_lines.parquet"): shutil.copy(O + f, N + f)   # t15a4_closure_points already holds all 9 candidates
A = pd.read_csv(O + "t15a4_events_all.csv"); C = A[A.candidate == True].copy(); C["start"] = pd.to_datetime(C.start); C["last_start"] = pd.to_datetime(C.last_start)
old = pd.read_csv(O + "t15a4_events_chosen.csv", parse_dates=["start"]); C["event_id"] = [old.event_id[old.start == s].iloc[0] if (old.start == s).any() else None for s in C.start]
C = C.sort_values("start"); k = 7
for i in C.index[C.event_id.isna()]: C.loc[i, "event_id"] = f"E{k}"; k += 1
C["flow_start"] = C.start - pd.Timedelta(hours=48); C["flow_end"] = C.last_start + pd.Timedelta(hours=24); C.to_csv(N + "t15a4_events_chosen.csv", index=False); print(C[["event_id", "start", "records", "counties"]].to_string(index=False))
def run(src, subs):
    t = open(src, encoding="utf-8").read()
    for a, b in subs: assert a in t, (src, a); t = t.replace(a, b)
    p = N + "_" + os.path.basename(src); open(p, "w", encoding="utf-8").write(t); r = subprocess.run([sys.executable, p]); assert r.returncode == 0, src
P = ('O = "data/phase2/t15/"', 'O = "data/phase2/t15_nine/"')
run("src/validation/52_t15_crossings.py", [P])
run("src/validation/53_t15_flows.py", [P, ('for e in ev.itertuples():', 'for e in ev[ev.event_id.isin(["E7", "E8", "E9"])].itertuples():'),
                           ('pd.DataFrame(rows).to_parquet(O + "t15_peaks.parquet")', 'pd.concat([pd.read_parquet("data/phase2/t15/t15_peaks.parquet"), pd.DataFrame(rows)]).to_parquet(O + "t15_peaks.parquet")')])
run("src/validation/54_t15_test.py", [P])
