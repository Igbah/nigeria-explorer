"""Nigeria Demographic Explorer - batch 5: age & sex structure.
WorldPop R2025A 1 km age/sex counts give each 1 km cell's PROPORTIONS by sex and age; those proportions are applied to the
GRID3 v3.0 100 m population, so every total stays exactly as before. Output: pyramids for every state, LGA and H3 hexagon."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check
check('agesex_dir', 'population_tif')

import json, os, re, glob
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import h3

AGEDIR = FILES["agesex_dir"]
TIF = FILES["population_tif"]
HEXDIR = f"{OUT}/05_population/hex_by_state"
H3_RES = 7
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
log = []

SRC_AGES = [0, 1] + list(range(5, 95, 5))                        # WorldPop groups: 0, 1-4, 5-9 ... 85-89, 90+
LABELS = [f"{a}-{a + 4}" for a in range(0, 80, 5)] + ["80+"]      # output pyramid: 17 groups
def out_group(a): return min(a // 5, 16)
SEXES = ["m", "f"]

# ------------------------------------------------------------------ 1. read the 1 km rasters
def find(sex, age):
    f = glob.glob(f"{AGEDIR}/**/nga_{sex}_{age:02d}_*1km*.tif", recursive=True)
    return f[0] if f else None
ref = rasterio.open(find("f", 0))
H1, W1, T1 = ref.height, ref.width, ref.transform
grid = {}
missing = []
for s in SEXES:
    for a in SRC_AGES:
        f = find(s, a)
        if f is None:
            missing.append((s, a)); continue
        arr = rasterio.open(f).read(1).astype(np.float64)
        arr[~np.isfinite(arr) | (arr < 0)] = 0
        grid[(s, a)] = arr
for s, a in missing:   # interpolate a missing age group from its neighbours (geometric mean, per cell)
    lo, hi = grid[(s, a - 5)], grid[(s, a + 5)]
    grid[(s, a)] = np.where((lo > 0) & (hi > 0), np.sqrt(lo * hi), (lo + hi) / 2)
if missing:
    log.append("MISSING AGE GROUPS: " + ", ".join(f"{'male' if s == 'm' else 'female'} {a}-{a + 4}" for s, a in missing) +
               " were not in the upload and were ESTIMATED for each 1 km cell as the geometric mean of the groups either side. "
               "Send those files and re-run this step to replace the estimate.")
# collapse to 17 output groups x 2 sexes -> (34, H1, W1): males 0..16, females 17..33
K = 2 * len(LABELS)
C = np.zeros((K, H1, W1), dtype=np.float64)
for (s, a), arr in grid.items():
    C[(0 if s == "m" else len(LABELS)) + out_group(a)] += arr
tot1 = C.sum(axis=0)
wp_total = tot1.sum()
Cflat = C.reshape(K, -1).T                 # (cells, 34)
tflat = tot1.ravel()
del grid, C

# ------------------------------------------------------------------ 2. 100 m pixels -> LGA, hexagon, 1 km cell
lga = gpd.read_file(f"{OUT}/06_lga/nga_lga_boundaries.geojson").sort_values("lga_id").reset_index(drop=True)
src = rasterio.open(TIF)
pop = src.read(1); pop[~(np.isfinite(pop) & (pop > 0))] = 0
H, W = pop.shape
zones = rasterize(((g, i + 1) for i, g in enumerate(lga.geometry)), out_shape=(H, W), transform=src.transform, fill=0, dtype="uint16")
rows, cols = np.nonzero(pop)
vals = pop[rows, cols].astype(np.float64)
zz = zones[rows, cols].astype(np.int32)
del zones, pop
xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center"); xs, ys = np.asarray(xs), np.asarray(ys)
if (zz == 0).any():
    m = zz == 0
    opts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(xs[m], ys[m]), crs="EPSG:4326").to_crs("ESRI:102022")
    near = gpd.sjoin_nearest(opts, lga[["geometry"]].assign(zi=np.arange(1, len(lga) + 1)).to_crs("ESRI:102022"), how="left")
    zz[m] = near[~near.index.duplicated()]["zi"].values
inv = ~T1
c1, r1 = inv * (xs, ys)
r1 = np.floor(r1).astype(np.int64); c1 = np.floor(c1).astype(np.int64)
inside = (r1 >= 0) & (r1 < H1) & (c1 >= 0) & (c1 < W1)
cell = np.where(inside, r1 * W1 + c1, -1)
valid = inside & (tflat[np.clip(cell, 0, None)] > 0)
cell = np.where(valid, cell, -1)
hexid = np.array([h3.latlng_to_cell(y, x, H3_RES) for y, x in zip(ys, xs)])
del xs, ys, rows, cols

df = pd.DataFrame({"z": zz, "h3": hexid, "cell": cell, "pop": vals})
g = df.groupby(["z", "h3", "cell"], as_index=False)["pop"].sum()
del df
share_valid = g.loc[g.cell >= 0, "pop"].sum() / g["pop"].sum()

# counts for pairs with a valid 1 km cell
v = g.cell >= 0
props = Cflat[g.loc[v, "cell"].values] / tflat[g.loc[v, "cell"].values][:, None]
counts = np.zeros((len(g), K))
counts[v.values] = props * g.loc[v, "pop"].values[:, None]
# fallback: LGA-average structure (then national) for 100 m people whose 1 km cell is empty in WorldPop
lga_c = pd.DataFrame(counts[v.values]).groupby(g.loc[v, "z"].values).sum()
lga_p = lga_c.div(lga_c.sum(axis=1), axis=0)
nat_p = counts[v.values].sum(axis=0) / counts[v.values].sum()
fb = ~v.values
if fb.any():
    zf = g.loc[fb, "z"].values
    P = np.vstack([lga_p.loc[z].values if z in lga_p.index else nat_p for z in zf])
    counts[fb] = P * g.loc[fb, "pop"].values[:, None]
log.append(f"Age & sex: WorldPop R2025A 1 km age/sex counts (2025) were used only for PROPORTIONS; they were applied to the GRID3 v3.0 100 m "
           f"population, so all totals are unchanged ({g['pop'].sum():,.0f}). {share_valid:.1%} of people fell in a 1 km cell with WorldPop data; "
           f"the rest took their LGA's average age/sex structure. WorldPop's own 2025 total is {wp_total:,.0f} (for reference only). "
           f"Age groups: {', '.join(LABELS)} (WorldPop's 0 and 1–4 merged into 0–4; 80–84, 85–89 and 90+ merged into 80+).")

cols_m = [f"m_{l}" for l in LABELS]; cols_f = [f"f_{l}" for l in LABELS]
cnt = pd.DataFrame(counts, columns=cols_m + cols_f)
cnt["z"], cnt["h3"], cnt["pop"] = g["z"].values, g["h3"].values, g["pop"].values
lga_meta = lga[["lga_id", "lga", "state_code", "state"]].assign(z=np.arange(1, len(lga) + 1))
cnt = cnt.merge(lga_meta[["z", "state_code"]], on="z")

def indicators(d):
    m, f = d[cols_m].sum(axis=1), d[cols_f].sum(axis=1)
    tot = m + f
    kids = d[[f"{s}_{l}" for s in "mf" for l in LABELS[:3]]].sum(axis=1)
    old = d[[f"{s}_{l}" for s in "mf" for l in LABELS[13:]]].sum(axis=1)
    work = tot - kids - old
    out = pd.DataFrame({
        "population": tot.round(0).astype(np.int64), "male": m.round(0).astype(np.int64), "female": f.round(0).astype(np.int64),
        "sex_ratio_m_per_100f": (100 * m / f).round(1),
        "pct_0_14": (100 * kids / tot).round(1), "pct_15_64": (100 * work / tot).round(1), "pct_65_plus": (100 * old / tot).round(1),
        "dependency_ratio": (100 * (kids + old) / work).round(1),
        "under5": d[["m_0-4", "f_0-4"]].sum(axis=1).round(0).astype(np.int64),
        "women_15_49": d[[f"f_{l}" for l in LABELS[3:10]]].sum(axis=1).round(0).astype(np.int64),
        "youth_15_24": d[[f"{s}_{l}" for s in "mf" for l in LABELS[3:5]]].sum(axis=1).round(0).astype(np.int64)})
    return pd.concat([out, d[cols_m + cols_f].round(0).astype(np.int64)], axis=1)

# ------------------------------------------------------------------ 3. aggregate: LGA, state, national, hexagon
by_lga = cnt.groupby("z")[cols_m + cols_f].sum()
lga_as = lga_meta.set_index("z").join(indicators(by_lga)).reset_index(drop=True)
by_state = cnt.groupby("state_code")[cols_m + cols_f].sum()
st_names = lga_meta.drop_duplicates("state_code").set_index("state_code")[["state"]]
state_as = st_names.join(indicators(by_state)).reset_index()
nat = indicators(cnt[cols_m + cols_f].sum().to_frame().T).assign(state_code="NGA", state="Nigeria")
state_as = pd.concat([state_as, nat[state_as.columns]], ignore_index=True)
os.makedirs(f"{OUT}/05_population", exist_ok=True)
state_as.to_csv(f"{OUT}/05_population/agesex_by_state.csv", index=False)
lga_as.to_csv(f"{OUT}/05_population/agesex_by_lga.csv", index=False)
long = state_as.melt(id_vars=["state_code", "state"], value_vars=cols_m + cols_f, var_name="k", value_name="people")
long["sex"] = long.k.str[0].map({"m": "Male", "f": "Female"}); long["age_group"] = long.k.str[2:]
long.drop(columns="k").to_csv(f"{OUT}/05_population/agesex_by_state_long.csv", index=False)

# hexagons (split by state), rewritten with pyramids
hx = cnt.groupby(["state_code", "h3"])[["pop"] + cols_m + cols_f].sum().reset_index()
hx = hx[hx["pop"] >= 1]
for f in glob.glob(f"{HEXDIR}/*.json"):
    os.remove(f)
area = h3.average_hexagon_area(H3_RES, unit="km^2")
for code, d in hx.groupby("state_code"):
    d = d.sort_values("pop", ascending=False)
    M = d[cols_m].round(0).astype(int).values.tolist(); Fm = d[cols_f].round(0).astype(int).values.tolist()
    js = {"state_code": code, "h3_resolution": H3_RES, "hex_area_km2": round(area, 3),
          "source": "GRID3 NGA population v3.0 (100 m) with WorldPop R2025A 2025 age/sex proportions",
          "age_groups": LABELS, "fields": ["h3", "population", "male_by_age", "female_by_age"],
          "cells": [[h, int(round(p)), m, f] for h, p, m, f in zip(d.h3, d["pop"], M, Fm)]}
    name = st_names.loc[code, "state"]
    json.dump(js, open(f"{HEXDIR}/{code}_{slug(name)}_hex_r{H3_RES}.json", "w"), separators=(",", ":"))
log.append(f"Hexagon files rewritten with a male and female count for each of the 17 age groups ({len(hx):,} hexagons).")

# ------------------------------------------------------------------ 4. plug into profiles, LGA table, JSONs, workbook
KEEP = ["sex_ratio_m_per_100f", "pct_0_14", "pct_15_64", "pct_65_plus", "dependency_ratio", "under5", "women_15_49", "youth_15_24", "male", "female"]
prof_path = f"{OUT}/03_state_profiles/state_profiles_master.csv"
prof = pd.read_csv(prof_path, keep_default_na=False, na_values=[""])
prof = prof[[c for c in prof.columns if not c.startswith("age_")]].merge(
    state_as[["state_code"] + KEEP].add_prefix("age_").rename(columns={"age_state_code": "state_code"}), on="state_code")
prof.to_csv(prof_path, index=False)
gw = gpd.read_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson")
gw = gw[[c for c in gw.columns if not c.startswith("age_")]].merge(prof[["state_code"] + [c for c in prof.columns if c.startswith("age_")]], on="state_code")
gw.to_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

lp = pd.read_csv(f"{OUT}/06_lga/lga_profiles.csv", keep_default_na=False, na_values=[""], dtype={"lga_code": str})
lp = lp[[c for c in lp.columns if not c.startswith("age_")]].merge(
    lga_as[["lga_id"] + KEEP].add_prefix("age_").rename(columns={"age_lga_id": "lga_id"}), on="lga_id")
lp.to_csv(f"{OUT}/06_lga/lga_profiles.csv", index=False)
for f in glob.glob(f"{OUT}/06_lga/*.geojson") + glob.glob(f"{OUT}/06_lga/by_state/*.geojson"):
    gg = gpd.read_file(f)
    gg = gg[[c for c in gg.columns if not c.startswith("age_")]].merge(lga_as[["lga_id"] + KEEP].add_prefix("age_").rename(columns={"age_lga_id": "lga_id"}), on="lga_id", how="left")
    gg.to_file(f, driver="GeoJSON", COORDINATE_PRECISION=4 if "simplified" in f or "by_state" in f else 6)

for fjs in glob.glob(f"{OUT}/03_state_profiles/by_state/*.json"):
    js = json.load(open(fjs)); r = state_as[state_as.state_code == js["state_code"]].iloc[0]
    js["age_sex"] = {"age_groups": LABELS, "male": [int(r[c]) for c in cols_m], "female": [int(r[c]) for c in cols_f],
                     **{(k + "_total" if k in ("male", "female") else k): (float(r[k]) if isinstance(r[k], float) else int(r[k])) for k in KEEP},
                     "source": "WorldPop R2025A 2025 proportions applied to GRID3 v3.0 totals"}
    ld = lga_as[lga_as.state_code == js["state_code"]].set_index("lga_id")
    for item in js.get("lgas", []):
        if item["lga_id"] in ld.index:
            rr = ld.loc[item["lga_id"]]
            item["pyramid_male"] = [int(rr[c]) for c in cols_m]; item["pyramid_female"] = [int(rr[c]) for c in cols_f]
            item.update({k: (float(rr[k]) if isinstance(rr[k], float) else int(rr[k])) for k in ["sex_ratio_m_per_100f", "pct_0_14", "pct_65_plus", "dependency_ratio"]})
    json.dump(js, open(fjs, "w"), indent=1, ensure_ascii=False)

x = pd.ExcelFile(f"{OUT}/Nigeria_Explorer_Data.xlsx")
sheets = {s: x.parse(s, keep_default_na=False, na_values=[""]) for s in x.sheet_names}
notes = [n for n in sheets["README_notes"]["cleaning notes"].tolist() if not str(n).startswith(("AGE", "Age & sex", "MISSING AGE", "Hexagon files rewritten"))]
nr = state_as[state_as.state_code == "NGA"].iloc[0]
log.append(f"Nigeria (2025 model): {nr.pct_0_14}% aged 0–14, {nr.pct_15_64}% aged 15–64, {nr.pct_65_plus}% aged 65+; dependency ratio {nr.dependency_ratio}; "
           f"{nr.sex_ratio_m_per_100f} males per 100 females; {nr.under5:,} children under 5; {nr.women_15_49:,} women aged 15–49.")
sheets["README_notes"] = pd.DataFrame({"cleaning notes": notes + ["AGE & SEX (batch 5):"] + log})
s_ = sheets["Sources"]; s_ = s_[s_.dataset != "Age and sex structure"]
sheets["Sources"] = pd.concat([s_, pd.DataFrame([["Age and sex structure", "05_population/agesex_*",
    "WorldPop Global2 R2025A, Nigeria age structures 2025, 1 km (constrained, UN-adjusted)", "Used as proportions on GRID3 v3.0 totals"]], columns=s_.columns)])
sheets["State_Profiles"] = prof
sheets["LGA_Profiles"] = lp
sheets["AgeSex_by_State"] = state_as
sheets["AgeSex_by_LGA"] = lga_as
order = ["README_notes", "Sources", "State_Profiles", "LGA_Profiles", "AgeSex_by_State", "AgeSex_by_LGA"] + \
        [s for s in sheets if s not in ("README_notes", "Sources", "State_Profiles", "LGA_Profiles", "AgeSex_by_State", "AgeSex_by_LGA")]
with pd.ExcelWriter(f"{OUT}/Nigeria_Explorer_Data.xlsx") as xw:
    for s in order:
        sheets[s].to_excel(xw, sheet_name=s[:31], index=False)
open(f"{OUT}/CLEANING_NOTES.txt", "w").write("\n\n".join(f"- {n}" for n in sheets["README_notes"]["cleaning notes"]))
print("\n\n".join(log))
print(state_as[["state", "population", "sex_ratio_m_per_100f", "pct_0_14", "pct_15_64", "pct_65_plus", "dependency_ratio"]].sort_values("pct_0_14").to_string())
