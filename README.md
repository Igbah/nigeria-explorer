# Nigeria Demographic Explorer

An interactive web map of Nigeria's 37 states and 774 Local Government Areas (LGAs). It shows where people live (2025 model, 100 m detail), their age and sex structure, health facilities, poverty, maternal health and displacement. You can measure any area with a circle and compare two states or two areas side by side. It works on phones and computers and needs no server software beyond a static web host.

> **All figures are modelled or survey-based estimates.** Nigeria's last census was in 2006. Population counts come from satellite-based models (GRID3 / WorldPop), not a head count. See [Limitations](#11-limitations-read-before-quoting-figures).

---

## Contents

1. [What you can do with it](#1-what-you-can-do-with-it)
2. [Quick start: open it on your computer](#2-quick-start-open-it-on-your-computer)
3. [Share it online (GitHub Pages or Netlify)](#3-share-it-online)
4. [How to use the map (computer and phone)](#4-how-to-use-the-map)
5. [Project structure](#5-project-structure)
6. [Data sources](#6-data-sources)
7. [How the data was processed](#7-how-the-data-was-processed)
8. [Rebuilding the data yourself](#8-rebuilding-the-data-yourself)
9. [Data dictionary](#9-data-dictionary)
10. [Customising the map](#10-customising-the-map)
11. [Limitations](#11-limitations-read-before-quoting-figures)
12. [Troubleshooting](#12-troubleshooting)
13. [Credits and citation](#13-credits-and-citation)

---

## 1. What you can do with it

| Feature | What it shows |
|---|---|
| **National map** | All 37 states coloured by one of 10 indicators: population density, population, children under 15, dependency ratio, multidimensional poverty, health facilities per 10,000 people, people per secondary/tertiary facility, maternal mortality, modern contraception, displacement per 1,000 residents. A ranked table of all states and the national age–sex pyramid. |
| **State view** | Tap a state to see its population as ~5.2 km² hexagons, its LGA borders and (optionally) every health facility as a dot coloured by level of care. The side panel shows the state profile: key figures, age–sex pyramid, facilities by level and ownership, a sortable table of LGAs and displacement. |
| **Circle** | Drop a circle anywhere (2–40 km radius) and get the population inside it: male/female split, age pyramid, under-5s, women aged 15–49, facilities by level and ownership, and the nearest secondary or tertiary facility. |
| **Compare: two states** | Pick any two states and read about 35 indicators side by side, grouped into People, Age and sex, Health facilities, Poverty and health outcomes, and Displacement and insecurity, plus both age pyramids on the same scale. **The state names stay frozen at the top while you scroll the rows.** |
| **Compare: two areas** | Drop circles A and B and compare population, age pyramids and health facilities. The A/B header also stays frozen. |
| **Back** | A Back button (top of the panel and bottom toolbar) always takes you one step back: from Compare or Circle to where you were, and from a state to the whole of Nigeria. On phones and in browsers, the device's own back button does the same when the site is hosted. |
| **Starts on Nigeria** | Every visit opens zoomed to the whole country. |

---

## 2. Quick start: open it on your computer

The page loads its data files with `fetch()`, so it must be **served**, not double-clicked. (Opening `index.html` straight from the file system shows "The map data could not be loaded".) Internet is needed the first time for the map library and fonts.

### Option A: Python (any computer with Python)

```bash
cd path/to/Nigeria_Demographic_Explorer
python -m http.server 8000
```

Then open **http://localhost:8000** in your browser. Stop the server with `Ctrl + C`.

### Option B: VS Code

1. **File → Open Folder…** and choose this folder.
2. Install the **Live Server** extension (by Ritwick Dey).
3. Right-click `index.html` → **Open with Live Server**.

Or use the VS Code terminal with Option A, then `Ctrl + Shift + P` → **Simple Browser: Show** → `http://localhost:8000` to view it inside VS Code.

### Option C: Jupyter

Open `notebooks/open_explorer.ipynb` and run the first cell. It starts a server and shows the map inside the notebook, with a link to open it full screen.

---

## 3. Share it online

Any static host works. The site is about 22 MB (index.html plus 150 small data files).

### GitHub Pages (free, permanent link)

**With Git (recommended: no file-count limit)**

```bash
cd path/to/Nigeria_Demographic_Explorer
git init
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git add .
git commit -m "Nigeria Demographic Explorer"
git branch -M main
git remote add origin https://github.com/<your-username>/nigeria-explorer.git
git push -u origin main
```

Then on GitHub go to your repository → **Settings → Pages** → Branch **main**, folder **/(root)** → **Save**. After 1–2 minutes the site is live at `https://<your-username>.github.io/nigeria-explorer/`.

**With the website (no Git)**

* On a new empty repository, click the link **"uploading an existing file"**. On a repository that already has files, use **Add file → Upload files** (next to the green **Code** button).
* GitHub's uploader takes **at most 100 files at a time**. Upload in two rounds, dragging whole folders so the paths stay the same: (1) `index.html` + `data/hex`, then (2) `data/fac`, `data/lga`, `data/state`, `data/states.geojson`, `data/nigeria.json`.
* Then switch on Pages as above.

To update the site later, commit and push again (or upload the changed files). The link stays the same.

### Netlify Drop (fastest)

Go to **app.netlify.com/drop** and drag the whole folder onto the page. You get a link immediately. Create a free account to keep the site and choose a nicer address.

---

## 4. How to use the map

| Action | Computer | Phone |
|---|---|---|
| Open a state | Click it on the map, or click its row in the table | Tap it, or tap its row |
| See an LGA's or facility's figures | Hover over it | Tap it (an info card appears for a few seconds) |
| Show health facilities | Toggle **Health facilities** above the map | Same (scroll the chip row sideways if needed) |
| Drop a circle | **Circle** → click the map; drag the pin or click again to move | **Circle** → tap the map; tap again to move it |
| Compare two states | **Compare** → **Two states** → choose A and B (or click states on the map) | Same; tap a state on the map to swap it in |
| Compare two areas | **Compare** → **Two areas** → click A, then B | Tap A, then B; after that, a tap moves the nearer circle |
| Change circle size | Radius slider in the panel | Same |
| Go back | **Back** (panel or toolbar), or `Esc` | **Back** in the toolbar, or the phone's back button (hosted site) |
| More / less detail | The panel scrolls | Swipe the panel **up** for details, **down** to see the map, or tap the grey handle |

The **About** button explains the sources and methods inside the app.

---

## 5. Project structure

```
Nigeria_Demographic_Explorer/
├── index.html                 ← the whole web app (HTML, CSS and JavaScript in one file)
├── data/                      ← small files the app loads on demand (~22 MB, 150 files)
│   ├── states.geojson         ← 37 state outlines + headline indicators (national map)
│   ├── nigeria.json           ← national age–sex pyramid and totals
│   ├── state/NG001.json …     ← full profile of each state (incl. its LGA table)
│   ├── hex/NG001.json …       ← H3 hexagons: population + male/female by 17 age groups
│   ├── lga/NG001.geojson …    ← LGA outlines of each state with key figures
│   └── fac/NG001.json …       ← health facility points of each state (compact rows)
├── processing/                ← Python pipeline that builds data/ from raw_data/
│   ├── config.py              ← file names and folders (edit here if yours differ)
│   ├── run_all.py             ← runs steps 1–6 in order
│   ├── step1_state_indicators.py
│   ├── step2_health_facilities.py
│   ├── step3_population.py
│   ├── step4_lgas.py
│   ├── step5_age_sex.py
│   ├── step6_build_web_data.py
│   ├── app_template.html      ← index.html before the map-library stylesheet is pasted in
│   ├── build_page.py          ← rebuilds index.html from app_template.html
│   └── vendor/maplibre-gl.css
├── raw_data/README.md         ← exactly which files to download and what to name them
├── processed/                 ← created by the pipeline: clean CSV/GeoJSON/Excel dataset
├── notebooks/open_explorer.ipynb  ← opens the map inside Jupyter
├── requirements.txt           ← Python packages for the pipeline
└── README.md
```

State codes follow the OCHA admin-1 p-codes: `NG001` Abia … `NG015` Federal Capital Territory … `NG020` Kano … `NG025` Lagos … `NG037` Zamfara (alphabetical).

---

## 6. Data sources

| Theme | Dataset | Year / version | Detail | Notes |
|---|---|---|---|---|
| Population | GRID3 / WorldPop, *NGA population v3.0* | 2025 estimate | 100 m grid | 237,527,782 people in 7.18 million populated cells |
| Age and sex | WorldPop Global2 *R2025A v1*, individual countries, age structures | 2025 | 1 km | Used only as proportions (see §7) |
| State boundaries | eHealth Africa / GRID3 | 2018–19 | 37 polygons | |
| LGA boundaries | eHealth Africa / GRID3 operational boundaries | 2019 | 774 polygons | LGA codes match the facility registry exactly |
| Health facilities | eHealth Africa / GRID3 health facility registry | updated 2018–2020 | 46,148 points | Level (primary/secondary/tertiary), category, functional status. **No ownership field.** |
| Poverty | Multidimensional Poverty Index (OPHI) via HDX HAPI | 2013, 2016–17, 2018, 2021 | state | % poor, intensity, vulnerability, severe poverty |
| Maternal mortality | National Bureau of Statistics | 2016 | state | deaths per 100,000 live births |
| Contraception | NBS Demographic Statistics Bulletin | 2017 | state | % of currently married women, by method |
| Bribery | NBS Corruption Statistics | 2016 | state | % of adults who paid a bribe to a public official |
| Displacement | IDMC Internal Displacement Updates (mostly IOM DTM) | Jan 2025 – Aug 2026 | event points | new displacements; conflict and disaster |
| Conflict-related sexual violence | Insecurity Insight (SiND) | 2020–2026 | state | 70 reported incidents; locations withheld by the source |

Each dataset keeps its original licence. Credit the providers when you publish figures or maps (see §13).

---

## 7. How the data was processed

All steps are in `processing/` and are fully reproducible (`python processing/run_all.py`). The cleaning log for every run is written to `processed/CLEANING_NOTES.txt` and to the `README_notes` sheet of `processed/Nigeria_Explorer_Data.xlsx`.

### Step 1: state boundaries and state indicators (`step1_state_indicators.py`)

* **Standard state names and codes.** Every dataset spells states differently ("Fct", "FCT", "Federal Capital Territory", "Nassarawa", "Akwa-Ibom"…). One lookup maps them all to the official name and OCHA p-code (NG001–NG037), so every file joins on the same key.
* **Boundary fixes.** "Fct" renamed; capitals corrected (Ibandan → Ibadan, Oshogbo → Osogbo, Ado → Ado-Ekiti); geopolitical zones expanded (NCZ → North Central…). Area computed in km² with an equal-area projection (Africa Albers, ESRI:102022).
* **Poverty (MPI).** All four survey rounds kept for trends. The FCT had blank codes in the source and was filled as NG015.
* **Contraception.** 17 methods grouped into *modern short-acting* (pill, injectables, condoms, diaphragm/foam/jelly, LAM), *modern long-acting reversible* (IUD, implants), *permanent* (sterilisation) and *traditional* (periodic abstinence, withdrawal, other). The groups add up to the published totals for all 38 rows.
* **Bribery** converted from a proportion (0.358) to a percentage (35.8%).
* **Displacement (IDMC).** Only the 342 **"Recommended figure"** records (273,979 people) are counted. The other 2,189 "Triangulation" records are supporting estimates of the same events, and adding them would double-count (661,041). Each record is placed at its **origin** (where people fled from): the source's own lat/lon is an average of origin and destination and can fall in a third state. Origin name and origin point agree on the state for 99.2% of records. Events are grouped as armed conflict, communal violence, crime-related violence (banditry, kidnapping), flood, storm, wildfire and mixed disasters.
* **Conflict-related sexual violence.** Grouped by perpetrator (non-state armed group / state forces / other), type, survivor age and setting. The source withholds coordinates to protect survivors, so this is state-level only.

### Step 2: health facilities (`step2_health_facilities.py`)

* **Source.** The GeoJSON export (the CSV exports lose the latitude). 46,148 records, all with coordinates; all fall inside their recorded state.
* **Service type.** 45,879 patient-care facilities; 255 laboratories/pharmacies and 14 veterinary clinics are kept but not counted as health facilities.
* **Level of care.** Spelling variants merged. Where the category fixes the level in Nigeria's three-tier system, the category wins: Federal Medical Centres secondary → **tertiary** (46), maternity homes listed as secondary/tertiary → **primary** (89), and a few others. The source level is kept in `level_source`.
* **Facility type** grouped into 15 readable patient-care groups (primary health centre, dispensary / health post, maternity home, general hospital, teaching hospital, faith-based / NGO facility…).
* **Ownership (indicative).** The registry has **no ownership column**. Ownership was inferred only where the category or name makes it clear: general, cottage and district hospitals, FMCs, military and staff clinics, and names such as "State Hospital", "Government", "LGA" or "Primary Health Care" → Public. The "Private Non Profit" category and church/mission/Islamic names → Private non-profit. "Nursing Home", "Ltd" and "Clinic and Maternity" → Private for-profit. Babcock, Bowen, Igbinedion and Bingham teaching hospitals → Private. About 54% remain **"Not stated"**. The reason for each decision is stored in `ownership_basis`.
* **Duplicates.** None identical. 801 facilities share a name with another in the same LGA (usually generic names); only 8 sit within 100 m of their namesake and are flagged `possible_duplicate`. Nothing was deleted.
* **Location check.** 99.8% of points fall inside their recorded LGA; the other 79 are flagged in `location_flag`.

### Step 3: population (`step3_population.py`)

* The 100 m GRID3 raster is summed inside each state polygon. 46,678 people in coastline/border cells just outside any polygon are assigned to the nearest state.
* People are aggregated to **H3 hexagons at resolution 7** (about 5.2 km² each; 150,139 populated). A hexagon crossing a state border is split so each state file only counts its own people.
* Derived: density, facilities per 10,000 people, people per facility, people per secondary/tertiary facility, displaced per 1,000 residents. A 1 km summary GeoTIFF is also written for GIS use.

### Step 4: LGAs (`step4_lgas.py`)

* 774 LGA polygons, all inside the state they are labelled with. LGA totals add up to the state totals (difference 0.00%).
* For each LGA: population, density, share of people in dense settlement (≥1,500 people/km², a rough urban indicator), facilities by level, ownership and status, facilities per 10,000 people, whether it has any secondary/tertiary facility (132 LGAs have none in the registry), and displacement.

### Step 5: age and sex (`step5_age_sex.py`)

* WorldPop's 1 km age/sex counts give each 1 km cell's **share** of males and females in each age group. Those shares are applied to the GRID3 100 m population, so **all totals stay exactly the same** as step 3.
* Age groups: 0–4 (WorldPop's 0 and 1–4 merged), 5–9 … 75–79, 80+ (80–84, 85–89 and 90+ merged): 17 groups × 2 sexes, for every state, LGA and hexagon.
* Summary indicators: % aged 0–14, 15–64 and 65+, dependency ratio, males per 100 females, children under 5, women aged 15–49, youth 15–24.
* **Current gap:** the 35–39 files were not in the download, so 35–39 is estimated for each 1 km cell as the geometric mean of 30–34 and 40–44. Add `nga_f_35_…` and `nga_m_35_…` to `raw_data/worldpop_agesex_1km/` and run `python processing/run_all.py 5 6` to replace it.

### Step 6: web data (`step6_build_web_data.py`)

Packs everything into the compact files in `data/` (see §9), rounding numbers and simplifying outlines so the app stays light on mobile data. Each state is loaded only when someone opens it.

---

## 8. Rebuilding the data yourself

1. **Install Python 3.10+** and the packages:
   ```bash
   pip install -r requirements.txt
   ```
   On Windows, if `geopandas` or `rasterio` fail to install with pip, use conda:
   ```bash
   conda install -c conda-forge geopandas rasterio h3-py openpyxl
   ```
2. **Download the raw files** into `raw_data/` with the names listed in [`raw_data/README.md`](raw_data/README.md).
3. **Run the pipeline** from the project folder:
   ```bash
   python processing/run_all.py          # all steps, about 3 minutes
   python processing/run_all.py 5 6      # only age/sex + web data (e.g. after adding the 35–39 files)
   ```
4. **Refresh the page.** The app reads the new `data/` folder. Commit and push (or re-upload) to update the online site.

Outputs:

* `processed/`: the analysis-ready dataset (CSV, GeoJSON, a 1 km GeoTIFF and `Nigeria_Explorer_Data.xlsx` with every table and the cleaning notes).
* `data/`: the web files.

To keep the files elsewhere, set the environment variables `NGX_RAW`, `NGX_OUT` and `NGX_WEB`, or edit `processing/config.py`.

---

## 9. Data dictionary

### Web files (`data/`)

| File | Content |
|---|---|
| `states.geojson` | Per state: `code`, `name`, `capital`, `zone`, `area` (km²), `pop`, `density`, `poor` (% MPI-poor 2021), `hf10k`, `u15` (% under 15), `dep` (dependency ratio), `mmr`, `disp1k`, `cpr` (% modern contraception), `hf`, `pphosp` (people per secondary/tertiary facility), `sexr`, `bbox` |
| `nigeria.json` | National totals and pyramid: `pop`, `male[17]`, `female[17]`, `ages[17]` |
| `state/NGxxx.json` | Full profile: `population`, `age_sex` (pyramid + indicators), `health_facilities` (by level, ownership, type, status), `poverty_mpi` (4 rounds), `maternal_mortality_2016`, `contraceptive_use_2017`, `bribery_prevalence_2016_pct`, `displacement_2025_2026`, `crsv_2020_2026`, `lgas` (table with pyramids) |
| `hex/NGxxx.json` | `cells`: `[h3_id, population, male_by_age[17], female_by_age[17]]` |
| `lga/NGxxx.geojson` | LGA outlines with `id`, `name`, `pop`, `density`, `hf`, `hf10k`, `hf2`, `hf3`, `u15`, `disp`, `area` |
| `fac/NGxxx.json` | `rows`: `[lon, lat, name, level, owner, status, group, lga]`, with lookup lists `levels`, `owners`, `status`, `groups` |

### Main processed tables (`processed/`)

| File | One row per |
|---|---|
| `03_state_profiles/state_profiles_master.csv` | state (81 columns: every indicator) |
| `06_lga/lga_profiles.csv` | LGA |
| `04_health_facilities/health_facilities_clean.csv` | facility (with level, group, ownership + basis, status, location checks) |
| `05_population/population_by_state.csv`, `agesex_by_state.csv`, `agesex_by_lga.csv` | state / LGA |
| `02_events/displacement_idmc_2025_2026_all_records.csv` | IDMC record (`use_in_totals` marks the official figures) |
| `02_events/crsv_incidents_2020_2026.csv` | reported incident |
| `01_state_indicators/*.csv` | state (× survey year for poverty) |

---

## 10. Customising the map

Everything is in `index.html` (or `processing/app_template.html`, followed by `python processing/build_page.py`).

* **Indicators on the national map:** edit the `METRICS` list (`key` must be a property in `states.geojson`; add new ones in `step6_build_web_data.py`).
* **Colours:** the CSS variables at the top (`--accent`, `--male`, `--female`, `--lv1/2/3` for primary/secondary/tertiary) and the `MAGMA` list for the population ramp.
* **Default comparison states:** `cmpStates: ["NG025", "NG020"]` (Lagos, Kano).
* **Default circle radius:** `radius: 10` (km).
* **Phone panel heights:** `SHEET = { peek: 232, half: 0.52, full: 0.86 }`.
* **Hexagon size:** `H3_RES = 7` in `step3_population.py` and `step5_age_sex.py` (6 is coarser and lighter; 8 is finer but about 7× more data).

---

## 11. Limitations: read before quoting figures

* **Modelled population.** GRID3 v3.0 is a satellite- and survey-based model for 2025, not a census. Some totals differ from commonly quoted figures (for example Ogun, 12.9 million, slightly exceeds Lagos, 12.6 million, because the model counts the Lagos suburbs that spill into Ogun).
* **Age and sex** are WorldPop proportions applied to GRID3 totals. 35–39 is currently estimated (§7).
* **Facility registry** is from 2018–2020 and may be incomplete in some states. Low "facilities per 10,000" can reflect gaps in the registry as well as real shortages. Ownership is indicative and about half is "not stated". A quarter of facilities have no recorded functional status.
* **Old survey indicators.** Maternal mortality and bribery (2016) and contraception (2017) are the latest in these files. The 2023–24 Nigeria DHS has newer state figures for several of them.
* **Displacement** counts only official IDMC figures from January 2025 to August 2026.
* **Sexual violence** counts are reported incidents only, a minimum, far below true prevalence.
* **Circle tool:** a hexagon counts if its centre is inside the circle (edges accurate to about 1 km). The nearest-facility distance is a straight line, not travel distance or time.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| "The map data could not be loaded" | You opened the file directly. Serve the folder (§2) or use the hosted link. |
| Blank dark screen, no map | The map library could not download. Check the internet connection, then reload. |
| `git push` → `error: src refspec main does not match any` | Your branch is called `master` or nothing is committed yet. Run `git add .`, `git commit -m "first"`, `git branch -M main`, then `git push -u origin main`. |
| `git push` → `rejected … fetch first` | The GitHub repository already has a README. Run `git pull origin main --allow-unrelated-histories --no-edit`, then push again. |
| GitHub upload stops or files are missing | The web uploader takes at most 100 files at a time. Upload in rounds, or use Git. |
| GitHub Pages shows 404 | Wait 2 minutes. Check Settings → Pages is set to `main` and `/(root)`, and that `index.html` is at the top level of the repository, not inside another folder. |
| Page looks old after an update | Hard refresh (`Ctrl + Shift + R`) or clear the browser cache. On phones, close and reopen the tab. |
| `ModuleNotFoundError` when running the pipeline | `pip install -r requirements.txt` (or the conda command in §8). |
| `Missing input file(s)` | A raw file is missing or named differently. See `raw_data/README.md`. |
| Port 8000 already in use | Use another port: `python -m http.server 8080`, then open `http://localhost:8080`. |

---

## 13. Credits and citation

Built by **IMAJI (Igbah Friday)**, GIS and Remote Sensing.

Data: GRID3 and WorldPop (University of Southampton); eHealth Africa; Oxford Poverty and Human Development Initiative via OCHA HDX; National Bureau of Statistics, Nigeria; Internal Displacement Monitoring Centre (IDMC) and IOM DTM; Insecurity Insight.

Software: [MapLibre GL JS](https://maplibre.org) (BSD-3-Clause), [H3](https://h3geo.org) (Apache-2.0), pandas, GeoPandas, rasterio.

Suggested citation:

> Igbah, F. (2026). *Nigeria Demographic Explorer: an interactive map of population, age–sex structure, health facilities and vulnerability by state and LGA.* Data: GRID3 NGA population v3.0; WorldPop Global2 R2025A; eHealth Africa/GRID3 health facilities and boundaries; OPHI MPI; NBS; IDMC; Insecurity Insight.
