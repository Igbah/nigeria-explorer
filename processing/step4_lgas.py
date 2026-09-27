"""Nigeria Demographic Explorer - batch 4: LGA boundaries -> LGA population, health facilities and displacement."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check
check('lgas', 'population_tif')

import json, os, re, glob
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize

LGA_SRC = FILES["lgas"]
TIF = FILES["population_tif"]
LD = f"{OUT}/06_lga"
os.makedirs(f"{LD}/by_state", exist_ok=True)
log = []
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

lookup = pd.read_csv(f"{OUT}/00_reference/state_lookup.csv", keep_default_na=False)
ABBR = dict(zip(lookup.abbrev, lookup.state))
states = gpd.read_file(f"{OUT}/00_reference/nga_states.geojson")

# ------------------------------------------------------------------ clean boundaries
g = gpd.read_file(LGA_SRC)
g["state"] = g["statecode"].map(ABBR)
assert g.state.notna().all()
g = g.merge(lookup[["state", "state_code", "geozone"]], on="state")
g["lga_code"] = g["lgacode"].astype(str)
g["lga"] = g["lganame"].str.strip().str.replace(r"\s+", " ", regex=True)
g["lga_id"] = g["state_code"] + "_" + g["lga_code"]
fixed = int((~g.is_valid).sum())
g["geometry"] = g.geometry.make_valid() if fixed else g.geometry
g["area_km2"] = (g.to_crs("ESRI:102022").area / 1e6).round(1)
# does each LGA sit inside the state it claims?
rp = g.copy(); rp["geometry"] = g.representative_point()
chk = gpd.sjoin(rp[["lga_id", "state", "geometry"]], states[["state", "geometry"]].rename(columns={"state": "state_poly"}), how="left", predicate="within")
chk = chk[~chk.index.duplicated()]
mism = chk[chk.state != chk.state_poly]
lga = g[["lga_id", "lga_code", "lga", "state_code", "state", "geozone", "area_km2", "geometry"]].sort_values(["state_code", "lga"]).reset_index(drop=True)
per_state = lga.groupby("state").size()
log.append(f"LGA boundaries: {len(lga)} LGAs in 37 states (eHealth Africa/GRID3, 2019), EPSG:4326, all geometries valid"
           + (f" after repairing {fixed}" if fixed else "") + ". 'Fct' renamed Federal Capital Territory. "
           f"{len(lga) - len(mism)} of {len(lga)} LGAs sit inside the state polygon they are labelled with"
           + (f"; exceptions: {', '.join(mism.lga_id)}" if len(mism) else "") +
           f". LGA codes are unique nationally and identical to the codes in the health facility file. "
           f"States with most LGAs: {', '.join(f'{s} ({n})' for s, n in per_state.sort_values(ascending=False).head(3).items())}.")

# ------------------------------------------------------------------ population by LGA
src = rasterio.open(TIF)
pop = src.read(1); pop[~(np.isfinite(pop) & (pop > 0))] = 0
H, W = pop.shape
zones = rasterize(((geom, i + 1) for i, geom in enumerate(lga.geometry)), out_shape=(H, W), transform=src.transform,
                  fill=0, dtype="uint16")
orow, ocol = np.nonzero((zones == 0) & (pop > 0))
outside = float(pop[orow, ocol].sum(dtype=np.float64))
if len(orow):
    ox, oy = rasterio.transform.xy(src.transform, orow, ocol, offset="center")
    opts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(ox, oy), crs="EPSG:4326").to_crs("ESRI:102022")
    near = gpd.sjoin_nearest(opts, lga[["geometry"]].assign(zi=np.arange(1, len(lga) + 1)).to_crs("ESRI:102022"), how="left")
    zones[orow, ocol] = near[~near.index.duplicated()]["zi"].values.astype("uint16")
sums = np.bincount(zones.ravel(), weights=pop.ravel().astype(np.float64), minlength=len(lga) + 1)
lga["population"] = np.round(sums[1:]).astype(np.int64)
lga["density_per_km2"] = (lga.population / lga.area_km2).round(1)
# settled share: people living in cells >= 1,500/km² (≈15 people per 100 m cell) as a rough urban indicator
dense = np.bincount(zones.ravel(), weights=np.where(pop >= 15, pop, 0).ravel().astype(np.float64), minlength=len(lga) + 1)
lga["pct_in_dense_settlement"] = (100 * dense[1:] / np.maximum(sums[1:], 1)).round(1)
stp = pd.read_csv(f"{OUT}/05_population/population_by_state.csv", keep_default_na=False)
cmp_ = lga.groupby("state_code").population.sum().to_frame("lga_sum").join(stp.set_index("state_code").population)
maxdiff = (100 * (cmp_.lga_sum - cmp_.population).abs() / cmp_.population).max()
log.append(f"LGA population: summed from the same GRID3 v3.0 100 m grid ({outside:,.0f} coastal/border people assigned to the nearest LGA). "
           f"LGA totals add up to each state's total within {maxdiff:.2f}%. 'pct_in_dense_settlement' = share of people living at ≥1,500 people/km² "
           "(a rough urban indicator).")
del zones, pop

# ------------------------------------------------------------------ health facilities by LGA
hf = pd.read_csv(f"{OUT}/04_health_facilities/health_facilities_clean.csv", keep_default_na=False, na_values=[""], dtype={"lga_code": str})
hf["lga_id"] = hf["state_code"] + "_" + hf["lga_code"]
unmatched = hf[~hf.lga_id.isin(lga.lga_id)]
log.append(f"Facilities → LGAs: {len(hf) - len(unmatched):,} of {len(hf):,} facilities matched to an LGA polygon by LGA code"
           + (f"; {len(unmatched)} unmatched ({', '.join(sorted(unmatched.lga_id.unique())[:10])})" if len(unmatched) else " (100%)") + ".")
hf = hf.merge(lga[["lga_id", "lga"]].rename(columns={"lga": "lga_boundary_name"}), on="lga_id", how="left")
# check each point against the LGA polygon it claims
has_xy = hf.latitude.notna() & hf.longitude.notna()
hp = gpd.GeoDataFrame(hf[has_xy][["lga_id"]], geometry=gpd.points_from_xy(hf[has_xy].longitude, hf[has_xy].latitude), crs="EPSG:4326")
jl = gpd.sjoin(hp, lga[["lga_id", "geometry"]].rename(columns={"lga_id": "lga_id_at_point"}), how="left", predicate="within")
jl = jl[~jl.index.duplicated()]
hf["lga_id_at_point"] = jl["lga_id_at_point"].reindex(hf.index)
in_lga = (hf.lga_id_at_point == hf.lga_id)
hf.loc[has_xy & ~in_lga & (hf.location_flag == "OK"), "location_flag"] = "Point in a different LGA (same state)"
log.append(f"Facility points vs LGAs: {int(in_lga.sum()):,} of {int(has_xy.sum()):,} points ({in_lga.sum() / has_xy.sum():.1%}) fall inside the LGA they are "
           f"recorded in. Counts per LGA use the recorded LGA code; the map shows every point with its location_flag.")
hf.to_csv(f"{OUT}/04_health_facilities/health_facilities_clean.csv", index=False)
# slim point files for the web map (one per state)
pcols = ["facility_id", "name", "lga", "level", "facility_group", "ownership_simple", "functional_status", "location_flag"]
FD = f"{OUT}/04_health_facilities/points_by_state"; os.makedirs(FD, exist_ok=True)
pts_all = gpd.GeoDataFrame(hf[has_xy][pcols + ["state_code", "state", "service_type"]],
                           geometry=gpd.points_from_xy(hf[has_xy].longitude, hf[has_xy].latitude), crs="EPSG:4326")
pts_all.to_file(f"{OUT}/04_health_facilities/health_facilities_points.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
for code, d in pts_all[pts_all.service_type == "Patient care"].groupby("state_code"):
    d[pcols + ["geometry"]].to_file(f"{FD}/{code}_{slug(d.state.iloc[0])}_facilities.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
care = hf[hf.service_type == "Patient care"]
def cnt(col, vals, prefix):
    t = care.pivot_table(index="lga_id", columns=col, values="facility_id", aggfunc="count", fill_value=0).reindex(columns=vals, fill_value=0)
    t.columns = [f"{prefix}_{slug(v)}" for v in vals]; return t
fac = pd.concat([care.groupby("lga_id").size().rename("hf_total"),
                 cnt("level", ["Primary", "Secondary", "Tertiary"], "hf"),
                 cnt("ownership_simple", ["Public", "Private", "Not stated"], "hf_owner"),
                 cnt("functional_status", ["Functional", "Partially Functional", "Not Functional", "Not stated"], "hf_status")], axis=1)
lga = lga.merge(fac.reset_index(), on="lga_id", how="left")
hfcols = [c for c in lga.columns if c.startswith("hf_")]
lga[hfcols] = lga[hfcols].fillna(0).astype(int)
lga["hf_per_10k"] = (1e4 * lga.hf_total / lga.population.clip(lower=1)).round(2)
lga["hf_functional_per_10k"] = (1e4 * lga.hf_status_functional / lga.population.clip(lower=1)).round(2)
lga["people_per_facility"] = np.where(lga.hf_total > 0, (lga.population / lga.hf_total.clip(lower=1)).round(0), np.nan)
lga["has_secondary_or_tertiary"] = (lga.hf_secondary + lga.hf_tertiary) > 0

# ------------------------------------------------------------------ displacement by LGA (origin points)
dis = pd.read_csv(f"{OUT}/02_events/displacement_idmc_2025_2026_all_records.csv", keep_default_na=False, na_values=[""])
rec = dis[dis.use_in_totals.astype(str).str.lower() == "true"].dropna(subset=["latitude", "longitude"])
pts = gpd.GeoDataFrame(rec, geometry=gpd.points_from_xy(rec.longitude, rec.latitude), crs="EPSG:4326")
j = gpd.sjoin(pts, lga[["lga_id", "geometry"]], how="left", predicate="within")
j = j[~j.index.duplicated()]
miss = j.lga_id.isna()
if miss.any():
    near = gpd.sjoin_nearest(pts[miss].to_crs("ESRI:102022"), lga[["lga_id", "geometry"]].to_crs("ESRI:102022"), how="left")
    j.loc[miss, "lga_id"] = near[~near.index.duplicated()]["lga_id"].values
dl = j.pivot_table(index="lga_id", columns="displacement_type", values="people_displaced", aggfunc="sum", fill_value=0)
dl.columns = [f"displaced_{c.lower()}_2025_26" for c in dl.columns]
dl["displaced_total_2025_26"] = dl.sum(axis=1)
lga = lga.merge(dl.reset_index(), on="lga_id", how="left")
dcols = [c for c in lga.columns if c.startswith("displaced_")]
lga[dcols] = lga[dcols].fillna(0).astype(int)
lga["displaced_per_1k"] = (1e3 * lga.displaced_total_2025_26 / lga.population.clip(lower=1)).round(2)
log.append(f"Displacement → LGAs: {len(rec)} official-figure records placed in the LGA of their origin point; "
           f"{int((lga.displaced_total_2025_26 > 0).sum())} LGAs recorded new displacement in 2025–26.")

# ------------------------------------------------------------------ outputs
lga["people_per_facility"] = lga["people_per_facility"].astype("Int64")
lga.to_file(f"{LD}/nga_lga_boundaries.geojson", driver="GeoJSON")
web = lga.copy(); web["geometry"] = web.simplify(0.003, preserve_topology=True)
web.to_file(f"{LD}/nga_lga_web_simplified.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
for code, d in web.groupby("state_code"):
    d.to_file(f"{LD}/by_state/{code}_{slug(d.state.iloc[0])}_lgas.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
tab = lga.drop(columns="geometry")
tab.to_csv(f"{LD}/lga_profiles.csv", index=False)
log.append(f"LGA extremes: most populous {tab.loc[tab.population.idxmax(), 'lga']} ({tab.loc[tab.population.idxmax(), 'state']}, "
           f"{tab.population.max():,}); {int((tab.hf_total == 0).sum())} LGAs with no listed facility; "
           f"{int((~tab.has_secondary_or_tertiary).sum())} LGAs with no secondary or tertiary facility in the registry.")

# state profile JSONs: richer LGA list
for fjs in glob.glob(f"{OUT}/03_state_profiles/by_state/*.json"):
    js = json.load(open(fjs)); d = tab[tab.state_code == js["state_code"]]
    js.setdefault("health_facilities", {}).pop("by_lga", None)
    js["lgas"] = json.loads(d[["lga_id", "lga", "area_km2", "population", "density_per_km2", "hf_total", "hf_primary", "hf_secondary",
                               "hf_tertiary", "hf_owner_public", "hf_owner_private", "hf_per_10k", "displaced_total_2025_26"]]
                            .to_json(orient="records"))
    js["lga_file"] = os.path.basename(glob.glob(f"{LD}/by_state/{js['state_code']}_*")[0])
    json.dump(js, open(fjs, "w"), indent=1, ensure_ascii=False)

# state-level: LGAs without hospitals
prof_path = f"{OUT}/03_state_profiles/state_profiles_master.csv"
prof = pd.read_csv(prof_path, keep_default_na=False, na_values=[""])
prof = prof[[c for c in prof.columns if not c.startswith("lga_")]]
add = tab.groupby("state_code").agg(lga_count=("lga_id", "count"),
                                    lga_without_secondary_or_tertiary=("has_secondary_or_tertiary", lambda s: int((~s).sum())),
                                    lga_min_hf_per_10k=("hf_per_10k", "min"), lga_max_hf_per_10k=("hf_per_10k", "max")).reset_index()
prof = prof.merge(add, on="state_code"); prof.to_csv(prof_path, index=False)

x = pd.ExcelFile(f"{OUT}/Nigeria_Explorer_Data.xlsx")
sheets = {s: x.parse(s, keep_default_na=False, na_values=[""]) for s in x.sheet_names}
notes = [n for n in sheets["README_notes"]["cleaning notes"].tolist() if not str(n).startswith(("LGA", "Facilities →", "Displacement →"))]
sheets["README_notes"] = pd.DataFrame({"cleaning notes": notes + ["LGA LEVEL (batch 4):"] + log})
s_ = sheets["Sources"]; s_ = s_[s_.dataset != "LGA boundaries"]
sheets["Sources"] = pd.concat([s_, pd.DataFrame([["LGA boundaries", "06_lga/*", "eHealth Africa / GRID3 LGA boundaries, 2019", "774 LGAs, EPSG:4326"]], columns=s_.columns)])
sheets["State_Profiles"] = prof
sheets["LGA_Profiles"] = tab
sheets["HF_Facilities_All"] = hf
sheets.pop("HF_by_LGA", None)
order = ["README_notes", "Sources", "State_Profiles", "LGA_Profiles", "Population_by_State"] + \
        [s for s in sheets if s not in ("README_notes", "Sources", "State_Profiles", "LGA_Profiles", "Population_by_State")]
with pd.ExcelWriter(f"{OUT}/Nigeria_Explorer_Data.xlsx") as xw:
    for s in order:
        sheets[s].to_excel(xw, sheet_name=s[:31], index=False)
os.remove(f"{OUT}/04_health_facilities/health_facilities_by_lga.csv") if os.path.exists(f"{OUT}/04_health_facilities/health_facilities_by_lga.csv") else None
open(f"{OUT}/CLEANING_NOTES.txt", "w").write("\n\n".join(f"- {n}" for n in sheets["README_notes"]["cleaning notes"]))
print("\n\n".join(log))
print(tab.sort_values("hf_per_10k").head(8)[["lga", "state", "population", "hf_total", "hf_per_10k"]].to_string())
print(tab.sort_values("population", ascending=False).head(8)[["lga", "state", "population", "density_per_km2", "hf_total", "hf_per_10k"]].to_string())
