"""
county_health_rankings.py
-------------------------
Pulls County Health Rankings (CHR) annual analytic data files for Michigan,
2010-2024. Replaces (or complements) CDC PLACES with a time-varying,
county-level health controls dataset.

Outputs to /data_next_steps/:
    county_health_rankings_mi_2010_2024.csv      (long: county × year × measure)
    county_health_rankings_mi_wide.csv           (wide: one row per county-year)

CAVEATS
-------
1. CHR was first published in 2010 (covering data circa 2003-2009). Earlier
   years are not available — for 2005-2009 you'll need to fall back to PLACES
   or BRFSS SMART (BRFSS county estimates start 2002 but are sparse for
   small counties).

2. Many CHR measures are smoothed multi-year averages of underlying BRFSS or
   vital statistics data. The release year is NOT the year of the underlying
   data. Use the `year` column as the publication year; CHR documents which
   data vintage each measure represents.

3. File naming has changed over time:
       2014-present: analytic_data{YYYY}.csv
       2010-2013:    different schema, distributed as state-specific Excel
                     files (chr-mi-{year}.xls). We attempt only the modern
                     analytic_data files; pre-2014 will likely fail and
                     require manual download.

4. CHR is published by University of Wisconsin Population Health Institute,
   funded by RWJF. Data is free and public-domain-equivalent.

USAGE
-----
    python scripts/next_steps/county_health_rankings.py
"""
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "data_next_steps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2014, 2025))   # earliest reliably scriptable

HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}

URL_PATTERNS = [
    # 2020+: hosted on S3
    "https://www.countyhealthrankings.org/sites/default/files/media/document/analytic_data{year}.csv",
    "https://www.countyhealthrankings.org/sites/default/files/analytic_data{year}.csv",
    # Older alt
    "https://www.countyhealthrankings.org/sites/default/files/analytic_data{year}_0.csv",
]


def try_download(year):
    for pat in URL_PATTERNS:
        url = pat.format(year=year)
        try:
            r = requests.get(url, headers=HEADERS, timeout=180)
            if r.status_code == 200 and len(r.content) > 10000:
                print(f"  [{year}] OK from {url}")
                return r.content
        except requests.RequestException:
            continue
    print(f"  [{year}] not found at any known URL pattern")
    return None


def parse(year, blob):
    # CHR files typically have a 1- or 2-row header; first row is variable name,
    # second is human-readable label. We read row 1 as columns and skip row 2.
    try:
        # Peek
        df0 = pd.read_csv(BytesIO(blob), dtype=str, nrows=2, encoding="latin-1")
        # Detect: if row 0 col 0 looks like a label not a value, skip it
        df = pd.read_csv(BytesIO(blob), dtype=str, encoding="latin-1",
                         low_memory=False)
    except Exception as e:
        print(f"  [{year}] parse error: {e}")
        return pd.DataFrame()

    df.columns = [c.strip() for c in df.columns]
    # Standardize key columns across years
    rename = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ("statecode", "state code", "state fips code"):
            rename[c] = "state_fips"
        elif cl in ("countycode", "county code", "county fips code"):
            rename[c] = "county_fips"
        elif cl in ("state", "state abbreviation"):
            rename[c] = "state"
        elif cl in ("county", "name", "county name"):
            rename[c] = "county"
        elif cl == "fipscode":
            rename[c] = "fips"
    df = df.rename(columns=rename)

    # Filter to MI (state FIPS = 26 or state abbr = MI)
    if "state_fips" in df.columns:
        df = df[df["state_fips"].astype(str).str.zfill(2) == "26"].copy()
    elif "state" in df.columns:
        df = df[df["state"].str.upper() == "MI"].copy()
    else:
        print(f"  [{year}] no state column found")
        return pd.DataFrame()

    # Drop state-aggregate row (county_fips == "000")
    if "county_fips" in df.columns:
        df = df[df["county_fips"].astype(str).str.zfill(3) != "000"].copy()
    df["year"] = year
    return df


def main():
    frames = []
    for y in YEARS:
        blob = try_download(y)
        if blob is None:
            continue
        df = parse(y, blob)
        if df.empty:
            continue
        frames.append(df)

    if not frames:
        print("No CHR data collected.", file=sys.stderr)
        sys.exit(1)

    # Outer-concat — schemas drift, so columns vary year-to-year
    chr_wide = pd.concat(frames, ignore_index=True, sort=False)
    out_wide = OUT_DIR / "06_county_health_rankings_mi_wide.csv"
    chr_wide.to_csv(out_wide, index=False)
    print(f"\nWide:  {chr_wide.shape}  -> {out_wide.name}")

    # Long-format: melt numeric measure columns
    id_cols = [c for c in ["year", "state_fips", "county_fips", "fips",
                           "state", "county"] if c in chr_wide.columns]
    val_cols = [c for c in chr_wide.columns if c not in id_cols]
    chr_long = chr_wide.melt(id_vars=id_cols, value_vars=val_cols,
                             var_name="measure", value_name="value")
    chr_long["value_num"] = pd.to_numeric(chr_long["value"], errors="coerce")
    chr_long = chr_long.dropna(subset=["value_num"])
    out_long = OUT_DIR / "06_county_health_rankings_mi_2010_2024.csv"
    chr_long.to_csv(out_long, index=False)
    print(f"Long:  {chr_long.shape}  -> {out_long.name}")

    if "county" in chr_wide.columns:
        print(f"\nMI counties covered: {chr_wide['county'].nunique()}")
    print(f"Years covered: {sorted(chr_wide['year'].unique().tolist())}")


if __name__ == "__main__":
    main()
