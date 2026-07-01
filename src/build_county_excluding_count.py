"""Build county_excluding_count.csv — county-year panel of all regressors
*except* the licensed-nurse count DV.

Output: /Users/juanvilla/Documents/gse-580-clean/county_excluding_count.csv
        83 MI counties x 13 years (2010-2017, 2019-2023) = 1,079 rows

Layers:
  1. ACS 5-year (Census API, per-year pull)
  2. CHR (from gse-580-final-proposal long panel)
  3. IPEDS nursing completions (aggregated to county-year)
  4. AHRF 2020-2023 CSV releases (stitched) + time-invariant typology broadcast
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import requests

ROOT = Path("/Users/juanvilla/Documents/gse-580-clean")
REF = Path("/Users/juanvilla/Documents/gse-580-final-proposal")
OUT = ROOT / "county_excluding_count.csv"

STATE_FIPS = "26"
YEARS = [y for y in range(2010, 2024) if y != 2018]
CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")


# ---------------------------------------------------------------------------
# Layer 1: ACS 5-year
# ---------------------------------------------------------------------------
def acs5_url(year, vars_):
    base = f"https://api.census.gov/data/{year}/acs/acs5"
    url = f"{base}?get={','.join(vars_)}&for=county:*&in=state:{STATE_FIPS}"
    if CENSUS_KEY:
        url += f"&key={CENSUS_KEY}"
    return url


def pull_acs_year(year):
    age_m = [f"B01001_{i:03d}E" for i in range(20, 26)]      # males 65+
    age_f = [f"B01001_{i:03d}E" for i in range(44, 50)]      # females 65+
    # prime-age 25-54: males 011-016, females 035-040
    prime_m = [f"B01001_{i:03d}E" for i in range(11, 17)]
    prime_f = [f"B01001_{i:03d}E" for i in range(35, 41)]
    edu_high = [f"B15003_{i:03d}E" for i in range(22, 26)]   # BA, MA, prof, doc
    uninsured = [f"B27001_{i:03d}E" for i in
                 [5, 8, 11, 14, 17, 20, 23, 26, 29,
                  33, 36, 39, 42, 45, 48, 51, 54, 57]]
    commute_30plus = [f"B08303_{i:03d}E" for i in range(8, 14)]
    # Full B08303 distribution for bucket-midpoint mean (B08136/B08101 is
    # suppressed for ~half of MI counties).
    commute_all_buckets = [f"B08303_{i:03d}E" for i in range(2, 14)]
    # Renter & owner housing-cost burden (Section 2C of reference PDF).
    rent_burden = [f"B25070_{i:03d}E" for i in (7, 8, 9, 10)]
    own_burden = [f"B25091_{i:03d}E" for i in (8, 9, 10, 11)]

    detail = (["B01001_001E"] + age_m + age_f + prime_m + prime_f
              + ["B19013_001E", "B25064_001E", "B25077_001E",
                 "B23025_002E", "B23025_003E", "B23025_005E",
                 "B15003_001E"] + edu_high
              + ["B27001_001E"] + uninsured
              + ["B08303_001E"] + commute_all_buckets
              + ["B17001_001E", "B17001_002E",
                 "B02001_002E", "B02001_003E", "B02001_005E",
                 "B03002_012E",
                 "B25070_001E"] + rent_burden
              + ["B25091_001E"] + own_burden)

    # Census API caps GET at 50 vars/request; batch into chunks. Some
    # tables (B15003, B27001) started in 2012 — fall back to per-var calls
    # for any chunk that 400s so missing vars don't kill the whole year.
    BATCH = 45
    d = None

    def _fetch(vars_):
        r = requests.get(acs5_url(year, vars_), timeout=120)
        r.raise_for_status()
        rows = r.json()
        part = pd.DataFrame(rows[1:], columns=rows[0])
        part["fips"] = part["state"] + part["county"]
        return part[[c for c in vars_ if c in part.columns] + ["fips"]]

    for i in range(0, len(detail), BATCH):
        chunk = detail[i:i + BATCH]
        try:
            part = _fetch(chunk)
        except requests.HTTPError:
            # Retry one variable at a time; skip those that 400
            sub = None
            for v in chunk:
                try:
                    p = _fetch([v])
                    sub = p if sub is None else sub.merge(p, on="fips", how="outer")
                except requests.HTTPError:
                    pass
            part = sub
        if part is None:
            continue
        d = part if d is None else d.merge(part, on="fips", how="outer")
    # Ensure all expected columns exist (NaN where API didn't return them)
    for c in detail:
        if c not in d.columns:
            d[c] = np.nan
        d[c] = pd.to_numeric(d[c], errors="coerce")

    out = pd.DataFrame({"fips": d["fips"], "year": year})
    out["pop_total"] = d["B01001_001E"]
    pop65 = d[age_m + age_f].sum(axis=1)
    pop2554 = d[prime_m + prime_f].sum(axis=1)
    out["pop_65plus"] = pop65
    out["pct_65plus"] = (pop65 / out["pop_total"] * 100).round(2)
    out["pop_25_54"] = pop2554
    out["pct_25_54"] = (pop2554 / out["pop_total"] * 100).round(2)
    out["median_hh_income"] = d["B19013_001E"]
    out["median_gross_rent"] = d["B25064_001E"]
    out["median_home_value"] = d["B25077_001E"]
    out["unemployment_rate"] = (d["B23025_005E"] / d["B23025_003E"] * 100).round(2)
    out["lfp_rate"] = (d["B23025_002E"] / d["B01001_001E"] * 100).round(2)
    out["pct_bachelors_plus"] = (d[edu_high].sum(axis=1)
                                  / d["B15003_001E"] * 100).round(2)
    out["pct_uninsured"] = (d[uninsured].sum(axis=1)
                             / d["B27001_001E"] * 100).round(2)
    out["pct_commute_30plus"] = (d[commute_30plus].sum(axis=1)
                                  / d["B08303_001E"] * 100).round(2)
    # Mean commute minutes from B08303 bucket midpoints. Full coverage
    # (B08136/B08101 is disclosure-suppressed for ~half of MI counties).
    # Bucket spec: <5, 5-9, 10-14, 15-19, 20-24, 25-29, 30-34, 35-39,
    # 40-44, 45-59, 60-89, 90+ -> midpoints below (open-ended top capped
    # at 105 minutes as a conservative estimate).
    BUCKET_MIDPOINTS = [2.5, 7, 12, 17, 22, 27, 32, 37, 42, 52, 74.5, 105]
    weighted = sum(d[col] * mid for col, mid in
                    zip(commute_all_buckets, BUCKET_MIDPOINTS))
    out["mean_commute_minutes"] = (weighted / d["B08303_001E"]).round(2)
    # Housing cost burden: % of renter / owner households spending 30%+ of
    # income on housing.
    out["rent_burden_pct"] = (d[rent_burden].sum(axis=1)
                               / d["B25070_001E"] * 100).round(2)
    out["own_burden_pct"] = (d[own_burden].sum(axis=1)
                              / d["B25091_001E"] * 100).round(2)
    out["poverty_rate"] = (d["B17001_002E"] / d["B17001_001E"] * 100).round(2)
    out["pct_white"] = (d["B02001_002E"] / d["B01001_001E"] * 100).round(2)
    out["pct_black"] = (d["B02001_003E"] / d["B01001_001E"] * 100).round(2)
    out["pct_asian"] = (d["B02001_005E"] / d["B01001_001E"] * 100).round(2)
    out["pct_hispanic"] = (d["B03002_012E"] / d["B01001_001E"] * 100).round(2)
    return out


def build_acs():
    frames = []
    for y in YEARS:
        try:
            f = pull_acs_year(y)
            frames.append(f)
            print(f"  ACS5 {y}: {len(f)} counties")
        except Exception as e:
            print(f"  ACS5 {y}: FAILED -- {e}")
        time.sleep(0.4)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Layer 2: CHR (read existing long panel from reference project)
# ---------------------------------------------------------------------------
CHR_MEASURES = [
    ("premature death",
     ["Years of Potential Life Lost Rate", "YPLL Rate"],
     "chr_premature_death_rate"),
    ("preventable hospital stays",
     ["Preventable Hospitalization Rate", "Preventable Hosp. Rate",
      "Preventable Hospital Stays Rate"],
     "chr_preventable_hosp_rate"),
    ("poor or fair health",
     ["% Fair/Poor", "% Fair or Poor Health"],
     "chr_pct_fair_poor_health"),
    ("low birthweight",
     ["% LBW", "% Low Birthweight"],
     "chr_pct_low_birthweight"),
    ("primary care physicians",
     ["Primary Care Physicians Rate", "PCP Rate"],
     "chr_pcp_rate"),
    ("dentists", ["Dentist Rate"], "chr_dentist_rate"),
    ("uninsured", ["% Uninsured"], "chr_pct_uninsured"),
    ("adult smoking",
     ["% Smokers", "% Adults Reporting Currently Smoking", "% Currently Smoking"],
     "chr_pct_adult_smoking"),
    ("adult obesity",
     ["% Obese", "% Adults with Obesity"],
     "chr_pct_adult_obesity"),
    ("poor mental health days",
     ["Mentally Unhealthy Days", "Average Number of Mentally Unhealthy Days"],
     "chr_avg_mental_unhealthy_days"),
    ("children in poverty", ["% Children in Poverty"], "chr_pct_children_in_poverty"),
]


def build_chr():
    long = pd.read_csv(REF / "data/chr_michigan_panel.csv", dtype={"fips": str})
    long["fips"] = long["fips"].str.zfill(5)
    pieces = []
    for chr_name, subs, out_col in CHR_MEASURES:
        sub = long[(long["measure"] == chr_name) & (long["sub_col"].isin(subs))]
        if sub.empty:
            print(f"  CHR {out_col}: no rows")
            continue
        wide = (sub.pivot_table(index=["year", "fips"], columns="sub_col",
                                 values="value", aggfunc="first")
                  .reset_index())
        existing = [s for s in subs if s in wide.columns]
        wide[out_col] = wide[existing].bfill(axis=1).iloc[:, 0]
        pieces.append(wide[["year", "fips", out_col]])
        print(f"  CHR {out_col}: n={wide[out_col].notna().sum()}")
    chr_w = pieces[0]
    for p in pieces[1:]:
        chr_w = chr_w.merge(p, on=["year", "fips"], how="outer")
    return chr_w


# ---------------------------------------------------------------------------
# Layer 3: IPEDS nursing completions
# ---------------------------------------------------------------------------
def build_ipeds():
    p = ROOT / "data_next_steps/05_ipeds_nursing_completions_mi_2005_2023.csv"
    df = pd.read_csv(p, dtype={"COUNTYCD": str})
    df["fips"] = df["COUNTYCD"].str.zfill(5)
    # Aggregate completions per (fips, year, occ_track)
    pivoted = (df.groupby(["fips", "year", "occ_track"])["CTOTALT"]
                 .sum().unstack("occ_track", fill_value=0).reset_index())
    pivoted.columns.name = None
    # Rename track columns
    rename = {c: f"ipeds_completions_{c}" for c in pivoted.columns
              if c not in ("fips", "year")}
    pivoted = pivoted.rename(columns=rename)
    pivoted["ipeds_completions_total"] = pivoted[list(rename.values())].sum(axis=1)
    print(f"  IPEDS: {len(pivoted)} county-year rows, "
          f"tracks={list(rename.values())}")
    return pivoted


# ---------------------------------------------------------------------------
# Layer 4: AHRF (2020-2023 CSV stitching + typology broadcast)
# ---------------------------------------------------------------------------
AHRF_HP_BASES = [
    "phys_nf_prim_care_pc_exc_rsdt", "phys_nf_prim_care_pc_rsdnt",
    "md_nf_activ", "do_nf_activ", "md_nf_fed_activ",
    "md_nf_pc_ofc", "md_nf_pc_hosp_all",
    "md_nf_all_med_spec_all_pc", "md_nf_all_surg_spec_all_pc",
    "md_nf_all_oth_spec_all_pc",
    "md_nf_fammed_gen_all_pc",
]
AHRF_HF_BASES = [
    "hosp", "stgh", "critcl_access_hosp", "rural_hlth_clincs",
    "fedly_qualfd_hlth_ctr", "comn_mentl_hlth_ctr",
    "nurs_fac", "nurs_fac_beds", "hosp_beds", "hosp_adm",
    "nhsc_sites", "nhsc_fte_provdrs",
    "medcr_ffs_prev_hosp_rate", "medcr_ffs_hosp_readm_rate",
    "stgh_fte_lpnlvn_incl_nh", "stgh_nursng_asst_ft_incl_nh",
    "stgh_aprn_ft", "stgh_aprn_pa",
]
AHRF_POP_BASES = [
    "per_cap_persnl_incom", "medcr_ffs_eligbl_medcd_pct",
    "vetn_popn_est", "popn_est",
]
AHRF_GEO_STATIC = [
    "rural_urban_contnm", "urban_influnc",
    "cbsa", "cbsa_name", "cbsa_ind",
    "econ_depndnt_typolgy", "mfg_depndnt_typolgy",
    "recrtn_typolgy", "hi_povty_typolgy",
    "prstnt_povty_typolgy", "popn_loss_typolgy",
    "retrmnt_destntn_typolgy",
]
AHRF_HPSA_STATIC = ["hpsa_prim_care", "hpsa_dent", "hpsa_mentl_hlth"]
AHRF_ENV_STATIC = ["popn_densty_per_squr_mi", "land_area_mi2"]

AHRF_RELEASES = [
    ("2023", REF / "ahrf_data/AHRF_CSV_2022-2023/DATA/CSV Files by Categories"),
    ("2024", REF / "ahrf_data/AHRF 2023-2024 CSV/CSV Files by Categories"),
    ("2025", REF / "ahrf_data/NCHWA-2024-2025+AHRF+COUNTY+CSV"),
]


def _match_cols(df_cols, bases):
    """Match base or base_YY (2-digit year)."""
    matched = {}
    for c in df_cols:
        for b in bases:
            if c == b:
                matched.setdefault(b, []).append((c, None))
            elif c.startswith(b + "_") and len(c) == len(b) + 3 and c[-2:].isdigit():
                matched.setdefault(b, []).append((c, c[-2:]))
    return matched


def _read_csv(dirpath, suffix):
    """Find a file like 'AHRF2025hp.csv' or 'ahrf2024hp.csv' in dirpath."""
    candidates = list(Path(dirpath).glob(f"*{suffix}.csv")) + \
                 list(Path(dirpath).glob(f"*{suffix.upper()}.csv"))
    if not candidates:
        return None
    return pd.read_csv(candidates[0], dtype={"fips_st_cnty": str},
                       low_memory=False)


def _theme_long(theme_suffix, bases, release_label, dirpath):
    df = _read_csv(dirpath, theme_suffix)
    if df is None:
        return pd.DataFrame()
    df["fips_st_cnty"] = df["fips_st_cnty"].str.zfill(5)
    df = df[df["fips_st_cnty"].str.startswith(STATE_FIPS)].copy()
    matched = _match_cols(df.columns, bases)
    rows = []
    for base, hits in matched.items():
        for col, yy in hits:
            if yy is None:
                # static — emit one row per county with year=None marker
                for _, r in df.iterrows():
                    rows.append((r["fips_st_cnty"], None, base, r[col]))
            else:
                yr = 2000 + int(yy)
                for _, r in df.iterrows():
                    rows.append((r["fips_st_cnty"], yr, base, r[col]))
    L = pd.DataFrame(rows, columns=["fips", "year", "variable", "value"])
    L["_release"] = release_label
    return L


def build_ahrf():
    frames = []
    for label, d in AHRF_RELEASES:
        for theme, bases in [("hp", AHRF_HP_BASES),
                              ("hf", AHRF_HF_BASES),
                              ("pop", AHRF_POP_BASES)]:
            f = _theme_long(theme, bases, label, d)
            if not f.empty:
                frames.append(f)
                print(f"  AHRF {label}/{theme}: {len(f)} long rows")
    if not frames:
        return pd.DataFrame(), pd.DataFrame()
    long = pd.concat(frames, ignore_index=True)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    # Prefer newest release for overlapping (fips, year, variable)
    rank = {"2023": 1, "2024": 2, "2025": 3}
    long["_rank"] = long["_release"].map(rank)
    timevar = long.dropna(subset=["year"]).sort_values("_rank")
    timevar = timevar.drop_duplicates(["fips", "year", "variable"], keep="last")
    timevar_wide = (timevar.pivot_table(index=["fips", "year"],
                                         columns="variable", values="value",
                                         aggfunc="first").reset_index())
    timevar_wide.columns.name = None
    timevar_wide["year"] = timevar_wide["year"].astype(int)

    # Static (typology / HPSA current / env) — broadcast across all years.
    # Pull from the 2025 release's geo + env files (most current).
    static_frames = []
    geo_df = _read_csv(REF / "ahrf_data/NCHWA-2024-2025+AHRF+COUNTY+CSV", "geo")
    env_df = _read_csv(REF / "ahrf_data/NCHWA-2024-2025+AHRF+COUNTY+CSV", "env")
    for df, basis in [(geo_df, AHRF_GEO_STATIC + AHRF_HPSA_STATIC),
                       (env_df, AHRF_ENV_STATIC)]:
        if df is None:
            continue
        df["fips_st_cnty"] = df["fips_st_cnty"].astype(str).str.zfill(5)
        df = df[df["fips_st_cnty"].str.startswith(STATE_FIPS)].copy()
        # For typology with year-suffix (e.g., _15, _22), pick most recent
        keep_cols = ["fips_st_cnty"]
        out_map = {}
        for base in basis:
            cands = [c for c in df.columns
                     if c == base
                     or (c.startswith(base + "_") and len(c) == len(base) + 3
                         and c[-2:].isdigit())]
            if not cands:
                continue
            latest = sorted(cands, key=lambda c: c[-2:] if c != base else "00")[-1]
            out_map[base] = df[latest]
        if not out_map:
            continue
        sd = pd.DataFrame({"fips": df["fips_st_cnty"]})
        for k, v in out_map.items():
            sd[k] = v.values
        static_frames.append(sd)
    if static_frames:
        static = static_frames[0]
        for s in static_frames[1:]:
            static = static.merge(s, on="fips", how="outer")
    else:
        static = pd.DataFrame()
    print(f"  AHRF time-varying: {timevar_wide.shape}, static: {static.shape}")
    return timevar_wide, static


# ---------------------------------------------------------------------------
# County name (use from AHRF geo)
# ---------------------------------------------------------------------------
def get_county_names():
    df = _read_csv(REF / "ahrf_data/NCHWA-2024-2025+AHRF+COUNTY+CSV", "geo")
    df["fips_st_cnty"] = df["fips_st_cnty"].astype(str).str.zfill(5)
    df = df[df["fips_st_cnty"].str.startswith(STATE_FIPS)]
    df = df[["fips_st_cnty", "cnty_name_st_abbrev"]].copy()
    df["county_name"] = (df["cnty_name_st_abbrev"].astype(str)
                          .str.replace(", MI", "", regex=False)
                          .str.strip())
    return df.rename(columns={"fips_st_cnty": "fips"})[["fips", "county_name"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not CENSUS_KEY:
        print("ERROR: CENSUS_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    print("[1/4] ACS 5-year ...")
    acs = build_acs()
    print(f"  ACS shape: {acs.shape}")

    print("[2/4] CHR ...")
    chr_df = build_chr()
    print(f"  CHR shape: {chr_df.shape}")

    print("[3/4] IPEDS ...")
    ipeds = build_ipeds()
    print(f"  IPEDS shape: {ipeds.shape}")

    print("[4/4] AHRF ...")
    ahrf_var, ahrf_static = build_ahrf()

    # Skeleton: 83 MI counties x 13 years
    names = get_county_names()
    counties = names["fips"].tolist()
    skel = pd.MultiIndex.from_product([counties, YEARS],
                                       names=["fips", "year"]).to_frame(index=False)
    skel = skel.merge(names, on="fips", how="left")

    # Merge layers
    merged = (skel
              .merge(acs, on=["fips", "year"], how="left")
              .merge(chr_df, on=["fips", "year"], how="left")
              .merge(ipeds, on=["fips", "year"], how="left")
              # counties without any nursing school in a given year have no
              # IPEDS row -> treat missing as 0 completions
              .assign(**{c: lambda d, c=c: d[c].fillna(0)
                          for c in ipeds.columns if c not in ("fips", "year")})
              .merge(ahrf_var, on=["fips", "year"], how="left")
              .merge(ahrf_static, on="fips", how="left"))

    # Order columns: ids, ACS, CHR, IPEDS, AHRF time-varying, AHRF static
    id_cols = ["fips", "county_name", "year"]
    acs_cols = [c for c in acs.columns if c not in ("fips", "year")]
    chr_cols = [c for c in chr_df.columns if c not in ("fips", "year")]
    ipeds_cols = [c for c in ipeds.columns if c not in ("fips", "year")]
    ahrf_var_cols = [c for c in ahrf_var.columns
                     if c not in ("fips", "year")] if not ahrf_var.empty else []
    ahrf_st_cols = [c for c in ahrf_static.columns
                    if c != "fips"] if not ahrf_static.empty else []
    ordered = id_cols + acs_cols + chr_cols + ipeds_cols + ahrf_var_cols + ahrf_st_cols
    ordered = [c for c in ordered if c in merged.columns]
    merged = merged[ordered].sort_values(["fips", "year"]).reset_index(drop=True)

    merged.to_csv(OUT, index=False)
    print(f"\n[done] {OUT}")
    print(f"  shape: {merged.shape}")
    print(f"  counties: {merged['fips'].nunique()}")
    print(f"  years: {sorted(merged['year'].unique())}")


if __name__ == "__main__":
    main()
