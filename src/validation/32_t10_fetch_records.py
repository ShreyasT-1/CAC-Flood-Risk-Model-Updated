"""Phase 2 / T10B: full 1979-2023 NWM v3.0 retro hourly record for every reach of the assessed report crossings -> data/phase2/t10/nwm_full_record.parquet (m3/s, float32). Usage (repo root): python src/32_t10_fetch_records.py"""
import sys, time, pandas as pd; sys.path.insert(0, "src"); from nwm_retro import fetch
C = pd.read_parquet("data/phase2/t10/report_crossings.parquet"); ids = C.feature_id.dropna().astype("int64").unique(); print("reaches", len(ids), flush=True)
t = time.time(); F = fetch(ids); print(F.shape, "NaN share", float(F.isna().mean().mean()), "s", round(time.time() - t), flush=True)
F.to_parquet("data/phase2/t10/nwm_full_record.parquet"); print(F.index[0], F.index[-1])
