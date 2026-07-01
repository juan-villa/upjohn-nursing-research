"""Fill missing full-in-progress.csv covariates from newly added panel files.

This script fills blanks conservatively:
- AHRF time-varying covariates are filled from mi_county_health_panel.csv.
- CHR headline covariates are checked against chr_headline_measures.csv.

Existing non-missing values are preserved, even when the new source differs.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
FULL_PATH = ROOT / "full-in-progress.csv"
HEALTH_PATH = ROOT / "mi_county_health_panel.csv"
CHR_PATH = ROOT / "chr_headline_measures.csv"

AHRF_TIME_VARYING_COLUMNS = [
    "comn_mentl_hlth_ctr",
    "critcl_access_hosp",
    "do_nf_activ",
    "fedly_qualfd_hlth_ctr",
    "hosp",
    "hosp_adm",
    "hosp_beds",
    "md_nf_activ",
    "md_nf_all_med_spec_all_pc",
    "md_nf_all_oth_spec_all_pc",
    "md_nf_all_surg_spec_all_pc",
    "md_nf_fammed_gen_all_pc",
    "md_nf_fed_activ",
    "md_nf_pc_hosp_all",
    "md_nf_pc_ofc",
    "medcr_ffs_eligbl_medcd_pct",
    "medcr_ffs_hosp_readm_rate",
    "medcr_ffs_prev_hosp_rate",
    "nhsc_fte_provdrs",
    "nhsc_sites",
    "nurs_fac",
    "nurs_fac_beds",
    "per_cap_persnl_incom",
    "phys_nf_prim_care_pc_exc_rsdt",
    "phys_nf_prim_care_pc_rsdnt",
    "popn_est",
    "rural_hlth_clincs",
    "stgh",
    "stgh_aprn_ft",
    "stgh_aprn_pa",
    "stgh_fte_lpnlvn_incl_nh",
    "stgh_nursng_asst_ft_incl_nh",
    "vetn_popn_est",
]


def normalize_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns={"fips_st_cnty": "fips"}).copy()
    out["fips"] = out["fips"].astype(str).str.zfill(5)
    out["year"] = pd.to_numeric(out["year"], errors="raise").astype(int)
    if out.duplicated(["fips", "year"]).any():
        dupes = out.loc[out.duplicated(["fips", "year"], keep=False), ["fips", "year"]]
        raise ValueError(f"Duplicate source keys found:\n{dupes.to_string(index=False)}")
    return out


def fill_missing_from_source(
    panel: pd.DataFrame,
    source: pd.DataFrame,
    columns: list[str],
    label: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    available = [c for c in columns if c in panel.columns and c in source.columns]
    if not available:
        return panel, pd.DataFrame()

    before_missing = panel[available].isna().sum()
    source_subset = source[["fips", "year"] + available].copy()
    merged = panel.merge(
        source_subset,
        on=["fips", "year"],
        how="left",
        suffixes=("", "__fill"),
        validate="one_to_one",
    )

    report_rows = []
    for col in available:
        fill_col = f"{col}__fill"
        filled = int(merged[col].isna().sum() - merged[col].combine_first(merged[fill_col]).isna().sum())
        both_nonmissing = merged[col].notna() & merged[fill_col].notna()
        differing = 0
        if both_nonmissing.any():
            left = pd.to_numeric(merged.loc[both_nonmissing, col], errors="coerce")
            right = pd.to_numeric(merged.loc[both_nonmissing, fill_col], errors="coerce")
            differing = int((left - right).abs().gt(1e-9).sum())
        merged[col] = merged[col].combine_first(merged[fill_col])
        report_rows.append(
            {
                "source": label,
                "column": col,
                "missing_before": int(before_missing[col]),
                "filled": filled,
                "overlapping_nonmissing_differences_preserved": differing,
                "missing_after": int(merged[col].isna().sum()),
            }
        )

    merged = merged.drop(columns=[f"{c}__fill" for c in available])
    return merged, pd.DataFrame(report_rows)


def main() -> None:
    panel = pd.read_csv(FULL_PATH, dtype={"fips": str})
    panel["fips"] = panel["fips"].astype(str).str.zfill(5)
    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    if panel.duplicated(["fips", "year"]).any():
        raise ValueError("full-in-progress.csv has duplicate fips-year keys")

    health = normalize_source(pd.read_csv(HEALTH_PATH, dtype={"fips_st_cnty": str}, low_memory=False))
    chr_source = normalize_source(pd.read_csv(CHR_PATH, dtype={"fips_st_cnty": str}, low_memory=False))
    chr_columns = [c for c in panel.columns if c.startswith("chr_")]

    reports = []
    panel, report = fill_missing_from_source(panel, health, AHRF_TIME_VARYING_COLUMNS, "mi_county_health_panel.csv")
    reports.append(report)
    panel, report = fill_missing_from_source(panel, chr_source, chr_columns, "chr_headline_measures.csv")
    reports.append(report)

    panel.to_csv(FULL_PATH, index=False)
    report = pd.concat([r for r in reports if not r.empty], ignore_index=True)

    total_filled = int(report["filled"].sum()) if not report.empty else 0
    print(f"Wrote {FULL_PATH}")
    print(f"Total filled cells: {total_filled:,}")
    print("\nFilled cells by source:")
    print(report.groupby("source")["filled"].sum().to_string())

    filled = report[report["filled"] > 0].sort_values(["source", "filled"], ascending=[True, False])
    print("\nColumns filled:")
    print(filled.to_string(index=False))

    preserved = report[report["overlapping_nonmissing_differences_preserved"] > 0]
    if not preserved.empty:
        print("\nExisting non-missing values that differed from the new source were preserved:")
        print(
            preserved[
                ["source", "column", "overlapping_nonmissing_differences_preserved"]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
