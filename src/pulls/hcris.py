"""
hcris.py — CMS HCRIS Hospital cost reports → contract-labor share by MSA.

Downloads HOSP10FY{year}.zip from CMS for each year, extracts Worksheet S-3
Part II line items, computes per-hospital contract-labor share, and aggregates
to MSA × calendar year (matched on fiscal-year-end).

Form 2552-10 Worksheet S-3 Part II columns (verified by inspection of 2024):
    00100 col = cost center code
    00200 col = paid hours
    00400 col = adjusted hours
    00500 col = total wage costs (USD)
    00600 col = average hourly wage

Lines of interest:
    00100 = Total Salaries (all employed staff)
    01401 = Contract Labor — Direct Patient Care
    01402 = Contract Labor — Excluded Employees

Contract labor share = (line_01401 + line_01402) / total wage outlay.

Output: data/processed/hcris_contract_labor.csv
        columns: cbsa, year, contract_labor_share, n_hospitals, total_wages
"""
import zipfile
import pandas as pd
import requests
from io import BytesIO
from ._common import HEADERS, CACHE, PROCESSED, YEARS

HCRIS_URL = "https://downloads.cms.gov/files/hcris/HOSP10FY{year}.zip"

TARGET_WKSHT = "S300002"
LINE_TOTAL = "00100"      # total salaries
LINE_CL_DPC = "01401"     # contract labor — direct patient care
LINE_CL_EX = "01402"      # contract labor — excluded employees
COL_DOLLARS = "00500"


def download(year):
    fn = CACHE / f"HOSP10FY{year}.zip"
    if fn.exists() and fn.stat().st_size > 1_000_000:
        return fn
    print(f"  downloading {year}...", end=" ", flush=True)
    url = HCRIS_URL.format(year=year)
    r = requests.get(url, headers=HEADERS, timeout=600, stream=True)
    if r.status_code != 200:
        print(f"FAILED {r.status_code}")
        return None
    with open(fn, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    print(f"{fn.stat().st_size/1e6:.0f} MB")
    return fn


def parse_year(year, hospitals):
    """Return per-MSA contract-labor share for one HCRIS fiscal year."""
    zf_path = download(year)
    if zf_path is None:
        return pd.DataFrame()

    z = zipfile.ZipFile(zf_path)
    rpt_name = next(n for n in z.namelist() if "rpt" in n.lower())
    nmrc_name = next(n for n in z.namelist() if "nmrc" in n.lower())

    rpt = pd.read_csv(z.open(rpt_name), header=None, dtype=str)
    rpt.columns = ["RPT_REC_NUM","CTRL_TYPE","PRVDR_NUM","NPI","RPT_STUS_CD",
                   "FY_BGN_DT","FY_END_DT","PROC_DT","INITL_RPT_SW","LAST_RPT_SW",
                   "TRNSMTL_NUM","FI_NUM","ADR_VNDR_CD","FI_CREAT_DT","UTIL_CD",
                   "NPR_DT","SPEC_IND","FI_RCPT_DT"][:rpt.shape[1]]
    rpt = rpt[rpt["PRVDR_NUM"].str.startswith("23", na=False)].copy()
    # Filter to one report per provider per FY (most recent)
    rpt["FY_END_DT"] = pd.to_datetime(rpt["FY_END_DT"], errors="coerce")
    rpt = rpt.dropna(subset=["FY_END_DT"])
    rpt = (rpt.sort_values("FY_END_DT")
              .drop_duplicates(subset=["PRVDR_NUM"], keep="last"))
    rpt["calendar_year"] = rpt["FY_END_DT"].dt.year
    mi_rec_nums = set(rpt["RPT_REC_NUM"])
    if not mi_rec_nums:
        print(f"  [{year}] no MI providers in report file")
        return pd.DataFrame()

    # Stream NMRC, keep only S-3 II rows for MI hospitals on lines of interest
    keep_lines = {LINE_TOTAL, LINE_CL_DPC, LINE_CL_EX}
    rows = []
    with z.open(nmrc_name) as f:
        for chunk in pd.read_csv(f, header=None, dtype=str,
                                 names=["RPT_REC_NUM","WKSHT_CD","LINE_NUM",
                                        "CLMN_NUM","ITM_VAL_NUM"],
                                 chunksize=500_000):
            mask = ((chunk["WKSHT_CD"] == TARGET_WKSHT)
                    & (chunk["LINE_NUM"].isin(keep_lines))
                    & (chunk["CLMN_NUM"] == COL_DOLLARS)
                    & chunk["RPT_REC_NUM"].isin(mi_rec_nums))
            if mask.any():
                rows.append(chunk[mask].copy())
    if not rows:
        print(f"  [{year}] no S-3 II rows found")
        return pd.DataFrame()
    nmrc = pd.concat(rows, ignore_index=True)
    nmrc["val"] = pd.to_numeric(nmrc["ITM_VAL_NUM"], errors="coerce")

    # Pivot lines into columns per hospital
    piv = nmrc.pivot_table(index="RPT_REC_NUM", columns="LINE_NUM",
                           values="val", aggfunc="sum").reset_index()
    for c in [LINE_TOTAL, LINE_CL_DPC, LINE_CL_EX]:
        if c not in piv.columns:
            piv[c] = 0.0
    piv = piv.fillna(0.0)
    piv["total_wages"] = piv[LINE_TOTAL]
    piv["contract_labor"] = piv[LINE_CL_DPC] + piv[LINE_CL_EX]
    piv["denom"] = piv["total_wages"] + piv["contract_labor"]
    piv = piv[piv["denom"] > 0]

    # Join to provider info → MSA
    piv = piv.merge(rpt[["RPT_REC_NUM","PRVDR_NUM","calendar_year"]],
                    on="RPT_REC_NUM", how="left")
    piv = piv.merge(hospitals[["facility_id","cbsa","msa_name"]],
                    left_on="PRVDR_NUM", right_on="facility_id", how="left")
    piv = piv[piv["cbsa"].notna()]
    if piv.empty:
        print(f"  [{year}] no MSA-matched MI hospitals")
        return pd.DataFrame()

    # Aggregate to MSA (wage-weighted contract labor share)
    agg = (piv.groupby(["cbsa","msa_name","calendar_year"])
              .apply(lambda x: pd.Series({
                  "contract_labor_share": x["contract_labor"].sum() / x["denom"].sum(),
                  "total_wages": x["total_wages"].sum(),
                  "contract_labor": x["contract_labor"].sum(),
                  "n_hospitals": len(x),
              }))
              .reset_index())
    agg = agg.rename(columns={"calendar_year": "year"})
    print(f"  [{year}] {len(agg)} MSAs, {int(agg['n_hospitals'].sum())} hospitals")
    return agg


def main():
    hospitals = pd.read_csv(PROCESSED / "mi_hospitals.csv", dtype=str)
    out = []
    for y in YEARS:
        df = parse_year(y, hospitals)
        if not df.empty:
            out.append(df)
    if not out:
        print("No HCRIS data extracted.")
        return
    full = pd.concat(out, ignore_index=True)
    out_path = PROCESSED / "hcris_contract_labor.csv"
    full.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}: {full.shape}")
    print(full.groupby("year")["n_hospitals"].sum())


if __name__ == "__main__":
    main()
