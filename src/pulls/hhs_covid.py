"""
hhs_covid.py — HHS Protect facility-level hospitalizations → MSA × year peaks.

Pulls weekly facility-level COVID-19 hospitalization data for Michigan from
healthdata.gov dataset anag-cw7u (covers 2020-03 through 2024-04). Aggregates
to MSA level using county FIPS → MSA crosswalk, then computes annual peak
weekly admissions per 100k for each MSA.

Output: data/processed/covid_msa_year.csv
        columns: cbsa, year, covid_peak_per_100k, covid_avg_per_100k
"""
import pandas as pd
import requests
from io import StringIO
from ._common import HEADERS, PROCESSED, MI_COUNTY_TO_MSA, CBSA, YEARS

URL = "https://healthdata.gov/resource/anag-cw7u.csv"

KEEP = [
    "hospital_pk", "collection_week", "state", "fips_code",
    "total_beds_7_day_avg",
    "total_adult_patients_hospitalized_confirmed_covid_7_day_avg",
    "previous_day_admission_adult_covid_confirmed_7_day_sum",
]


def fetch_all_mi():
    rows = []
    offset = 0
    page = 50_000
    while True:
        params = {
            "state": "MI",
            "$limit": page,
            "$offset": offset,
            "$select": ",".join(KEEP),
        }
        r = requests.get(URL, headers=HEADERS, params=params, timeout=180)
        r.raise_for_status()
        chunk = pd.read_csv(StringIO(r.text))
        if chunk.empty:
            break
        rows.append(chunk)
        offset += len(chunk)
        print(f"    pulled {offset} rows...")
        if len(chunk) < page:
            break
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main():
    print("Fetching HHS Protect facility COVID data for MI...")
    df = fetch_all_mi()
    print(f"Total rows: {len(df)}")
    if df.empty:
        return

    df["collection_week"] = pd.to_datetime(df["collection_week"], errors="coerce")
    df["year"] = df["collection_week"].dt.year
    df["fips_code"] = df["fips_code"].astype(str).str.split(".").str[0].str.zfill(5)
    df["msa_name"] = df["fips_code"].map(MI_COUNTY_TO_MSA)
    df["cbsa"] = df["msa_name"].map(CBSA)

    # Numeric coercion — "-999999" is the dataset's missing/suppressed sentinel
    num = "total_adult_patients_hospitalized_confirmed_covid_7_day_avg"
    df[num] = pd.to_numeric(df[num], errors="coerce")
    df.loc[df[num] < 0, num] = pd.NA

    # First aggregate to MSA × week (sum across hospitals)
    msa_week = (df.dropna(subset=["cbsa", num])
                  .groupby(["cbsa", "msa_name", "year", "collection_week"])
                  [num].sum()
                  .reset_index())

    # Need MSA population per year for per-100k conversion. Pull from master
    # if available, else use rough ACS lookups.
    try:
        m = pd.read_csv(PROCESSED.parent.parent / "master_panel.csv",
                        dtype={"cbsa": str})
        pop = (m[["cbsa", "year", "pop_total"]]
               .dropna()
               .groupby(["cbsa", "year"])["pop_total"]
               .first()
               .reset_index())
        msa_week = msa_week.merge(pop, on=["cbsa", "year"], how="left")
        # ffill within MSA across years (covers 2020 ACS gap)
        msa_week = msa_week.sort_values(["cbsa", "year"])
        msa_week["pop_total"] = msa_week.groupby("cbsa")["pop_total"].ffill().bfill()
        msa_week["per_100k"] = msa_week[num] / msa_week["pop_total"] * 100_000
    except FileNotFoundError:
        print("  master_panel.csv not found — using raw counts only")
        msa_week["per_100k"] = pd.NA

    # Annual aggregation: peak weekly + average weekly per 100k
    annual = (msa_week.groupby(["cbsa", "msa_name", "year"])
                       .agg(covid_peak_per_100k=("per_100k", "max"),
                            covid_avg_per_100k=("per_100k", "mean"))
                       .reset_index())

    # Fill pre-COVID years with zero, post-data with NaN
    full_grid = pd.DataFrame([(c, y) for c in annual["cbsa"].unique()
                              for y in YEARS], columns=["cbsa", "year"])
    full = full_grid.merge(annual, on=["cbsa", "year"], how="left")
    full.loc[full["year"] < 2020,
             ["covid_peak_per_100k", "covid_avg_per_100k"]] = 0.0

    out_path = PROCESSED / "covid_msa_year.csv"
    full.to_csv(out_path, index=False)
    print(f"Wrote {out_path}: {full.shape}")
    print(full[full["year"].between(2020, 2024)]
          .pivot_table(index="cbsa", columns="year",
                       values="covid_peak_per_100k").round(1).head(20))


if __name__ == "__main__":
    main()
