"""
oews_nursing_extended.py
------------------------
Pulls OEWS data for RN, LPN, and CNA at Michigan MSA + nonmetro BOS areas,
extended back to 2005 (OEWS publishes from 1999, but BLS area definitions
and SOC codes shift over time — see caveats below).

Outputs three CSVs in /data_next_steps/:
    oews_michigan_rn_2005_2024.csv
    oews_michigan_lpn_2005_2024.csv
    oews_michigan_cna_2005_2024.csv

CAVEATS
-------
1. CNA SOC code changed in May 2019 OEWS:
       2005-2018: 31-1014  (Nursing Assistants, 2000/2010 SOC)
       2019-2024: 31-1131  (Nursing Assistants, 2018 SOC)
   We pull both codes; only one will match per year.
   31-1014 in 2010 SOC also included Orderlies; 2018 SOC split into
   31-1131 (Nursing Assistants) + 31-1132 (Orderlies). Not strictly
   comparable across the 2019 break — flag in analysis.

2. RN (29-1141) and LPN (29-2061) codes are stable 2000 -> 2010 -> 2018 SOC.

3. OEWS URL pattern:
       2008-2024: https://www.bls.gov/oes/special-requests/oesm{YY}all.zip
       2005-2007: variable — uses separate state/MSA zip files, sometimes .xls
   We attempt the unified URL first; pre-2008 may fail and require manual
   download. The script logs which years succeeded.

4. MSA boundary changes (OMB 2003, 2013, 2015, 2018, 2023 delineations) mean
   "Detroit-Warren-Dearborn" pre-2015 was "Detroit-Warren-Livonia", etc.
   We match by substring ("Detroit") to capture rebrands; final analysis
   should crosswalk CBSA codes for strict comparability.

5. OEWS data are 3-year rolling averages through 2002; from May 2003 onward
   they are 6-month panel estimates released annually. Methodology is most
   comparable post-2003.

USAGE
-----
    cd /Users/juanvilla/Documents/gse-580-clean
    python scripts/next_steps/oews_nursing_extended.py
    # Optional: limit years for testing
    python scripts/next_steps/oews_nursing_extended.py --years 2023 2024
"""
import argparse
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data_next_steps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OCC_CODES = {
    "rn":  ["29-1141"],
    "lpn": ["29-2061"],
    "cna": ["31-1014", "31-1131"],  # pre-2019, post-2019
}

MICHIGAN_AREAS = [
    "Ann Arbor", "Battle Creek", "Bay City", "Detroit",
    "Flint", "Grand Rapids", "Jackson, MI", "Kalamazoo",
    "Lansing", "Midland, MI", "Monroe, MI", "Muskegon",
    "Niles", "Saginaw", "Holland", "Northern Michigan",
    "Upper Peninsula", "Michigan nonmetropolitan",
]

YEARS = list(range(2005, 2025))

def url_for(year):
    return f"https://www.bls.gov/oes/special-requests/oesm{year % 100:02d}all.zip"

HEADERS = {
    "User-Agent": "GSE580-Research juanmvilla09@gmail.com",
    "Accept": "*/*",
    "Referer": "https://www.bls.gov/oes/tables.htm",
}

SUPPRESS = {"**", "*", "#", "~"}

KEEP_COLS = [
    "area", "area_title", "occ_code", "occ_title",
    "tot_emp", "emp_prse", "h_mean", "a_mean",
    "h_median", "a_median", "loc_quotient", "pct_total",
]


def is_michigan(t):
    if not isinstance(t, str):
        return False
    tl = t.lower()
    return any(m.lower() in tl for m in MICHIGAN_AREAS)


def clean_cols(df):
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def to_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().replace(list(SUPPRESS), pd.NA)
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def find_data_file(z):
    """Return name of all-area data file inside zip (xlsx, xls, or csv)."""
    names = z.namelist()
    for n in names:
        nl = n.lower()
        if "all_data" in nl and (nl.endswith(".xlsx") or nl.endswith(".xls")):
            return n
    # Older years sometimes named differently (e.g. national_M2007_dl.xls)
    for n in names:
        nl = n.lower()
        if nl.endswith(".xlsx") or nl.endswith(".xls"):
            # Skip dictionary / field files
            if "dict" in nl or "field" in nl or "readme" in nl:
                continue
            return n
    for n in names:
        if n.lower().endswith(".csv"):
            return n
    return None


def load_year(year):
    url = url_for(year)
    print(f"\n[{year}] {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=600)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching: {e}")
        return pd.DataFrame()

    print(f"  Downloaded {len(r.content)/1e6:.1f} MB")
    try:
        z = zipfile.ZipFile(BytesIO(r.content))
    except zipfile.BadZipFile:
        print("  ERROR: not a valid zip (likely an HTML error page)")
        return pd.DataFrame()

    fn = find_data_file(z)
    if not fn:
        print(f"  ERROR: no data file in zip. Contents: {z.namelist()[:6]}")
        return pd.DataFrame()
    print(f"  Reading: {fn}")

    try:
        data = z.read(fn)
        if fn.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(data), dtype=str, encoding="latin-1")
        else:
            df = pd.read_excel(BytesIO(data), dtype=str)
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return pd.DataFrame()

    df = clean_cols(df)
    if "occ_code" not in df.columns or "area_title" not in df.columns:
        print(f"  WARNING: expected columns missing. Got: {list(df.columns)[:10]}")
        return pd.DataFrame()

    # Filter to nursing SOC codes (any of RN/LPN/CNA), Michigan areas
    all_codes = sum(OCC_CODES.values(), [])
    df = df[df["occ_code"].str.strip().isin(all_codes)]
    df = df[df["area_title"].apply(is_michigan)].copy()
    df["year"] = year
    print(f"  Michigan nursing rows: {len(df)}")
    return df


def build_panel(years):
    frames = []
    for y in years:
        df = load_year(y)
        if df.empty:
            continue
        cols = [c for c in KEEP_COLS if c in df.columns] + ["year"]
        df = df[cols].copy()
        df = to_numeric(df, ["tot_emp", "emp_prse", "h_mean", "a_mean",
                             "h_median", "a_median", "loc_quotient", "pct_total"])
        frames.append(df)
        time.sleep(2)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["year", "area_title"])


def split_and_write(panel):
    for occ, codes in OCC_CODES.items():
        sub = panel[panel["occ_code"].astype(str).str.strip().isin(codes)].copy()
        out = OUT_DIR / f"01_oews_michigan_{occ}_2005_2024.csv"
        sub.to_csv(out, index=False)
        years = sorted(sub["year"].unique().tolist()) if not sub.empty else []
        print(f"  {occ.upper():3s}  rows={len(sub):5d}  years={years}  -> {out.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=YEARS)
    args = ap.parse_args()

    panel = build_panel(args.years)
    if panel.empty:
        print("\nNo data collected.", file=sys.stderr)
        sys.exit(1)

    print("\nWriting outputs:")
    split_and_write(panel)
    print("\nDone.")


if __name__ == "__main__":
    main()at 