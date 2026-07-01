"""Recover 2018 rows for regression-data-base.csv.

Adds 83 rows (one per MI county) for year=2018 by pulling from:
  - full-in-progress.rebuilt.csv (ACS, AHRF time-varying, IPEDS, PUMS, Bartik)
  - hcris_county_panel_2012_2023.csv (HCRIS hospital aggregates)
  - /Users/juanvilla/Documents/gse-580-final-proposal/data/chr_michigan_panel.csv
  - oews_michigan_rn_panel.csv + data_next_steps/01_oews_michigan_lpn_2005_2024.csv
  - data/lightcast_postings_county_panel.csv
  - For time-invariant columns (typology, HPSA, density, cbsa_name, etc.):
    broadcast from the same fips' 2017 row in regression-data-base.csv.
  - Old nurse-license outcomes (rn/lpn_licensed_county, *_age_*) stay NaN.

Output: regression-data-base.csv is rewritten with 83 new rows appended,
sorted by fips, year.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/juanvilla/Documents/gse-580-clean")
PROPOSAL = Path("/Users/juanvilla/Documents/gse-580-final-proposal")

PANEL = ROOT / "regression-data-base.csv"
FULL = ROOT / "full-in-progress.rebuilt.csv"
HCRIS = ROOT / "hcris_county_panel_2012_2023.csv"
CHR = PROPOSAL / "data/chr_michigan_panel.csv"
OEWS_RN = ROOT / "oews_michigan_rn_panel_clean.csv"
OEWS_LPN = ROOT / "data_next_steps/01_oews_michigan_lpn_2005_2024.csv"
LIGHT = ROOT / "data/lightcast_postings_county_panel.csv"

sys.path.insert(0, str(ROOT / "scripts"))
from pulls._common import CBSA, MI_COUNTY_TO_MSA  # noqa: E402

YEAR = 2018

# CHR measure → regression-data-base column
CHR_MAP = [
    ("premature death", ["Years of Potential Life Lost Rate", "YPLL Rate"],
     "chr_premature_death_rate"),
    ("preventable hospital stays",
     ["Preventable Hospitalization Rate", "Preventable Hosp. Rate",
      "Preventable Hospital Stays Rate"],
     "chr_preventable_hosp_rate"),
    ("poor or fair health", ["% Fair/Poor", "% Fair or Poor Health"],
     "chr_pct_fair_poor_health"),
    ("low birthweight", ["% LBW", "% Low Birthweight"],
     "chr_pct_low_birthweight"),
    ("primary care physicians",
     ["Primary Care Physicians Rate", "PCP Rate"], "chr_pcp_rate"),
    ("dentists", ["Dentist Rate"], "chr_dentist_rate"),
    ("uninsured", ["% Uninsured"], "chr_pct_uninsured"),
    ("adult smoking",
     ["% Smokers", "% Adults Reporting Currently Smoking",
      "% Currently Smoking"], "chr_pct_adult_smoking"),
    ("adult obesity", ["% Obese", "% Adults with Obesity"],
     "chr_pct_adult_obesity"),
    ("poor mental health days",
     ["Mentally Unhealthy Days",
      "Average Number of Mentally Unhealthy Days"],
     "chr_avg_mental_unhealthy_days"),
    ("children in poverty", ["% Children in Poverty"],
     "chr_pct_children_in_poverty"),
]


def load_panel():
    return pd.read_csv(PANEL, dtype={"fips": str}, low_memory=False)


def base_2018(panel):
    """83-row skeleton: fips, county_name, year=2018."""
    base = (panel.sort_values(["fips", "year"])
                 .drop_duplicates("fips")[["fips", "county_name"]]
                 .copy())
    base["year"] = YEAR
    return base


def add_full_in_progress(base, panel_cols):
    f = pd.read_csv(FULL, dtype={"fips": str}, low_memory=False)
    f["fips"] = f["fips"].str.zfill(5)
    f18 = f[f.year == YEAR].copy()
    # pop_65plus lives in full-in-progress as pop_65plus_x / pop_65plus_y;
    # they're identical (the rebuild merged two layers). Prefer _x.
    if "pop_65plus" not in f18.columns:
        f18["pop_65plus"] = f18.get("pop_65plus_x",
                                     f18.get("pop_65plus_y"))
    take = [c for c in f18.columns
            if c in panel_cols and c not in ("year", "fips", "county_name")]
    f18 = f18[["fips"] + take]
    return base.merge(f18, on="fips", how="left")


def add_hcris(df):
    h = pd.read_csv(HCRIS, dtype={"county_fips": str}, low_memory=False)
    h = h[h.cal_year == YEAR].copy()
    h["fips"] = (h["county_fips"].astype(str).str.split(".")
                  .str[0].str.zfill(5))
    # Some counties appear twice (name variants). Aggregate:
    #   - n_hospitals, total_beds: sum
    #   - operating_margin_wmean, overhead_ratio_wmean,
    #     net_income_per_bed_wmean: bed-weighted mean (best available
    #     reconstruction from the per-row weighted means)
    #   - single_hospital_county: True only if county has exactly one hospital
    def agg(g):
        beds = g["total_beds"].fillna(0)
        w = beds / beds.sum() if beds.sum() > 0 else None
        nh = g["n_hospitals"].sum()
        out = {
            "n_hospitals": nh,
            "total_beds": g["total_beds"].sum(),
            "single_hospital_county": bool(nh == 1),
        }
        for c in ("operating_margin_wmean", "overhead_ratio_wmean",
                 "net_income_per_bed_wmean"):
            if w is not None:
                out[c] = float((g[c].fillna(0) * w).sum())
            else:
                out[c] = g[c].mean()
        return pd.Series(out)

    h_agg = h.groupby("fips").apply(agg, include_groups=False).reset_index()
    df = df.merge(h_agg, on="fips", how="left")
    return df


def add_has_medicare_hospital(df, panel):
    """Time-invariant: broadcast from 2017 (latest pre-gap) per fips."""
    src = (panel[panel.year == 2017][["fips", "has_medicare_hospital"]]
           .drop_duplicates("fips"))
    return df.merge(src, on="fips", how="left")


def add_chr(df):
    chr_df = pd.read_csv(CHR, dtype={"fips": str})
    chr_df["fips"] = chr_df["fips"].str.zfill(5)
    sub18 = chr_df[chr_df.year == YEAR].copy()
    pieces = []
    for measure, subs, out_col in CHR_MAP:
        m = sub18[(sub18["measure"] == measure)
                  & (sub18["sub_col"].isin(subs))]
        if m.empty:
            print(f"  CHR {out_col}: no 2018 rows")
            continue
        # Pivot just in case of multiple sub_col aliases — first non-null wins
        wide = (m.pivot_table(index="fips", columns="sub_col",
                              values="value", aggfunc="first")
                 .reset_index())
        existing = [s for s in subs if s in wide.columns]
        wide[out_col] = wide[existing].bfill(axis=1).iloc[:, 0]
        pieces.append(wide[["fips", out_col]])
    out = pieces[0]
    for p in pieces[1:]:
        out = out.merge(p, on="fips", how="outer")
    return df.merge(out, on="fips", how="left")


def add_oews(df):
    """OEWS is MSA-level. Map each MI MSA county to its MSA's 2018 values."""
    # Build CBSA → county-fips mapping (inverse of MI_COUNTY_TO_MSA via CBSA)
    cbsa_to_fips = {}
    for fips, msa_name in MI_COUNTY_TO_MSA.items():
        code = CBSA[msa_name]
        cbsa_to_fips.setdefault(code, []).append(fips)

    rn = pd.read_csv(OEWS_RN)
    rn = rn[(rn.year == YEAR) & (rn.occ_code == "29-1141")].copy()
    rn["cbsa"] = rn["area"].astype(str)

    lpn = pd.read_csv(OEWS_LPN)
    lpn = lpn[(lpn.year == YEAR) & (lpn.occ_code == "29-2061")].copy()
    lpn["cbsa"] = lpn["area"].astype(str)

    rn_keep = ["cbsa", "tot_emp", "a_mean", "a_median", "h_mean", "h_median"]
    lpn_keep = ["cbsa", "tot_emp", "a_mean", "a_median", "h_mean", "h_median"]
    rn = (rn[rn_keep]
          .rename(columns={"tot_emp": "rn_tot_emp",
                            "a_mean": "rn_a_mean", "a_median": "rn_a_median",
                            "h_mean": "rn_h_mean",
                            "h_median": "rn_h_median"}))
    lpn = (lpn[lpn_keep]
           .rename(columns={"tot_emp": "lpn_tot_emp",
                             "a_mean": "lpn_a_mean",
                             "a_median": "lpn_a_median",
                             "h_mean": "lpn_h_mean",
                             "h_median": "lpn_h_median"}))

    rn_nonmetro = rn[rn.cbsa == "2600004"]
    lpn_nonmetro = lpn[lpn.cbsa == "2600004"]
    rows = []
    msa_fips_set = set(MI_COUNTY_TO_MSA.keys())
    all_fips = sorted(set(df["fips"]))
    for f in all_fips:
        row = {"fips": f}
        if f in msa_fips_set:
            cbsa_code = CBSA[MI_COUNTY_TO_MSA[f]]
            rn_row = rn[rn.cbsa == cbsa_code]
            lpn_row = lpn[lpn.cbsa == cbsa_code]
        else:
            # Mirror legacy regression-data-base behavior: non-MSA counties
            # get the Balance-of-LP nonmetro values (single value applied
            # statewide to all non-MSA counties).
            rn_row = rn_nonmetro
            lpn_row = lpn_nonmetro
        if not rn_row.empty:
            for c in ["rn_tot_emp", "rn_a_mean", "rn_a_median",
                      "rn_h_mean", "rn_h_median"]:
                row[c] = rn_row.iloc[0][c]
        if not lpn_row.empty:
            for c in ["lpn_tot_emp", "lpn_a_mean", "lpn_a_median",
                      "lpn_h_mean", "lpn_h_median"]:
                row[c] = lpn_row.iloc[0][c]
        rows.append(row)
    oews18 = pd.DataFrame(rows)
    return df.merge(oews18, on="fips", how="left")


def add_lightcast(df):
    light = pd.read_csv(LIGHT, dtype={"fips": str})
    light["fips"] = light["fips"].str.zfill(5)
    l18 = (light[light.year == YEAR]
           [["fips", "rn_postings", "rn_post_wage_annual",
             "rn_post_wage_hourly", "lpn_postings", "lpn_post_wage_annual",
             "lpn_post_wage_hourly"]])
    return df.merge(l18, on="fips", how="left")


TIME_INVARIANT = [
    "rural_urban_contnm", "urban_influnc", "cbsa", "cbsa_name", "cbsa_ind",
    "econ_depndnt_typolgy", "mfg_depndnt_typolgy", "recrtn_typolgy",
    "hi_povty_typolgy", "prstnt_povty_typolgy", "popn_loss_typolgy",
    "retrmnt_destntn_typolgy", "hpsa_prim_care", "hpsa_dent",
    "hpsa_mentl_hlth", "popn_densty_per_squr_mi", "land_area_mi2",
    "magnet_hospital_present",  # treated as time-invariant; data quality
                                 # suggests it does not change within window
]


def broadcast_time_invariant(df, panel):
    """Take 2017 values per fips from regression-data-base and write into
    the corresponding 2018 cells, but only where the 2018 cell is empty."""
    src = (panel[panel.year == 2017][["fips"] + TIME_INVARIANT]
           .drop_duplicates("fips"))
    df = df.merge(src, on="fips", how="left", suffixes=("", "_ti"))
    for c in TIME_INVARIANT:
        ti = f"{c}_ti"
        if c in df.columns and ti in df.columns:
            df[c] = df[c].combine_first(df[ti])
            df = df.drop(columns=[ti])
        elif ti in df.columns:
            df = df.rename(columns={ti: c})
    return df


def compute_derived(df):
    # share_65plus, uninsured_rate, disability_rate, bachelors_plus_share
    # are renames of pct_65plus / pct_uninsured / pct_disability /
    # pct_bachelors_plus from full-in-progress.rebuilt (which we already
    # merged). Reproduce them here.
    aliases = [
        ("share_65plus",          "pct_65plus"),
        ("uninsured_rate",        "pct_uninsured"),
        ("disability_rate",       "pct_disability"),
        ("bachelors_plus_share",  "pct_bachelors_plus"),
    ]
    full = pd.read_csv(FULL, dtype={"fips": str}, low_memory=False)
    full["fips"] = full["fips"].str.zfill(5)
    f18 = full[full.year == YEAR][["fips", "pct_65plus", "pct_uninsured",
                                    "pct_disability", "pct_bachelors_plus"]]
    df = df.merge(f18, on="fips", how="left", suffixes=("", "_src"))
    for new, src in aliases:
        col = src if src in df.columns else f"{src}_src"
        if col in df.columns:
            df[new] = df[col]
    drop = [c for c in ("pct_65plus", "pct_uninsured", "pct_disability",
                        "pct_bachelors_plus") if c in df.columns]
    df = df.drop(columns=drop, errors="ignore")

    # hosp_beds_per_1k = hosp_beds (AHRF) / pop_total * 1000
    if "hosp_beds" in df.columns and "pop_total" in df.columns:
        pop = df["pop_total"].replace(0, np.nan)
        df["hosp_beds_per_1k"] = df["hosp_beds"] / pop * 1000

    # nh_beds_per_65plus_ahrf = nurs_fac_beds / pop_65plus * 1000
    if "nurs_fac_beds" in df.columns and "pop_65plus" in df.columns:
        pop65 = df["pop_65plus"].replace(0, np.nan)
        df["nh_beds_per_65plus_ahrf"] = df["nurs_fac_beds"] / pop65 * 1000

    # postings_per_10k & log_postings
    pop = df["pop_total"].replace(0, np.nan)
    df["rn_postings_per_10k"]  = df["rn_postings"]  / pop * 10000
    df["lpn_postings_per_10k"] = df["lpn_postings"] / pop * 10000
    df["log_rn_postings"]  = np.log1p(df["rn_postings"])
    df["log_lpn_postings"] = np.log1p(df["lpn_postings"])

    # has_med_hosp_x_overhead
    if "has_medicare_hospital" in df.columns and \
       "overhead_ratio_wmean" in df.columns:
        df["has_med_hosp_x_overhead"] = (df["has_medicare_hospital"].fillna(0)
                                          * df["overhead_ratio_wmean"]
                                              .fillna(0))
    return df


SLOW_MOVING_AHRF = [
    # AHRF columns absent from full-in-progress.rebuilt.csv (or empty in
    # its 2018 slice) but present in regression-data-base.csv for adjacent
    # years. They describe facility counts / staffing / Medicare program
    # metrics that change slowly; we broadcast the 2017 value into 2018
    # rather than leaving NaN. Flagged explicitly so future-you can
    # replace with actual 2018 AHRF parses.
    "hosp", "stgh_aprn_ft", "stgh_aprn_pa",
    "stgh_fte_lpnlvn_incl_nh", "stgh_nursng_asst_ft_incl_nh",
    "medcr_ffs_eligbl_medcd_pct", "medcr_ffs_prev_hosp_rate",
    "medcr_ffs_hosp_readm_rate",
    "phys_nf_prim_care_pc_rsdnt", "md_nf_pc_ofc", "nhsc_fte_provdrs",
]


def broadcast_slow_moving(df, panel):
    src = (panel[panel.year == 2017][["fips"] + SLOW_MOVING_AHRF]
           .drop_duplicates("fips"))
    df = df.merge(src, on="fips", how="left", suffixes=("", "_sm"))
    for c in SLOW_MOVING_AHRF:
        sm = f"{c}_sm"
        if c in df.columns and sm in df.columns:
            df[c] = df[c].combine_first(df[sm])
            df = df.drop(columns=[sm])
        elif sm in df.columns:
            df = df.rename(columns={sm: c})
    return df


def fill_ipeds_zeros(df):
    """Counties without an IPEDS-reporting nursing school have zero
    completions; mirror build_county_excluding_count.py:443-444."""
    for c in ("ipeds_completions_cna", "ipeds_completions_lpn",
              "ipeds_completions_other_nursing", "ipeds_completions_rn",
              "ipeds_completions_total"):
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df


def fill_pop_65plus(df):
    """pop_65plus = pop_total * pct_65plus / 100 (when missing)."""
    if {"pop_total", "pct_65plus", "pop_65plus"}.issubset(df.columns):
        mask = df["pop_65plus"].isna() & df["pop_total"].notna() \
               & df["pct_65plus"].notna()
        df.loc[mask, "pop_65plus"] = (df.loc[mask, "pop_total"]
                                       * df.loc[mask, "pct_65plus"] / 100)
    return df


def compute_lags_from_panel(df, panel):
    """Lag-based columns: pull from the existing panel (2017 → lag1=2017 of
    2018? Actually *_lag1 in 2018 = value at 2017; *_lag5 in 2018 = 2013).
    These come from full-in-progress.rebuilt for ipeds; for AHRF lag5 we
    pull from the existing regression-data-base rows.
    """
    # ipeds_rn_per_10k_lag1 in 2018 = ipeds_rn_per_10k in 2017 =
    # ipeds_completions_rn_2017 / pop_total_2017 * 10000.
    src17 = panel[panel.year == 2017][["fips", "ipeds_completions_rn",
                                        "ipeds_completions_lpn",
                                        "pop_total"]].copy()
    src17["pop_total"] = src17["pop_total"].replace(0, np.nan)
    src17["ipeds_rn_per_10k_lag1"] = (src17["ipeds_completions_rn"]
                                       / src17["pop_total"] * 10000)
    src17["ipeds_lpn_per_10k_lag1"] = (src17["ipeds_completions_lpn"]
                                        / src17["pop_total"] * 10000)
    src17 = src17[["fips", "ipeds_rn_per_10k_lag1",
                    "ipeds_lpn_per_10k_lag1"]]
    df = df.merge(src17, on="fips", how="left", suffixes=("", "_src"))
    for c in ("ipeds_rn_per_10k_lag1", "ipeds_lpn_per_10k_lag1"):
        if f"{c}_src" in df.columns:
            df[c] = df[c].combine_first(df[f"{c}_src"])
            df = df.drop(columns=[f"{c}_src"])

    # hosp_beds_per_1k_ahrf_lag5: 2018 value lags from 2013
    # nh_beds_per_65plus_ahrf_lag5: same.
    lag5 = (panel[panel.year == 2013][["fips", "hosp_beds_per_1k",
                                         "nh_beds_per_65plus_ahrf"]]
            .rename(columns={"hosp_beds_per_1k":
                              "hosp_beds_per_1k_ahrf_lag5",
                              "nh_beds_per_65plus_ahrf":
                              "nh_beds_per_65plus_ahrf_lag5"}))
    df = df.merge(lag5, on="fips", how="left", suffixes=("", "_src"))
    for c in ("hosp_beds_per_1k_ahrf_lag5", "nh_beds_per_65plus_ahrf_lag5"):
        if f"{c}_src" in df.columns:
            df[c] = df[c].combine_first(df[f"{c}_src"])
            df = df.drop(columns=[f"{c}_src"])

    # nh_beds_per_65plus_cms: not derivable here; leave NaN.
    return df


def main():
    panel = load_panel()
    panel_cols = list(panel.columns)
    if YEAR in panel.year.unique():
        raise SystemExit(f"{YEAR} already in {PANEL}; nothing to do.")
    print(f"Base panel: {panel.shape}, "
          f"years={sorted(panel.year.unique())}")

    new = base_2018(panel)
    print(f"Skeleton: {new.shape}")

    new = add_full_in_progress(new, set(panel_cols))
    print(f"After full-in-progress merge: {new.shape}")

    new = add_hcris(new)
    new = add_has_medicare_hospital(new, panel)
    print(f"After HCRIS + Medicare-flag merge: {new.shape}")

    new = add_chr(new)
    print(f"After CHR merge: {new.shape}")

    new = add_oews(new)
    print(f"After OEWS merge: {new.shape}")

    new = add_lightcast(new)
    print(f"After Lightcast merge: {new.shape}")

    new = broadcast_time_invariant(new, panel)
    new = broadcast_slow_moving(new, panel)
    new = fill_ipeds_zeros(new)
    new = compute_derived(new)
    new = fill_pop_65plus(new)
    new = compute_lags_from_panel(new, panel)

    # Ensure all panel columns exist; missing ones stay NaN.
    for c in panel_cols:
        if c not in new.columns:
            new[c] = np.nan
    new = new[panel_cols]
    assert list(new.columns) == panel_cols
    assert len(new) == 83

    out = (pd.concat([panel, new], ignore_index=True)
             .sort_values(["fips", "year"])
             .reset_index(drop=True))
    out.to_csv(PANEL, index=False)
    print(f"\nWrote {PANEL}")
    print(f"New shape: {out.shape}, years={sorted(out.year.unique())}")

    # Diagnostics: 2018 non-null counts per column, vs 2017
    nn18 = new.notna().sum()
    nn17 = panel[panel.year == 2017].notna().sum()
    diff = pd.DataFrame({"2017": nn17, "2018": nn18}).fillna(0).astype(int)
    diff["delta"] = diff["2018"] - diff["2017"]
    print("\nColumns where 2018 fill < 2017 fill (recovery gaps):")
    gap = diff[diff.delta < 0].sort_values("delta")
    print(gap.to_string())


if __name__ == "__main__":
    main()
