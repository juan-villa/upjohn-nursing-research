"""
build_county.py — build county-master.csv (Michigan counties × year).

Pulls ACS 5-year (all controls), BLS QCEW hospital industry (NAICS 622),
CDC PLACES chronic disease prevalence, and applies state-level COVID stress.

Output: county-master.csv

Requires environment variable CENSUS_API_KEY (free signup at
https://api.census.gov/data/key_signup.html).
"""
import os
import io
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "county-master.csv"

YEARS = list(range(2015, 2025))
STATE_FIPS = "26"  # Michigan
HEADERS = {"User-Agent": "GSE580-Research juanmvilla09@gmail.com"}
CENSUS_KEY = os.environ.get("CENSUS_API_KEY")

CPI_U = {
    2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736,
    2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107,
    2019: 255.657, 2020: 258.811, 2021: 270.970, 2022: 292.655,
    2023: 304.702, 2024: 313.689,
}

MI_COVID = {2015: 0, 2016: 0, 2017: 0, 2018: 0, 2019: 0,
            2020: 18.5, 2021: 14.2, 2022: 12.0, 2023: 3.1, 2024: 1.8}


def _acs_url(year, vars_):
    base = "https://api.census.gov/data"
    url = (f"{base}/{year}/acs/acs5?get={','.join(vars_)}"
           f"&for=county:*&in=state:{STATE_FIPS}")
    if CENSUS_KEY:
        url += f"&key={CENSUS_KEY}"
    return url


def get_counties():
    url = _acs_url(2022, ["NAME"])
    r = requests.get(url, timeout=30).json()
    c = pd.DataFrame(r[1:], columns=r[0])
    c["fips"] = c["state"] + c["county"]
    c["county_name"] = c["NAME"].str.replace(" County, Michigan", "",
                                              regex=False)
    return c[["fips", "county_name"]].sort_values("fips").reset_index(drop=True)


def pull_acs5_year(year):
    age_m = [f"B01001_{i:03d}E" for i in range(20, 26)]
    age_f = [f"B01001_{i:03d}E" for i in range(44, 50)]
    edu_high = [f"B15003_{i:03d}E" for i in range(22, 26)]
    uninsured_cols = [f"B27001_{i:03d}E" for i in
                      [5, 8, 11, 14, 17, 20, 23, 26, 29,
                       33, 36, 39, 42, 45, 48, 51, 54, 57]]
    # B08303: travel time to work distribution. _001E = total workers 16+
    # who did not work from home. _008E..._013E = 30-34, 35-39, 40-44,
    # 45-59, 60-89, 90+ minute buckets (sum = 30+ minutes).
    commute_30plus = [f"B08303_{i:03d}E" for i in range(8, 14)]
    # B08136 / B08101 = aggregate minutes / workers -> mean commute.
    commute_agg = ["B08136_001E", "B08101_001E"]
    detail_vars = (["B01001_001E"] + age_m + age_f
                   + ["B19013_001E", "B25064_001E",
                      "B23025_002E", "B23025_003E", "B23025_005E",
                      "B15003_001E"] + edu_high
                   + ["B27001_001E"] + uninsured_cols
                   + ["B08303_001E"] + commute_30plus + commute_agg)

    r = requests.get(_acs_url(year, detail_vars), timeout=60)
    r.raise_for_status()
    rows = r.json()
    d = pd.DataFrame(rows[1:], columns=rows[0])
    d["fips"] = d["state"] + d["county"]
    for c in detail_vars:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    out = pd.DataFrame({"fips": d["fips"], "year": year})
    out["pop_total"] = d["B01001_001E"]
    out["pop_65plus"] = d[age_m + age_f].sum(axis=1)
    out["pct_65plus"] = (out["pop_65plus"] / out["pop_total"] * 100).round(2)
    out["median_hh_income"] = d["B19013_001E"]
    out["median_gross_rent"] = d["B25064_001E"]
    out["unemployment_rate"] = (d["B23025_005E"] / d["B23025_003E"] * 100).round(2)
    out["lfp_rate"] = (d["B23025_002E"] / d["B01001_001E"] * 100).round(2)
    out["pct_bachelors_plus"] = (d[edu_high].sum(axis=1)
                                  / d["B15003_001E"] * 100).round(2)
    out["pct_uninsured"] = (d[uninsured_cols].sum(axis=1)
                             / d["B27001_001E"] * 100).round(2)
    out["pct_commute_30plus"] = (d[commute_30plus].sum(axis=1)
                                  / d["B08303_001E"] * 100).round(2)
    out["mean_commute_minutes"] = (d["B08136_001E"]
                                    / d["B08101_001E"]).round(2)
    return out


def pull_qcew_year(year, naics="622"):
    url = f"https://data.bls.gov/cew/data/api/{year}/a/industry/{naics}.csv"
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), dtype={"area_fips": str})
    df = df[(df["own_code"] == 5)
            & (df["area_fips"].str.len() == 5)
            & df["area_fips"].str.startswith(STATE_FIPS)]
    df = df.rename(columns={"area_fips": "fips",
                            "annual_avg_emplvl": "hosp_emp",
                            "annual_avg_wkly_wage": "hosp_wkly_wage",
                            "annual_avg_estabs": "hosp_estabs"})
    df["year"] = year
    return df[["fips", "year", "hosp_emp", "hosp_wkly_wage", "hosp_estabs"]]


def pull_places():
    url = ("https://data.cdc.gov/resource/swc5-untb.json"
           "?stateabbr=MI&$limit=5000")
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    raw = pd.DataFrame(r.json())
    if raw.empty or "measureid" not in raw.columns:
        return pd.DataFrame(columns=["fips", "diabetes_pct",
                                      "hypertension_pct",
                                      "mental_distress_pct"])
    keep = {"DIABETES": "diabetes_pct", "BPHIGH": "hypertension_pct",
            "MHLTH": "mental_distress_pct"}
    p = raw[raw["measureid"].isin(keep.keys())].copy()
    p["data_value"] = pd.to_numeric(p["data_value"], errors="coerce")
    p["fips"] = p["locationid"].astype(str).str.zfill(5)
    return (p.pivot_table(index="fips", columns="measureid",
                          values="data_value", aggfunc="first")
              .rename(columns=keep)
              .reset_index())


def main():
    counties = get_counties()
    print(f"{len(counties)} MI counties")

    acs_frames = []
    for y in YEARS:
        try:
            acs_frames.append(pull_acs5_year(y))
            print(f"  ACS5 {y}: ok")
        except Exception as e:
            print(f"  ACS5 {y}: FAILED ({e})")
        time.sleep(0.4)
    acs = pd.concat(acs_frames, ignore_index=True) if acs_frames else pd.DataFrame()

    qcew_frames = []
    for y in YEARS:
        try:
            qcew_frames.append(pull_qcew_year(y))
            print(f"  QCEW {y}: ok")
        except Exception as e:
            print(f"  QCEW {y}: FAILED ({e})")
        time.sleep(0.5)
    qcew = pd.concat(qcew_frames, ignore_index=True) if qcew_frames else pd.DataFrame()

    places = pull_places()
    covid = pd.DataFrame([{"year": y, "covid_hosp_per_100k": v}
                          for y, v in MI_COVID.items()])

    spine = (counties.assign(key=1)
             .merge(pd.DataFrame({"year": YEARS, "key": 1}), on="key")
             .drop(columns="key"))
    m = (spine
         .merge(acs, on=["fips", "year"], how="left")
         .merge(qcew, on=["fips", "year"], how="left")
         .merge(places, on="fips", how="left")
         .merge(covid, on="year", how="left"))

    m["hosp_emp_per_100k"] = (m["hosp_emp"] / m["pop_total"] * 100_000).round(1)
    m["hosp_emp_growth"] = (m.sort_values(["fips", "year"])
                              .groupby("fips")["hosp_emp"]
                              .pct_change() * 100)
    base = CPI_U[2024]
    m["cpi_u"] = m["year"].map(CPI_U)
    m["hosp_wkly_wage_real"] = (m["hosp_wkly_wage"] * (base / m["cpi_u"])).round(2)
    m["hosp_wkly_wage_growth"] = (m.sort_values(["fips", "year"])
                                    .groupby("fips")["hosp_wkly_wage_real"]
                                    .pct_change() * 100)

    cols = ["fips", "county_name", "year",
            "hosp_emp", "hosp_emp_per_100k", "hosp_emp_growth",
            "hosp_wkly_wage", "hosp_wkly_wage_real", "hosp_wkly_wage_growth",
            "hosp_estabs",
            "covid_hosp_per_100k",
            "diabetes_pct", "hypertension_pct", "mental_distress_pct",
            "pop_total", "pct_65plus", "pct_uninsured",
            "median_hh_income", "median_gross_rent",
            "unemployment_rate", "lfp_rate", "pct_bachelors_plus"]
    cols = [c for c in cols if c in m.columns]
    m = m[cols].sort_values(["county_name", "year"]).reset_index(drop=True)
    m.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}: {m.shape}")
    print(f"Counties: {m.county_name.nunique()}, years: "
          f"{m.year.min()}-{m.year.max()}")


if __name__ == "__main__":
    main()
