# raw_data: what to download and what to call it

The processing scripts look for the files below **in this folder, with exactly these names**.
If your download has a different name, rename it. Nothing here is needed to *view* the map; these files
are only needed to *rebuild* the `data/` folder.

| Save as | What it is | Where to get it | Used by |
|---|---|---|---|
| `NGA_State.geojson` | 37 state boundaries (eHealth Africa / GRID3, 2018–19) | GRID3 Nigeria data hub (data.grid3.org), "NGA State Boundaries", GeoJSON | step 1 |
| `NGA_LGA_Boundaries.geojson` | 774 LGA boundaries (eHealth Africa / GRID3, 2019) | data.grid3.org, "GRID3 NGA Operational LGA Boundaries", GeoJSON | step 4 |
| `hdx_hapi_poverty_rate_nga.csv` | Multidimensional Poverty Index by state, 2013–2021 (OPHI) | HDX HAPI, "Poverty rate – Nigeria" (data.humdata.org) | step 1 |
| `maternal-mortality-rate-2016.csv` | Maternal mortality by state, 2016 (NBS) | Nigeria Data Portal / NBS export | step 1 |
| `contraceptive-use-2017.csv` | Contraceptive use by method and state, 2017 (NBS) | Nigeria Data Portal / NBS Demographic Statistics Bulletin 2017 | step 1 |
| `corruption-index-prevalence-of-bribery-2016.csv` | Prevalence of bribery by state, 2016 (NBS) | Nigeria Data Portal / NBS Corruption Statistics | step 1 |
| `nga_idmc_idu_events.csv` | Internal displacement events 2025–2026 (IDMC) | HDX, "Nigeria – Internal Displacement Updates (IDU)" | step 1 |
| `crsv-incident-data-2020-2026.xlsx` | Conflict-related sexual violence incidents (Insecurity Insight) | HDX, "Nigeria – Conflict-related sexual violence" | step 1 |
| `nigerian-health-care-facilities.geojson` | 46,148 health facilities with coordinates (eHealth Africa / GRID3) | data.grid3.org, "Nigeria health care facilities (primary, secondary and tertiary)". **Download as GeoJSON**: the CSV export loses the coordinates. | step 2 |
| `NGA_population_v3_0_gridded.tif` | 100 m population grid, 2025 (GRID3 / WorldPop, v3.0) | data.worldpop.org/repo/wopr/NGA/population/v3.0/ → `NGA_population_v3_0_gridded.zip`, unzip | steps 3, 4, 5 |
| `worldpop_agesex_1km/` (folder) | 38 GeoTIFFs: `nga_f_00_2025_…_1km_R2025A_UA_v1.tif` … `nga_m_90_…` | hub.worldpop.org → Population Counts → Age and sex structures → Individual countries 2015–2030 (1 km) R2025A v1 → Nigeria → 2025 | step 5 |

## Notes

* **Age and sex files.** Put all the `nga_f_…` and `nga_m_…` files inside a folder called
  `worldpop_agesex_1km`. Age groups are 00, 01, 05, 10 … 90. If a group is missing (the current build is
  missing 35–39), step 5 estimates it from its neighbours and says so in the cleaning notes. Add the two
  missing files and run `python processing/run_all.py 5 6` to replace the estimate.
* **CSV files from the NBS portal** start with 6 lines of title text before the header row. Leave them as
  downloaded; the scripts skip those lines.
* **Large files.** This folder is listed in `.gitignore`, so the raw data is not uploaded to GitHub.
