"""Nigeria Demographic Explorer - batch 1 cleaning and state organisation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FILES, OUT, WEB, check
check('states', 'poverty', 'mmr', 'contra', 'bribery', 'idmc', 'crsv')

import json, re, os
import numpy as np
import pandas as pd
import geopandas as gpd

F = FILES
for sub in ["00_reference", "01_state_indicators", "02_events", "03_state_profiles"]:
    os.makedirs(f"{OUT}/{sub}", exist_ok=True)
log = []

# ------------------------------------------------------------------ 0. reference
PCODES = {  # OCHA admin-1 p-codes (alphabetical, FCT = NG015)
    "Abia": "NG001", "Adamawa": "NG002", "Akwa Ibom": "NG003", "Anambra": "NG004", "Bauchi": "NG005",
    "Bayelsa": "NG006", "Benue": "NG007", "Borno": "NG008", "Cross River": "NG009", "Delta": "NG010",
    "Ebonyi": "NG011", "Edo": "NG012", "Ekiti": "NG013", "Enugu": "NG014", "Federal Capital Territory": "NG015",
    "Gombe": "NG016", "Imo": "NG017", "Jigawa": "NG018", "Kaduna": "NG019", "Kano": "NG020", "Katsina": "NG021",
    "Kebbi": "NG022", "Kogi": "NG023", "Kwara": "NG024", "Lagos": "NG025", "Nasarawa": "NG026", "Niger": "NG027",
    "Ogun": "NG028", "Ondo": "NG029", "Osun": "NG030", "Oyo": "NG031", "Plateau": "NG032", "Rivers": "NG033",
    "Sokoto": "NG034", "Taraba": "NG035", "Yobe": "NG036", "Zamfara": "NG037"}
ALIASES = {"fct": "Federal Capital Territory", "abuja": "Federal Capital Territory", "fct abuja": "Federal Capital Territory",
           "federal capital territory": "Federal Capital Territory", "nassarawa": "Nasarawa", "akwa-ibom": "Akwa Ibom",
           "akwaibom": "Akwa Ibom", "cross-river": "Cross River"}

def std_state(x):
    """Any spelling of a state name -> canonical name (or None)."""
    if pd.isna(x):
        return None
    s = re.sub(r"\s+state$", "", str(x).strip(), flags=re.I).strip()
    s = re.sub(r"[,]", " ", s); s = re.sub(r"\s+", " ", s).strip()
    key = s.lower()
    if key in ALIASES:
        return ALIASES[key]
    for name in PCODES:
        if name.lower() == key:
            return name
    return None

ZONES = {"NCZ": "North Central", "NEZ": "North East", "NWZ": "North West",
         "SEZ": "South East", "SSZ": "South South", "SWZ": "South West"}
CAPITAL_FIX = {"Ibandan": "Ibadan", "Oshogbo": "Osogbo", "Ado": "Ado-Ekiti"}

g = gpd.read_file(F["states"])
g["state"] = g["statename"].map(std_state)
assert g["state"].notna().all() and g["state"].nunique() == 37
g["state_code"] = g["state"].map(PCODES)
g["abbrev"] = g["statecode"]
g["capital"] = g["capcity"].replace(CAPITAL_FIX)
g["geozone"] = g["geozone"].map(ZONES)
g["area_km2"] = g.to_crs("ESRI:102022").area / 1e6          # Africa Albers equal-area
states = g[["state_code", "state", "abbrev", "capital", "geozone", "area_km2", "geometry"]].sort_values("state_code").reset_index(drop=True)
states["area_km2"] = states["area_km2"].round(1)
states.to_file(f"{OUT}/00_reference/nga_states.geojson", driver="GeoJSON")
web = states.copy(); web["geometry"] = web.simplify(0.01, preserve_topology=True)
web.to_file(f"{OUT}/00_reference/nga_states_web_simplified.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
lookup = states.drop(columns="geometry")
lookup.to_csv(f"{OUT}/00_reference/state_lookup.csv", index=False)
log.append("States: 37 polygons; 'Fct' renamed 'Federal Capital Territory'; capitals fixed (Ibandan->Ibadan, Oshogbo->Osogbo, Ado->Ado-Ekiti); "
           "geozone codes expanded; OCHA p-codes and area (km², equal-area projection) added; simplified web copy made.")
BASE = lookup[["state_code", "state", "geozone"]]

def attach(df, col="state"):
    df = df.copy(); df["state"] = df[col].map(std_state)
    return BASE.merge(df.drop(columns=[c for c in ["state_code", "geozone"] if c in df]), on="state", how="right")

def read_nbs(path):
    """NBS csv exports have 6 metadata lines before the header."""
    return pd.read_csv(path, skiprows=6)

# ------------------------------------------------------------------ 1. state indicators
# Poverty (Multidimensional Poverty Index, OPHI via HDX HAPI)
pv = pd.read_csv(F["poverty"])
pv["state"] = pv["provider_admin1_name"].map(std_state)
pv["period"] = pv["reference_period_start"].str[-4:] + np.where(
    pv["reference_period_start"].str[-4:] != pv["reference_period_end"].str[-4:], "–" + pv["reference_period_end"].str[-2:], "")
pv["survey_year"] = pv["reference_period_end"].str[-4:].astype(int)
pov = BASE.merge(pv[["state", "period", "survey_year", "mpi", "headcount_ratio", "intensity_of_deprivation",
                     "vulnerable_to_poverty", "in_severe_poverty"]], on="state")
pov = pov.rename(columns={"headcount_ratio": "poor_pct", "intensity_of_deprivation": "intensity_pct",
                          "vulnerable_to_poverty": "vulnerable_pct", "in_severe_poverty": "severe_poverty_pct"})
pov[["poor_pct", "intensity_pct", "vulnerable_pct", "severe_poverty_pct"]] = pov[["poor_pct", "intensity_pct", "vulnerable_pct", "severe_poverty_pct"]].round(2)
pov = pov.sort_values(["state_code", "survey_year"])
pov.to_csv(f"{OUT}/01_state_indicators/poverty_mpi_2013_2021.csv", index=False)
log.append(f"Poverty: {len(pov)} rows (37 states × 4 survey rounds). FCT had blank admin codes in the source; filled as NG015.")

# Maternal mortality
mm = read_nbs(F["mmr"]).rename(columns={"total": "mmr_per_100k_live_births"})
mmr_nat = float(mm.loc[mm.state == "Nigeria", "mmr_per_100k_live_births"].iloc[0])
mmr = attach(mm[mm.state != "Nigeria"])[["state_code", "state", "geozone", "mmr_per_100k_live_births"]].assign(year=2016)
mmr.to_csv(f"{OUT}/01_state_indicators/maternal_mortality_2016.csv", index=False)

# Contraceptive use (currently married women)
ct = read_nbs(F["contra"])
wide = ct.pivot(index="state", columns="method", values="total")
GROUPS = {
    "modern_short_acting": ["Pill", "Injectables", "Male condom", "Female condom", "Diaphragm/Foam/Jelly", "LAM"],
    "modern_long_acting_reversible": ["IUD", "Implants"],
    "modern_permanent": ["Female sterilization", "Male sterilization"],
    "traditional": ["Periodic abstinence", "Withdrawal", "Other"],
}
for k, cols in GROUPS.items():
    wide[k] = wide[cols].sum(axis=1).round(1)
wide["check_modern_diff"] = (wide[GROUPS["modern_short_acting"] + GROUPS["modern_long_acting_reversible"] + GROUPS["modern_permanent"]].sum(axis=1) - wide["Any modern method"]).round(1)
wide["check_traditional_diff"] = (wide["traditional"] - wide["Traditional Method"]).round(1)
bad = wide[(wide.check_modern_diff.abs() > 0.3) | (wide.check_traditional_diff.abs() > 0.3)]
log.append(f"Contraceptive use: methods grouped into modern short-acting / long-acting reversible / permanent / traditional. "
           f"Sub-totals agree with the published 'any modern' and 'traditional' totals within rounding for "
           f"{len(wide) - len(bad)} of {len(wide)} rows" + (f"; check: {', '.join(bad.index)}" if len(bad) else "."))
wide = wide.drop(columns=["check_modern_diff", "check_traditional_diff"])
ren = {c: re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in wide.columns}
wide = wide.rename(columns=ren).rename(columns={"any_method": "any_method_pct", "any_modern_method": "modern_pct",
                                                 "traditional_method": "traditional_pct", "no_method": "no_method_pct"})
order = ["any_method_pct", "modern_pct", "traditional_pct", "no_method_pct"] + list(GROUPS) + \
        sorted(set(wide.columns) - {"any_method_pct", "modern_pct", "traditional_pct", "no_method_pct"} - set(GROUPS))
wide = wide[order].reset_index()
contra_nat = wide[wide.state == "Nigeria"].drop(columns="state")
contra = attach(wide[wide.state != "Nigeria"]).assign(year=2017)
contra.to_csv(f"{OUT}/01_state_indicators/contraceptive_use_2017.csv", index=False)

# Bribery
br = read_nbs(F["bribery"])
bribery = attach(br)[["state_code", "state", "geozone"]].assign(bribery_prevalence_pct=(br["total"].values * 100).round(1), year=2016)
bribery.to_csv(f"{OUT}/01_state_indicators/bribery_prevalence_2016.csv", index=False)
log.append("Bribery prevalence converted from a proportion (0.358) to a percentage (35.8%).")
for name, d in {"maternal mortality": mmr, "contraceptive": contra, "bribery": bribery}.items():
    assert d.state_code.notna().all() and d.state.nunique() == 37, name

# ------------------------------------------------------------------ 2. events
# 2a. IDMC internal displacement
idu = pd.read_csv(F["idmc"])
# Each record lists one or more places (origin / destination). The lat/lon columns are the centroid of all of them,
# which can fall in a third state, so we locate the ORIGIN place (where people were displaced from) instead.
def split_places(row):
    names = [n.strip() for n in str(row.locations_name).split(";")]
    types = [t.strip() for t in str(row.locations_type).split(";")]
    coords = [c.strip() for c in str(row.locations_coordinates).split(";")]
    places = []
    for i, n in enumerate(names):
        t = types[i] if i < len(types) else ""
        try: lat, lon = [float(v) for v in coords[i].split(",")]
        except Exception: lat = lon = np.nan
        parts = [p.strip() for p in n.split(",")]
        places.append({"name": n, "type": t, "lat": lat, "lon": lon, "state_named": std_state(parts[-2]) if len(parts) >= 2 else None})
    return places
origin, dest_states = [], []
for _, r in idu.iterrows():
    pl = split_places(r)
    o = next((p for p in pl if "origin" in p["type"].lower()), pl[0])
    origin.append(o)
    dest_states.append("; ".join(sorted({p["state_named"] or "?" for p in pl if "destination" in p["type"].lower()})))
idu["origin_place"] = [o["name"] for o in origin]
idu["origin_lat"] = [o["lat"] for o in origin]
idu["origin_lon"] = [o["lon"] for o in origin]
idu["state_named"] = [o["state_named"] for o in origin]
idu["destination_states"] = dest_states
pts = gpd.GeoDataFrame(idu, geometry=gpd.points_from_xy(idu.origin_lon, idu.origin_lat), crs="EPSG:4326")
j = gpd.sjoin(pts, states[["state", "geometry"]].rename(columns={"state": "state_point"}), how="left", predicate="within")
miss = j.state_point.isna() & j.origin_lat.notna()
if miss.any():   # points just outside the coast/border -> nearest state
    near = gpd.sjoin_nearest(pts[miss].to_crs("ESRI:102022"), states[["state", "geometry"]].rename(columns={"state": "state_point"}).to_crs("ESRI:102022"), how="left")
    j.loc[miss, "state_point"] = near["state_point"].values
j = j[~j.index.duplicated()]
j["state"] = j.state_named.fillna(j.state_point)          # the named state wins; coordinates fill gaps
j = j.merge(BASE, on="state", how="left")
agree = (j.state_named == j.state_point)[j.state_named.notna()]
log.append(f"Displacement (IDMC): {len(idu)} records. Each record was placed in the state of its ORIGIN location (where people fled from); "
           f"the source's lat/lon is an average of origin and destination and can land in a third state. "
           f"Origin place name and origin coordinates agree on the state for {agree.mean():.1%} of records; "
           f"{int(j.state_named.isna().sum())} records without a state name were placed by coordinates. Destination states are kept in a separate column.")
j["latitude"], j["longitude"] = j.origin_lat, j.origin_lon
j["locations_name"] = j.locations_name
HAZ = {"Non-International armed conflict (NIAC)": "Armed conflict", "Communal violence": "Communal violence",
       "Crime-related violence": "Crime-related violence (banditry, kidnapping)", "Flood": "Flood", "Storm": "Storm",
       "Wildfire": "Wildfire", "Mixed disasters": "Mixed disasters"}
dis = pd.DataFrame({
    "event_id": j.event_id, "record_id": j.id, "state_code": j.state_code, "state": j.state, "geozone": j.geozone,
    "year": j.year, "displacement_start": j.displacement_start_date, "displacement_end": j.displacement_end_date,
    "displacement_type": j.displacement_type, "hazard_group": j.subtype.map(HAZ), "hazard_subtype_raw": j.subtype,
    "people_displaced": j.figure, "figure_role": j.role, "use_in_totals": j.role.eq("Recommended figure"),
    "evacuation": j.displacement_occurred.str.contains("preventive", case=False, na=False) & ~j.displacement_occurred.str.contains("without", case=False, na=False),
    "origin_place": j.origin_place, "destination_states": j.destination_states,
    "latitude": j.latitude, "longitude": j.longitude, "all_places": j.locations_name, "event_name": j.event_name, "source": j.sources})
dis = dis.sort_values(["state_code", "displacement_start"])
dis.to_csv(f"{OUT}/02_events/displacement_idmc_2025_2026_all_records.csv", index=False)
rec = dis[dis.use_in_totals]
gpd.GeoDataFrame(rec, geometry=gpd.points_from_xy(rec.longitude, rec.latitude), crs="EPSG:4326") \
   .to_file(f"{OUT}/02_events/displacement_idmc_2025_2026_points.geojson", driver="GeoJSON")
dsum = rec.pivot_table(index=["state_code", "state"], columns=["year", "displacement_type"], values="people_displaced",
                       aggfunc="sum", fill_value=0)
dsum.columns = [f"displaced_{t.lower()}_{y}" for y, t in dsum.columns]
hz = rec.pivot_table(index=["state_code", "state"], columns="hazard_group", values="people_displaced", aggfunc="sum", fill_value=0)
hz.columns = ["displaced_" + re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in hz.columns]
ev = rec.groupby(["state_code", "state"]).agg(displacement_records=("record_id", "count"), displaced_total=("people_displaced", "sum"))
disp_state = BASE.merge(pd.concat([ev, dsum, hz], axis=1).reset_index(), on=["state_code", "state"], how="left")
num = disp_state.columns.difference(["state_code", "state", "geozone"])
disp_state[num] = disp_state[num].fillna(0).astype(int)
disp_state.to_csv(f"{OUT}/02_events/displacement_by_state_2025_2026.csv", index=False)
log.append(f"Displacement totals use only the {len(rec)} 'Recommended figure' records ({rec.people_displaced.sum():,} people). "
           f"The other {int((~dis.use_in_totals).sum())} 'Triangulation' records are supporting estimates of the same events; adding them "
           f"would double-count ({dis.people_displaced.sum():,} if summed). They are kept in the all-records file, flagged use_in_totals = False.")

# 2b. Conflict-related sexual violence (Insecurity Insight SiND)
cr = pd.read_excel(F["crsv"])
cr = cr.drop(columns=[c for c in cr.columns if cr[c].isna().all()])  # empty: description, lat/lon
PERP = {"NSA": "Non-state armed group", "Government: Military": "State forces", "Foreign Forces: Military": "State forces (foreign)",
        "Other": "Other / unidentified", "No Information": "Not reported"}
def sv_group(t):
    t = str(t).lower()
    if "rape" in t: return "Rape"
    if "attempted" in t or "assault" in t: return "Sexual assault (incl. attempted)"
    if "strip" in t: return "Forced stripping"
    if "harass" in t or "threat" in t: return "Harassment / threats"
    return "Not reported"
crsv = pd.DataFrame({
    "sind_event_id": cr["SIND Event ID"], "date": pd.to_datetime(cr["Date"]).dt.date, "year": pd.to_datetime(cr["Date"]).dt.year,
    "state": cr["Admin 1"].map(std_state)})
crsv = BASE.merge(crsv, on="state", how="right")
crsv["state"] = crsv["state"].fillna("Not reported")
crsv["perpetrator_group"] = cr["Reported Perpetrator"].map(PERP).fillna("Not reported").values
crsv["perpetrator_name"] = cr["Reported Perpetrator Name"].values
crsv["violence_type_group"] = cr["Type Of Sexual Violence"].map(sv_group).values
crsv["violence_type_raw"] = cr["Type Of Sexual Violence"].values
crsv["classification"] = cr["Classification of Sexual Violence"].values
crsv["survivor_age"] = cr["Adult Or Minor"].replace({"Adult, Minor": "Adult and minor"}).values
crsv["survivor_sex"] = cr["Survivor Or Victim Sex"].replace({"Female, Male": "Female and male"}).values
crsv["setting"] = cr["Location Where Sexual Violence Was Committed"].replace({"No Information": "Not reported", "Not Applicable": "Not reported"}).values
crsv["weapon"] = cr["Weapon Carried/Used"].replace({"No Information on the Weapon Used": "Not reported"}).values
crsv["reported_victims"] = cr["Number of Reported Victims"].values
crsv["reported_deaths"] = cr["Reported Deaths Following the Sexual Violence"].fillna(0).astype(int).values
crsv["context"] = cr["Sexual Violence Context"].values
crsv = crsv.sort_values("date", ascending=False)
crsv.to_csv(f"{OUT}/02_events/crsv_incidents_2020_2026.csv", index=False)
cs = crsv[crsv.state_code.notna()].groupby(["state_code", "state"]).agg(
    crsv_incidents=("sind_event_id", "count"), crsv_reported_victims=("reported_victims", "sum"),
    crsv_reported_deaths=("reported_deaths", "sum"),
    crsv_incidents_minors=("survivor_age", lambda s: s.str.contains("inor").sum()),
    crsv_by_non_state_groups=("perpetrator_group", lambda s: (s == "Non-state armed group").sum()),
    crsv_by_state_forces=("perpetrator_group", lambda s: s.str.startswith("State forces").sum())).reset_index()
crsv_state = BASE.merge(cs, on=["state_code", "state"], how="left")
num = crsv_state.columns.difference(["state_code", "state", "geozone"]); crsv_state[num] = crsv_state[num].fillna(0).astype(int)
crsv_state.to_csv(f"{OUT}/02_events/crsv_by_state_2020_2026.csv", index=False)
crsv_year = crsv.pivot_table(index="state", columns="year", values="sind_event_id", aggfunc="count", fill_value=0)
crsv_year.to_csv(f"{OUT}/02_events/crsv_incidents_by_state_and_year.csv")
log.append(f"CRSV: {len(crsv)} reported incidents (2020–2026) in {crsv.state_code.nunique()} states; {int(crsv.state_code.isna().sum())} with no state. "
           "Coordinates are withheld in the source for survivor safety, so this layer is state-level only. "
           "Reported counts are a floor, not true prevalence: most incidents go unreported.")

# ------------------------------------------------------------------ 3. state profiles
latest_pov = pov[pov.survey_year == pov.survey_year.max()].drop(columns=["geozone"]).add_prefix("mpi2021_").rename(
    columns={"mpi2021_state_code": "state_code", "mpi2021_state": "state"}).drop(columns=["mpi2021_period", "mpi2021_survey_year"])
prof = lookup.merge(latest_pov, on=["state_code", "state"]) \
    .merge(mmr[["state_code", "mmr_per_100k_live_births"]].rename(columns={"mmr_per_100k_live_births": "mmr2016_per_100k"}), on="state_code") \
    .merge(contra[["state_code", "any_method_pct", "modern_pct", "traditional_pct"] + list(GROUPS)].add_prefix("cpr2017_").rename(columns={"cpr2017_state_code": "state_code"}), on="state_code") \
    .merge(bribery[["state_code", "bribery_prevalence_pct"]].rename(columns={"bribery_prevalence_pct": "bribery2016_pct"}), on="state_code") \
    .merge(disp_state.drop(columns=["state", "geozone"]).add_prefix("idmc_").rename(columns={"idmc_state_code": "state_code"}), on="state_code") \
    .merge(crsv_state.drop(columns=["state", "geozone"]), on="state_code")
prof.to_csv(f"{OUT}/03_state_profiles/state_profiles_master.csv", index=False)
states.merge(prof.drop(columns=["state", "abbrev", "capital", "geozone", "area_km2"]), on="state_code") \
      .assign(geometry=lambda d: d.simplify(0.01, preserve_topology=True)) \
      .to_file(f"{OUT}/03_state_profiles/state_profiles_web.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

# one JSON per state (for the web app)
os.makedirs(f"{OUT}/03_state_profiles/by_state", exist_ok=True)
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else round(float(o), 4)
    return o
for _, s in lookup.iterrows():
    c = s.state_code
    cr_s = crsv[crsv.state_code == c]
    rec_s = rec[rec.state_code == c]
    out = {
        "state": s.state, "state_code": c, "abbrev": s.abbrev, "capital": s.capital, "geozone": s.geozone, "area_km2": s.area_km2,
        "poverty_mpi": pov[pov.state_code == c][["period", "mpi", "poor_pct", "intensity_pct", "vulnerable_pct", "severe_poverty_pct"]].to_dict("records"),
        "maternal_mortality_2016": {"per_100k_live_births": mmr.loc[mmr.state_code == c, "mmr_per_100k_live_births"].iloc[0], "nigeria": mmr_nat},
        "contraceptive_use_2017": contra[contra.state_code == c].drop(columns=["state_code", "state", "geozone", "year"]).iloc[0].to_dict(),
        "bribery_prevalence_2016_pct": bribery.loc[bribery.state_code == c, "bribery_prevalence_pct"].iloc[0],
        "displacement_2025_2026": {
            "total": rec_s.people_displaced.sum(), "records": len(rec_s),
            "by_type": rec_s.groupby("displacement_type").people_displaced.sum().to_dict(),
            "by_hazard": rec_s.groupby("hazard_group").people_displaced.sum().to_dict(),
            "by_year": rec_s.groupby("year").people_displaced.sum().to_dict()},
        "crsv_2020_2026": {
            "incidents": len(cr_s), "reported_victims": cr_s.reported_victims.sum(), "reported_deaths": cr_s.reported_deaths.sum(),
            "by_year": cr_s.groupby("year").size().to_dict(),
            "by_perpetrator": cr_s.perpetrator_group.value_counts().to_dict(),
            "by_type": cr_s.violence_type_group.value_counts().to_dict(),
            "by_survivor_age": cr_s.survivor_age.value_counts().to_dict()},
    }
    out["displacement_2025_2026"]["by_year"] = {str(k): v for k, v in out["displacement_2025_2026"]["by_year"].items()}
    out["crsv_2020_2026"]["by_year"] = {str(k): v for k, v in out["crsv_2020_2026"]["by_year"].items()}
    fn = re.sub(r"[^a-z0-9]+", "_", s.state.lower()).strip("_")
    json.dump(clean(out), open(f"{OUT}/03_state_profiles/by_state/{c}_{fn}.json", "w"), indent=1, ensure_ascii=False)

# national reference values
json.dump(clean({"maternal_mortality_2016_per_100k": mmr_nat, "contraceptive_use_2017": contra_nat.iloc[0].to_dict()}),
          open(f"{OUT}/00_reference/national_values.json", "w"), indent=1)

# ------------------------------------------------------------------ 4. data dictionary + workbook
sources = pd.DataFrame([
    ["State boundaries", "nga_states.geojson", "eHealth Africa / GRID3 (eHA_Polio), 2018–19", "37 polygons, EPSG:4326"],
    ["Multidimensional poverty", "poverty_mpi_2013_2021.csv", "OPHI MPI via HDX HAPI", "Survey rounds 2013, 2016–17, 2018, 2021; percentages of population"],
    ["Maternal mortality", "maternal_mortality_2016.csv", "National Bureau of Statistics, 2018", "Deaths per 100,000 live births, 2016"],
    ["Contraceptive use", "contraceptive_use_2017.csv", "NBS Demographic Statistics Bulletin 2017", "% of currently married women using a method"],
    ["Bribery prevalence", "bribery_prevalence_2016.csv", "NBS Corruption Statistics, 2016", "% of adults who paid a bribe when in contact with a public official"],
    ["Internal displacement", "displacement_idmc_2025_2026_*.csv/geojson", "IDMC Internal Displacement Updates (IOM DTM, NEMA and others)", "New displacements, Jan 2025 – Aug 2026; use 'Recommended figure' rows only"],
    ["Conflict-related sexual violence", "crsv_*.csv", "Insecurity Insight SiND, 2020–2026", "Reported incidents only; state level (coordinates withheld)"],
], columns=["dataset", "files", "source", "units / notes"])
with pd.ExcelWriter(f"{OUT}/Nigeria_Explorer_Data_batch1.xlsx") as xw:
    pd.DataFrame({"cleaning notes": log}).to_excel(xw, sheet_name="README_notes", index=False)
    sources.to_excel(xw, sheet_name="Sources", index=False)
    prof.to_excel(xw, sheet_name="State_Profiles", index=False)
    lookup.to_excel(xw, sheet_name="State_Lookup", index=False)
    pov.to_excel(xw, sheet_name="Poverty_MPI", index=False)
    mmr.to_excel(xw, sheet_name="Maternal_Mortality_2016", index=False)
    contra.to_excel(xw, sheet_name="Contraceptive_Use_2017", index=False)
    bribery.to_excel(xw, sheet_name="Bribery_2016", index=False)
    disp_state.to_excel(xw, sheet_name="Displacement_by_State", index=False)
    rec.to_excel(xw, sheet_name="Displacement_Events", index=False)
    crsv_state.to_excel(xw, sheet_name="CRSV_by_State", index=False)
    crsv.to_excel(xw, sheet_name="CRSV_Incidents", index=False)
open(f"{OUT}/CLEANING_NOTES.txt", "w").write("\n\n".join(f"- {l}" for l in log))
print("\n".join(log))
