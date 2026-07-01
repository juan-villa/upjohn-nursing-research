"""
hcris_hospital.py — re-process cached HCRIS zips at hospital level.

Outputs: data/processed/hcris_hospital.csv
Columns per hospital × fiscal-year-end:
    facility_id (CCN)  - 6-digit Medicare provider number
    fy_end_year        - calendar year of FY end (used to align with panel year)
    total_wages        - S-3 II line 1 col 5: total wage cost (USD)
    total_paid_hours   - S-3 II line 1 col 2: total paid hours
    total_fte          - total_paid_hours / 2080 (FTE conversion)
    contract_labor_dpc - S-3 II line 14.01 col 5: contract labor direct patient care (USD)
    contract_labor_ex  - S-3 II line 14.02 col 5: contract labor excluded employees (USD)
    contract_labor_share - (dpc + ex) / (wages + dpc + ex)
    beds_available     - S-3 I  line 14 col 2: total facility beds (best-effort interp)
    inpatient_days     - S-3 I  line 14 col 6: total inpatient days (best-effort interp)
"""
import zipfile
import pandas as pd
import numpy as np
from ._common import CACHE, PROCESSED, YEARS

KEEP = {
    ("S300002", "00100", "00500"): "total_wages",
    ("S300002", "00100", "00200"): "total_paid_hours",
    ("S300002", "01401", "00500"): "contract_labor_dpc",
    ("S300002", "01402", "00500"): "contract_labor_ex",
    ("S300001", "01400", "00200"): "beds_available",
    ("S300001", "01400", "00600"): "inpatient_days",
}


def parse_year(year):
    fn = CACHE / f"HOSP10FY{year}.zip"
    if not fn.exists():
        print(f"  [{year}] missing zip — skipped")
        return pd.DataFrame()
    z = zipfile.ZipFile(fn)
    rpt_name = next(n for n in z.namelist() if "rpt" in n.lower())
    nmrc_name = next(n for n in z.namelist() if "nmrc" in n.lower())

    rpt = pd.read_csv(z.open(rpt_name), header=None, dtype=str)
    cols = ["RPT_REC_NUM","CTRL_TYPE","PRVDR_NUM","NPI","RPT_STUS_CD",
            "FY_BGN_DT","FY_END_DT","PROC_DT","INITL_RPT_SW","LAST_RPT_SW",
            "TRNSMTL_NUM","FI_NUM","ADR_VNDR_CD","FI_CREAT_DT","UTIL_CD",
            "NPR_DT","SPEC_IND","FI_RCPT_DT"]
    rpt.columns = cols[:rpt.shape[1]]
    rpt = rpt[rpt["PRVDR_NUM"].str.startswith("23", na=False)].copy()
    rpt["FY_END_DT"] = pd.to_datetime(rpt["FY_END_DT"], errors="coerce")
    rpt = rpt.dropna(subset=["FY_END_DT"])
    rpt = rpt.sort_values("FY_END_DT").drop_duplicates(
        subset=["PRVDR_NUM"], keep="last")
    rpt["fy_end_year"] = rpt["FY_END_DT"].dt.year
    rec_set = set(rpt["RPT_REC_NUM"])
    if not rec_set:
        return pd.DataFrame()

    rows = []
    with z.open(nmrc_name) as f:
        for chunk in pd.read_csv(f, header=None, dtype=str,
                                 names=["RPT_REC_NUM","WKSHT_CD","LINE_NUM",
                                        "CLMN_NUM","ITM_VAL_NUM"],
                                 chunksize=500_000):
            mask = chunk["RPT_REC_NUM"].isin(rec_set)
            if not mask.any():
                continue
            sub = chunk[mask].copy()
            sub["key"] = list(zip(sub["WKSHT_CD"], sub["LINE_NUM"], sub["CLMN_NUM"]))
            sub = sub[sub["key"].isin(KEEP.keys())]
            if not sub.empty:
                rows.append(sub)
    if not rows:
        return pd.DataFrame()
    nmrc = pd.concat(rows, ignore_index=True)
    nmrc["val"] = pd.to_numeric(nmrc["ITM_VAL_NUM"], errors="coerce")
    nmrc["var"] = nmrc["key"].map(KEEP)
    piv = nmrc.pivot_table(index="RPT_REC_NUM", columns="var",
                           values="val", aggfunc="sum").reset_index()

    # derive contract labor share & FTEs
    for c in ["total_wages","total_paid_hours","contract_labor_dpc",
              "contract_labor_ex","beds_available","inpatient_days"]:
        if c not in piv.columns:
            piv[c] = 0.0
    piv = piv.fillna({"contract_labor_dpc": 0, "contract_labor_ex": 0})
    piv["total_fte"] = piv["total_paid_hours"] / 2080
    piv["contract_labor_total"] = piv["contract_labor_dpc"] + piv["contract_labor_ex"]
    denom = piv["total_wages"] + piv["contract_labor_total"]
    piv["contract_labor_share"] = np.where(denom > 0,
                                            piv["contract_labor_total"] / denom,
                                            np.nan)
    piv = piv.merge(rpt[["RPT_REC_NUM","PRVDR_NUM","fy_end_year"]],
                    on="RPT_REC_NUM", how="left")
    piv = piv.rename(columns={"PRVDR_NUM": "facility_id"})
    piv["hcris_source_year"] = year
    out = piv[["facility_id","fy_end_year","hcris_source_year",
               "total_wages","total_paid_hours","total_fte",
               "contract_labor_dpc","contract_labor_ex",
               "contract_labor_total","contract_labor_share",
               "beds_available","inpatient_days"]]
    print(f"  [{year}] {len(out)} hospital reports")
    return out


def main():
    out = [parse_year(y) for y in YEARS]
    out = [d for d in out if not d.empty]
    if not out:
        print("No data extracted.")
        return
    full = pd.concat(out, ignore_index=True)
    # de-duplicate to one row per (facility, fy_end_year) — keep latest source
    full = (full.sort_values(["facility_id","fy_end_year","hcris_source_year"])
               .drop_duplicates(subset=["facility_id","fy_end_year"], keep="last"))
    out_path = PROCESSED / "hcris_hospital.csv"
    full.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}: {full.shape}")
    print(f"Unique hospitals: {full.facility_id.nunique()}")
    print(f"Year coverage:")
    print(full.fy_end_year.value_counts().sort_index())


if __name__ == "__main__":
    main()
