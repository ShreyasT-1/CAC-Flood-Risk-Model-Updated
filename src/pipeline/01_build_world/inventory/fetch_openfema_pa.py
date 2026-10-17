"""OpenFEMA Public Assistance Funded Projects Details v2: NC, damage categories C (roads/bridges) and D (water control), counties of Area A and B. No coordinates in this dataset."""
import os, sys, requests, pandas as pd, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_geo import ROOT
U = "https://www.fema.gov/api/open/v2/PublicAssistanceFundedProjectsDetails"
cs = ["Wake", "Durham", "Orange", "New Hanover", "Brunswick", "Pender"]
flt = "stateAbbreviation eq 'NC' and (damageCategoryCode eq 'C' or damageCategoryCode eq 'D') and (" + " or ".join(f"county eq '{c} County'" for c in cs) + ")"
rows, skip = [], 0
while True:
    j = requests.get(U, params={"$filter": flt, "$top": 1000, "$skip": skip, "$orderby": "gmProjectId"}, timeout=120).json()["PublicAssistanceFundedProjectsDetails"]
    rows += j; skip += 1000
    if len(j) < 1000: break
df = pd.DataFrame(rows); d = f"{ROOT}/data/raw_new/openfema_pa"; os.makedirs(d, exist_ok=True); p = f"{d}/pa_projects_CD_areasAB.csv"
assert not os.path.exists(p); df.to_csv(p, index=False); print(len(df))
print(df.groupby(["disasterNumber", "county"]).size().unstack(fill_value=0))
