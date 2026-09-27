"""Pack the cleaned dataset into small files for the Nigeria Demographic Explorer web page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check

import json, os, glob, re, shutil
import numpy as np
import pandas as pd
import geopandas as gpd

D = OUT
W = WEB
shutil.rmtree(W, ignore_errors=True)
for s in ["state", "hex", "lga", "fac"]:
    os.makedirs(f"{W}/{s}", exist_ok=True)

def r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)

# ---- states (national map)
g = gpd.read_file(f"{D}/03_state_profiles/state_profiles_web.geojson")
keep = {"state_code": "code", "state": "name", "capital": "capital", "geozone": "zone", "area_km2": "area",
        "pop_population": "pop", "pop_density_per_km2": "density", "mpi2021_poor_pct": "poor",
        "pop_facilities_per_10k": "hf10k", "age_pct_0_14": "u15", "age_dependency_ratio": "dep",
        "mmr2016_per_100k": "mmr", "pop_displaced_per_1k_2025_26": "disp1k", "cpr2017_modern_pct": "cpr",
        "hf_facilities_total": "hf", "pop_people_per_secondary_or_tertiary": "pphosp", "age_sex_ratio_m_per_100f": "sexr"}
g = g[list(keep) + ["geometry"]].rename(columns=keep)
b = g.bounds
g["bbox"] = [[round(a, 3), round(bb, 3), round(c, 3), round(d, 3)] for a, bb, c, d in b.values]
g["geometry"] = g.simplify(0.01, preserve_topology=True)
fc = json.loads(g.to_json())
for f in fc["features"]:
    p = f["properties"]
    for k, v in list(p.items()):
        if isinstance(v, float): p[k] = round(v, 2)
json.dump(fc, open(f"{W}/states.geojson", "w"), separators=(",", ":"))

# national reference
agenat = pd.read_csv(f"{D}/05_population/agesex_by_state.csv", keep_default_na=False)
nr = agenat[agenat.state_code == "NGA"].iloc[0]
L = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+"]
json.dump({"pop": int(nr.population), "male": [int(nr[f"m_{l}"]) for l in L], "female": [int(nr[f"f_{l}"]) for l in L], "ages": L,
           "u15": float(nr.pct_0_14), "dep": float(nr.dependency_ratio), "sexr": float(nr.sex_ratio_m_per_100f)},
          open(f"{W}/nigeria.json", "w"), separators=(",", ":"))

# ---- per-state profile
for f in glob.glob(f"{D}/03_state_profiles/by_state/*.json"):
    js = json.load(open(f)); code = js["state_code"]
    js.pop("lga_file", None); js["population"].pop("hex_file", None)
    js.get("health_facilities", {}).pop("level_by_ownership", None)
    json.dump(js, open(f"{W}/state/{code}.json", "w"), separators=(",", ":"), ensure_ascii=False)

# ---- hexagons (already compact)
for f in glob.glob(f"{D}/05_population/hex_by_state/*.json"):
    js = json.load(open(f))
    out = {"ages": js["age_groups"], "cells": js["cells"]}
    json.dump(out, open(f"{W}/hex/{js['state_code']}.json", "w"), separators=(",", ":"))

# ---- LGAs per state
lk = {"lga_id": "id", "lga": "name", "population": "pop", "density_per_km2": "density", "hf_total": "hf", "hf_per_10k": "hf10k",
      "hf_secondary": "hf2", "hf_tertiary": "hf3", "age_pct_0_14": "u15", "displaced_total_2025_26": "disp", "area_km2": "area"}
for f in glob.glob(f"{D}/06_lga/by_state/*.geojson"):
    gl = gpd.read_file(f)
    code = gl.state_code.iloc[0]
    gl = gl[list(lk) + ["geometry"]].rename(columns=lk)
    fc = json.loads(gl.to_json())
    for ft in fc["features"]:
        for k, v in list(ft["properties"].items()):
            if isinstance(v, float): ft["properties"][k] = round(v, 2)
    json.dump(fc, open(f"{W}/lga/{code}.geojson", "w"), separators=(",", ":"))

# ---- facilities per state, compact rows
hf = pd.read_csv(f"{D}/04_health_facilities/health_facilities_clean.csv", keep_default_na=False, na_values=[""], low_memory=False)
hf = hf[(hf.service_type == "Patient care") & hf.latitude.notna()]
LEV = ["Primary", "Secondary", "Tertiary", "Not stated"]
OWN = ["Public", "Private", "Not stated"]
STA = ["Functional", "Partially Functional", "Not Functional", "Not stated"]
GRP = sorted(hf.facility_group.unique())
for code, d in hf.groupby("state_code"):
    rows = [[round(a, 5), round(bb, 5), n, LEV.index(l) if l in LEV else 3, OWN.index(o), STA.index(s) if s in STA else 3, GRP.index(gp), lg]
            for a, bb, n, l, o, s, gp, lg in zip(d.longitude, d.latitude, d.name, d.level, d.ownership_simple, d.functional_status, d.facility_group, d.lga)]
    json.dump({"levels": LEV, "owners": OWN, "status": STA, "groups": GRP,
               "fields": ["lon", "lat", "name", "level", "owner", "status", "group", "lga"], "rows": rows},
              open(f"{W}/fac/{code}.json", "w"), separators=(",", ":"), ensure_ascii=False)
tot = sum(os.path.getsize(p) for p in glob.glob(f"{W}/**/*", recursive=True) if os.path.isfile(p))
print(f"web data: {len(glob.glob(f'{W}/**/*.*', recursive=True))} files, {tot / 1e6:.1f} MB")
