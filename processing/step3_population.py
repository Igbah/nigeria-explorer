"""Nigeria Demographic Explorer - batch 3: GRID3 population v3.0 (100 m) -> state totals + H3 hexagons per state."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check
check('population_tif')

import json, os, re, glob, time
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
import h3

TIF = FILES["population_tif"]
HEXDIR = f"{OUT}/05_population/hex_by_state"
os.makedirs(HEXDIR, exist_ok=True)
H3_RES = 7          # ~5.2 km² per hexagon
log = []
t0 = time.time()

states = gpd.read_file(f"{OUT}/00_reference/nga_states.geojson")
lookup = pd.read_csv(f"{OUT}/00_reference/state_lookup.csv", keep_default_na=False)

src = rasterio.open(TIF)
pop = src.read(1)
pop[~(np.isfinite(pop) & (pop > 0))] = 0
H, W = pop.shape
total = pop.sum(dtype=np.float64)

# ------------------------------------------------------------------ state zones (pixel -> state index 1..37)
states = states.sort_values("state_code").reset_index(drop=True)
zones = rasterize(((g, i + 1) for i, g in enumerate(states.geometry)), out_shape=(H, W),
                  transform=src.transform, fill=0, dtype="uint8", all_touched=False)
sums = np.bincount(zones.ravel(), weights=pop.ravel().astype(np.float64), minlength=len(states) + 1)
outside = sums[0]
# populated pixels outside every polygon (coast / border slivers) -> nearest state
orow, ocol = np.nonzero((zones == 0) & (pop > 0))
if len(orow):
    ox, oy = rasterio.transform.xy(src.transform, orow, ocol, offset="center")
    opts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(ox, oy), crs="EPSG:4326").to_crs("ESRI:102022")
    near = gpd.sjoin_nearest(opts, states[["geometry"]].assign(zi=np.arange(1, len(states) + 1)).to_crs("ESRI:102022"), how="left")
    near = near[~near.index.duplicated()]
    zones[orow, ocol] = near["zi"].values.astype("uint8")
    sums = np.bincount(zones.ravel(), weights=pop.ravel().astype(np.float64), minlength=len(states) + 1)
log.append(f"Population raster: GRID3 NGA population v3.0, 100 m grid (14,392 × 11,532 cells, EPSG:4326). Total = {total:,.0f} people "
           f"in {int((pop > 0).sum()):,} settled cells. {outside:,.0f} people ({100 * outside / total:.2f}%) sat in cells just outside the "
           f"state polygons (coastline/border slivers) and were assigned to the nearest state.")

st = states[["state_code", "state", "area_km2"]].copy()
st["population"] = np.round(sums[1:]).astype(np.int64)
st["pop_share_pct"] = (100 * st.population / st.population.sum()).round(2)
st["density_per_km2"] = (st.population / st.area_km2).round(1)

# ------------------------------------------------------------------ H3 hexagons
rows, cols = np.nonzero(pop)
vals = pop[rows, cols].astype(np.float64); zz = zones[rows, cols]
xs, ys = rasterio.transform.xy(src.transform, rows, cols, offset="center")
xs, ys = np.asarray(xs), np.asarray(ys)
cells = np.array([h3.latlng_to_cell(y, x, H3_RES) for y, x in zip(ys, xs)])
hexdf = pd.DataFrame({"h3": cells, "z": zz, "pop": vals}).groupby(["z", "h3"], as_index=False)["pop"].sum()
hexdf["state_code"] = hexdf["z"].map(lambda i: states.state_code.iloc[i - 1])
hexdf["pop"] = hexdf["pop"].round(1)
hexdf = hexdf[hexdf["pop"] >= 1]
hex_area = h3.average_hexagon_area(H3_RES, unit="km^2")
log.append(f"Hexagons: H3 resolution {H3_RES} (≈{hex_area:.1f} km² each). {len(hexdf):,} populated hexagons nationwide; a hexagon on a state border "
           "is split so each state file only counts its own people. Hexagons with fewer than 1 person are dropped.")

# per-state stats from hexes: settlement concentration
agg = []
for code, d in hexdf.groupby("state_code"):
    d = d.sort_values("pop", ascending=False)
    fn = re.sub(r"[^a-z0-9]+", "_", st.loc[st.state_code == code, "state"].iloc[0].lower()).strip("_")
    json.dump({"state_code": code, "h3_resolution": H3_RES, "hex_area_km2": round(hex_area, 3),
               "source": "GRID3 NGA population v3.0 (100 m), aggregated", "fields": ["h3", "population"],
               "cells": [[h, int(round(p))] for h, p in zip(d.h3, d["pop"])]},
              open(f"{HEXDIR}/{code}_{fn}_hex_r{H3_RES}.json", "w"), separators=(",", ":"))
    cum = d["pop"].cumsum() / d["pop"].sum()
    agg.append({"state_code": code, "populated_hexagons": len(d),
                "max_hex_population": int(d["pop"].iloc[0]),
                "pct_area_holding_half_the_people": round(100 * (int((cum < 0.5).sum()) + 1) / len(d), 1)})
st = st.merge(pd.DataFrame(agg), on="state_code")

# ------------------------------------------------------------------ facilities per population
hfs = pd.read_csv(f"{OUT}/04_health_facilities/health_facilities_by_state.csv", keep_default_na=False)
st = st.merge(hfs[["state_code", "facilities_total", "level_primary", "level_secondary", "level_tertiary", "status_functional"]], on="state_code")
st["facilities_per_10k"] = (1e4 * st.facilities_total / st.population).round(2)
st["functional_facilities_per_10k"] = (1e4 * st.status_functional / st.population).round(2)
st["people_per_facility"] = (st.population / st.facilities_total).round(0).astype(int)
st["people_per_secondary_or_tertiary"] = (st.population / (st.level_secondary + st.level_tertiary)).round(0).astype(int)
st["primary_per_10k"] = (1e4 * st.level_primary / st.population).round(2)

# displacement / CRSV rates
prof_path = f"{OUT}/03_state_profiles/state_profiles_master.csv"
prof = pd.read_csv(prof_path, keep_default_na=False, na_values=[""])
st = st.merge(prof[["state_code", "idmc_displaced_total", "crsv_incidents"]], on="state_code")
st["displaced_per_1k_2025_26"] = (1e3 * st.idmc_displaced_total / st.population).round(2)
st = st.drop(columns=["idmc_displaced_total", "crsv_incidents"])
st = lookup[["state_code", "geozone"]].merge(st, on="state_code")
st = st[["state_code", "state", "geozone", "area_km2", "population", "pop_share_pct", "density_per_km2", "populated_hexagons",
         "max_hex_population", "pct_area_holding_half_the_people", "facilities_total", "facilities_per_10k",
         "functional_facilities_per_10k", "primary_per_10k", "people_per_facility", "people_per_secondary_or_tertiary",
         "displaced_per_1k_2025_26"]]
st.to_csv(f"{OUT}/05_population/population_by_state.csv", index=False)

# 1 km summary raster for quick web/GIS use (sum of 10x10 cells)
f = 10
Hc, Wc = H // f, W // f
coarse = pop[:Hc * f, :Wc * f].reshape(Hc, f, Wc, f).sum(axis=(1, 3)).astype("float32")
prof_r = src.profile.copy()
prof_r.update(width=Wc, height=Hc, transform=src.transform * rasterio.Affine.scale(f), dtype="float32", nodata=0, compress="deflate", tiled=True,
              blockxsize=256, blockysize=256)
with rasterio.open(f"{OUT}/05_population/nga_population_1km.tif", "w", **prof_r) as dst:
    dst.write(coarse, 1)

# ------------------------------------------------------------------ update state profiles
keep = [c for c in prof.columns if not c.startswith("pop_")]
prof = prof[keep].merge(st.drop(columns=["state", "geozone", "area_km2", "facilities_total"]).add_prefix("pop_")
                        .rename(columns={"pop_state_code": "state_code"}), on="state_code")
prof.to_csv(prof_path, index=False)
gw = gpd.read_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson")
gw = gw[[c for c in gw.columns if not c.startswith("pop_")]].merge(
    prof[["state_code"] + [c for c in prof.columns if c.startswith("pop_")]], on="state_code")
gw.to_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
for fjs in glob.glob(f"{OUT}/03_state_profiles/by_state/*.json"):
    js = json.load(open(fjs)); r = st[st.state_code == js["state_code"]].iloc[0]
    js["population"] = {"total": int(r.population), "share_of_nigeria_pct": float(r.pop_share_pct), "density_per_km2": float(r.density_per_km2),
                        "facilities_per_10k": float(r.facilities_per_10k), "people_per_facility": int(r.people_per_facility),
                        "people_per_secondary_or_tertiary_facility": int(r.people_per_secondary_or_tertiary),
                        "displaced_per_1k_2025_26": float(r.displaced_per_1k_2025_26),
                        "hex_file": os.path.basename(glob.glob(f"{HEXDIR}/{js['state_code']}_*")[0]),
                        "source": "GRID3 NGA population v3.0 (modelled estimate)"}
    json.dump(js, open(fjs, "w"), indent=1, ensure_ascii=False)

# ------------------------------------------------------------------ workbook + notes
x = pd.ExcelFile(f"{OUT}/Nigeria_Explorer_Data.xlsx")
sheets = {s: x.parse(s, keep_default_na=False, na_values=[""]) for s in x.sheet_names}
notes = [n for n in sheets["README_notes"]["cleaning notes"].tolist() if not str(n).startswith(("POPULATION", "Population raster", "Hexagons", "Health access"))]
nat = st.population.sum()
log.append(f"Health access: facilities per 10,000 people range from {st.facilities_per_10k.min()} ({st.loc[st.facilities_per_10k.idxmin(), 'state']}) "
           f"to {st.facilities_per_10k.max()} ({st.loc[st.facilities_per_10k.idxmax(), 'state']}); national {1e4 * st.facilities_total.sum() / nat:.2f}.")
sheets["README_notes"] = pd.DataFrame({"cleaning notes": notes + ["POPULATION (batch 3):"] + log})
src_t = sheets["Sources"]; src_t = src_t[src_t.dataset != "Population"]
sheets["Sources"] = pd.concat([src_t, pd.DataFrame([["Population", "05_population/*", "GRID3 NGA population v3.0 (WorldPop / GRID3), 100 m",
                                                    "Modelled estimate, not a census count; people per 100 m cell"]], columns=src_t.columns)])
sheets["State_Profiles"] = prof
sheets["Population_by_State"] = st
order = ["README_notes", "Sources", "State_Profiles", "Population_by_State"] + [s for s in sheets if s not in ("README_notes", "Sources", "State_Profiles", "Population_by_State")]
with pd.ExcelWriter(f"{OUT}/Nigeria_Explorer_Data.xlsx") as xw:
    for s in order:
        sheets[s].to_excel(xw, sheet_name=s, index=False)
open(f"{OUT}/CLEANING_NOTES.txt", "w").write("\n\n".join(f"- {n}" for n in sheets["README_notes"]["cleaning notes"]))
print("\n\n".join(log)); print(f"{time.time() - t0:.0f}s")
print(st.sort_values("population", ascending=False).to_string())
