"""
cdc_places.py — CDC PLACES county-level chronic disease prevalence,
aggregated to MSA.

Pulls latest PLACES county release (dataset `swc5-untb`) for Michigan and
aggregates to MSA via county FIPS, weighted by county population. Output
is cross-sectional (PLACES doesn't publish a long time series) — values
are attached to every panel year.

Measures kept (BRFSS prevalence in adults):
  DIABETES   - diagnosed diabetes (%)
  BPHIGH     - high blood pressure (%)
  MHLTH      - frequent mental distress (14+ unhealthy days / 30) (%)
  COPD       - chronic obstructive pulmonary disease (%)
  OBESITY    - obesity (%)

Output: data/processed/cdc_places_msa.csv
Columns: cbsa, diabetes_pct, hypertension_pct, mental_distress_pct,
         copd_pct, obesity_pct
"""
import pandas as pd
import requests
from io import StringIO
from ._common import HEADERS, PROCESSED, MI_COUNTY_TO_MSA, CBSA

URL = "https://data.cdc.gov/resource/swc5-untb.json"
MEASURES = {
    "DIABETES": "diabetes_pct",
    "BPHIGH":   "hypertension_pct",
    "MHLTH":    "mental_distress_pct",
    "COPD":     "copd_pct",
    "OBESITY":  "obesity_pct",
}


def fetch_mi_places():
    params = {"stateabbr": "MI", "$limit": 50000}
    r = requests.get(URL, headers=HEADERS, params=params, timeout=120)
    r.raise_for_status()
    return pd.DataFrame(r.json())


def main():
    raw = fetch_mi_places()
    print(f"PLACES rows: {len(raw)}")
    if raw.empty:
        return

    raw = raw[raw["measureid"].isin(MEASURES.keys())].copy()
    raw["data_value"] = pd.to_numeric(raw["data_value"], errors="coerce")
    raw["fips"] = raw["locationid"].astype(str).str.zfill(5)
    raw["msa_name"] = raw["fips"].map(MI_COUNTY_TO_MSA)
    raw["cbsa"] = raw["msa_name"].map(CBSA)
    raw["pop"] = pd.to_numeric(raw["totalpopulation"], errors="coerce")
    raw = raw.dropna(subset=["cbsa", "data_value", "pop"])

    # population-weighted MSA aggregation
    def wmean(g):
        return (g["data_value"] * g["pop"]).sum() / g["pop"].sum()
    pivoted = (raw.groupby(["cbsa", "measureid"])
                  .apply(wmean)
                  .unstack("measureid")
                  .rename(columns=MEASURES)
                  .reset_index())

    out_path = PROCESSED / "cdc_places_msa.csv"
    pivoted.to_csv(out_path, index=False)
    print(f"Wrote {out_path}: {pivoted.shape}")
    print(pivoted.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
