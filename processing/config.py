"""Paths used by every processing script.

By default everything is relative to the project folder:
    raw_data/     the files you downloaded (see raw_data/README.md for the exact names)
    processed/    the cleaned, analysis-ready dataset (CSV, GeoJSON, Excel)
    data/         the small files the web page (index.html) reads

You can point the scripts somewhere else with environment variables:
    NGX_RAW, NGX_OUT, NGX_WEB
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(os.environ.get("NGX_RAW", ROOT / "raw_data"))
OUT = str(Path(os.environ.get("NGX_OUT", ROOT / "processed")))
WEB = str(Path(os.environ.get("NGX_WEB", ROOT / "data")))

FILES = {
    "states": RAW / "NGA_State.geojson",
    "lgas": RAW / "NGA_LGA_Boundaries.geojson",
    "poverty": RAW / "hdx_hapi_poverty_rate_nga.csv",
    "mmr": RAW / "maternal-mortality-rate-2016.csv",
    "contra": RAW / "contraceptive-use-2017.csv",
    "bribery": RAW / "corruption-index-prevalence-of-bribery-2016.csv",
    "idmc": RAW / "nga_idmc_idu_events.csv",
    "crsv": RAW / "crsv-incident-data-2020-2026.xlsx",
    "health": RAW / "nigerian-health-care-facilities.geojson",
    "population_tif": RAW / "NGA_population_v3_0_gridded.tif",
    "agesex_dir": RAW / "worldpop_agesex_1km",
}
FILES = {k: str(v) for k, v in FILES.items()}


def check(*keys):
    """Stop with a clear message if an input file is missing."""
    missing = [FILES[k] for k in keys if not os.path.exists(FILES[k])]
    if missing:
        raise SystemExit("Missing input file(s):\n  " + "\n  ".join(missing) +
                         "\nSee raw_data/README.md for what to download and how to name it.")
