"""
clean_panel.py
--------------
Addresses structural caveats in oews_michigan_rn_panel.csv.

Fixes applied:
  1. Drop pct_total (100% null).
  2. Drop the Detroit-Dearborn-Livonia metropolitan division (2015-2017).
     It is a SUB-area of Detroit-Warren-Dearborn — keeping both double-counts.
  3. Harmonize MSA renames so the same place has one stable name across years.
     Use the CURRENT (2024) BLS names as canonical, since they reflect what
     future releases will use:
        Grand Rapids-Wyoming         -> Grand Rapids-Wyoming-Kentwood
        Muskegon                     -> Muskegon-Norton Shores
        Niles-Benton Harbor          -> Niles
  4. Handle the 2024 nonmetropolitan redefinition. BLS replaced the old three
     "Balance/Northeast/Northwest Lower Peninsula" nonmetro areas with three
     new ones (Northern / Mid / Southern Michigan nonmetro) starting 2024.
     These do NOT map 1-to-1, so we mark them with area_definition_era and
     drop the 2024 nonmetro rows from the longitudinal panel (kept in a
     separate file for reference).
  5. Add stable area_id column for joins/regressions.

Output:
    oews_michigan_rn_panel_clean.csv   <- harmonized longitudinal panel
    oews_michigan_rn_2024_nonmetro.csv <- 2024-only redefined nonmetro areas
"""

import pandas as pd

INPUT = "oews_michigan_rn_panel.csv"
OUT_PANEL = "oews_michigan_rn_panel_clean.csv"
OUT_NONMETRO_2024 = "oews_michigan_rn_2024_nonmetro.csv"

NAME_MAP = {
    # Current 2024 naming used canonically
    "Grand Rapids-Wyoming, MI": "Grand Rapids-Wyoming-Kentwood, MI",
    "Muskegon, MI": "Muskegon-Norton Shores, MI",
    "Niles-Benton Harbor, MI": "Niles, MI",
    # Pre-2015 names map to current Detroit-Warren-Dearborn MSA
    "Detroit-Warren-Livonia, MI": "Detroit-Warren-Dearborn, MI",
    # Pre-2014 names for Saginaw MSA
    "Saginaw-Saginaw Township North, MI": "Saginaw, MI",
}

DROP_AREAS = {
    "Detroit-Dearborn-Livonia, MI Metropolitan Division",
    "Detroit-Livonia-Dearborn, MI Metropolitan Division",
    "Warren-Troy-Farmington Hills, MI Metropolitan Division",
    "Warren-Farmington Hills-Troy, MI Metropolitan Division",
}

NEW_2024_NONMETRO = {
    "Northern Michigan nonmetropolitan area",
    "Mid Michigan nonmetropolitan area",
    "Southern Michigan nonmetropolitan area",
}

OLD_NONMETRO = {
    "Balance of Lower Peninsula of Michigan nonmetropolitan area",
    "Northeast Lower Peninsula of Michigan nonmetropolitan area",
    "Northwest Lower Peninsula of Michigan nonmetropolitan area",
}


def main():
    df = pd.read_csv(INPUT)
    print(f"Loaded {len(df)} rows, {df['area_title'].nunique()} areas, "
          f"years {df['year'].min()}–{df['year'].max()}")

    # 1. Drop fully-null column
    if "pct_total" in df.columns and df["pct_total"].isna().all():
        df = df.drop(columns=["pct_total"])
        print("Dropped pct_total (100% null)")

    # 2. Drop double-counting Detroit division
    n_before = len(df)
    df = df[~df["area_title"].isin(DROP_AREAS)].copy()
    print(f"Dropped {n_before - len(df)} Detroit-Dearborn-Livonia rows")

    # 3. Harmonize names
    df["area_title"] = df["area_title"].replace(NAME_MAP)
    print(f"Renamed {len(NAME_MAP)} area variants to canonical names")

    # 4. Split off the 2024-only redefined nonmetro areas
    nonmetro_2024 = df[df["area_title"].isin(NEW_2024_NONMETRO)].copy()
    df = df[~df["area_title"].isin(NEW_2024_NONMETRO)].copy()
    nonmetro_2024.to_csv(OUT_NONMETRO_2024, index=False)
    print(f"Split off {len(nonmetro_2024)} rows of 2024-only redefined "
          f"nonmetro areas -> {OUT_NONMETRO_2024}")

    # Tag definition era for transparency
    df["area_definition_era"] = df["area_title"].apply(
        lambda a: "old_nonmetro_2015_2023" if a in OLD_NONMETRO else "stable"
    )

    # 5. Stable area_id (slug of canonical name)
    df["area_id"] = (df["area_title"]
                     .str.lower()
                     .str.replace(r"[^a-z0-9]+", "_", regex=True)
                     .str.strip("_"))

    # Reorder columns
    front = ["year", "area_id", "area_title", "area_definition_era",
             "area", "occ_code", "occ_title"]
    rest = [c for c in df.columns if c not in front]
    df = df[front + rest].sort_values(["area_title", "year"]).reset_index(drop=True)

    df.to_csv(OUT_PANEL, index=False)
    print(f"\nWrote {OUT_PANEL}: {df.shape[0]} rows, {df['area_title'].nunique()} areas")

    # Quick coverage report
    cov = df.groupby("area_title")["year"].agg(["min", "max", "nunique"])
    cov.columns = ["first_year", "last_year", "n_years"]
    print("\nCoverage by area:")
    print(cov.sort_values("n_years", ascending=False).to_string())


if __name__ == "__main__":
    main()
