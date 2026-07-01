"""
hcris_utilization_s3.py
-----------------------
Extracts Worksheet S-3 Part I utilization data from cached HCRIS HOSP10 zips
(2011-2024, form 2552-10). Produces a long-format CSV with every S-3 Part I
cell for Michigan hospitals, so you can pick the exact (line, column) pairs
your analysis needs without re-parsing.

Outputs to /data_next_steps/:
    hcris_s3_part1_long_mi.csv         (one row per provider × fy × line × col)
    hcris_s3_part1_wide_mi.csv         (curated wide-format with common cells)

PRE-2011 NOTE
-------------
HCRIS form 2552-96 (cost reports starting before 5/1/2010) lives in the
HOSP9610 dataset, with DIFFERENT worksheet codes and line numbers. This
script does not handle 2552-96. For 2005-2010 coverage you need to:
    1. Download HOSP9610_FY{2005..2010}.zip from
       https://www.cms.gov/data-research/statistics-trends-and-reports/
       cost-reports/hospital-2552-96-form
    2. Map old worksheet codes: 2552-96 Worksheet S-3 Part I has code "S30001"
       (different from 2552-10's "S300001"); column/line definitions differ.
    3. Use a published crosswalk (e.g. the RAND HCRIS crosswalk or NBER's).

The 2010-form-only output is still useful — it doubles your panel length
without the methodological break.

KEY CELLS (form 2552-10 Worksheet S-3 Part I)
---------------------------------------------
Line 14 = "Total facility" (all units combined). Columns:
    col 02  Beds available
    col 04  Bed days available
    col 06  Inpatient days, Title V
    col 07  Inpatient days, Title XVIII
    col 08  Inpatient days, Title XIX
    col 12  Inpatient days, Other
    (per CMS documentation; verify against the latest form revision)
Line 14 also reports discharges in a different column block in some
versions. ALWAYS validate against the CMS Provider Reimbursement Manual
cell-mapping before publishing numbers — column definitions are versioned.

Discharges typically appear on S-3 Part I lines for each unit type or are
reported on Worksheet S-3 Part I, Line 14, columns 13-15 (V/XVIII/XIX) and
line 14 column 16 in some vintages. Because of version drift we extract
ALL columns for line 14 and let analysis code pick.

USAGE
-----
    python scripts/next_steps/hcris_utilization_s3.py
"""
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data" / "cache"
OUT_DIR = ROOT / "data_next_steps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2011, 2025))

# Michigan provider numbers start with state code "23"
MI_PRVDR_PREFIX = "23"


def parse_year(year):
    fn = CACHE / f"HOSP10FY{year}.zip"
    if not fn.exists():
        print(f"  [{year}] missing {fn.name} — skipped")
        return pd.DataFrame()
    z = zipfile.ZipFile(fn)
    rpt_name = next(n for n in z.namelist() if "rpt" in n.lower())
    nmrc_name = next(n for n in z.namelist() if "nmrc" in n.lower())

    rpt_cols = ["RPT_REC_NUM", "CTRL_TYPE", "PRVDR_NUM", "NPI", "RPT_STUS_CD",
                "FY_BGN_DT", "FY_END_DT", "PROC_DT", "INITL_RPT_SW", "LAST_RPT_SW",
                "TRNSMTL_NUM", "FI_NUM", "ADR_VNDR_CD", "FI_CREAT_DT", "UTIL_CD",
                "NPR_DT", "SPEC_IND", "FI_RCPT_DT"]
    rpt = pd.read_csv(z.open(rpt_name), header=None, dtype=str)
    rpt.columns = rpt_cols[:rpt.shape[1]]
    rpt = rpt[rpt["PRVDR_NUM"].str.startswith(MI_PRVDR_PREFIX, na=False)].copy()
    rpt["FY_END_DT"] = pd.to_datetime(rpt["FY_END_DT"], errors="coerce")
    rpt = rpt.dropna(subset=["FY_END_DT"])
    rpt = rpt.sort_values("FY_END_DT").drop_duplicates(subset=["PRVDR_NUM"], keep="last")
    rpt["fy_end_year"] = rpt["FY_END_DT"].dt.year
    rec_set = set(rpt["RPT_REC_NUM"])
    if not rec_set:
        return pd.DataFrame()

    rows = []
    with z.open(nmrc_name) as f:
        for chunk in pd.read_csv(f, header=None, dtype=str,
                                 names=["RPT_REC_NUM", "WKSHT_CD", "LINE_NUM",
                                        "CLMN_NUM", "ITM_VAL_NUM"],
                                 chunksize=500_000):
            mask = (chunk["RPT_REC_NUM"].isin(rec_set)
                    & (chunk["WKSHT_CD"] == "S300001"))
            if mask.any():
                rows.append(chunk[mask].copy())
    if not rows:
        return pd.DataFrame()
    nmrc = pd.concat(rows, ignore_index=True)
    nmrc["val"] = pd.to_numeric(nmrc["ITM_VAL_NUM"], errors="coerce")
    nmrc = nmrc.merge(rpt[["RPT_REC_NUM", "PRVDR_NUM", "fy_end_year"]],
                      on="RPT_REC_NUM", how="left")
    nmrc = nmrc.rename(columns={"PRVDR_NUM": "facility_id"})
    nmrc["hcris_source_year"] = year
    out = nmrc[["facility_id", "fy_end_year", "hcris_source_year",
                "WKSHT_CD", "LINE_NUM", "CLMN_NUM", "val"]]
    print(f"  [{year}] {nmrc['facility_id'].nunique()} MI hospitals, "
          f"{len(out)} S-3 Part I cells")
    return out


# Common cells we'll surface in the wide CSV. Keys must match (LINE_NUM, CLMN_NUM)
# as stored in HCRIS — 5-digit zero-padded.
WIDE_CELLS = {
    ("01400", "00200"): "beds_total",
    ("01400", "00400"): "bed_days_available",
    ("01400", "00600"): "ip_days_title_v",
    ("01400", "00700"): "ip_days_title_xviii",
    ("01400", "00800"): "ip_days_title_xix",
    ("01400", "01200"): "ip_days_other",
    ("01400", "01300"): "discharges_title_v",
    ("01400", "01400"): "discharges_title_xviii",
    ("01400", "01500"): "discharges_title_xix",
    ("01400", "01600"): "discharges_other",
}


def to_wide(long_df):
    sub = long_df.copy()
    sub["key"] = list(zip(sub["LINE_NUM"], sub["CLMN_NUM"]))
    sub = sub[sub["key"].isin(WIDE_CELLS.keys())].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["var"] = sub["key"].map(WIDE_CELLS)
    wide = (sub.pivot_table(
                index=["facility_id", "fy_end_year", "hcris_source_year"],
                columns="var", values="val", aggfunc="sum")
              .reset_index())
    # Derived totals
    ip_cols = ["ip_days_title_v", "ip_days_title_xviii", "ip_days_title_xix", "ip_days_other"]
    disch_cols = ["discharges_title_v", "discharges_title_xviii",
                  "discharges_title_xix", "discharges_other"]
    for c in ip_cols + disch_cols:
        if c not in wide.columns:
            wide[c] = 0
    wide["inpatient_days_total"] = wide[ip_cols].sum(axis=1)
    wide["discharges_total"] = wide[disch_cols].sum(axis=1)
    return wide


def main():
    frames = [parse_year(y) for y in YEARS]
    frames = [d for d in frames if not d.empty]
    if not frames:
        print("No data extracted.", file=sys.stderr)
        sys.exit(1)
    long_df = pd.concat(frames, ignore_index=True)
    # Deduplicate to one report per (facility, fy_end_year) — keep most recent source
    long_df = (long_df.sort_values(["facility_id", "fy_end_year", "hcris_source_year"])
                      .drop_duplicates(
                          subset=["facility_id", "fy_end_year", "WKSHT_CD",
                                  "LINE_NUM", "CLMN_NUM"],
                          keep="last"))
    out_long = OUT_DIR / "04_hcris_s3_part1_long_mi.csv"
    long_df.to_csv(out_long, index=False)
    print(f"\nLong:  {long_df.shape}  -> {out_long.name}")

    wide = to_wide(long_df)
    if not wide.empty:
        out_wide = OUT_DIR / "04_hcris_s3_part1_wide_mi.csv"
        wide.to_csv(out_wide, index=False)
        print(f"Wide:  {wide.shape}  -> {out_wide.name}")
        print(f"\nMI hospitals: {wide['facility_id'].nunique()}")
        print(f"Years: {sorted(wide['fy_end_year'].dropna().unique().astype(int).tolist())}")
    else:
        print("Wide table empty — none of the expected cells matched. "
              "Inspect long CSV to identify actual line/column codes.")


if __name__ == "__main__":
    main()
