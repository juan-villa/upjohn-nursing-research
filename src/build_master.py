"""
build_master.py
---------------
Assembles a single master MSA x year panel for the Michigan RN shortage study.

Spine: oews_michigan_rn_panel_clean.csv (18 MSAs / nonmetro areas, 2015-2024).

Variables added:
  Outcome / wage:
    h_median_real        - real median hourly wage (CPI-U deflated, 2024 USD)
    h_median_growth      - YoY % change in real median wage  [revealed shortage proxy]

  Stress regressors:
    case_mix_index       - CMS Medicare CMI, MSA-weighted by hospital discharges
    covid_hosp_per_100k  - peak weekly COVID hosp per 100k (HHS Protect, 0 pre-2020)

  Wage instrument:
    h_median_loo         - leave-one-out mean RN wage across other MI MSAs (year t)

  Controls (ACS 1-year, MSA level):
    pop_total
    pct_65plus
    pct_uninsured
    median_hh_income
    pct_female_lfp

The script writes:
    master_panel.csv   - one row per (msa, year), all variables wide
    master_panel.log   - per-source summary of what merged and what didn't

Required environment:
    CENSUS_API_KEY  - free at https://api.census.gov/data/key_signup.html
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
import numpy as np
import requests

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PANEL_IN = ROOT / "oews_michigan_rn_panel_clean.csv"
PANEL_OUT = ROOT / "master_panel.csv"
LOG_OUT = ROOT / "master_panel.log"

YEARS = list(range(2011, 2025))
CENSUS_KEY = os.environ.get("CENSUS_API_KEY")

HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}

# Hand-built crosswalk: cleaned MSA name -> Census CBSA code
# (Nonmetro areas have no CBSA -> ACS will be NaN; controls come from
#  county-level rollups or are dropped from the regression sample.)
CBSA = {
    "Ann Arbor, MI": "11460",
    "Battle Creek, MI": "12980",
    "Bay City, MI": "13020",
    "Detroit-Warren-Dearborn, MI": "19820",
    "Flint, MI": "22420",
    "Grand Rapids-Wyoming-Kentwood, MI": "24340",
    "Jackson, MI": "27100",
    "Kalamazoo-Portage, MI": "28020",
    "Lansing-East Lansing, MI": "29620",
    "Midland, MI": "33220",
    "Monroe, MI": "33780",
    "Muskegon-Norton Shores, MI": "34740",
    "Niles, MI": "35660",
    "Saginaw, MI": "40980",
}

LOG_LINES = []


def log(msg):
    print(msg)
    LOG_LINES.append(msg)


# ---------------------------------------------------------------------------
# 1. Spine
# ---------------------------------------------------------------------------

def load_spine():
    df = pd.read_csv(PANEL_IN)
    log(f"[spine] {len(df)} rows, {df['area_title'].nunique()} areas")
    return df


# ---------------------------------------------------------------------------
# 2. Real wages + leave-one-out instrument
# ---------------------------------------------------------------------------

# CPI-U annual averages (FRED CPIAUCSL, 1982-84=100). Hard-coded to avoid
# another API dependency for 10 numbers.
CPI_U = {
    2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736,
    2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107,
    2019: 255.657, 2020: 258.811, 2021: 270.970, 2022: 292.655,
    2023: 304.702, 2024: 313.689,
}

def add_real_wages_and_iv(df):
    base = CPI_U[2024]
    df["cpi_u"] = df["year"].map(CPI_U)
    df["h_median_real"] = df["h_median"] * (base / df["cpi_u"])

    df = df.sort_values(["area_title", "year"])
    df["h_median_growth"] = (df.groupby("area_title")["h_median_real"]
                               .pct_change() * 100)

    # leave-one-out mean wage across MI MSAs in same year
    yr_mean = df.groupby("year")["h_median_real"].transform("mean")
    yr_count = df.groupby("year")["h_median_real"].transform("count")
    df["h_median_loo"] = ((yr_mean * yr_count - df["h_median_real"])
                          / (yr_count - 1))
    log(f"[wage] real wages + LOO instrument computed")
    return df


# ---------------------------------------------------------------------------
# 3. ACS controls
# ---------------------------------------------------------------------------

def pull_acs_year(year, cbsa_codes):
    """
    ACS 1-year MSA estimates. 2020 1-year was not released — we skip it.

    Uses DETAIL tables (stable variable codes) for all primary controls:
      B01001_001E              = total population
      B01001_020E..025E        = males 65+    (6 buckets)
      B01001_044E..049E        = females 65+  (6 buckets)
      B19013_001E              = median household income
      B25064_001E              = median gross rent (housing cost control)
      B23025_002E              = population 16+ in labor force
      B23025_003E              = civilian labor force
      B23025_005E              = unemployed
      B15003_001E              = population 25+
      B15003_022E..025E        = bachelor's, master's, professional, doctorate
      B08303_001E              = workers 16+ with reported travel time
      B08303_008E..013E        = workers w/ 30+ min commute (six buckets)
      B08136_001E              = aggregate travel time to work (minutes)
      B08101_001E              = workers 16+ (denom for mean commute)
    Subject table (stable since 2010):
      S2701_C05_001E           = pct uninsured (civilian noninstitutionalized)
    """
    if year == 2020:
        return pd.DataFrame()

    age_male = [f"B01001_{i:03d}E" for i in range(20, 26)]
    age_female = [f"B01001_{i:03d}E" for i in range(44, 50)]
    edu_high = [f"B15003_{i:03d}E" for i in range(22, 26)]
    commute_30plus = [f"B08303_{i:03d}E" for i in range(8, 14)]
    commute_agg = ["B08136_001E", "B08101_001E"]
    detail_vars = (["B01001_001E"] + age_male + age_female
                   + ["B19013_001E", "B25064_001E",
                      "B23025_002E", "B23025_003E", "B23025_005E",
                      "B15003_001E"] + edu_high
                   + ["B08303_001E"] + commute_30plus + commute_agg)

    base = "https://api.census.gov/data"
    geo = ("metropolitan%20statistical%20area/"
           "micropolitan%20statistical%20area:*")

    def _fetch(path, vars_):
        url = f"{base}/{year}/acs/{path}?get={','.join(vars_)}&for={geo}"
        if CENSUS_KEY:
            url += f"&key={CENSUS_KEY}"
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            rows = r.json()
            return pd.DataFrame(rows[1:], columns=rows[0])
        except requests.RequestException as e:
            log(f"[acs {year} {path}] failed: {e}")
            return pd.DataFrame()

    detail = _fetch("acs1", detail_vars)
    subj = _fetch("acs1/subject", ["S2701_C05_001E"])

    if detail.empty:
        return pd.DataFrame()

    # rename geography column
    msa_col = [c for c in detail.columns
               if "metropolitan" in c.lower()][0]
    detail = detail.rename(columns={msa_col: "cbsa"})
    detail["cbsa"] = detail["cbsa"].astype(str)
    detail = detail[detail["cbsa"].isin(cbsa_codes)].copy()

    # numeric
    for c in detail_vars:
        detail[c] = pd.to_numeric(detail[c], errors="coerce")

    detail["pop_total"] = detail["B01001_001E"]
    detail["pop_65plus"] = detail[age_male + age_female].sum(axis=1)
    detail["pct_65plus"] = (detail["pop_65plus"] / detail["pop_total"] * 100).round(2)
    # Age 75+ buckets: M 75-79, M 80-84, M 85+ (023-025) + F same (047-049)
    age75 = ["B01001_023E", "B01001_024E", "B01001_025E",
            "B01001_047E", "B01001_048E", "B01001_049E"]
    detail["pop_75plus"] = detail[age75].sum(axis=1)
    detail["pct_75plus"] = (detail["pop_75plus"] / detail["pop_total"] * 100).round(2)
    detail["median_hh_income"] = detail["B19013_001E"]
    detail["median_gross_rent"] = detail["B25064_001E"]
    detail["unemployment_rate"] = (detail["B23025_005E"]
                                   / detail["B23025_003E"] * 100).round(2)
    detail["lfp_rate"] = (detail["B23025_002E"]
                          / detail["pop_total"] * 100).round(2)
    detail["pct_bachelors_plus"] = (detail[edu_high].sum(axis=1)
                                    / detail["B15003_001E"] * 100).round(2)
    detail["pct_commute_30plus"] = (detail[commute_30plus].sum(axis=1)
                                     / detail["B08303_001E"] * 100).round(2)
    detail["mean_commute_minutes"] = (detail["B08136_001E"]
                                       / detail["B08101_001E"]).round(2)
    detail["year"] = year

    if not subj.empty:
        subj_col = [c for c in subj.columns
                    if "metropolitan" in c.lower()][0]
        subj = subj.rename(columns={subj_col: "cbsa",
                                     "S2701_C05_001E": "pct_uninsured"})
        subj["cbsa"] = subj["cbsa"].astype(str)
        subj["pct_uninsured"] = pd.to_numeric(subj["pct_uninsured"], errors="coerce")
        detail = detail.merge(subj[["cbsa", "pct_uninsured"]],
                              on="cbsa", how="left")
    else:
        detail["pct_uninsured"] = np.nan

    return detail[["cbsa", "year", "pop_total", "pct_65plus", "pct_75plus",
                   "pct_uninsured", "median_hh_income",
                   "median_gross_rent", "unemployment_rate",
                   "lfp_rate", "pct_bachelors_plus",
                   "pct_commute_30plus", "mean_commute_minutes"]]


def add_acs(df):
    df["cbsa"] = df["area_title"].map(CBSA)
    if not CENSUS_KEY:
        log("[acs] CENSUS_API_KEY not set — using unauthenticated calls "
            "(rate limited, may be slow)")

    cbsa_codes = set(CBSA.values())
    frames = []
    for y in YEARS:
        f = pull_acs_year(y, cbsa_codes)
        if not f.empty:
            frames.append(f)
            log(f"[acs {y}] {len(f)} MSAs")
        time.sleep(0.5)

    acs_cols = ["pop_total", "pct_65plus", "pct_75plus", "pct_uninsured",
                "median_hh_income", "median_gross_rent",
                "unemployment_rate", "lfp_rate", "pct_bachelors_plus",
                "pct_commute_30plus", "mean_commute_minutes"]
    if not frames:
        log("[acs] no data pulled")
        for c in acs_cols:
            df[c] = np.nan
        return df

    acs = pd.concat(frames, ignore_index=True)
    df = df.merge(acs, on=["cbsa", "year"], how="left")
    return df


# ---------------------------------------------------------------------------
# 4. COVID hospitalizations (HHS Protect)
# ---------------------------------------------------------------------------

def add_covid_hospitalizations(df):
    """
    MSA × year COVID hospitalization stress.

    Pulled from HHS Protect facility-level data (anag-cw7u), aggregated to
    MSA via county FIPS, normalized per 100k pop. Both annual peak and
    average weekly rates retained. Pre-2020 = 0.
    """
    cov_path = ROOT / "data" / "processed" / "covid_msa_year.csv"
    if not cov_path.exists():
        log("[covid] processed/covid_msa_year.csv missing — run "
            "scripts/pulls/hhs_covid.py")
        df["covid_peak_per_100k"] = np.nan
        df["covid_avg_per_100k"] = np.nan
        return df
    cov = pd.read_csv(cov_path, dtype={"cbsa": str})
    df = df.merge(cov[["cbsa", "year", "covid_peak_per_100k",
                       "covid_avg_per_100k"]],
                  on=["cbsa", "year"], how="left")
    log("[covid] merged MSA-level COVID hospitalization peaks")
    return df


# ---------------------------------------------------------------------------
# 5. CMS Case Mix Index
# ---------------------------------------------------------------------------

def add_case_mix_index(df):
    """
    CMS publishes an annual IPPS Impact File listing every PPS hospital
    with its CMI and Medicare discharges. URL pattern is unstable across
    years, so this function expects the files to already be downloaded
    into data/cms_ipps/{year}.csv with columns:
        provider_id, state, msa_cbsa, cmi, total_discharges
    If the directory is empty, the column is filled with NaN.
    """
    cms_dir = ROOT / "data" / "cms_ipps"
    if not cms_dir.exists():
        log("[cmi] data/cms_ipps/ missing — column left NaN")
        df["case_mix_index"] = np.nan
        return df

    frames = []
    for y in YEARS:
        f = cms_dir / f"{y}.csv"
        if not f.exists():
            continue
        h = pd.read_csv(f)
        # discharge-weighted CMI by MSA
        agg = (h.groupby("msa_cbsa")
                 .apply(lambda x: np.average(x["cmi"],
                                             weights=x["total_discharges"]))
                 .rename("case_mix_index").reset_index())
        agg["year"] = y
        agg["cbsa"] = agg["msa_cbsa"].astype(str)
        frames.append(agg[["cbsa", "year", "case_mix_index"]])
        log(f"[cmi {y}] {len(agg)} MSAs")

    if not frames:
        log("[cmi] no CMS files found")
        df["case_mix_index"] = np.nan
        return df

    cmi = pd.concat(frames, ignore_index=True)
    df = df.merge(cmi, on=["cbsa", "year"], how="left")
    return df


# ---------------------------------------------------------------------------
# 6. Final cleanup
# ---------------------------------------------------------------------------

def finalize(df):
    # MSA-only sample: drop nonmetro/unmapped areas
    n_before = len(df)
    df = df[df["cbsa"].notna()].copy()
    log(f"\n[filter] dropped {n_before - len(df)} non-MSA rows "
        f"(nonmetro areas without CBSA)")

    # Also drop rows where OEWS wage outcome is missing — they're not usable
    n_before = len(df)
    df = df.dropna(subset=["h_median_real"]).copy()
    log(f"[filter] dropped {n_before - len(df)} rows with no OEWS wage")

    keep_front = [
        # identifiers
        "year", "area_id", "area_title", "cbsa",
        # OEWS outcome / wage
        "tot_emp", "emp_prse", "loc_quotient",
        "h_median", "h_median_real", "h_median_growth", "h_median_loo",
        # stress (case_mix_index dropped — requires CMS IPPS files not pulled)
        "covid_peak_per_100k", "covid_avg_per_100k",
        # primary shortage outcome from HCRIS
        "contract_labor_share", "n_hospitals_reporting",
        # demographic / demand controls
        "pop_total", "pct_65plus", "pct_75plus", "pct_uninsured",
        # demand-weighted RN density (age-standardized)
        "effective_pop", "rn_per_1k_raw", "rn_per_1k_adj",
        # chronic disease (PLACES, MSA-aggregated, time-invariant)
        "diabetes_pct", "hypertension_pct", "mental_distress_pct",
        "copd_pct", "obesity_pct",
        # economic controls
        "median_hh_income", "median_gross_rent",
        "unemployment_rate", "lfp_rate", "pct_bachelors_plus",
        "pct_commute_30plus", "mean_commute_minutes",
        # supply-side
        "hospital_count", "hospital_beds", "beds_per_100k",
        # policy-lever exposure — only Magnet retained as a usable lever.
        # Lorna Breen and MIHEF grants have too few recipients (5-7 MSAs)
        # to support quantitative inference; available in policy_levers.csv
        # if needed for descriptive context.
        "magnet_hospitals", "magnet_active",
    ]
    keep_front = [c for c in keep_front if c in df.columns]
    df = df[keep_front].sort_values(["area_title", "year"]).reset_index(drop=True)
    df.to_csv(PANEL_OUT, index=False)
    log(f"\n[done] wrote {PANEL_OUT}: {df.shape}")
    log(f"       {df['area_title'].nunique()} MSAs, "
        f"{df['year'].min()}-{df['year'].max()}")

    # Coverage report
    log("\nNon-null counts by variable:")
    for c in keep_front:
        if c in df.columns:
            pct = df[c].notna().mean() * 100
            log(f"  {c:<25} {df[c].notna().sum():>4} / {len(df)}  "
                f"({pct:5.1f}%)")

    # Per-MSA year coverage
    log("\nYears per MSA:")
    for area, sub in df.groupby("area_title"):
        log(f"  {area:<40} {sub['year'].min()}-{sub['year'].max()} "
            f"(n={len(sub)})")

    LOG_OUT.write_text("\n".join(LOG_LINES))


def add_policy_levers(df):
    """Merge in MSA-level policy exposure variables from policy_levers.csv."""
    lev_path = ROOT / "policy_levers.csv"
    if not lev_path.exists():
        log("[policy] policy_levers.csv missing — run scripts/policy_levers.py")
        for c in ["magnet_hospitals", "magnet_active",
                  "lorna_breen_count", "lorna_breen_recipient",
                  "mihef_workforce_grants", "mihef_recipient"]:
            df[c] = np.nan
        return df
    lev = pd.read_csv(lev_path, dtype={"cbsa": str})
    df = df.merge(lev.drop(columns=["area_title"]),
                  on=["cbsa", "year"], how="left")
    log(f"[policy] merged {len(lev)} policy-exposure rows")
    return df


def add_cdc_places(df):
    """Merge MSA chronic-disease prevalence (time-invariant) from PLACES."""
    p = ROOT / "data" / "processed" / "cdc_places_msa.csv"
    if not p.exists():
        log("[places] cdc_places_msa.csv missing — run scripts.pulls.cdc_places")
        for c in ["diabetes_pct", "hypertension_pct", "mental_distress_pct",
                  "copd_pct", "obesity_pct"]:
            df[c] = np.nan
        return df
    pl = pd.read_csv(p, dtype={"cbsa": str})
    df = df.merge(pl, on="cbsa", how="left")
    log("[places] merged CDC PLACES chronic disease prevalence")
    return df


def add_demand_weighted_ratios(df):
    """
    Age-weighted RN-per-1,000-population ratios.

    Standard indirect age standardization: weight elderly residents by their
    higher hospital-utilization intensity. Weights of (1, 2, 4) correspond
    roughly to HCUP/NIS discharge-rate ratios for age 18-64 : 65-74 : 75+.

    Outputs:
      rn_per_1k_raw      — naive RN headcount per 1,000 residents
      rn_per_1k_adj      — same but with demand-weighted denominator
      effective_pop      — weighted denominator (residents-equivalent)
    """
    df["pop_65plus_n"] = df["pop_total"] * df["pct_65plus"] / 100
    df["pop_75plus_n"] = df["pop_total"] * df["pct_75plus"] / 100
    df["pop_under65"]  = df["pop_total"]    - df["pop_65plus_n"]
    df["pop_65to74"]   = df["pop_65plus_n"] - df["pop_75plus_n"]
    df["effective_pop"] = (df["pop_under65"]
                            + 2 * df["pop_65to74"]
                            + 4 * df["pop_75plus_n"])
    df["rn_per_1k_raw"] = (df["tot_emp"] / df["pop_total"] * 1000).round(2)
    df["rn_per_1k_adj"] = (df["tot_emp"] / df["effective_pop"] * 1000).round(2)
    # drop helper columns
    df = df.drop(columns=["pop_65plus_n", "pop_75plus_n",
                          "pop_under65", "pop_65to74"])
    log("[demand-weighted] computed rn_per_1k_raw and rn_per_1k_adj "
        "(weights 1, 2, 4 for <65 / 65-74 / 75+)")
    return df


def add_hospital_supply(df):
    """
    MSA-level hospital supply controls:
      hospital_count       — count of HCRIS-reporting hospitals in MSA-year
      hospital_beds        — total beds across reporting hospitals
      beds_per_100k        — beds normalized by MSA population
    Derived from hcris_hospital.csv + mi_hospitals.csv crosswalk.
    """
    hosp = ROOT / "data" / "processed" / "mi_hospitals.csv"
    hcris_h = ROOT / "data" / "processed" / "hcris_hospital.csv"
    if not (hosp.exists() and hcris_h.exists()):
        log("[supply] hospital files missing — run hospital pulls first")
        for c in ["hospital_count", "hospital_beds", "beds_per_100k"]:
            df[c] = np.nan
        return df
    meta = pd.read_csv(hosp, dtype={"facility_id": str, "cbsa": str})
    hh = pd.read_csv(hcris_h, dtype={"facility_id": str})
    hh = hh.rename(columns={"fy_end_year": "year"})
    merged = hh.merge(meta[["facility_id", "cbsa"]], on="facility_id",
                      how="left").dropna(subset=["cbsa"])
    agg = (merged.groupby(["cbsa", "year"])
                  .agg(hospital_count=("facility_id", "nunique"),
                       hospital_beds=("beds_available", "sum"))
                  .reset_index())
    df = df.merge(agg, on=["cbsa", "year"], how="left")
    df["beds_per_100k"] = (df["hospital_beds"] / df["pop_total"]
                            * 100_000).round(1)
    log(f"[supply] merged hospital count + bed capacity for "
        f"{agg['cbsa'].nunique()} MSAs")
    return df


def add_hcris_contract_labor(df):
    """Merge MSA-level contract-labor share from HCRIS cost reports."""
    hc_path = ROOT / "data" / "processed" / "hcris_contract_labor.csv"
    if not hc_path.exists():
        log("[hcris] processed/hcris_contract_labor.csv missing — run "
            "scripts/pulls/hcris.py")
        for c in ["contract_labor_share", "n_hospitals_reporting"]:
            df[c] = np.nan
        return df
    hc = pd.read_csv(hc_path, dtype={"cbsa": str})
    hc = hc[["cbsa", "year", "contract_labor_share", "n_hospitals"]].rename(
        columns={"n_hospitals": "n_hospitals_reporting"})
    # Some MSAs have multiple FY-end years per calendar year — keep mean
    hc = (hc.groupby(["cbsa", "year"])
            .agg({"contract_labor_share": "mean",
                  "n_hospitals_reporting": "sum"})
            .reset_index())
    df = df.merge(hc, on=["cbsa", "year"], how="left")
    log(f"[hcris] merged contract labor share for {hc['cbsa'].nunique()} MSAs")
    return df


def main():
    df = load_spine()
    df = add_real_wages_and_iv(df)
    df = add_acs(df)
    df = add_covid_hospitalizations(df)
    df = add_case_mix_index(df)
    df = add_policy_levers(df)
    df = add_hcris_contract_labor(df)
    df = add_cdc_places(df)
    df = add_hospital_supply(df)
    df = add_demand_weighted_ratios(df)
    finalize(df)


if __name__ == "__main__":
    main()
