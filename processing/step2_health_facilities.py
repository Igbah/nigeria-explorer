"""Nigeria Demographic Explorer - batch 2: health facilities, cleaned, categorised and organised by state/LGA."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check
check('health')

import json, re, os, glob
import numpy as np
import pandas as pd

SRC = FILES["health"]   # GeoJSON export, 46,148 points (CRS84 lon/lat)
os.makedirs(f"{OUT}/04_health_facilities/by_state", exist_ok=True)
log = []

lookup = pd.read_csv(f"{OUT}/00_reference/state_lookup.csv", keep_default_na=False)   # 'NA' = Nasarawa abbreviation
ABBR = dict(zip(lookup.abbrev, lookup.state))

# keep_default_na=False: otherwise pandas reads Nasarawa's code 'NA' as missing
gj = json.load(open(SRC))
p = pd.DataFrame([f["properties"] for f in gj["features"]]).astype({"id": str, "lga_code": str, "ward_code": str})
p = p.replace({"": np.nan})
xy = [(f.get("geometry") or {}).get("coordinates") or [np.nan, np.nan] for f in gj["features"]]
p["lon"] = [c[0] for c in xy]; p["lat"] = [c[1] for c in xy]
n0 = len(p)

hf = pd.DataFrame({
    "facility_id": p["id"], "global_id": p["global_id"],
    "name": p["name"].str.strip().str.replace(r"\s+", " ", regex=True),
    "alternate_name": p["alternate_name"].str.strip(),
    "state": p["state_code"].map(ABBR),
    "lga_code": p["lga_code"], "lga": p["lga_name"].str.strip().str.title(), "ward_code": p["ward_code"],
    "category_source": p["category"].fillna("Not stated"),
    "level_source": p["type"],
    "functional_status": p["functional_status"],
    "longitude": p["lon"].round(6), "latitude": p["lat"].round(6),
    "last_updated": pd.to_datetime(p["timestamp"], format="mixed", utc=True).dt.date,
})
hf = hf.merge(lookup[["state", "state_code", "geozone"]], on="state", how="left")
assert hf.state_code.notna().all()

# ---------------------------------------------------------------- level of care
LEVEL_VARIANTS = {"Primary Health Clinic": "Primary", "Health Post Dispensary": "Primary", "Primary Health Center": "Primary"}
hf["level_source"] = hf["level_source"].replace(LEVEL_VARIANTS)
LEVEL_BY_CATEGORY = {   # Nigerian three-tier system, where the category settles it
    "Primary Health Center": "Primary", "Dispensary": "Primary", "Comprehensive Health Center": "Primary",
    "Community Health Center": "Primary", "Maternity Home": "Primary",
    "General Hospital": "Secondary", "Cottage Hospital": "Secondary", "District Hospital": "Secondary",
    "Teaching Hospital": "Tertiary", "Federal Medical Center": "Tertiary", "Research Hospital": "Tertiary"}
hf["level"] = hf["category_source"].map(LEVEL_BY_CATEGORY).fillna(hf["level_source"])
hf.loc[hf.category_source == "Veterinary Clinic", "level"] = "Not a human health facility"
hf.loc[hf.level.eq("Unknown"), "level"] = "Not stated"
hf["level_changed"] = hf["level"].ne(hf["level_source"]) & hf["level"].isin(["Primary", "Secondary", "Tertiary"])
chg = hf[hf.level_changed].groupby(["category_source", "level_source", "level"]).size().reset_index(name="n")
log.append("Level of care: spelling variants merged (e.g. 'Primary Health Clinic' → Primary). Where the facility category fixes the level in "
           "Nigeria's three-tier system, the category wins: " +
           "; ".join(f"{r.category_source} {r.level_source}→{r.level} ({r.n})" for r in chg.itertuples()) +
           ". The original level is kept in 'level_source'. Veterinary clinics are marked as not human health facilities.")

# ---------------------------------------------------------------- facility group (finer sub-category)
GROUP = {
    "Primary Health Center": "Primary health centre", "Comprehensive Health Center": "Comprehensive health centre",
    "Community Health Center": "Primary health centre", "Dispensary": "Dispensary / health post",
    "Maternity Home": "Maternity home", "Medical Center": "Medical centre / clinic",
    "General Hospital": "General hospital", "Cottage Hospital": "Cottage / district hospital", "District Hospital": "Cottage / district hospital",
    "Specialist Hospital": "Specialist hospital", "Teaching Hospital": "Teaching hospital", "Federal Medical Center": "Federal medical centre",
    "Research Hospital": "Teaching hospital", "Military and Paramilitary Clinic": "Military / paramilitary clinic",
    "Federal Staff Clinic": "Staff clinic", "Educational Clinic": "School / university clinic", "Private Non Profit": "Faith-based / NGO facility",
    "Laboratory": "Laboratory", "Pharmacy": "Pharmacy", "Veterinary Clinic": "Veterinary clinic",
    "Others": "Other / not stated", "Not stated": "Other / not stated"}
hf["facility_group"] = hf["category_source"].map(GROUP)
hf["service_type"] = np.select([hf.category_source.isin(["Laboratory", "Pharmacy"]), hf.category_source.eq("Veterinary Clinic")],
                               ["Support service (lab / pharmacy)", "Veterinary"], "Patient care")

# ---------------------------------------------------------------- ownership (the source has NO ownership field)
nm = hf["name"].str.lower()
PRIVATE_TEACHING = r"babcock|bowen|igbinedion|bingham"
FAITH = r"\b(?:catholic|mission|baptist|methodist|anglican|ecwa|adventist|seventh.day|apostolic|church|islamic|ansar|muslim|jama.?atu|salvation army|evangel)|\b(?:st\.?|saint)\s+[a-z']+\s+(?:hospital|clinic|maternity|health)"
PRIVATE_NAME = r"nursing home|\bltd\b|limited|\bprivate\b|specialist clinic|& maternity|and maternity|medical centre ltd"
PUBLIC_STRONG = r"\bstate hospital|general hospital|\bgovt\b|government|federal|hospitals management board|\blga\b|local government"
PUBLIC_NAME = r"primary health care|primary health cent|\bphc\b|health post|model phc|comprehensive health"
PUBLIC_CAT = ["Federal Medical Center", "Federal Staff Clinic", "Military and Paramilitary Clinic", "General Hospital",
              "Cottage Hospital", "District Hospital", "Comprehensive Health Center"]
own = np.full(len(hf), "Not stated in source", dtype=object); basis = np.full(len(hf), "", dtype=object)
def setm(mask, o, b):
    m = mask & (own == "Not stated in source"); own[m] = o; basis[m] = b
setm(hf.category_source.eq("Teaching Hospital") & nm.str.contains(PRIVATE_TEACHING), "Private for-profit", "category + name")
setm(nm.str.contains(PUBLIC_STRONG, regex=True), "Public", "name")
setm(hf.category_source.eq("Private Non Profit"), "Private non-profit (faith-based / NGO)", "category")
setm(nm.str.contains(FAITH, regex=True), "Private non-profit (faith-based / NGO)", "name")
setm(hf.category_source.isin(PUBLIC_CAT + ["Teaching Hospital", "Research Hospital"]), "Public", "category")
setm(nm.str.contains(PRIVATE_NAME, regex=True), "Private for-profit", "name")
setm(nm.str.contains(PUBLIC_NAME, regex=True), "Public", "name")
hf["ownership_indicative"] = own; hf["ownership_basis"] = basis
hf["ownership_simple"] = hf["ownership_indicative"].map({"Public": "Public", "Private for-profit": "Private",
                                                         "Private non-profit (faith-based / NGO)": "Private"}).fillna("Not stated")
oc = hf.ownership_indicative.value_counts()
log.append("Ownership: the source file has NO ownership column. An indicative ownership was derived only where the category or name makes it clear "
           "(e.g. General/Cottage/District hospitals, FMCs, military clinics → Public; 'Private Non Profit' category and church/mission/Islamic names → "
           "Private non-profit; 'Nursing Home', 'Ltd' → Private for-profit; 'Primary Health Care/Centre', 'Health Post' → Public; Babcock, Bowen, "
           "Igbinedion and Bingham teaching hospitals → Private). Result: " + ", ".join(f"{k} {v:,}" for k, v in oc.items()) +
           ". 'ownership_basis' records why each facility was classed. Treat this as indicative until an official ownership field is added.")

# ---------------------------------------------------------------- quality flags
hf["functional_status"] = hf["functional_status"].replace({"Unknown": "Not stated"}).fillna("Not stated")
# ---------------------------------------------------------------- location checks
import geopandas as gpd
stp = gpd.read_file(f"{OUT}/00_reference/nga_states.geojson")[["state", "geometry"]].rename(columns={"state": "state_at_point"})
hfp = gpd.GeoDataFrame(hf[["longitude", "latitude"]], geometry=gpd.points_from_xy(hf.longitude, hf.latitude), crs="EPSG:4326")
jj = gpd.sjoin(hfp, stp, how="left", predicate="within"); jj = jj[~jj.index.duplicated()]
hf["state_at_point"] = jj["state_at_point"].values
no_xy = hf.latitude.isna() | hf.longitude.isna()
outside_ng = hf.state_at_point.isna() & ~no_xy
wrong_state = hf.state_at_point.notna() & (hf.state_at_point != hf.state)
hf["location_flag"] = np.select([no_xy, outside_ng, wrong_state], ["No coordinates", "Point outside Nigeria", "Point in a different state"], "OK")
same_spot = hf.duplicated(["name", "longitude", "latitude"], keep=False) & ~no_xy
log.append(f"COORDINATES: the GeoJSON export has a point for {int((~no_xy).sum()):,} of {len(hf):,} facilities. "
           f"{int((hf.location_flag == 'OK').sum()):,} fall inside their recorded state, {int(outside_ng.sum())} fall outside Nigeria and "
           f"{int(wrong_state.sum())} fall in a different state. Any problem points are marked in 'location_flag'.")
hf["exact_duplicate_point"] = same_spot
# possible duplicates: same name, same LGA, within 100 m of each other
pr = hfp.to_crs("ESRI:102022"); hf["_x"], hf["_y"] = pr.geometry.x.values, pr.geometry.y.values
hf["possible_duplicate"] = False
same_name = hf[hf.duplicated(["state", "lga", "name"], keep=False) & ~no_xy]
for _, grp in same_name.groupby(["state", "lga", "name"]):
    xy_ = grp[["_x", "_y"]].values
    d = np.sqrt(((xy_[:, None, :] - xy_[None, :, :]) ** 2).sum(-1)); np.fill_diagonal(d, np.inf)
    hf.loc[grp.index[(d < 100).any(axis=1)], "possible_duplicate"] = True
hf = hf.drop(columns=["_x", "_y"])
log.append(f"Duplicates: no identical records. {len(same_name):,} facilities share a name with another in the same LGA (often generic names like "
           f"'Health Post'); of these, {int(hf.possible_duplicate.sum())} sit within 100 m of their namesake and are flagged 'possible_duplicate' "
           f"({int(same_spot.sum())} share exactly the same point). Nothing was deleted.")

cols = ["facility_id", "global_id", "name", "alternate_name", "state_code", "state", "geozone", "lga_code", "lga", "ward_code",
        "level", "level_source", "level_changed", "facility_group", "category_source", "service_type",
        "ownership_simple", "ownership_indicative", "ownership_basis", "functional_status", "possible_duplicate", "exact_duplicate_point", "location_flag", "state_at_point",
        "longitude", "latitude", "last_updated"]
hf = hf[cols].sort_values(["state_code", "lga", "level", "name"]).reset_index(drop=True)
hf.to_csv(f"{OUT}/04_health_facilities/health_facilities_clean.csv", index=False)
for (code, st), d in hf.groupby(["state_code", "state"]):
    fn = re.sub(r"[^a-z0-9]+", "_", st.lower()).strip("_")
    d.to_csv(f"{OUT}/04_health_facilities/by_state/{code}_{fn}_health_facilities.csv", index=False)

# ---------------------------------------------------------------- summaries
care = hf[hf.service_type == "Patient care"]
def wide_counts(d, idx):
    lv = d.pivot_table(index=idx, columns="level", values="facility_id", aggfunc="count", fill_value=0)
    lv = lv.reindex(columns=["Primary", "Secondary", "Tertiary", "Not stated"], fill_value=0).add_prefix("level_")
    ow = d.pivot_table(index=idx, columns="ownership_simple", values="facility_id", aggfunc="count", fill_value=0) \
          .reindex(columns=["Public", "Private", "Not stated"], fill_value=0).add_prefix("owner_")
    fs = d.pivot_table(index=idx, columns="functional_status", values="facility_id", aggfunc="count", fill_value=0) \
          .reindex(columns=["Functional", "Partially Functional", "Not Functional", "Not stated"], fill_value=0).add_prefix("status_")
    tot = d.groupby(idx).facility_id.count().rename("facilities_total")
    out = pd.concat([tot, lv, ow, fs], axis=1).fillna(0).astype(int)
    out.columns = [re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in out.columns]
    return out.reset_index()
by_state = lookup[["state_code", "state", "geozone"]].merge(wide_counts(care, ["state_code"]), on="state_code", how="left")
support = hf[hf.service_type != "Patient care"].groupby(["state_code", "service_type"]).size().unstack(fill_value=0)
support.columns = ["labs_pharmacies" if "lab" in c.lower() else "veterinary" for c in support.columns]
by_state = by_state.merge(support.reset_index(), on="state_code", how="left").fillna(0)
by_state["pct_functional"] = (100 * by_state.status_functional / by_state.facilities_total).round(1)
by_state["pct_status_not_stated"] = (100 * by_state.status_not_stated / by_state.facilities_total).round(1)
by_state["tertiary_per_100_facilities"] = (100 * by_state.level_tertiary / by_state.facilities_total).round(2)
by_state.to_csv(f"{OUT}/04_health_facilities/health_facilities_by_state.csv", index=False)

by_lga = wide_counts(care, ["state_code", "state", "lga_code", "lga"])
by_lga.to_csv(f"{OUT}/04_health_facilities/health_facilities_by_lga.csv", index=False)
grp = care.pivot_table(index=["state_code", "state"], columns="facility_group", values="facility_id", aggfunc="count", fill_value=0).reset_index()
grp.to_csv(f"{OUT}/04_health_facilities/health_facilities_by_state_and_type.csv", index=False)
matrix = pd.crosstab([care.level], [care.ownership_simple], margins=True, margins_name="Total")
matrix.to_csv(f"{OUT}/04_health_facilities/national_level_by_ownership.csv")
log.append(f"Health facilities: {n0:,} records → {len(care):,} patient-care facilities, "
           f"{int((hf.service_type == 'Support service (lab / pharmacy)').sum())} labs/pharmacies and {int((hf.service_type == 'Veterinary').sum())} veterinary clinics "
           f"(kept but not counted as health facilities). All 37 states and {hf.groupby('state').lga.nunique().sum()} LGAs are represented. "
           f"Functional status is 'Unknown' for {int((hf.functional_status == 'Not stated').sum()):,} facilities ({(hf.functional_status == 'Not stated').mean():.0%}).")

# ---------------------------------------------------------------- merge into state profiles
prof_path = f"{OUT}/03_state_profiles/state_profiles_master.csv"
prof = pd.read_csv(prof_path, keep_default_na=False, na_values=[""])
prof = prof[[c for c in prof.columns if not c.startswith("hf_")]]
add = by_state.drop(columns=["state", "geozone"]).add_prefix("hf_").rename(columns={"hf_state_code": "state_code"})
prof = prof.merge(add, on="state_code", how="left")
prof.to_csv(prof_path, index=False)

import geopandas as gpd
gw = gpd.read_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson")
gw = gw[[c for c in gw.columns if not c.startswith("hf_")]].merge(add, on="state_code", how="left")
gw.to_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return None if np.isnan(o) else round(float(o), 4)
    return o
for f in glob.glob(f"{OUT}/03_state_profiles/by_state/*.json"):
    js = json.load(open(f)); c = js["state_code"]; d = care[care.state_code == c]
    js["health_facilities"] = {
        "total_patient_care": len(d),
        "by_level": d.level.value_counts().to_dict(),
        "by_ownership": d.ownership_simple.value_counts().to_dict(),
        "by_ownership_detail": d.ownership_indicative.value_counts().to_dict(),
        "by_type": d.facility_group.value_counts().to_dict(),
        "by_functional_status": d.functional_status.value_counts().to_dict(),
        "level_by_ownership": {lv: g.ownership_simple.value_counts().to_dict() for lv, g in d.groupby("level")},
        "labs_pharmacies": int(((hf.state_code == c) & (hf.service_type == "Support service (lab / pharmacy)")).sum()),
        "by_lga": by_lga[by_lga.state_code == c][["lga", "facilities_total", "level_primary", "level_secondary", "level_tertiary",
                                                   "owner_public", "owner_private", "owner_not_stated"]].to_dict("records"),
        "note": "Ownership is indicative (derived from category/name); the source has no ownership field.",
    }
    json.dump(clean(js), open(f, "w"), indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- consolidated workbook (batch 1 + 2)
old = pd.ExcelFile(f"{OUT}/Nigeria_Explorer_Data_batch1.xlsx")
sheets = {s: old.parse(s, keep_default_na=False, na_values=[""]) for s in old.sheet_names}
notes_prev = open(f"{OUT}/CLEANING_NOTES.txt").read().split("\n\n")
notes_prev = [n for n in notes_prev if not n.startswith("- Health") and "HEALTH FACILITIES" not in n]
allnotes = [n.lstrip("- ") for n in notes_prev] + ["HEALTH FACILITIES (batch 2):"] + log
sheets["README_notes"] = pd.DataFrame({"cleaning notes": allnotes})
src = sheets["Sources"]
src = src[src.dataset != "Health facilities"]
sheets["Sources"] = pd.concat([src, pd.DataFrame([["Health facilities", "04_health_facilities/*",
    "eHealth Africa / GRID3 health facility registry (sv_health_facilities), updated 2018–2020",
    "Points (latitude missing in this export); level, category, functional status; ownership indicative"]], columns=src.columns)])
sheets["State_Profiles"] = prof
new = {"HF_by_State": by_state, "HF_by_State_and_Type": grp, "HF_by_LGA": by_lga,
       "HF_Level_x_Ownership": matrix.reset_index(), "HF_Facilities_All": hf}
order = ["README_notes", "Sources", "State_Profiles", "State_Lookup"] + list(new) + \
        [s for s in sheets if s not in ("README_notes", "Sources", "State_Profiles", "State_Lookup")]
with pd.ExcelWriter(f"{OUT}/Nigeria_Explorer_Data.xlsx") as xw:
    for s in order:
        (new.get(s) if s in new else sheets[s]).to_excel(xw, sheet_name=s, index=False)
os.remove(f"{OUT}/Nigeria_Explorer_Data_batch1.xlsx")
open(f"{OUT}/CLEANING_NOTES.txt", "w").write("\n\n".join(f"- {n}" for n in allnotes))
print("\n\n".join(log)); print(matrix)
print(by_state[["state", "facilities_total", "level_primary", "level_secondary", "level_tertiary", "owner_public", "owner_private", "owner_not_stated", "pct_functional"]].to_string())
