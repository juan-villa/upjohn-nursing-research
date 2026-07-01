"""Parse AHRF .asc files using their SAS layout (.sas) files.

The SAS INPUT block looks like:
     @00001    f00001   $  01.  /*Blank ... */
     @00478    f0978710 $  01.  /*HPSA Code - Primary Care  12/10 ...*/
     @0xxxxx   f<n>     [$]  <len>.  /*<description>*/

Output: a long county-year DataFrame with columns:
  fips_st_cnty, year, variable, value, _release

`variable` is mapped to the AHRF CSV human-readable name where the
description matches a known pattern; otherwise the raw f-code is kept.

Usage as a library:
    from parse_ahrf_asc import parse_release
    df = parse_release(asc_path, sas_path, release_label="2015-16",
                       state_fips="26")
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterator
import pandas as pd

# ---------------------------------------------------------------------------
# SAS layout parser
# ---------------------------------------------------------------------------
# Lines look like (whitespace-flexible):
#   @00478    f0978710 $  01.  /*HPSA Code - Primary Care  12/10 ...*/
#   @09371    f1467018    08.  /*Total Population  Census 2010 ...*/
INPUT_LINE = re.compile(
    r"@\s*0*(\d+)\s+"            # 1: start position (1-indexed)
    r"(f\d+\w*)\s+"              # 2: f-code
    r"(\$\s+)?"                  # 3: optional $ -> character
    r"0*(\d+)\.\s*"              # 4: length
    r"(?:/\*\s*(.*?)\s*\*/)?"    # 5: optional description
)


def parse_sas_layout(sas_path: Path) -> pd.DataFrame:
    text = Path(sas_path).read_text(errors="replace")
    rows = []
    for m in INPUT_LINE.finditer(text):
        start = int(m.group(1))
        f_code = m.group(2)
        is_char = m.group(3) is not None
        length = int(m.group(4))
        desc = (m.group(5) or "").strip()
        rows.append((start, length, f_code, is_char, desc))
    return pd.DataFrame(rows, columns=["start", "length", "f_code",
                                        "is_char", "description"])


# ---------------------------------------------------------------------------
# Description pattern -> AHRF-CSV variable name mapping
# ---------------------------------------------------------------------------
# Each entry: (regex on description, base name in AHRF CSV format).
# The 2-digit year suffix is extracted from the description independently.
#
# Patterns are evaluated in order; first match wins so put specific patterns
# before generic ones (e.g., "MDs Activ Non-Fed Excl Resdnt PC" before
# "MDs Activ Non-Fed Excl Resdnt").
DESCRIPTION_MAP = [
    # ---------- Physician supply (HP theme) ----------
    # NOTE: descriptions can use "M.D." or "MD", "DO's" or "DOs", etc.
    # Order: most-specific first.
    (re.compile(r"^Phys,\s*Primary\s+Care,\s*Patient\s+Care", re.I),
     "phys_nf_prim_care_pc_exc_rsdt"),
    (re.compile(r"^MD'?s?,\s*Primary\s+Care,\s*Patient\s+Care", re.I),
     "md_nf_prim_care_pc_excl_rsdnt"),
    (re.compile(r"^DO'?s?,\s*Primary\s+Care,\s*Patient\s+Care", re.I),
     "do_nf_prim_care_pc_excl_rsdnt"),
    (re.compile(r"Primary\s+Care\s+Resid(en)?t", re.I),
     "phys_nf_prim_care_pc_rsdnt"),
    # Active MD/DO totals (non-federal)
    (re.compile(r"Total\s+Active\s+M\.?D\.?'?s?\s+Non-?Federal", re.I),
     "md_nf_activ"),
    (re.compile(r"Total\s+Active\s+D\.?O\.?'?s?\s+Non-?Federal", re.I),
     "do_nf_activ"),
    (re.compile(r"Total\s+Active\s+D\.?O\.?'?s?", re.I), "do_nf_activ"),
    # Federal MDs
    (re.compile(r"Total\s+Active\s+M\.?D\.?'?s?\s+Federal", re.I),
     "md_nf_fed_activ"),
    # Practice setting
    (re.compile(r"M\.?D\.?'?s?,?\s*(Tot\s+)?Off(ice)?-?Bas(ed)?\s+P/?C",
                 re.I),
     "md_nf_pc_ofc"),
    (re.compile(r"M\.?D\.?'?s?,?\s*Tot\s+Hosp-Based\s+P/?C", re.I),
     "md_nf_pc_hosp_all"),
    # Specialty roll-ups (all in patient care)
    (re.compile(r"M\.?D\.?'?s?\s+(Total\s+)?Med(ical)?\s+Spec.*PC", re.I),
     "md_nf_all_med_spec_all_pc"),
    (re.compile(r"M\.?D\.?'?s?\s+(Total\s+)?Surg.*Spec.*PC", re.I),
     "md_nf_all_surg_spec_all_pc"),
    (re.compile(r"M\.?D\.?'?s?\s+(Total\s+)?Other\s+Spec.*PC", re.I),
     "md_nf_all_oth_spec_all_pc"),
    (re.compile(r"Fam(ily)?\s+Med.*Gen", re.I), "md_nf_fammed_gen_all_pc"),
    # ---------- Health facilities (HF theme) ----------
    # Critical access must come BEFORE generic Hospital patterns.
    (re.compile(r"#?\s*Critical\s+Access\s+ST\s+Gen\s+Hosps?", re.I), "stgh"),
    (re.compile(r"#?\s*Critical\s+Access\s+Hosp", re.I), "critcl_access_hosp"),
    (re.compile(r"Short.?Term\s+Gen.*Hospital", re.I), "stgh"),
    (re.compile(r"^Hospitals?\s*$|^#\s*Hospitals\s*$", re.I), "hosp"),
    (re.compile(r"Rural\s+Health\s+Clinic", re.I), "rural_hlth_clincs"),
    (re.compile(r"Fed(erally)?\s+Qual(ified)?\s+H(ea)?lth\s+C(en)?t", re.I),
     "fedly_qualfd_hlth_ctr"),
    (re.compile(r"Com(munity)?\s+Mental\s+Health\s+C(en)?t", re.I),
     "comn_mentl_hlth_ctr"),
    (re.compile(r"Nursing\s+Fac.*Beds?", re.I), "nurs_fac_beds"),
    (re.compile(r"\bNursing\s+Fac(ilit)?", re.I), "nurs_fac"),
    (re.compile(r"\bHospital\s+Beds?\b", re.I), "hosp_beds"),
    (re.compile(r"\bHosp(ital)?\s+Adm(iss|itt)?", re.I), "hosp_adm"),
    (re.compile(r"NHSC\s+Sites", re.I), "nhsc_sites"),
    (re.compile(r"NHSC\s+FTE\s+(All\s+)?Provdrs?", re.I), "nhsc_fte_provdrs"),
    # Hospital-employed nurses
    (re.compile(r"STGH.*LPN.*LVN", re.I), "stgh_fte_lpnlvn_incl_nh"),
    (re.compile(r"STGH.*Nurs(ing)?\s+Asst", re.I),
     "stgh_nursng_asst_ft_incl_nh"),
    (re.compile(r"STGH.*APRN", re.I), "stgh_aprn_ft"),
    # Medicare measures - 2015-16 descriptions use 'Medcre' and 'Mdcr'
    (re.compile(r"(Mdcr|Medcre).*Prev(en)?(table)?.*Hosp", re.I),
     "medcr_ffs_prev_hosp_rate"),
    (re.compile(r"(Mdcr|Medcre).*Hosp.*Readmiss\s+Rate", re.I),
     "medcr_ffs_hosp_readm_rate"),
    (re.compile(r"%\s*(Mdcr|Medcre).*El(igibl)?.*M(dcd|edicaid)|"
                 r"(Mdcr|Medcre).*Dually?\s+Eligible", re.I),
     "medcr_ffs_eligbl_medcd_pct"),
    # ---------- Disability (ACS 5-year, civilian noninstitutionalized) ----------
    # F15409 (with disability) and F15413 (without) form the rate.
    # Note: AHRF spells the second one "Disabilty" (sic).
    (re.compile(r"#\s*w/\s*Disabil[i]?ty\s+Civ(il)?\s+Noninst", re.I),
     "disab_with"),
    (re.compile(r"#\s*w/?o\s+Disabil[i]?ty\s+Civ(il)?\s+Noninst", re.I),
     "disab_without"),
    # ---------- ACS-derived structural covariates (AHRF-only mode) ----------
    # Education: F14452 (numerator) / F14440 (denominator); 5-year ACS pooled.
    # Order matters — "Persons 25+ w/4+ Yrs College" must beat "Persons 25+".
    (re.compile(r"Pers(ons|ns)?\s+25\+\s+(Yrs\s+)?w/?\s*4\+\s+Yrs?\s+Coll(ege)?",
                re.I),
     "pers_25plus_4yr_coll"),
    (re.compile(r"^Pers(ons|ns)?\s+25\+\s+Yrs?\b", re.I),
     "pers_25plus"),
    # Insurance (SAHIE): F15474 / F14751 already a percent (% <65 uninsured).
    (re.compile(r"%\s*<\s*65\s+without\s+Health\s+Insur(ance)?", re.I),
     "pct_uninsured_under65"),
    # Poverty (SAIPE): F13223 (count) — divide by popn_est for rate.
    (re.compile(r"^Persons?\s+in\s+Poverty\b", re.I),
     "persons_in_poverty"),
    # Population 65+ (F14083). Must be BEFORE generic popn_est pattern.
    (re.compile(r"Pop(ulation)?\s+Est(imate)?\s*65\+?", re.I),
     "pop_65plus"),
    # ---------- Population/Econ (POP theme) ----------
    (re.compile(r"Per\s+Capita\s+Pers(onal)?\s+Income", re.I),
     "per_cap_persnl_incom"),
    (re.compile(r"Veteran\s+Pop(ulation)?\s+Est", re.I), "vetn_popn_est"),
    (re.compile(r"Pop(ulation)?\s+Est(imate)?[^65]*$", re.I), "popn_est"),
    # ---------- HPSA flags (current vintage only) ----------
    (re.compile(r"HPSA.*Primary\s+Care", re.I), "hpsa_prim_care"),
    (re.compile(r"HPSA.*Dent", re.I), "hpsa_dent"),
    (re.compile(r"HPSA.*Ment(al)?\s+H(ea)?lth", re.I), "hpsa_mentl_hlth"),
    # ---------- Geography/typology (broadcast) ----------
    (re.compile(r"Rural-?Urban\s+Continuum", re.I), "rural_urban_contnm"),
    (re.compile(r"Urban\s+Influence", re.I), "urban_influnc"),
    (re.compile(r"Core\s+Based\s+Stat.*Code", re.I), "cbsa"),
    (re.compile(r"Core\s+Based\s+Stat.*Name", re.I), "cbsa_name"),
    (re.compile(r"CBSA\s+Indicator", re.I), "cbsa_ind"),
    (re.compile(r"Econ.*Depen?d.*Typol", re.I), "econ_depndnt_typolgy"),
    (re.compile(r"Mfg|Manufactur.*Depen?d.*Typol", re.I),
     "mfg_depndnt_typolgy"),
    (re.compile(r"Recreation\s+Typol", re.I), "recrtn_typolgy"),
    (re.compile(r"High\s+Poverty\s+Typol", re.I), "hi_povty_typolgy"),
    (re.compile(r"Persistent\s+Pov(rty|erty)\s+Typol", re.I),
     "prstnt_povty_typolgy"),
    (re.compile(r"Pop(ulation)?\s+Loss\s+Typol", re.I), "popn_loss_typolgy"),
    (re.compile(r"Retire.*Typol", re.I), "retrmnt_destntn_typolgy"),
    (re.compile(r"Pop(ulation)?\s+Density\s+per\s+Sqr?\s+Mi", re.I),
     "popn_densty_per_squr_mi"),
    (re.compile(r"Land\s+Area", re.I), "land_area_mi2"),
    # ---------- IDs ----------
    (re.compile(r"Header\s*-\s*FIPS", re.I), "fips_st_cnty"),
    (re.compile(r"County\s+Name\s+w/State\s+Abbrev", re.I),
     "cnty_name_st_abbrev"),
]

# Extract year suffix from description like:
#   "HPSA Code - Primary Care  05/15"
#   "MDs Active Non-Fed Excl Resdnt PC  12/20"
#   "Total Population YR 2018 ..."
#   "Births 3yr avg ending 2017"
YEAR_PATTERNS = [
    re.compile(r"(?:^|\s)0?[1-9]/(\d{2})\b"),     # 05/15 or 5/15
    re.compile(r"\b(?:19|20)(\d{2})\b"),           # 2015 -> 15
    re.compile(r"(?:YR|year)\s*0?(\d{2})\b", re.I),  # YR15 / yr 15
]


def _year_from_fcode(f_code: str) -> str | None:
    """AHRF f-codes encode the data year as the last 2 digits when the
    code is >=7 characters total (e.g., f0978716 -> year 16, HPSA 2016).
    Codes <=6 chars are typically static system fields."""
    digits = f_code[1:]  # strip leading 'f'
    if len(digits) < 7:
        return None
    yy = digits[-2:]
    if not yy.isdigit():
        return None
    iyy = int(yy)
    # Accept 00-30 as 2000-2030; reject anything else as not-a-year.
    if 0 <= iyy <= 30:
        return yy
    return None


def annotate_layout(layout: pd.DataFrame) -> pd.DataFrame:
    out = layout.copy()
    names = []
    years = []
    for _, row in out.iterrows():
        desc = row["description"]
        f_code = row["f_code"]
        name = None
        for pat, base in DESCRIPTION_MAP:
            if pat.search(desc):
                name = base
                break
        names.append(name)
        # ID columns are static (no year suffix)
        if name in ("fips_st_cnty", "cnty_name_st_abbrev"):
            years.append(None)
        else:
            years.append(_year_from_fcode(f_code))
    out["csv_name"] = names
    out["year_suffix"] = years
    return out


# ---------------------------------------------------------------------------
# .asc reader
# ---------------------------------------------------------------------------
def read_asc(asc_path: Path, layout: pd.DataFrame,
              state_fips: str = "26") -> pd.DataFrame:
    """Read fixed-width .asc file using layout. Returns long DataFrame
    with mapped variable names, year-suffixed, filtered to state."""
    # Only keep rows with a csv_name AND a year_suffix; skip ID columns
    # that we'll grab separately.
    id_layout = layout[layout["csv_name"].isin(
        ["fips_st_cnty", "cnty_name_st_abbrev"])]
    var_layout = layout[layout["csv_name"].notna()
                          & layout["year_suffix"].notna()].copy()

    if id_layout.empty or var_layout.empty:
        return pd.DataFrame()

    # Build the full read spec
    keep = pd.concat([id_layout, var_layout], ignore_index=True)
    colspecs = [(int(r["start"]) - 1, int(r["start"]) - 1 + int(r["length"]))
                for _, r in keep.iterrows()]
    names = []
    for _, r in keep.iterrows():
        if r["csv_name"] in ("fips_st_cnty", "cnty_name_st_abbrev"):
            names.append(r["csv_name"])
        else:
            names.append(f"{r['csv_name']}__{r['year_suffix']}__{r['f_code']}")

    df = pd.read_fwf(asc_path, colspecs=colspecs, names=names,
                     dtype=str, header=None, encoding="latin-1")
    df["fips_st_cnty"] = df["fips_st_cnty"].str.zfill(5)
    df = df[df["fips_st_cnty"].str.startswith(state_fips)].copy()

    # Long format
    id_cols = ["fips_st_cnty", "cnty_name_st_abbrev"]
    val_cols = [c for c in df.columns if c not in id_cols]
    long = df.melt(id_vars=id_cols, value_vars=val_cols,
                    var_name="_compound", value_name="value")
    parts = long["_compound"].str.split("__", expand=True)
    long["variable"] = parts[0]
    long["year_suffix"] = parts[1]
    long["f_code"] = parts[2]
    long = long.drop(columns=["_compound"])

    # Coalesce when multiple f-codes map to same (variable, year): keep first
    # non-null. (Different theme files in CSV releases can hit the same var.)
    long["value"] = pd.to_numeric(long["value"].str.strip(), errors="coerce")
    long["year"] = 2000 + pd.to_numeric(long["year_suffix"], errors="coerce")
    long["year"] = long["year"].astype("Int64")
    long = long.dropna(subset=["value", "year"])
    long = (long.sort_values(["fips_st_cnty", "variable", "year"])
                .drop_duplicates(["fips_st_cnty", "variable", "year"],
                                  keep="first"))
    return long[["fips_st_cnty", "cnty_name_st_abbrev", "year",
                  "variable", "value", "f_code"]]


def parse_release(asc_path: str, sas_path: str, release_label: str,
                   state_fips: str = "26") -> pd.DataFrame:
    layout = annotate_layout(parse_sas_layout(Path(sas_path)))
    df = read_asc(Path(asc_path), layout, state_fips=state_fips)
    df["_release"] = release_label
    return df


# ---------------------------------------------------------------------------
# CSV-format AHRF releases (2022-23 onward)
# ---------------------------------------------------------------------------
# Recent AHRF releases distribute county data as CSV with columns like
# `popn_est_22`, `hosp_beds_21`, `pers_4yrs_collg_ge25_21`. The same
# DESCRIPTION_MAP regexes apply — the only difference is where the
# description text comes from (the documentation xlsx rather than the
# SAS layout comments).
def _build_csv_var_map(doc_xlsx: Path) -> dict:
    """Parse the AHRF CSV documentation xlsx. Returns
    {csv_col_name: canonical_variable_name} using DESCRIPTION_MAP.

    The xlsx has columns: FIELD | CAT | YEAR OF DATA | VARIABLE NAME | ...
    FIELD is the CSV column name (with year suffix); VARIABLE NAME is the
    human description we run DESCRIPTION_MAP against.
    """
    import openpyxl
    wb = openpyxl.load_workbook(doc_xlsx, read_only=True, data_only=True)
    ws = wb.active
    out = {}
    for row in ws.iter_rows(values_only=True):
        if not row or len(row) < 4:
            continue
        field = str(row[0]).strip() if row[0] else ""
        desc  = str(row[3]).strip() if row[3] else ""
        if not field or not desc or field.upper() == "FIELD":
            continue
        for pat, base_name in DESCRIPTION_MAP:
            if pat.search(desc):
                out[field] = base_name
                break
    return out


def parse_csv_release(csv_path: str, doc_xlsx_path: str, release_label: str,
                       state_fips: str = "26") -> pd.DataFrame:
    """Parse an AHRF CSV-format release. Returns the same long-format
    DataFrame as parse_release: fips_st_cnty, year, variable, value,
    _release."""
    col2var = _build_csv_var_map(Path(doc_xlsx_path))
    if not col2var:
        raise ValueError(f"No DESCRIPTION_MAP matches found in {doc_xlsx_path}")

    df = pd.read_csv(csv_path, dtype=str, low_memory=False,
                     encoding="latin-1")
    if "fips_st_cnty" not in df.columns:
        raise ValueError(f"fips_st_cnty column missing in {csv_path}")
    df["fips_st_cnty"] = df["fips_st_cnty"].astype(str).str.zfill(5)
    df = df[df["fips_st_cnty"].str.startswith(state_fips)].copy()

    # Identify columns to melt: must end in _YY (00-30) and have a mapped variable
    col_pat = re.compile(r"^(.+)_(\d{2})$")
    melt_cols = []
    col_meta: dict[str, tuple[str, int]] = {}
    for col in df.columns:
        m = col_pat.match(col)
        if not m:
            continue
        try:
            iyy = int(m.group(2))
        except ValueError:
            continue
        if not (0 <= iyy <= 30):
            continue
        var = col2var.get(col)
        if not var:
            continue
        melt_cols.append(col)
        col_meta[col] = (var, 2000 + iyy)

    if not melt_cols:
        return pd.DataFrame(columns=["fips_st_cnty", "year", "variable",
                                       "value", "_release"])

    sub = df[["fips_st_cnty"] + melt_cols].copy()
    long = sub.melt(id_vars=["fips_st_cnty"], value_vars=melt_cols,
                     var_name="col", value_name="value")
    long["variable"] = long["col"].map(lambda c: col_meta[c][0])
    long["year"]     = long["col"].map(lambda c: col_meta[c][1]).astype("Int64")
    long["value"]    = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    # Coalesce duplicates that arise when multiple csv cols map to the same
    # variable+year (e.g., race-disaggregated rows).
    long = long.drop_duplicates(["fips_st_cnty", "year", "variable"],
                                  keep="first")
    long["_release"] = release_label
    return long[["fips_st_cnty", "year", "variable", "value", "_release"]]


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    REF = Path("/Users/juanvilla/Documents/gse-580-final-proposal/ahrf_data")
    L = REF / "layouts"
    cases = [
        ("2015-16", REF / "ahrf2016.asc", L / "ahrf_2015-16.sas"),
        ("2019-20", REF / "ahrf2020.asc", L / "ahrf_2019-20.sas"),
        ("2020-21", REF / "ahrf2021.asc", L / "ahrf_2020-21.sas"),
        ("2021-22", REF / "ahrf2022.asc", L / "ahrf_2021-22.sas"),
    ]
    for label, asc, sas in cases:
        if not asc.exists() or not sas.exists():
            print(f"[skip] {label}: missing files")
            continue
        layout = annotate_layout(parse_sas_layout(sas))
        n_named = layout["csv_name"].notna().sum()
        print(f"\n=== {label} ===")
        print(f"  SAS layout rows: {len(layout)}")
        print(f"  mapped to known vars: {n_named}")
        print(f"  with year suffix: "
              f"{(layout['csv_name'].notna() & layout['year_suffix'].notna()).sum()}")
        df = read_asc(asc, layout)
        if df.empty:
            print("  (no data extracted)")
            continue
        print(f"  long rows for MI: {len(df)}")
        print(f"  unique variables: {df['variable'].nunique()}")
        print(f"  years: {sorted(df['year'].dropna().unique().tolist())}")
        wayne = df[df.fips_st_cnty == "26163"].sort_values(
            ["variable", "year"])
        sample = wayne[wayne["variable"] == "phys_nf_prim_care_pc_exc_rsdt"]
        if len(sample):
            print("  Wayne County primary-care MDs:")
            print(sample[["year", "value"]].head(10).to_string(index=False))
