"""
oews_michigan_rn.py
--------------------
Downloads BLS OEWS annual files (2011-2024), filters to Michigan RNs,
and builds a clean panel CSV ready for analysis.

Usage:
    pip install requests pandas openpyxl
    python oews_michigan_rn.py

Two fixes vs prior version:
  1. Correct URL path: /special-requests/ (hyphen) not /special.requests/ (dot)
  2. Browser-like headers so BLS server doesn't return 403
"""

import os
import time
import zipfile
import requests
import pandas as pd
from io import BytesIO

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

OCC_CODE = "29-1141"  # Registered Nurses

MICHIGAN_AREAS = [
    "Ann Arbor", "Battle Creek", "Bay City", "Detroit",
    "Flint", "Grand Rapids", "Jackson, MI", "Kalamazoo",
    "Lansing", "Midland, MI", "Monroe, MI", "Muskegon",
    "Niles", "Saginaw", "Northern Michigan", "Upper Peninsula",
    "Michigan nonmetropolitan",
]

# Correct URLs from https://www.bls.gov/oes/tables.htm
# Path is /special-requests/ with a hyphen — NOT /special.requests/
YEAR_URLS = {
    2024: "https://www.bls.gov/oes/special-requests/oesm24all.zip",
    2023: "https://www.bls.gov/oes/special-requests/oesm23all.zip",
    2022: "https://www.bls.gov/oes/special-requests/oesm22all.zip",
    2021: "https://www.bls.gov/oes/special-requests/oesm21all.zip",
    2020: "https://www.bls.gov/oes/special-requests/oesm20all.zip",
    2019: "https://www.bls.gov/oes/special-requests/oesm19all.zip",
    2018: "https://www.bls.gov/oes/special-requests/oesm18all.zip",
    2017: "https://www.bls.gov/oes/special-requests/oesm17all.zip",
    2016: "https://www.bls.gov/oes/special-requests/oesm16all.zip",
    2015: "https://www.bls.gov/oes/special-requests/oesm15all.zip",
    2014: "https://www.bls.gov/oes/special-requests/oesm14all.zip",
    2013: "https://www.bls.gov/oes/special-requests/oesm13all.zip",
    2012: "https://www.bls.gov/oes/special-requests/oesm12all.zip",
    2011: "https://www.bls.gov/oes/special-requests/oesm11all.zip",
}

# BLS now requires a User-Agent with a contact email — generic browser
# UAs return 403. See https://www.bls.gov/bls/pss.htm
HEADERS = {
    "User-Agent": "GSE580-Research juanmvilla09@gmail.com",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bls.gov/oes/tables.htm",
}

SUPPRESS_VALUES = {"**", "*", "#", "~"}

KEEP_COLS = [
    "area", "area_title", "occ_code", "occ_title",
    "tot_emp", "emp_prse", "h_mean", "a_mean",
    "h_median", "a_median", "loc_quotient", "pct_total",
]

OUTPUT_FILE = "oews_michigan_rn_panel.csv"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def is_michigan(area_title):
    if not isinstance(area_title, str):
        return False
    t = area_title.lower()
    return any(m.lower() in t for m in MICHIGAN_AREAS)


def clean_cols(df):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def to_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df[c] = df[c].replace(list(SUPPRESS_VALUES), float("nan"))
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def find_xlsx_in_zip(z):
    """Find the all-data Excel file inside a zip."""
    names = z.namelist()
    # Prefer files with 'all_data' in name
    for candidate in names:
        if "all_data" in candidate.lower() and candidate.endswith(".xlsx"):
            return candidate
    # Fall back to any xlsx
    for candidate in names:
        if candidate.endswith(".xlsx") or candidate.endswith(".xls"):
            return candidate
    return None


def load_year(year, url):
    print(f"\n[{year}] Downloading {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=300)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR: {e}")
        return pd.DataFrame()

    mb = len(r.content) / 1e6
    print(f"  Downloaded {mb:.1f} MB")

    try:
        z = zipfile.ZipFile(BytesIO(r.content))
    except zipfile.BadZipFile:
        print("  ERROR: File is not a valid zip")
        return pd.DataFrame()

    xlsx_name = find_xlsx_in_zip(z)
    if not xlsx_name:
        print(f"  ERROR: No xlsx found inside zip. Contents: {z.namelist()[:8]}")
        return pd.DataFrame()

    print(f"  Reading sheet from: {xlsx_name}")
    try:
        df = pd.read_excel(BytesIO(z.read(xlsx_name)), dtype=str)
    except Exception as e:
        print(f"  ERROR reading Excel file: {e}")
        return pd.DataFrame()

    print(f"  Raw shape: {df.shape}")
    df = clean_cols(df)

    if "occ_code" not in df.columns:
        print(f"  WARNING: occ_code column missing. Available: {list(df.columns[:10])}")
        return pd.DataFrame()

    # Filter: RNs only
    df = df[df["occ_code"].str.strip() == OCC_CODE]

    # Filter: Michigan geographies only
    if "area_title" not in df.columns:
        print("  WARNING: area_title column missing")
        return pd.DataFrame()

    df = df[df["area_title"].apply(is_michigan)].copy()
    print(f"  Michigan RN rows found: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# PANEL BUILDER
# ---------------------------------------------------------------------------

def build_panel(years=None):
    if years is None:
        years = sorted(YEAR_URLS.keys())

    frames = []
    for year in years:
        df = load_year(year, YEAR_URLS[year])
        if df.empty:
            continue

        available = [c for c in KEEP_COLS if c in df.columns]
        df = df[available].copy()

        num_cols = ["tot_emp", "emp_prse", "h_mean", "a_mean",
                    "h_median", "a_median", "loc_quotient", "pct_total"]
        df = to_numeric(df, num_cols)
        df["year"] = year
        frames.append(df)

        time.sleep(2)  # polite delay between requests

    if not frames:
        print("\nNo data collected.")
        return pd.DataFrame()

    panel = (pd.concat(frames, ignore_index=True)
               .sort_values(["year", "area_title"])
               .reset_index(drop=True))
    return panel


# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

def print_summary(panel):
    print("\n" + "=" * 55)
    print("MICHIGAN RN OEWS PANEL — SUMMARY")
    print("=" * 55)
    print(f"Years:       {sorted(panel['year'].unique())}")
    print(f"Areas:       {panel['area_title'].nunique()}")
    print(f"Total rows:  {len(panel)}")

    print("\nGeographies included:")
    for a in sorted(panel["area_title"].unique()):
        print(f"  {a}")

    latest_year = panel["year"].max()
    latest = panel[panel["year"] == latest_year].copy()

    if "h_median" in panel.columns:
        print(f"\nMedian RN hourly wage ({latest_year}):")
        print(latest[["area_title", "h_median", "tot_emp"]]
              .sort_values("h_median", ascending=False)
              .to_string(index=False))

    if "loc_quotient" in panel.columns:
        print(f"\nLocation quotient ({latest_year})  [LQ < 1 = RN shortage area]:")
        print(latest[["area_title", "loc_quotient"]]
              .sort_values("loc_quotient")
              .to_string(index=False))

    print("\n" + "-" * 55)
    print("NEXT STEP — compute outcome variable Y_mt:")
    print("  Y_mt = tot_emp / (msa_population / 100000)")
    print("  Get MSA population: data.census.gov → table B01003")
    print("  Merge on area_title + year, then divide.")


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Michigan RN OEWS Panel Builder")
    print("Files are 50-150 MB each — allow ~10 min for full run.")
    print("To test first with 2 years only, change the build_panel() call below.\n")

    # Quick test: build_panel(years=[2023, 2024])
    # Full panel:
    panel = build_panel()

    if not panel.empty:
        panel.to_csv(OUTPUT_FILE, index=False)
        print(f"\nSaved to: {OUTPUT_FILE}")
        print(f"Shape: {panel.shape}")
        print_summary(panel)
        print("\nSample output:")
        print(panel.head(8).to_string())
    else:
        print("Panel empty — check errors above.")
