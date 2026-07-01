"""regressors_data_script.py — rebuild the public-source regressor block of
full-in-progress.csv for Michigan counties × year (2010–2023).

What this builds (joined onto an 83-county × 14-year spine):

  • ACS 5-year (Census API)            — demographics, income, housing,
                                          education, insurance, commute,
                                          poverty, race/ethnicity, burden
  • IPEDS completions (NCES bulk)      — CNA / LPN / RN / other nursing
  • CHR (countyhealthrankings.org)     — chr_* headline measures
  • AHRF (HRSA fixed-width)            — hospital/MD/nursing-fac/HPSA/etc.
                                          (uses scripts/parse_ahrf_asc.py;
                                           requires .asc + .sas in data/cache)
  • USDA ERS county typologies         — rural-urban, urban-influence,
                                          econ/mfg/recreation/poverty types
  • OMB CBSA delineations              — cbsa, cbsa_name, cbsa_ind
  • Census Gazetteer                   — land_area_mi2, popn_densty_per_squr_mi
  • HRSA HPSA designations             — hpsa_prim_care/dent/mentl_hlth

What it does NOT build (manual data — left blank or merged from existing
full-in-progress.csv if --preserve-manual is passed):
  rn_licensed_county, rn_age_*, lpn_licensed_county, lpn_age_*,
  nurse_total_count, rn_per_100k, lpn_per_100k, nurse_total_per_100k

Output: full-in-progress.rebuilt.csv (next to full-in-progress.csv).

Usage:
  export CENSUS_API_KEY=...
  python scripts/regressors_data_script.py                  # full rebuild
  python scripts/regressors_data_script.py --preserve-manual  # keep nurse cols
  python scripts/regressors_data_script.py --only acs,ipeds,chr  # subset
"""
from __future__ import annotations

import argparse
import io
import os
import re
import time
import zipfile
from pathlib import Path

try:
    import pandas as pd
    import requests
except ImportError as e:
    raise SystemExit(
        f"\n[setup] Missing required Python package: {e.name}\n"
        f"Install dependencies first:\n"
        f"    pip install -r {Path(__file__).resolve().parent.parent}/requirements.txt\n"
    )

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

OUT = ROOT / "full-in-progress.rebuilt.csv"
EXISTING = ROOT / "full-in-progress.csv"
ENV_FILE = ROOT / ".census_api_key"   # plain-text fallback for non-coders

STATE_FIPS = "26"
YEARS = list(range(2010, 2024))                      # 2010–2023 inclusive
HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}


# Bundled Census API key (Juan's). The recipient does not need to register
# their own. Override by setting the CENSUS_API_KEY environment variable.
DEFAULT_CENSUS_KEY = "8d58a978a2d45c87998d698e464ae0357cd06108"


def get_census_key() -> str:
    return (os.environ.get("CENSUS_API_KEY", "").strip()
            or (ENV_FILE.read_text().strip() if ENV_FILE.exists() else "")
            or DEFAULT_CENSUS_KEY)


CENSUS_KEY = None  # set in main()

MANUAL_NURSE_COLS = [
    "rn_licensed_county", "rn_age_under35_pct", "rn_age_55plus_pct",
    "lpn_licensed_county", "lpn_age_under35_pct", "lpn_age_55plus_pct",
    "nurse_total_count", "rn_per_100k", "lpn_per_100k", "nurse_total_per_100k",
]


def _get_with_retry(url: str, *, timeout: int = 120, attempts: int = 4):
    """GET with exponential backoff on transient network/DNS failures."""
    last = None
    for i in range(attempts):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            last = e
            wait = 2 ** i
            print(f"    retry {i+1}/{attempts} after {wait}s ({type(e).__name__})")
            time.sleep(wait)
    raise last


def _cached_get(url: str, fname: str, binary: bool = False) -> bytes | str:
    p = CACHE / fname
    if p.exists():
        return p.read_bytes() if binary else p.read_text()
    r = _get_with_retry(url)
    if binary:
        p.write_bytes(r.content)
        return r.content
    p.write_text(r.text)
    return r.text


# ---------------------------------------------------------------------------
# Spine
# ---------------------------------------------------------------------------
def build_spine() -> pd.DataFrame:
    url = (f"https://api.census.gov/data/2022/acs/acs5?get=NAME"
           f"&for=county:*&in=state:{STATE_FIPS}")
    url += f"&key={CENSUS_KEY}"
    r = requests.get(url, timeout=30)
    try:
        rows = r.json()
    except ValueError:
        msg = r.text[:300].strip()
        if r.status_code in (401, 403) or "key" in msg.lower():
            raise SystemExit(
                "\n[setup] The Census API rejected your key.\n"
                "  Delete the file '.census_api_key' in this folder and\n"
                "  re-run the script to enter a new key.\n"
                f"  (Server said: {msg})\n")
        raise SystemExit(
            f"\n[error] Census API returned non-JSON (HTTP {r.status_code}):\n  {msg}\n")
    c = pd.DataFrame(rows[1:], columns=rows[0])
    c["fips"] = c["state"] + c["county"]
    c["county_name"] = c["NAME"].str.replace(" County, Michigan", "",
                                              regex=False)
    counties = c[["fips", "county_name"]].sort_values("fips")
    spine = (counties.assign(k=1)
             .merge(pd.DataFrame({"year": YEARS, "k": 1}), on="k")
             .drop(columns="k")
             .reset_index(drop=True))
    return spine


# ---------------------------------------------------------------------------
# ACS 5-year (2010 onward; pre-2010 5-year doesn't exist)
# ---------------------------------------------------------------------------
def pull_acs() -> pd.DataFrame:
    age_m_65 = [f"B01001_{i:03d}E" for i in range(20, 26)]
    age_f_65 = [f"B01001_{i:03d}E" for i in range(44, 50)]
    age_m_25_54 = [f"B01001_{i:03d}E" for i in range(11, 17)]
    age_f_25_54 = [f"B01001_{i:03d}E" for i in range(35, 41)]
    edu_high = [f"B15003_{i:03d}E" for i in range(22, 26)]
    # 2010/2011 fallback: B15002 (sex × education) — bachelor's+ is
    # sum of male (015–018) and female (032–035), denominator is _001E
    edu_high_legacy = [f"B15002_{i:03d}E" for i in [15, 16, 17, 18,
                                                     32, 33, 34, 35]]
    uninsured = [f"B27001_{i:03d}E" for i in
                 [5, 8, 11, 14, 17, 20, 23, 26, 29,
                  33, 36, 39, 42, 45, 48, 51, 54, 57]]
    commute_30 = [f"B08303_{i:03d}E" for i in range(8, 14)]
    commute_agg = ["B08136_001E", "B08101_001E"]
    # rent/owner burden: B25070 (rent), B25091 (mortgage), shares 30%+
    rent_burden = [f"B25070_{i:03d}E" for i in [7, 8, 9, 10]]
    own_burden  = [f"B25091_{i:03d}E" for i in [8, 9, 10, 11, 19, 20, 21, 22]]
    race = ["B02001_001E", "B02001_002E", "B02001_003E", "B02001_005E"]
    hisp = ["B03003_003E", "B03003_001E"]
    # C18120 = Employment Status by Disability Status (18-64, civilian
    # noninstitutionalized) — same table AHRF uses for its F15409/F15413
    # disability fields. Direct ACS pull fills AHRF's 2017-2019 gap.
    disab = ["C18120_001E", "C18120_004E", "C18120_007E", "C18120_010E"]

    vars_ = (["B01001_001E"] + age_m_65 + age_f_65 + age_m_25_54 + age_f_25_54
             + ["B19013_001E", "B25064_001E", "B25077_001E",
                "B23025_002E", "B23025_003E", "B23025_005E",
                "B15003_001E"] + edu_high
             + ["B15002_001E"] + edu_high_legacy
             + ["B27001_001E"] + uninsured
             + ["B08303_001E"] + commute_30 + commute_agg
             + ["B25070_001E"] + rent_burden
             + ["B25091_001E"] + own_burden
             + ["B17001_001E", "B17001_002E"]
             + race + hisp + disab)

    # Census API caps `get=` at 50 variables per call — chunk and merge.
    CHUNK = 45  # leave headroom for required state/county fields
    chunks = [vars_[i:i + CHUNK] for i in range(0, len(vars_), CHUNK)]

    _bad_var_re = re.compile(r"unknown variable '([^']+)'")

    def _fetch_chunk(y: int, chunk: list[str]) -> pd.DataFrame | None:
        """Fetch a chunk; if Census reports an unknown variable, drop it
        and retry. Some ACS5 tables (B15003, B27001, B23025) don't exist
        in 2010/2011."""
        dropped = []
        while chunk:
            url = (f"https://api.census.gov/data/{y}/acs/acs5"
                   f"?get={','.join(chunk)}&for=county:*&in=state:{STATE_FIPS}"
                   f"&key={CENSUS_KEY}")
            try:
                r = _get_with_retry(url, timeout=60, attempts=3)
            except requests.exceptions.HTTPError as e:
                body = getattr(e.response, "text", "") or ""
                m = _bad_var_re.search(body)
                if m and m.group(1) in chunk:
                    chunk = [v for v in chunk if v != m.group(1)]
                    dropped.append(m.group(1))
                    continue
                print(f"  ACS {y}: HTTP {e.response.status_code} — {body[:120]}")
                return None
            except requests.exceptions.RequestException as e:
                print(f"  ACS {y}: FAIL ({e})")
                return None
            try:
                rows = r.json()
            except ValueError:
                print(f"  ACS {y}: non-JSON ({r.text[:120].strip()})")
                return None
            part = pd.DataFrame(rows[1:], columns=rows[0])
            part["fips"] = part["state"] + part["county"]
            for v in dropped:                    # add missing cols as NaN
                part[v] = pd.NA
            return part.drop(columns=["state", "county"])
        return None

    def _fetch_year(y: int) -> pd.DataFrame | None:
        parts = []
        for chunk in chunks:
            p = _fetch_chunk(y, list(chunk))
            if p is None:
                return None
            parts.append(p)
        d = parts[0]
        for p in parts[1:]:
            d = d.merge(p, on="fips", how="outer")
        return d

    frames = []
    for y in YEARS:
        d = _fetch_year(y)
        if d is None:
            continue
        for c in vars_:
            if c in d.columns:
                d[c] = pd.to_numeric(d[c], errors="coerce")
            else:
                d[c] = pd.NA

        def _ratio(num_cols, den_col):
            num = d[num_cols].sum(axis=1) if isinstance(num_cols, list) else d[num_cols]
            return (num / d[den_col] * 100).round(2)

        o = pd.DataFrame({"fips": d["fips"], "year": y})
        o["pop_total"]    = d["B01001_001E"]
        o["pop_65plus"]   = d[age_m_65 + age_f_65].sum(axis=1)
        o["pct_65plus"]   = (o.pop_65plus / o.pop_total * 100).round(2)
        o["pop_25_54"]    = d[age_m_25_54 + age_f_25_54].sum(axis=1)
        o["pct_25_54"]    = (o.pop_25_54 / o.pop_total * 100).round(2)
        o["median_hh_income"]      = d["B19013_001E"]
        o["median_gross_rent"]     = d["B25064_001E"]
        o["median_home_value"]     = d["B25077_001E"]
        o["unemployment_rate"]     = _ratio("B23025_005E", "B23025_003E")
        o["lfp_rate"]              = _ratio("B23025_002E", "B01001_001E")
        # Prefer modern B15003 (2012+); fall back to B15002 for 2010/2011
        modern = _ratio(edu_high, "B15003_001E")
        legacy = _ratio(edu_high_legacy, "B15002_001E")
        o["pct_bachelors_plus"]    = modern.fillna(legacy)
        o["pct_uninsured"]         = _ratio(uninsured, "B27001_001E")
        o["pct_commute_30plus"]    = _ratio(commute_30, "B08303_001E")
        o["mean_commute_minutes"]  = (d["B08136_001E"] / d["B08101_001E"]).round(2)
        o["rent_burden_pct"]       = _ratio(rent_burden, "B25070_001E")
        o["own_burden_pct"]        = _ratio(own_burden, "B25091_001E")
        # Disability rate (civilian noninstitutionalized 18-64) — sum of
        # "with a disability" sub-codes (employed, unemployed, not in LF)
        # divided by C18120 universe denominator. Matches AHRF F15409
        # methodology (corr=0.9997 verified empirically).
        o["pct_disability"] = _ratio(
            ["C18120_004E", "C18120_007E", "C18120_010E"], "C18120_001E")
        o["poverty_rate"]          = _ratio("B17001_002E", "B17001_001E")
        o["pct_white"]    = _ratio("B02001_002E", "B02001_001E")
        o["pct_black"]    = _ratio("B02001_003E", "B02001_001E")
        o["pct_asian"]    = _ratio("B02001_005E", "B02001_001E")
        o["pct_hispanic"] = _ratio("B03003_003E", "B03003_001E")
        frames.append(o)
        print(f"  ACS {y}: ok")
        time.sleep(0.3)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# IPEDS completions (nursing CIPs)
# ---------------------------------------------------------------------------
# CIP families: 51.3801 RN, 51.3901 LPN, 51.3902 CNA, others under 51.39xx
def pull_ipeds() -> pd.DataFrame:
    frames = []
    for y in YEARS:
        # NCES posts the "C" completion file as e.g. c2020_a.zip with CSV inside
        url = f"https://nces.ed.gov/ipeds/datacenter/data/C{y}_A.zip"
        try:
            raw = _cached_get(url, f"ipeds_C{y}_A.zip", binary=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                # main CSV is e.g. c2020_a.csv (lowercase, no _rv)
                name = next(n for n in z.namelist()
                            if n.lower().endswith(".csv")
                            and "_rv" not in n.lower())
                df = pd.read_csv(z.open(name), dtype=str, low_memory=False)
        except Exception as e:
            print(f"  IPEDS {y}: FAIL ({e})"); continue
        # Standardise column names
        df.columns = [c.lower() for c in df.columns]
        if "cipcode" not in df.columns or "ctotalt" not in df.columns:
            print(f"  IPEDS {y}: unexpected schema"); continue
        df["ctotalt"] = pd.to_numeric(df["ctotalt"], errors="coerce").fillna(0)
        df = df[df["cipcode"].astype(str).str.startswith("51.39")
                | (df["cipcode"].astype(str) == "51.3801")]
        # Merge institution → county via HD file (same year)
        hd_url = f"https://nces.ed.gov/ipeds/datacenter/data/HD{y}.zip"
        try:
            hd_raw = _cached_get(hd_url, f"ipeds_HD{y}.zip", binary=True)
            with zipfile.ZipFile(io.BytesIO(hd_raw)) as z:
                hd_name = next(n for n in z.namelist()
                               if n.lower().endswith(".csv")
                               and "_rv" not in n.lower())
                hd = pd.read_csv(z.open(hd_name), dtype=str,
                                 low_memory=False, encoding_errors="replace")
            hd.columns = [c.lower() for c in hd.columns]
            hd = hd[hd["stabbr"] == "MI"][["unitid", "fips", "countycd"]]
            # countycd is full 5-digit state+county fips
            hd = hd.rename(columns={"countycd": "fips_full"})
            df = df.merge(hd, on="unitid", how="inner")
            df["fips"] = df["fips_full"].astype(str).str.zfill(5)
        except Exception as e:
            print(f"  IPEDS {y} HD: FAIL ({e})"); continue

        def _bucket(cip):
            if cip == "51.3801": return "rn"
            if cip == "51.3901": return "lpn"
            if cip == "51.3902": return "cna"
            return "other_nursing"
        df["bucket"] = df["cipcode"].map(_bucket)
        g = (df.groupby(["fips", "bucket"])["ctotalt"].sum()
                .unstack(fill_value=0).reset_index())
        for b in ("cna", "lpn", "rn", "other_nursing"):
            if b not in g.columns:
                g[b] = 0
        g["year"] = y
        g = g.rename(columns={
            "cna": "ipeds_completions_cna",
            "lpn": "ipeds_completions_lpn",
            "rn":  "ipeds_completions_rn",
            "other_nursing": "ipeds_completions_other_nursing",
        })
        g["ipeds_completions_total"] = (g.ipeds_completions_cna
            + g.ipeds_completions_lpn + g.ipeds_completions_rn
            + g.ipeds_completions_other_nursing)
        frames.append(g)
        print(f"  IPEDS {y}: ok")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# County Health Rankings — headline measures
# ---------------------------------------------------------------------------
# Annual analytic data Excel: stable URL pattern per release year.
# Columns vary by year; we map to chr_* names via a fuzzy column finder.
CHR_TARGETS = {
    "chr_premature_death_rate":         ["premature death", "ypll", "years of potential life lost"],
    "chr_preventable_hosp_rate":        ["preventable hospital"],
    "chr_pct_fair_poor_health":         ["fair or poor health", "% fair", "fair/poor"],
    "chr_pct_low_birthweight":          ["low birthweight", "low birth weight"],
    "chr_pcp_rate":                     ["primary care physicians rate", "pcp rate"],
    "chr_dentist_rate":                 ["dentist rate"],
    "chr_pct_uninsured":                ["uninsured", "% uninsured"],
    "chr_pct_adult_smoking":            ["adult smoking", "% smokers"],
    "chr_pct_adult_obesity":            ["adult obesity", "% obese", "% adults with obesity"],
    "chr_avg_mental_unhealthy_days":    ["mentally unhealthy", "poor mental health days"],
    "chr_pct_children_in_poverty":      ["children in poverty"],
}

def pull_chr() -> pd.DataFrame:
    """Looks for pre-downloaded CHR analytic CSVs in data/cache/chr_{year}.csv.

    The County Health Rankings site blocks scripted downloads. The MANUAL
    step is documented in REGRESSORS_README.md — download
      https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation
    "Analytic Data" CSV for each year, rename to chr_{year}.csv, drop in
    data/cache/.
    """
    frames = []
    found_any = False
    for y in YEARS:
        local = CACHE / f"chr_{y}.csv"
        if not local.exists():
            continue
        found_any = True
        try:
            df = pd.read_csv(local, low_memory=False)
        except Exception as e:
            print(f"  CHR {y}: FAIL reading local file ({e})"); continue
        # standard CHR analytic CSV has 5fipscode + statecode + countycode
        cols = {c.lower(): c for c in df.columns}
        fips_col = (cols.get("5-digit fips code")
                    or cols.get("5digitfipscode") or cols.get("fipscode"))
        if not fips_col:
            print(f"  CHR {y}: no fips col"); continue
        df["fips"] = df[fips_col].astype(str).str.zfill(5)
        df = df[df["fips"].str.startswith(STATE_FIPS)
                & (df["fips"].str.slice(2) != "000")]
        o = pd.DataFrame({"fips": df["fips"], "year": y})
        lc = {c.lower(): c for c in df.columns}
        for target, keys in CHR_TARGETS.items():
            match = None
            for k in keys:
                hits = [orig for low, orig in lc.items()
                        if k in low and "raw value" in low]
                if hits:
                    match = hits[0]; break
                hits = [orig for low, orig in lc.items() if k in low]
                if hits:
                    match = hits[0]; break
            o[target] = pd.to_numeric(df[match], errors="coerce") if match else pd.NA
        frames.append(o)
        print(f"  CHR {y}: ok")
    if not found_any:
        print("  CHR: no local files found — see REGRESSORS_README.md "
              "(section 'CHR manual download'). Skipping.")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# AHRF — uses local .asc + .sas via parse_ahrf_asc.py
# ---------------------------------------------------------------------------
# Two supported layouts:
#   (a) Per-release subdirectories under data/cache/ahrf/{YYYY-YYYY}/
#       containing the unzipped .asc anywhere underneath, plus a .sas (or
#       .sas.txt) under tech_doc_*/Technical Documentation/. This is the
#       layout produced by manual download + unzip.
#   (b) Legacy flat layout: data/cache/AHRF*.asc with a same-stem .sas
#       next to it.
AHRF_DIR = CACHE / "ahrf"


def ahrf_files_available() -> list[tuple[Path, Path]]:
    """Return (data, doc) path pairs, one per AHRF release found. The data
    file is either a fixed-width .asc (with .sas doc) or a CSV (with
    Technical Documentation xlsx). build_ahrf_spine() dispatches on the
    data file's extension."""
    pairs: list[tuple[Path, Path]] = []
    seen_data: set[Path] = set()

    if AHRF_DIR.exists():
        for year_dir in sorted(AHRF_DIR.iterdir()):
            if not year_dir.is_dir():
                continue
            files = [p for p in year_dir.rglob("*") if p.is_file()]
            ascs = [p for p in files if p.suffix.lower() == ".asc"]
            sass = [p for p in files
                    if p.suffix.lower() == ".sas"
                    or p.name.lower().endswith(".sas.txt")]
            csvs = [p for p in files
                    if p.suffix.lower() == ".csv"
                    and re.match(r"ahrf\d{4}(_\w+)?\.csv$", p.name.lower())
                    # exclude per-category files (ahrf2024hf.csv etc.)
                    and not re.match(r"ahrf\d{4}[a-z]{2,4}", p.name.lower())]
            xlsxs = [p for p in files
                     if p.suffix.lower() == ".xlsx"
                     and ("tech" in p.name.lower()
                          or "documentation" in p.name.lower())]

            # Prefer ASC release if available (parser is faster + battle-tested)
            if ascs and sass:
                asc = max(ascs, key=lambda p: p.stat().st_size)
                sas_pref = [s for s in sass
                            if "tech" in str(s).lower()
                            or "documentation" in str(s).lower()]
                sas = (sas_pref or sass)[0]
                pairs.append((asc, sas))
                seen_data.add(asc.resolve())
                continue

            # Fall back to CSV release
            if csvs and xlsxs:
                csv = max(csvs, key=lambda p: p.stat().st_size)
                # Prefer CSV-doc xlsx if both ASCII-doc and CSV-doc exist
                xlsx_pref = [x for x in xlsxs if "csv" in str(x).lower()]
                xlsx = (xlsx_pref or xlsxs)[0]
                pairs.append((csv, xlsx))
                seen_data.add(csv.resolve())

    # Legacy flat layout
    for asc in sorted(set(CACHE.glob("AHRF*.asc")) | set(CACHE.glob("ahrf*.asc"))):
        if asc.resolve() in seen_data:
            continue
        sas = asc.with_suffix(".sas")
        if sas.exists():
            pairs.append((asc, sas))

    return pairs


def build_ahrf_spine() -> pd.DataFrame:
    """Parse every AHRF release in data/cache/ and build a county-year wide
    panel. Each (county, year, variable) cell takes the value from the
    most recent release that publishes it — standard AHRF practice since
    HRSA periodically revises historical estimates."""
    try:
        from parse_ahrf_asc import parse_release, parse_csv_release
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from parse_ahrf_asc import parse_release, parse_csv_release

    pairs = ahrf_files_available()
    if not pairs:
        return pd.DataFrame()

    frames = []
    for data, doc in pairs:
        # release label = the latest 4-digit year in the filename
        years_in_name = re.findall(r"(19|20)\d{2}", data.name) or \
                        re.findall(r"(19|20)\d{2}", data.parent.name)
        if years_in_name:
            label = years_in_name[-1] + (re.findall(r"\d{2}", data.name)[-1]
                                           if re.findall(r"\d{2}", data.name)
                                           else "")
        else:
            label = data.stem
        try:
            if data.suffix.lower() == ".csv":
                df = parse_csv_release(data, doc, release_label=label,
                                        state_fips=STATE_FIPS)
            else:
                df = parse_release(data, doc, release_label=label,
                                    state_fips=STATE_FIPS)
            df["_release_rank"] = int(re.search(r"\d{4}", label).group())
            frames.append(df)
            print(f"  AHRF {data.name}: ok ({len(df):,} long rows, "
                  f"{df.year.nunique()} years, {df.variable.nunique()} vars)")
        except Exception as e:
            print(f"  AHRF {data.name}: FAIL ({e})")

    if not frames:
        return pd.DataFrame()

    long = pd.concat(frames, ignore_index=True)
    # Restrict to the configured panel window before pivoting wide.
    long = long[long["year"].between(min(YEARS), max(YEARS))]
    # Keep most-recent-release value per (county, year, variable)
    long = (long.sort_values("_release_rank", ascending=False)
                .drop_duplicates(["fips_st_cnty", "year", "variable"],
                                  keep="first"))
    wide = long.pivot_table(index=["fips_st_cnty", "year"],
                             columns="variable", values="value",
                             aggfunc="first").reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={"fips_st_cnty": "fips"})
    wide["fips"] = wide["fips"].astype(str).str.zfill(5)
    wide["year"] = wide["year"].astype(int)
    print(f"  AHRF spine: {wide.shape[0]:,} county-years × "
          f"{wide.shape[1] - 2} variables, "
          f"{int(wide.year.min())}–{int(wide.year.max())}")
    return wide


# ---------------------------------------------------------------------------
# USDA ERS county typologies (2015 vintage covers your panel window)
# ---------------------------------------------------------------------------
def pull_ers() -> pd.DataFrame:
    # URLs verified 2026-06; ERS rotates media IDs occasionally.
    rucc_url = "https://www.ers.usda.gov/media/5769/2013-rural-urban-continuum-codes.xls"
    uic_url  = "https://www.ers.usda.gov/media/6183/2013-urban-influence-codes.xls"
    typ_url  = "https://www.ers.usda.gov/media/6175/ers-county-typology-codes-2015-edition.xls"
    out = pd.DataFrame()
    try:
        raw = _cached_get(rucc_url, "rucc2013.xls", binary=True)
        d = pd.read_excel(io.BytesIO(raw), dtype=str)
        d.columns = [c.strip() for c in d.columns]
        d = d.rename(columns={"FIPS": "fips", "RUCC_2013": "rural_urban_contnm"})
        out = d[["fips", "rural_urban_contnm"]]
    except Exception as e:
        print(f"  ERS RUCC: FAIL ({e})")
    try:
        raw = _cached_get(uic_url, "uic2013.xls", binary=True)
        d = pd.read_excel(io.BytesIO(raw), dtype=str)
        d.columns = [c.strip() for c in d.columns]
        d = d.rename(columns={"FIPS": "fips", "UIC_2013": "urban_influnc"})
        out = (out.merge(d[["fips", "urban_influnc"]], on="fips", how="outer")
               if not out.empty else d[["fips", "urban_influnc"]])
    except Exception as e:
        print(f"  ERS UIC: FAIL ({e})")
    try:
        raw = _cached_get(typ_url, "ers_typology2015.xls", binary=True)
        d = pd.read_excel(io.BytesIO(raw), dtype=str)
        d.columns = [c.strip() for c in d.columns]
        rename = {
            "FIPStxt": "fips",
            "Type_2015_Update": "econ_depndnt_typolgy",
            "Manuf_2015_Update": "mfg_depndnt_typolgy",
            "Recreation_2015_Update": "recrtn_typolgy",
            "HiCreativeClass_2015_Update": None,
            "HiAmenity": None,
            "Low_Education_2015_update": None,
            "Low_Employment_2015_update": None,
            "Pop_loss_2015_update": "popn_loss_typolgy",
            "Retirement_Destination_2015_Update": "retrmnt_destntn_typolgy",
            "Persistent_Poverty_2013_Update": "prstnt_povty_typolgy",
            "Persistent_Child_Poverty_2013_Update": None,
        }
        keep = {k: v for k, v in rename.items() if v and k in d.columns}
        keep["FIPStxt"] = "fips"
        d2 = d[list(keep.keys())].rename(columns=keep)
        out = out.merge(d2, on="fips", how="outer") if not out.empty else d2
        # hi_povty derived from persistent_poverty if no direct field
        if "hi_povty_typolgy" not in out.columns and "prstnt_povty_typolgy" in out.columns:
            out["hi_povty_typolgy"] = out["prstnt_povty_typolgy"]
    except Exception as e:
        print(f"  ERS typology: FAIL ({e})")
    if out.empty:
        return out
    out = out[out["fips"].astype(str).str.startswith(STATE_FIPS)]
    print(f"  ERS typology: ok ({len(out)} MI counties)")
    return out


# ---------------------------------------------------------------------------
# Census Gazetteer — land area, density (uses 2020 vintage as time-invariant)
# ---------------------------------------------------------------------------
def pull_gazetteer() -> pd.DataFrame:
    url = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
           "2020_Gazetteer/2020_Gaz_counties_national.zip")
    try:
        raw = _cached_get(url, "gaz_2020_counties.zip", binary=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = next(n for n in z.namelist() if n.endswith(".txt"))
            df = pd.read_csv(z.open(name), sep="\t", dtype=str,
                             encoding="latin-1")
    except Exception as e:
        print(f"  Gazetteer: FAIL ({e})"); return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    df = df[df["USPS"] == "MI"].copy()
    df["fips"] = df["GEOID"].astype(str).str.zfill(5)
    df["land_area_mi2"] = pd.to_numeric(df["ALAND_SQMI"], errors="coerce")
    out = df[["fips", "land_area_mi2"]].reset_index(drop=True)
    print(f"  Gazetteer: ok ({len(out)} counties)")
    return out


# ---------------------------------------------------------------------------
# OMB CBSA delineations (uses 2023 vintage)
# ---------------------------------------------------------------------------
def pull_cbsa() -> pd.DataFrame:
    url = ("https://www2.census.gov/programs-surveys/metro-micro/"
           "geographies/reference-files/2023/delineation-files/list1_2023.xlsx")
    try:
        raw = _cached_get(url, "cbsa_2023.xlsx", binary=True)
        df = pd.read_excel(io.BytesIO(raw), header=2, dtype=str)
    except Exception as e:
        print(f"  CBSA: FAIL ({e})"); return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    state_col = next((c for c in df.columns if "FIPS State" in c), None)
    cnty_col  = next((c for c in df.columns if "FIPS County" in c), None)
    cbsa_col  = next((c for c in df.columns if c.startswith("CBSA Code")), None)
    name_col  = next((c for c in df.columns if "CBSA Title" in c), None)
    type_col  = next((c for c in df.columns if "Metropolitan/Micropolitan" in c), None)
    if not all([state_col, cnty_col, cbsa_col, name_col]):
        print("  CBSA: unexpected columns"); return pd.DataFrame()
    df = df.dropna(subset=[state_col, cnty_col])
    df = df[df[state_col] == STATE_FIPS].copy()
    df["fips"] = df[state_col] + df[cnty_col]
    df["cbsa"] = df[cbsa_col]
    df["cbsa_name"] = df[name_col]
    df["cbsa_ind"] = df[type_col].fillna("").str.contains("Metro").map(
        {True: "Metro", False: "Micro"})
    print(f"  CBSA: ok ({len(df)} MI counties in CBSAs)")
    return df[["fips", "cbsa", "cbsa_name", "cbsa_ind"]]


# ---------------------------------------------------------------------------
# HRSA HPSA — current designations (snapshot; not historical)
# ---------------------------------------------------------------------------
def pull_hpsa() -> pd.DataFrame:
    """HRSA publishes one CSV per discipline; we count designations per county."""
    disciplines = {
        "hpsa_prim_care":  "BCD_HPSA_FCT_DET_PC.csv",
        "hpsa_dent":       "BCD_HPSA_FCT_DET_DH.csv",
        "hpsa_mentl_hlth": "BCD_HPSA_FCT_DET_MH.csv",
    }
    base = "https://data.hrsa.gov/DataDownload/DD_Files/"
    out = None
    for colname, fname in disciplines.items():
        try:
            raw = _cached_get(base + fname, f"hpsa_{colname}.csv")
            df = pd.read_csv(io.StringIO(raw), low_memory=False, dtype=str)
        except Exception as e:
            print(f"  HPSA {colname}: FAIL ({e})"); continue
        state_col = next((c for c in df.columns
                          if "State Abbreviation" in c), None)
        fips_col  = next((c for c in df.columns
                          if "County Equivalent FIPS" in c
                          or "County FIPS" in c), None)
        status_col = next((c for c in df.columns
                           if "Status Description" in c
                           or c.strip() == "HPSA Status"), None)
        if not all([state_col, fips_col]):
            print(f"  HPSA {colname}: unexpected schema "
                  f"(cols={list(df.columns)[:5]}…)"); continue
        df = df[df[state_col] == "MI"]
        if status_col is not None:
            df = df[df[status_col].fillna("").str.contains("Designated",
                                                            case=False)]
        df["fips"] = df[fips_col].astype(str).str.zfill(5)
        g = (df.groupby("fips").size().rename(colname)
                .reset_index())
        out = g if out is None else out.merge(g, on="fips", how="outer")
        print(f"  HPSA {colname}: ok ({len(g)} MI counties)")
    return out if out is not None else pd.DataFrame()


# ---------------------------------------------------------------------------
# ACS PUMS — county-level RN/LPN wages via PUMA → county assignment
# ---------------------------------------------------------------------------
# Construction: each year of ACS 1-year PUMS contains person records with
# OCCP (occupation code), WAGP (annual wage), WKHP (usual hours/week),
# ADJINC (inflation adjustment factor), PWGTP (person weight), and PUMA.
# We compute the PWGTP-weighted median hourly wage by PUMA × year for
# RNs (OCCP=3255) and LPNs (OCCP=3500), then map PUMAs to counties using
# the 2010 tract-to-PUMA equivalency file as a population-share weight.
#
# Coverage: 2012–2021 (1-year ACS PUMA10 vintage). 2020 PUMS does not exist
# (Census suspended the 1-year program during the pandemic). 2022+ ACS PUMS
# uses PUMA20 boundaries which require a different crosswalk and are not
# yet wired here.
PUMS_OCC_CODES = {"rn": "3255", "lpn": "3500"}


def _weighted_median(values: pd.Series, weights: pd.Series) -> float:
    """PWGTP-weighted median. Used for PUMA-year aggregation."""
    df = pd.DataFrame({"v": values, "w": weights}).dropna()
    if df.empty or df["w"].sum() <= 0:
        return float("nan")
    df = df.sort_values("v")
    cutoff = df["w"].sum() / 2
    return float(df.loc[df["w"].cumsum() >= cutoff, "v"].iloc[0])


def _puma_county_xwalk_2010() -> pd.DataFrame:
    """Build a 2010 PUMA → county weighted crosswalk for Michigan.

    Uses the Census 2010 tract-to-PUMA equivalency file. Each tract is
    treated as ~equal-population, so the share of a county's tracts in
    a given PUMA approximates that PUMA's population share within the
    county. Returns fips, puma, pop_share (sums to 1 within county)."""
    url = ("https://www2.census.gov/geo/docs/maps-data/data/rel/"
           "2010_Census_Tract_to_2010_PUMA.txt")
    try:
        raw = _cached_get(url, "tract_to_puma_2010.txt")
        df = pd.read_csv(io.StringIO(raw), dtype=str)
    except Exception as e:
        print(f"  PUMA xwalk: FAIL ({e})"); return pd.DataFrame()
    df = df[df["STATEFP"] == STATE_FIPS].copy()
    df["fips"] = df["STATEFP"] + df["COUNTYFP"]
    df["puma"] = df["PUMA5CE"].astype(str).str.zfill(5)
    grp = (df.groupby(["fips", "puma"]).size()
              .rename("n_tracts").reset_index())
    totals = grp.groupby("fips")["n_tracts"].transform("sum")
    grp["pop_share"] = grp["n_tracts"] / totals
    print(f"  PUMA xwalk: ok ({grp.fips.nunique()} MI counties, "
          f"{grp.puma.nunique()} PUMAs)")
    return grp[["fips", "puma", "pop_share"]]


def pull_pums_wages() -> pd.DataFrame:
    """MI ACS PUMS 1-year files, 2012–2021. Returns fips, year,
    rn_pums_wage, lpn_pums_wage (median real hourly wage in harmonized
    ADJINC-adjusted dollars)."""
    supported = [y for y in YEARS if 2012 <= y <= 2021 and y != 2020]
    skipped = [y for y in YEARS if y not in supported]
    if skipped:
        print(f"  PUMS: skipping years {skipped} "
              f"(2020 absent; 2022+ needs PUMA20 crosswalk)")
    rows = []
    needed_cols = {"PUMA", "OCCP", "WAGP", "WKHP", "ADJINC", "PWGTP"}
    for y in supported:
        url = (f"https://www2.census.gov/programs-surveys/acs/data/pums/"
               f"{y}/1-Year/csv_pmi.zip")
        try:
            raw = _cached_get(url, f"pums_p_mi_{y}.zip", binary=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                # 2017+: psam_p{ST}.csv ; pre-2017: ss{YY}pmi.csv
                cands = [n for n in z.namelist()
                         if n.lower().endswith(".csv")]
                name = (next((n for n in cands
                              if "psam_p" in n.lower()), None)
                        or next((n for n in cands
                                 if n.lower().startswith("ss")
                                 and "pmi" in n.lower()), None))
                if not name:
                    print(f"  PUMS {y}: no person CSV in zip"); continue
                df = pd.read_csv(z.open(name), dtype=str,
                                 low_memory=False,
                                 usecols=lambda c: c in needed_cols)
        except Exception as e:
            print(f"  PUMS {y}: FAIL ({e})"); continue
        missing = needed_cols - set(df.columns)
        if missing:
            print(f"  PUMS {y}: missing cols {missing}"); continue
        for col in ("WAGP", "WKHP", "ADJINC", "PWGTP"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # Restrict to positive wage and reasonable full-ish hours so the
        # median is interpretable as a wage rate, not partial-year income.
        df = df[(df["WAGP"] > 0) & (df["WKHP"] >= 30)].copy()
        df["PUMA"] = df["PUMA"].astype(str).str.zfill(5)
        # ADJINC is stored as a 7-digit integer (e.g., 1010146 = 1.010146);
        # this puts WAGP into harmonized constant dollars across years.
        df["hourly"] = (df["WAGP"] * df["ADJINC"] / 1e6) / (df["WKHP"] * 50)

        parts = []
        for label, occ in PUMS_OCC_CODES.items():
            sub = df[df["OCCP"] == occ]
            if sub.empty:
                continue
            g = (sub.groupby("PUMA")
                    .apply(lambda x: _weighted_median(x["hourly"],
                                                       x["PWGTP"]),
                            include_groups=False)
                    .rename(f"{label}_pums_wage").reset_index())
            parts.append(g)
        if not parts:
            print(f"  PUMS {y}: no RN/LPN cells"); continue
        merged = parts[0]
        for p in parts[1:]:
            merged = merged.merge(p, on="PUMA", how="outer")
        merged["year"] = y
        merged = merged.rename(columns={"PUMA": "puma"})
        rows.append(merged)
        print(f"  PUMS {y}: ok ({len(merged)} PUMAs)")

    if not rows:
        return pd.DataFrame()
    pum = pd.concat(rows, ignore_index=True)
    xwalk = _puma_county_xwalk_2010()
    if xwalk.empty:
        return pd.DataFrame()
    j = pum.merge(xwalk, on="puma", how="inner")

    wage_cols = [c for c in j.columns if c.endswith("_pums_wage")]

    def _wavg(g):
        out = {}
        for c in wage_cols:
            mask = g[c].notna()
            w = g.loc[mask, "pop_share"]
            if w.sum() <= 0:
                out[c] = float("nan")
            else:
                out[c] = float((g.loc[mask, c] * w).sum() / w.sum())
        return pd.Series(out)

    final = (j.groupby(["fips", "year"])
               .apply(_wavg, include_groups=False).reset_index())
    for c in wage_cols:
        final[c] = final[c].round(2)
    print(f"  PUMS: ok ({final.fips.nunique()} counties × "
          f"{final.year.nunique()} years)")
    return final


# ---------------------------------------------------------------------------
# CMS Nursing Home Provider Information — county bed counts
# ---------------------------------------------------------------------------
# CMS publishes a monthly snapshot of certified nursing-home providers
# (formerly Nursing Home Compare). Bed counts change slowly; we apply the
# current snapshot to all panel years as a time-invariant structural
# supply-side capacity measure. Per-year snapshots before ~2017 are not
# maintained at stable URLs; LTCFocus.org carries historical files for a
# future refinement.
def _mi_county_lookup() -> dict[str, str]:
    """county-name (uppercase, no 'County' suffix) → 5-digit FIPS."""
    url = ("https://api.census.gov/data/2022/acs/acs5?get=NAME"
           f"&for=county:*&in=state:{STATE_FIPS}&key={CENSUS_KEY}")
    rows = requests.get(url, timeout=30).json()
    out = {}
    for name, state, cty in rows[1:]:
        cname = name.replace(" County, Michigan", "").upper().strip()
        out[cname] = state + cty
    return out


def pull_cms_nh() -> pd.DataFrame:
    """CMS Nursing Home Provider Information current snapshot. Returns
    fips, nh_beds_total (time-invariant)."""
    url = ("https://data.cms.gov/provider-data/api/1/datastore/query/"
           "4pq5-n9py/0/download?format=csv")
    try:
        raw = _cached_get(url, "cms_nh_provider_info.csv")
        df = pd.read_csv(io.StringIO(raw), low_memory=False, dtype=str)
    except Exception as e:
        print(f"  CMS NH: FAIL ({e}) — drop NH_ProviderInfo.csv in "
              f"data/cache/cms_nh_provider_info.csv to retry"); return pd.DataFrame()

    def find(*needles):
        for c in df.columns:
            cl = c.lower()
            if all(n in cl for n in needles):
                return c
        return None
    state_col  = find("provider", "state") or find("state")
    # Prefer "County/Parish" (actual name); "Provider SSA County Code" is numeric
    county_col = (find("county/parish") or find("county", "parish")
                  or find("county", "name") or find("provider", "county"))
    beds_col   = find("number", "certified", "beds") or find("certified", "beds") or find("number", "beds")
    if not all([state_col, county_col, beds_col]):
        print(f"  CMS NH: unexpected schema "
              f"({list(df.columns)[:8]}…)"); return pd.DataFrame()
    df = df[df[state_col].astype(str).str.upper() == "MI"].copy()
    df[beds_col] = pd.to_numeric(df[beds_col], errors="coerce")
    lookup = _mi_county_lookup()
    df["fips"] = (df[county_col].astype(str).str.upper().str.strip()
                  .map(lookup))
    df = df.dropna(subset=["fips"])
    g = (df.groupby("fips")[beds_col].sum()
            .rename("nh_beds_total").reset_index())
    print(f"  CMS NH: ok ({len(g)} MI counties)")
    return g


# ---------------------------------------------------------------------------
# ANCC Magnet — county mapping via CBSA delineations
# ---------------------------------------------------------------------------
# policy_levers.csv carries Magnet activity flags at the CBSA level for
# 2011–2024. We expand to county-year by joining on the CBSA → county
# crosswalk (OMB delineation file via pull_cbsa()).
def pull_magnet_county() -> pd.DataFrame:
    """Map CBSA-level Magnet flags from policy_levers.csv down to
    constituent MI counties. Returns fips, year, magnet_hospital_present."""
    pl_path = ROOT / "policy_levers.csv"
    if not pl_path.exists():
        print(f"  Magnet: {pl_path.name} not found"); return pd.DataFrame()
    pl = pd.read_csv(pl_path, dtype={"cbsa": str})
    if not {"cbsa", "year", "magnet_active"}.issubset(pl.columns):
        print(f"  Magnet: unexpected schema in policy_levers.csv")
        return pd.DataFrame()
    xwalk = pull_cbsa()
    if xwalk.empty:
        print("  Magnet: CBSA crosswalk unavailable"); return pd.DataFrame()
    merged = xwalk[["fips", "cbsa"]].merge(
        pl[["cbsa", "year", "magnet_active"]], on="cbsa", how="inner")
    merged["magnet_hospital_present"] = (
        pd.to_numeric(merged["magnet_active"], errors="coerce")
        .fillna(0).astype(int).clip(0, 1))
    print(f"  Magnet: ok ({merged.fips.nunique()} counties × "
          f"{merged.year.nunique()} years)")
    return merged[["fips", "year", "magnet_hospital_present"]]


# ---------------------------------------------------------------------------
# Bartik IV — county RN-wage instrument
# ---------------------------------------------------------------------------
# Construction (Bartik 1991 / Goldsmith-Pinkham, Sorkin, Swift 2020):
#   IV_{it} = s_{i,base} × (W_t^nat / W_{base}^nat)
# where s_{i,base} is the county's share of total private employment in
# health-care industries (NAICS 622 hospitals + 623 nursing/residential)
# in base_year, and W_t^nat is the national OEWS annual mean wage for
# Registered Nurses (SOC 29-1141). Industry shares are fixed at base_year;
# all time variation comes from the national wage series, satisfying the
# share/shock identification assumptions under the exclusion restriction
# that national nursing wage trends affect county nurse supply only
# through their effect on local nurse wages.
def _qcew_county_share(fips: str, year: int) -> float | None:
    url = f"https://data.bls.gov/cew/data/api/{year}/a/area/{fips}.csv"
    try:
        raw = _cached_get(url, f"qcew_{year}_{fips}.csv")
        d = pd.read_csv(io.StringIO(raw), low_memory=False, dtype=str)
    except Exception:
        return None
    d["industry_code"] = d["industry_code"].astype(str)
    d["own_code"] = d["own_code"].astype(str)
    d["annual_avg_emplvl"] = pd.to_numeric(d["annual_avg_emplvl"],
                                            errors="coerce")
    # own_code 5 = private; industry 10 = total covered
    priv = d[d["own_code"] == "5"]
    nh = priv.loc[priv["industry_code"].isin(["622", "623"]),
                   "annual_avg_emplvl"].sum()
    tot = d.loc[(d["industry_code"] == "10") & (d["own_code"].isin(["0", "5"])),
                "annual_avg_emplvl"].sum()
    return float(nh) / float(tot) if tot and tot > 0 else None


_OEWS_NAT_CACHE: dict[int, pd.DataFrame] = {}


def _oews_national_table(year: int) -> pd.DataFrame | None:
    """Load and cache the national OEWS table for a year (all occupations)."""
    if year in _OEWS_NAT_CACHE:
        return _OEWS_NAT_CACHE[year]
    yy = f"{year % 100:02d}"
    url = f"https://www.bls.gov/oes/special-requests/oesm{yy}nat.zip"
    try:
        raw = _cached_get(url, f"oesm{yy}nat.zip", binary=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            # Prefer the national data workbook (national_M{YYYY}_dl.xlsx)
            # over auxiliary files like field_descriptions.xlsx.
            candidates = [n for n in z.namelist()
                          if n.lower().endswith((".xlsx", ".xls"))]
            preferred = [n for n in candidates
                         if "national" in n.lower() and "_dl" in n.lower()]
            name = (preferred or candidates)[0] if candidates else None
            if not name:
                return None
            with z.open(name) as f:
                nat = pd.read_excel(f, dtype=str)
    except Exception as e:
        print(f"    OEWS nat {year}: FAIL ({e})"); return None
    nat.columns = [c.upper().strip() for c in nat.columns]
    _OEWS_NAT_CACHE[year] = nat
    return nat


def _oews_national_wage(year: int, soc: str) -> float | None:
    """National annual mean wage from OEWS for a given SOC code (e.g.,
    29-1141 = RN; 29-2061 = LPN/LVN)."""
    nat = _oews_national_table(year)
    if nat is None:
        return None
    occ_col  = next((c for c in nat.columns if c == "OCC_CODE"), None)
    wage_col = next((c for c in nat.columns
                     if c.replace("_", "") == "AMEAN"), None)
    if not (occ_col and wage_col):
        return None
    row = nat[nat[occ_col].astype(str) == soc]
    if row.empty:
        return None
    val = str(row[wage_col].iloc[0]).replace(",", "").replace("$", "")
    try:
        return float(val)
    except ValueError:
        return None


def pull_bartik(base_year: int = 2014) -> pd.DataFrame:
    """Construct Bartik IVs for RN and LPN county wages. Industry shares
    are identical for both (NAICS 622+623 employ both occupations); only
    the national wage shock series differs. Returns fips, year,
    init_nursing_emp_share, nat_rn_wage, nat_lpn_wage, bartik_iv (RN),
    bartik_iv_lpn.

    Base year defaults to 2014 — the earliest year with clean per-county
    coverage at the BLS QCEW per-area API endpoint. 2014 is still
    predetermined relative to the post-2018 shortage dynamics the panel
    examines, satisfying the Bartik exogeneity timing requirement."""
    # County base-year industry shares
    spine_fips = sorted(build_spine().fips.unique())
    shares = {}
    for fips in spine_fips:
        s = _qcew_county_share(fips, base_year)
        if s is not None:
            shares[fips] = s
    if not shares:
        print("  Bartik: no QCEW shares pulled"); return pd.DataFrame()
    print(f"  QCEW {base_year}: ok ({len(shares)} of "
          f"{len(spine_fips)} counties)")
    shares_df = pd.DataFrame({"fips": list(shares),
                              "init_nursing_emp_share": list(shares.values())})

    # National wage series — RN (29-1141) and LPN (29-2061)
    occ_series: dict[str, dict[int, float]] = {"rn": {}, "lpn": {}}
    SOC = {"rn": "29-1141", "lpn": "29-2061"}
    for y in YEARS:
        for label, soc in SOC.items():
            w = _oews_national_wage(y, soc)
            if w is not None:
                occ_series[label][y] = w
    for label in ("rn", "lpn"):
        if base_year not in occ_series[label]:
            print(f"  OEWS nat {label.upper()}: missing {base_year} "
                  f"baseline; aborting Bartik")
            return pd.DataFrame()

    nat_df = pd.DataFrame({"year": YEARS})
    nat_df["nat_rn_wage"]  = nat_df["year"].map(occ_series["rn"])
    nat_df["nat_lpn_wage"] = nat_df["year"].map(occ_series["lpn"])
    nat_df["nat_rn_wage_index"]  = (
        nat_df["nat_rn_wage"]  / occ_series["rn"][base_year])
    nat_df["nat_lpn_wage_index"] = (
        nat_df["nat_lpn_wage"] / occ_series["lpn"][base_year])
    yrs_ok = nat_df.dropna(subset=["nat_rn_wage", "nat_lpn_wage"])
    print(f"  OEWS nat: ok ({len(yrs_ok)} years with both RN+LPN)")

    out = (shares_df.assign(_k=1)
           .merge(nat_df.assign(_k=1), on="_k").drop(columns="_k"))
    out["bartik_iv"]     = (out["init_nursing_emp_share"]
                            * out["nat_rn_wage_index"])
    out["bartik_iv_lpn"] = (out["init_nursing_emp_share"]
                            * out["nat_lpn_wage_index"])
    return out[["fips", "year", "init_nursing_emp_share",
                "nat_rn_wage", "nat_lpn_wage",
                "bartik_iv", "bartik_iv_lpn"]]


# ---------------------------------------------------------------------------
# Analytic-panel subset — regression-ready columns
# ---------------------------------------------------------------------------
def _emit_stacked(wide: pd.DataFrame, out_path: Path) -> None:
    """Melt the wide analytic file into a long (stacked) frame with one
    row per (fips, year, nurse_type). Collapses occupation-specific
    columns into own_wage, own_ipeds_per_10k_lag1, own_bartik_iv.

    Use this file for the pooled regression:
        Y_{ijt} = α_i + λ_t + γ·1[j=LPN] + β1·D + β2·own_wage + β3·X + ε
    where own_wage is instrumented by own_bartik_iv.
    """
    occ_pairs = {
        "own_wage":                ("rn_pums_wage",          "lpn_pums_wage"),
        "own_ipeds_per_10k_lag1":  ("ipeds_rn_per_10k_lag1", "ipeds_lpn_per_10k_lag1"),
        "own_bartik_iv":           ("bartik_iv",             "bartik_iv_lpn"),
    }
    shared = [c for c in wide.columns if c not in {
        col for pair in occ_pairs.values() for col in pair}]
    rn  = wide[shared].copy(); rn["nurse_type"]  = "RN"
    lpn = wide[shared].copy(); lpn["nurse_type"] = "LPN"
    for own_col, (rn_col, lpn_col) in occ_pairs.items():
        rn[own_col]  = wide[rn_col]  if rn_col  in wide.columns else pd.NA
        lpn[own_col] = wide[lpn_col] if lpn_col in wide.columns else pd.NA
    stacked = pd.concat([rn, lpn], ignore_index=True).sort_values(
        ["fips", "year", "nurse_type"]).reset_index(drop=True)
    # Order: keys, nurse_type, own_* (the row-varying covariates), shared X
    keys = [c for c in ("fips", "county_name", "year") if c in stacked.columns]
    own_cols = list(occ_pairs.keys())
    rest = [c for c in stacked.columns
            if c not in keys + ["nurse_type"] + own_cols]
    stacked = stacked[keys + ["nurse_type"] + own_cols + rest]
    stacked.to_csv(out_path, index=False)
    xlsx_path = out_path.with_suffix(".xlsx")
    try:
        stacked.to_excel(xlsx_path, index=False, engine="openpyxl")
        print(f"Wrote stacked file {out_path.name} and {xlsx_path.name}: "
              f"{stacked.shape}")
    except Exception as e:
        print(f"Wrote stacked file {out_path}: {stacked.shape}")
        print(f"  (.xlsx skipped — {e})")


def emit_analytic_subset(panel: pd.DataFrame, out_path: Path) -> None:
    """Build the regression-ready analytic CSV from AHRF-sourced columns
    plus IPEDS (training pipeline), CMS NH (LTC capacity), Magnet, and
    Bartik IV.

    All 10 covariates (demand + supply + disadvantage) come from AHRF in
    AHRF mode; nothing depends on the Census ACS API. The 5 ACS-derived
    AHRF fields are: F14083 (pop 65+), F15474 (% <65 uninsured), F15409/13
    (disability), F13223 (persons in poverty), F14452/F14440 (bachelors+).
    """
    p = panel.copy().sort_values(["fips", "year"])

    # Resolve merge collisions: pandas auto-suffixes columns when AHRF and
    # ACS produce same-named columns (e.g., pop_65plus → pop_65plus_x/_y).
    # Coalesce them back to the canonical name, preferring AHRF (_y).
    for base in ("pop_65plus", "pop_total"):
        if base not in p.columns:
            y_col = f"{base}_y"; x_col = f"{base}_x"
            if y_col in p.columns or x_col in p.columns:
                p[base] = pd.to_numeric(p.get(y_col), errors="coerce")
                if x_col in p.columns:
                    p[base] = p[base].fillna(pd.to_numeric(p[x_col],
                                                            errors="coerce"))

    def _coalesce(*cols):
        """Return first non-null Series across columns (skipping missing cols)."""
        present = [c for c in cols if c in p.columns]
        if not present:
            return None
        out = pd.to_numeric(p[present[0]], errors="coerce")
        for c in present[1:]:
            out = out.fillna(pd.to_numeric(p[c], errors="coerce"))
        return out

    # --- derived demand vector ---
    # share_65plus: prefer AHRF pop_65plus / popn_est; fall back to ACS pct_65plus
    if {"pop_65plus", "popn_est"}.issubset(p.columns):
        p65 = pd.to_numeric(p["pop_65plus"], errors="coerce")
        pop = pd.to_numeric(p["popn_est"], errors="coerce")
        p["share_65plus_ahrf"] = (p65 / pop * 100).round(2)
    p["share_65plus"] = _coalesce("share_65plus_ahrf", "pct_65plus")
    # uninsured_rate: prefer ACS pct_uninsured (B27001) — full panel coverage;
    # AHRF pct_uninsured_under65 (F15474) is sparse.
    p["uninsured_rate"] = _coalesce("pct_uninsured", "pct_uninsured_under65")
    # disability_rate: prefer ACS pct_disability (C18120, new) — full panel
    # coverage 2010-2023; AHRF disab_with/(disab_with+disab_without) only
    # 2010-2016, 2020-2023.
    if {"disab_with", "disab_without"}.issubset(p.columns):
        dw = pd.to_numeric(p["disab_with"], errors="coerce")
        dn = pd.to_numeric(p["disab_without"], errors="coerce")
        p["disability_rate_ahrf"] = (dw / (dw + dn) * 100).round(2)
    p["disability_rate"] = _coalesce("pct_disability", "disability_rate_ahrf")

    # --- derived supply vector ---
    if {"hosp_beds", "popn_est"}.issubset(p.columns):
        hb = pd.to_numeric(p["hosp_beds"], errors="coerce")
        pop = pd.to_numeric(p["popn_est"], errors="coerce")
        p["hosp_beds_per_1k"] = (hb / pop * 1000).round(2)
    # IPEDS completions: counties without nursing schools have zero
    # completions, not unknown — fill NaN with 0 before normalizing.
    # Normalize to per-10k residents (matches per-capita outcome), then
    # take a 1-year lag.
    if {"ipeds_completions_rn", "popn_est"}.issubset(p.columns):
        pop = pd.to_numeric(p["popn_est"], errors="coerce")
        comp = pd.to_numeric(p["ipeds_completions_rn"], errors="coerce").fillna(0)
        p["ipeds_rn_per_10k"] = comp / pop * 10000
        p["ipeds_rn_per_10k_lag1"] = (
            p.groupby("fips")["ipeds_rn_per_10k"].shift(1))
    if {"ipeds_completions_lpn", "popn_est"}.issubset(p.columns):
        pop = pd.to_numeric(p["popn_est"], errors="coerce")
        comp = pd.to_numeric(p["ipeds_completions_lpn"], errors="coerce").fillna(0)
        p["ipeds_lpn_per_10k"] = comp / pop * 10000
        p["ipeds_lpn_per_10k_lag1"] = (
            p.groupby("fips")["ipeds_lpn_per_10k"].shift(1))
    if {"nh_beds_total", "pop_65plus"}.issubset(p.columns):
        nh = pd.to_numeric(p["nh_beds_total"], errors="coerce")
        p65 = pd.to_numeric(p["pop_65plus"], errors="coerce")
        p["nh_beds_per_65plus"] = (nh / p65 * 1000).round(2)

    # Magnet flag: counties not in the policy_levers × CBSA crosswalk have no
    # Magnet hospital — code those as 0 rather than NaN.
    if "magnet_hospital_present" in p.columns:
        p["magnet_hospital_present"] = (
            p["magnet_hospital_present"].fillna(0).astype(int))

    # --- derived disadvantage vector ---
    # poverty_rate: prefer ACS poverty_rate (B17001) — full panel coverage;
    # AHRF persons_in_poverty/popn_est missing 2010.
    if {"persons_in_poverty", "popn_est"}.issubset(p.columns):
        pov = pd.to_numeric(p["persons_in_poverty"], errors="coerce")
        pop = pd.to_numeric(p["popn_est"], errors="coerce")
        p["poverty_rate_ahrf"] = (pov / pop * 100).round(2)
    # If ACS column is already named "poverty_rate", that's perfect.
    p["poverty_rate"] = _coalesce("poverty_rate", "poverty_rate_ahrf")
    # bachelors_plus_share: prefer ACS pct_bachelors_plus (B15003/B15002) —
    # full panel coverage; AHRF pers_25plus_4yr_coll/pers_25plus missing
    # 2017-2019.
    if {"pers_25plus_4yr_coll", "pers_25plus"}.issubset(p.columns):
        ba = pd.to_numeric(p["pers_25plus_4yr_coll"], errors="coerce")
        den = pd.to_numeric(p["pers_25plus"], errors="coerce")
        p["bachelors_plus_share_ahrf"] = (ba / den * 100).round(2)
    p["bachelors_plus_share"] = _coalesce("pct_bachelors_plus",
                                            "bachelors_plus_share_ahrf")

    desired = [
        # demand
        "share_65plus", "uninsured_rate", "disability_rate",
        # supply — RN-specific
        "rn_pums_wage", "ipeds_rn_per_10k_lag1",
        # supply — LPN-specific
        "lpn_pums_wage", "ipeds_lpn_per_10k_lag1",
        # supply — shared
        "hpsa_prim_care", "hosp_beds_per_1k",
        "nh_beds_per_65plus", "magnet_hospital_present",
        # disadvantage
        "poverty_rate", "bachelors_plus_share",
        # IVs
        "bartik_iv", "bartik_iv_lpn",
    ]
    keys = [c for c in ("fips", "county_name", "year") if c in p.columns]
    keep = keys + [c for c in desired if c in p.columns]
    missing = [c for c in desired if c not in p.columns]
    sub = p[keep].copy()
    sub.to_csv(out_path, index=False)
    xlsx_path = out_path.with_suffix(".xlsx")
    try:
        sub.to_excel(xlsx_path, index=False, engine="openpyxl")
        print(f"\nWrote analytic subset {out_path} and {xlsx_path.name}: "
              f"{sub.shape}")
    except Exception as e:
        print(f"\nWrote analytic subset {out_path}: {sub.shape}")
        print(f"  (.xlsx skipped — {e})")

    # Stacked long-format file for the pooled RN+LPN regression with a
    # nurse_type dummy. Each county-year contributes 2 rows; occupation-
    # specific columns collapse to own_* using the row's nurse_type.
    _emit_stacked(sub, out_path.parent / "analytic_panel_county_stacked.csv")
    if missing:
        print(f"  Columns NOT in panel (left out): {missing}")
        print(f"  In AHRF mode these typically derive from the AHRF parse — "
              f"check parse_ahrf_asc.py DESCRIPTION_MAP coverage in the "
              f"AHRF release used.")
    miss = sub.isna().mean().mul(100).round(1).sort_values(ascending=False)
    print("Analytic missingness:")
    print(miss.to_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
# Supplemental sources that complement (not duplicate) AHRF when AHRF is
# present. These are the sources whose detail/granularity isn't in AHRF.
SUPPLEMENT_SOURCES = {
    "acs":     pull_acs,             # detailed demographic / housing-burden / commute brackets
    "ipeds":   pull_ipeds,           # nursing completions by CIP
    "chr":     pull_chr,             # health-outcome composites (manual cache)
    "cms_nh":  pull_cms_nh,          # nursing-home bed capacity (time-invariant)
    "magnet":  pull_magnet_county,   # ANCC Magnet (MSA → county via CBSA)
    "bartik":  pull_bartik,          # Bartik IV for RN wages
    "pums":    pull_pums_wages,      # ACS PUMS county RN/LPN wages (2012–2021)
}

# Sources used only when AHRF is NOT available — AHRF covers all of these.
FALLBACK_SOURCES = {
    "ers":   pull_ers,
    "gaz":   pull_gazetteer,
    "cbsa":  pull_cbsa,
    "hpsa":  pull_hpsa,
}

ALL_SOURCES = {**SUPPLEMENT_SOURCES, **FALLBACK_SOURCES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated subset of supplements: "
                    + ",".join(SUPPLEMENT_SOURCES.keys())
                    + " (plus fallbacks when AHRF absent: "
                    + ",".join(FALLBACK_SOURCES.keys()) + ")")
    ap.add_argument("--no-ahrf", action="store_true",
                    help="ignore AHRF files even if present; use fallback "
                         "API sources for facility/HPSA/CBSA/typology data")
    ap.add_argument("--preserve-manual", action="store_true",
                    help="merge nurse-count columns from existing "
                         "full-in-progress.csv")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--analytic-subset", action="store_true",
                    help="after merge, also emit analytic_panel_county.csv "
                         "with the regression-ready 11-variable subset + "
                         "Bartik IV")
    args = ap.parse_args()

    global CENSUS_KEY
    CENSUS_KEY = get_census_key()

    # ---- Stage 1: decide spine ----
    ahrf_present = (not args.no_ahrf) and bool(ahrf_files_available())
    print("=" * 70)
    if ahrf_present:
        print(f"AHRF mode — {len(ahrf_files_available())} releases found in "
              f"data/cache/. AHRF drives the spine; ACS/IPEDS/CHR supplement.")
    else:
        reason = ("--no-ahrf" if args.no_ahrf
                  else "no AHRF .asc files in data/cache/")
        print(f"Fallback mode ({reason}). Census 2010–2023 spine; "
              f"facility/HPSA/CBSA/typology data from individual APIs.")
    print("=" * 70)

    # ---- Stage 2: build spine ----
    if ahrf_present:
        print("\nParsing AHRF releases…")
        ahrf = build_ahrf_spine()
        if ahrf.empty:
            raise SystemExit("AHRF parsing produced no data — see errors above.")
        # county_name from any release row; AHRF carries cnty_name_st_abbrev
        panel = ahrf
        active_supplements = list(SUPPLEMENT_SOURCES.keys())
        time_invariant = {"cms_nh"}
    else:
        print("\nBuilding Census spine (2010–2023)…")
        panel = build_spine()
        print(f"  spine: {panel.shape}")
        active_supplements = list(SUPPLEMENT_SOURCES.keys()) + list(FALLBACK_SOURCES.keys())
        time_invariant = {"ers", "gaz", "cbsa", "hpsa", "cms_nh"}

    # ---- Stage 3: validate --only against the active source set ----
    if args.only:
        requested = args.only.split(",")
        bad = [s for s in requested if s not in ALL_SOURCES]
        if bad:
            raise SystemExit(f"unknown sources: {bad}")
        skipped_fallbacks = [s for s in requested
                             if ahrf_present and s in FALLBACK_SOURCES]
        if skipped_fallbacks:
            print(f"\n[note] In AHRF mode, fallback sources are redundant; "
                  f"ignoring: {skipped_fallbacks}")
        todo = [s for s in requested if s in active_supplements]
    else:
        todo = active_supplements

    # ---- Stage 4: merge supplements ----
    for s in todo:
        print(f"\nPulling {s.upper()}…")
        df = ALL_SOURCES[s]()
        if df.empty:
            print(f"  {s}: nothing to merge"); continue
        on = ["fips"] if s in time_invariant else ["fips", "year"]
        panel = panel.merge(df, on=on, how="left")

    # popn_densty derivable in fallback mode (AHRF carries its own)
    if (not ahrf_present
            and {"pop_total", "land_area_mi2"}.issubset(panel.columns)):
        panel["popn_densty_per_squr_mi"] = (
            panel["pop_total"] / panel["land_area_mi2"]).round(2)

    # ---- Stage 5: manual nurse columns ----
    if args.preserve_manual and EXISTING.exists():
        old = pd.read_csv(EXISTING, dtype={"fips": str})
        keep = ["fips", "year"] + [c for c in MANUAL_NURSE_COLS if c in old.columns]
        panel = panel.merge(old[keep], on=["fips", "year"], how="left")
        print(f"\nMerged manual nurse cols: {keep[2:]}")
    else:
        for c in MANUAL_NURSE_COLS:
            panel[c] = pd.NA

    sort_keys = (["fips", "year"] if "county_name" not in panel.columns
                 else ["county_name", "year"])
    panel = panel.sort_values(sort_keys).reset_index(drop=True)
    panel.to_csv(args.out, index=False)
    print(f"\nWrote {args.out}: {panel.shape}")
    print(f"Year range: {int(panel.year.min())}–{int(panel.year.max())}, "
          f"{panel.fips.nunique()} counties")
    print("Missingness (top 15):")
    miss = panel.isna().mean().mul(100).round(1).sort_values(ascending=False)
    print(miss.head(15).to_string())

    if args.analytic_subset:
        emit_analytic_subset(panel, ROOT / "analytic_panel_county.csv")


if __name__ == "__main__":
    main()
