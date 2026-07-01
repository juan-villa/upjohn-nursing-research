"""Attach RN/LPN county-year outcomes to county_excluding_count.csv.

Inputs:
  county_excluding_count.csv
  outcome_data_nurse_counts/*.csv

The outcome files are keyed by county name and year. The county panel uses
"St." abbreviations while the nurse outcome files spell those counties as
"Saint", so this script normalizes those names before merging.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
PANEL_PATH = ROOT / "county_excluding_count.csv"
OUTCOME_DIR = ROOT / "outcome_data_nurse_counts"

RN_PATH = (
    OUTCOME_DIR
    / "minursemap_rn_county_age_panel_2012_2013_2014_2015_2016_2017_2019_2020_2022_2023.csv"
)

OUTCOME_COLUMNS = [
    "rn_licensed_county",
    "rn_age_under35_pct",
    "rn_age_55plus_pct",
    "lpn_licensed_county",
    "lpn_age_under35_pct",
    "lpn_age_55plus_pct",
]
LEGACY_COLUMNS = ["lpn_missing_flag"]


def normalize_county_name(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .replace(
            {
                "Saint Clair": "St. Clair",
                "Saint Joseph": "St. Joseph",
            }
        )
    )


def load_rn_outcomes() -> pd.DataFrame:
    rn = pd.read_csv(RN_PATH)
    rn["county_name"] = normalize_county_name(rn["county"])
    keep = ["county_name", "year", "rn_licensed_county", "rn_age_under35_pct", "rn_age_55plus_pct"]
    rn = rn[keep].copy()
    if rn.duplicated(["county_name", "year"]).any():
        dupes = rn.loc[rn.duplicated(["county_name", "year"], keep=False), ["county_name", "year"]]
        raise ValueError(f"Duplicate RN county-year rows found:\n{dupes.to_string(index=False)}")
    return rn


def load_lpn_outcomes() -> pd.DataFrame:
    frames = []
    for path in sorted(OUTCOME_DIR.glob("lpn_county*.csv")):
        lpn = pd.read_csv(path)
        lpn["county_name"] = normalize_county_name(lpn["county"])
        lpn = lpn[lpn["county_name"] != "Outside Michigan"].copy()
        frames.append(lpn)

    if not frames:
        raise FileNotFoundError(f"No LPN outcome files found in {OUTCOME_DIR}")

    out = pd.concat(frames, ignore_index=True)
    keep = [
        "county_name",
        "year",
        "lpn_licensed_county",
        "lpn_age_under35_pct",
        "lpn_age_55plus_pct",
    ]
    out = out[keep].copy()
    if out.duplicated(["county_name", "year"]).any():
        dupes = out.loc[out.duplicated(["county_name", "year"], keep=False), ["county_name", "year"]]
        raise ValueError(f"Duplicate LPN county-year rows found:\n{dupes.to_string(index=False)}")
    return out


def main() -> None:
    panel = pd.read_csv(PANEL_PATH, dtype={"fips": str})
    panel = panel.drop(columns=[c for c in OUTCOME_COLUMNS + LEGACY_COLUMNS if c in panel.columns])

    rn = load_rn_outcomes()
    lpn = load_lpn_outcomes()

    merged = (
        panel.merge(rn, on=["county_name", "year"], how="left", validate="one_to_one")
        .merge(lpn, on=["county_name", "year"], how="left", validate="one_to_one")
        .sort_values(["fips", "year"])
        .reset_index(drop=True)
    )

    merged.to_csv(PANEL_PATH, index=False)

    outcome_years = sorted(set(rn["year"]).union(lpn["year"]))
    print(f"Wrote {PANEL_PATH}")
    print(f"Shape: {merged.shape}")
    print(f"Outcome years available: {outcome_years}")
    for col in OUTCOME_COLUMNS:
        print(f"{col}: {merged[col].notna().sum()} non-missing")

    missing_by_year = (
        merged.groupby("year")[["rn_licensed_county", "lpn_licensed_county"]]
        .apply(lambda d: d.isna().sum())
        .reset_index()
        .rename(
            columns={
                "rn_licensed_county": "rn_missing_rows",
                "lpn_licensed_county": "lpn_missing_rows",
            }
        )
    )
    print("\nMissing rows by year:")
    print(missing_by_year.to_string(index=False))


if __name__ == "__main__":
    main()
