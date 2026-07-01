"""
ipeds_nursing.py
----------------
Pulls IPEDS Completions ("C" survey) data for nursing CIP codes at
Michigan institutions, 2005-2023 (most recent available is typically
2-year lag).

Outputs to /data_next_steps/:
    ipeds_nursing_completions_mi_2005_2023.csv
    ipeds_institutions_mi.csv

NURSING CIP CODES (NCES taxonomy)
---------------------------------
RN-track (we tag occ_track="rn"):
    51.3801  Registered Nursing/RN
    51.3818  Nursing Practice (DNP)
    51.3808  Nursing Science (MSN/PhD research)
    51.3899  Registered Nursing, Other
LPN-track (occ_track="lpn"):
    51.3901  Licensed Practical/Vocational Nurse Training
CNA-track (occ_track="cna"):
    51.3902  Nursing Assistant/Aide and Patient Care Assistant/Aide
Other nursing (occ_track="other_nursing"):
    51.38xx  catch-all (specialist programs, adult health, etc.)

CAVEATS
-------
1. IPEDS unit-record changes: CIP 2000 used pre-2010, CIP 2010 used 2010-2019,
   CIP 2020 used 2020+. Most nursing codes are stable but 51.3818 (DNP) was
   added in CIP 2010 — pre-2010 DNP grads appear under other codes.

2. Award level: we include all award levels (certificate, associate,
   bachelor's, master's, doctorate). For "RN pipeline" specifically you
   usually want associate (3) + bachelor's (5) — filter in analysis.

3. Institution -> MSA mapping: IPEDS provides CBSA in the HD (Header) file.
   We merge that on. Online-heavy schools (e.g. WGU, Chamberlain) will
   credit grads to the HQ MSA but enrolled students may live anywhere —
   a known limitation.

4. URL pattern: https://nces.ed.gov/ipeds/datacenter/data/C{YYYY}_A.zip
   File-naming varies for older years (some are C{YY}_A.zip).
   We try both. Each file is small (<5 MB) and contains all institutions
   nationally; we filter to Michigan (STABBR == "MI") via HD file.

USAGE
-----
    python scripts/next_steps/ipeds_nursing.py
    python scripts/next_steps/ipeds_nursing.py --years 2022 2023
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

YEARS = list(range(2005, 2024))

CIP_TRACKS = {
    "51.3801": "rn",
    "51.3808": "rn",
    "51.3818": "rn",
    "51.3899": "rn",
    "51.3901": "lpn",
    "51.3902": "cna",
}

HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}


def hd_url(year):
    # HD = institutional header (one row per institution)
    return f"https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip"


def c_urls(year):
    # IPEDS renamed Completions files: C{YYYY}_A (awards by CIP/race/sex)
    # The "_A" suffix appears starting in 2008. Pre-2008 the file is C{YYYY}.zip
    # which has wider CIP/awlevel breakdowns.
    return [
        f"https://nces.ed.gov/ipeds/datacenter/data/C{year}_A.zip",
        f"https://nces.ed.gov/ipeds/datacenter/data/C{year}.zip",
    ]


def fetch_zip(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=180)
        if r.status_code != 200 or len(r.content) < 1000:
            return None
        return zipfile.ZipFile(BytesIO(r.content))
    except (requests.RequestException, zipfile.BadZipFile):
        return None


def read_csv_from_zip(z):
    """IPEDS zips contain a single CSV (or _rv revised CSV). Prefer revised."""
    names = z.namelist()
    rv = [n for n in names if n.lower().endswith(".csv") and "_rv" in n.lower()]
    if rv:
        name = rv[0]
    else:
        csvs = [n for n in names if n.lower().endswith(".csv")]
        if not csvs:
            return None
        name = csvs[0]
    try:
        return pd.read_csv(z.open(name), dtype=str, encoding="latin-1",
                           low_memory=False)
    except Exception:
        return None


def load_hd_michigan(year):
    z = fetch_zip(hd_url(year))
    if z is None:
        print(f"  [{year}] HD file unavailable")
        return pd.DataFrame()
    df = read_csv_from_zip(z)
    if df is None:
        return pd.DataFrame()
    df.columns = [c.upper() for c in df.columns]
    if "STABBR" not in df.columns or "UNITID" not in df.columns:
        return pd.DataFrame()
    mi = df[df["STABBR"].str.upper() == "MI"].copy()
    cols = ["UNITID", "INSTNM", "CITY", "STABBR", "ZIP", "CBSA",
            "CBSATYPE", "COUNTYCD", "COUNTYNM", "SECTOR", "ICLEVEL"]
    keep = [c for c in cols if c in mi.columns]
    mi = mi[keep].copy()
    mi["year"] = year
    return mi


def load_completions(year, mi_unitids):
    for u in c_urls(year):
        z = fetch_zip(u)
        if z is not None:
            print(f"  [{year}] completions: {u.split('/')[-1]}")
            df = read_csv_from_zip(z)
            if df is None:
                continue
            df.columns = [c.upper() for c in df.columns]
            if "UNITID" not in df.columns or "CIPCODE" not in df.columns:
                continue
            # CIP comes in as "51.3801" — strip and normalize
            df["CIPCODE"] = df["CIPCODE"].astype(str).str.strip()
            # Filter: Michigan institutions, nursing family (51.38, 51.39)
            df = df[df["UNITID"].astype(str).isin(mi_unitids)]
            df = df[df["CIPCODE"].str.startswith(("51.38", "51.39"))].copy()
            df["year"] = year
            df["occ_track"] = df["CIPCODE"].map(CIP_TRACKS).fillna("other_nursing")
            return df
    print(f"  [{year}] completions file unavailable at any URL")
    return pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=YEARS)
    args = ap.parse_args()

    hd_frames, comp_frames = [], []
    for y in args.years:
        print(f"\n[{y}] HD ...")
        hd = load_hd_michigan(y)
        if hd.empty:
            continue
        hd_frames.append(hd)
        mi_unitids = set(hd["UNITID"].astype(str))
        comp = load_completions(y, mi_unitids)
        if not comp.empty:
            # attach minimal institution metadata
            comp = comp.merge(
                hd[[c for c in ["UNITID", "INSTNM", "CBSA", "COUNTYCD"] if c in hd.columns]],
                on="UNITID", how="left")
            comp_frames.append(comp)
        time.sleep(1)

    if not hd_frames:
        print("No HD data; aborting.", file=sys.stderr)
        sys.exit(1)

    hd_all = pd.concat(hd_frames, ignore_index=True)
    hd_out = OUT_DIR / "05_ipeds_institutions_mi.csv"
    hd_all.to_csv(hd_out, index=False)
    print(f"\nSaved {len(hd_all)} institution-years -> {hd_out.name}")

    if comp_frames:
        comp_all = pd.concat(comp_frames, ignore_index=True)
        # Numeric coercion for award counts
        for c in ["CTOTALT", "CTOTALM", "CTOTALW", "AWLEVEL"]:
            if c in comp_all.columns:
                comp_all[c] = pd.to_numeric(comp_all[c], errors="coerce")
        out = OUT_DIR / "05_ipeds_nursing_completions_mi_2005_2023.csv"
        comp_all.to_csv(out, index=False)
        print(f"Saved {len(comp_all)} completion rows -> {out.name}")
        print("\nBy track / year:")
        if "CTOTALT" in comp_all.columns:
            piv = comp_all.groupby(["year", "occ_track"])["CTOTALT"].sum().unstack(fill_value=0)
            print(piv.to_string())
    else:
        print("No completions data collected.")


if __name__ == "__main__":
    main()
