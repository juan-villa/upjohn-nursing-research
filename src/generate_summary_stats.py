"""
generate_summary_stats.py — publication-style descriptive-statistics tables.

Outputs:
  summary-stats-msa-lvl.csv          summary-stats-msa-lvl.png
  summary-stats-hospital-lvl.csv     summary-stats-hospital-lvl.png

Layout follows journal convention (booktabs-style rules, serif font,
grouped by variable category). Columns: N, Mean, SD, Min, Max.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams

ROOT = Path(__file__).resolve().parent.parent

rcParams["font.family"] = "serif"
rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
rcParams["mathtext.fontset"] = "stix"
# Disable matplotlib mathtext parsing — treat $ and ^ as literal characters
rcParams["text.parse_math"] = False


# ---------------------------------------------------------------------------
# Variable labels and grouping for each panel.
# Tuple is (column, display_label, scale_factor, decimals)
# scale_factor divides values before display (e.g. 1e6 → "$M")
# ---------------------------------------------------------------------------

MSA_GROUPS = [
    ("RN labor market (OEWS)", [
        ("tot_emp",              "Total RN employment",                  1,    0),
        ("rn_per_1k_raw",        "RNs per 1,000 residents (raw)",        1,    2),
        ("rn_per_1k_adj",        "RNs per 1,000 age-demand-weighted",    1,    2),
        ("h_median",             "Median hourly wage (nominal, $)",      1,    2),
        ("h_median_real",        "Median hourly wage, real (2024 $)",    1,    2),
        ("h_median_growth",      "Real wage growth (YoY, %)",            1,    2),
    ]),
    ("Shortage outcome (HCRIS)", [
        ("contract_labor_share", "Contract labor share",                 1,    3),
        ("n_hospitals_reporting","Hospitals reporting contract labor",   1,    0),
    ]),
    ("Stress (HHS Protect)", [
        ("covid_peak_per_100k",  "COVID peak admissions per 100k",       1,    2),
        ("covid_avg_per_100k",   "COVID avg admissions per 100k",        1,    2),
    ]),
    ("Demographics (ACS)", [
        ("pop_total",            "Population (1,000s)",                1000,    0),
        ("pct_65plus",           "Population age 65+ (%)",               1,    2),
        ("pct_uninsured",        "Uninsured (%)",                        1,    2),
        ("pct_bachelors_plus",   "Bachelor's degree+ (%)",               1,    2),
        ("lfp_rate",             "Labor force participation (%)",        1,    2),
        ("unemployment_rate",    "Unemployment rate (%)",                1,    2),
    ]),
    ("Economic controls", [
        ("median_hh_income",     "Median household income ($)",          1,    0),
        ("median_gross_rent",    "Median gross rent ($)",                1,    0),
    ]),
    ("Hospital supply", [
        ("hospital_count",       "Total HCRIS hospitals (count)",        1,    0),
        ("hospital_beds",        "Total hospital beds",                  1,    0),
        ("beds_per_100k",        "Beds per 100,000 residents",           1,    1),
    ]),
    ("Policy levers", [
        ("magnet_hospitals",     "Magnet hospitals (count)",             1,    2),
        ("magnet_active",        "Any Magnet hospital (0/1)",            1,    2),
    ]),
]

HOSP_GROUPS = [
    ("Treatment", [
        ("hospital_magnet",      "Magnet certified (0/1)",               1,    2),
    ]),
    ("Shortage outcome (HCRIS)", [
        ("contract_labor_share", "Contract labor share",                 1,    3),
        ("contract_labor_total", "Contract labor ($M)",                 1e6,   2),
    ]),
    ("Hospital operations (HCRIS)", [
        ("total_wages",          "Total wages ($M)",                    1e6,   1),
        ("total_paid_hours",     "Total paid hours (M)",                1e6,   1),
        ("total_fte",            "Total FTE",                            1,    0),
        ("beds_available",       "Beds available",                       1,    0),
        ("inpatient_days",       "Inpatient days",                       1,    0),
    ]),
    ("Patient experience (HCAHPS, snapshot)", [
        ("nurse_comm_score",     "Nurse communication score (0–100)",    1,    2),
        ("nurse_comm_star",      "Nurse communication stars (1–5)",      1,    2),
        ("overall_rating",       "Overall hospital rating (0–100)",      1,    2),
        ("overall_star",         "Overall hospital stars (1–5)",         1,    2),
        ("summary_star",         "Summary stars (1–5)",                  1,    2),
    ]),
    ("Stress (hospital-level COVID)", [
        ("covid_peak_per_bed",   "Peak COVID adm. per bed",              1,    3),
        ("covid_avg_per_bed",    "Avg COVID adm. per bed",               1,    3),
        ("covid_peak_admissions_count", "Peak COVID adm. (count)",       1,    1),
        ("mean_total_beds",      "Mean total beds",                      1,    0),
    ]),
]


def stats_for(series, scale, decimals):
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s / scale
    if len(s) == 0:
        return ["—"] * 5
    fmt = lambda v: format_number(v, decimals)
    return [f"{len(s):,}", fmt(s.mean()), fmt(s.std()),
            fmt(s.min()), fmt(s.max())]


def format_number(v, decimals):
    if pd.isna(v):
        return "—"
    if decimals == 0:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}"


def build_rows(df, groups):
    rows = []  # (group_header_or_None, label, n, mean, sd, min, max)
    for grp_name, vars_ in groups:
        rows.append(("HEADER", grp_name, "", "", "", "", ""))
        for col, label, scale, dec in vars_:
            if col not in df.columns:
                continue
            n, mean, sd, mn, mx = stats_for(df[col], scale, dec)
            rows.append((None, label, n, mean, sd, mn, mx))
    return rows


def render_pub_table(rows, title, subtitle, out_path):
    n_rows = len(rows)
    # column widths (relative): label wide, others narrow
    fig_h = max(4.5, 0.30 * n_rows + 1.2)
    fig_w = 9.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # title block
    ax.text(0.0, 0.985, title,
            ha="left", va="top", fontsize=12.5, fontweight="bold")
    ax.text(0.0, 0.955, subtitle,
            ha="left", va="top", fontsize=9.5, style="italic")

    # table area boundaries
    top_y = 0.91
    bottom_y = 0.04
    row_h = (top_y - bottom_y) / (n_rows + 1)  # +1 for header row

    # column positions (left-edges in axis coords)
    x_label = 0.00
    x_n     = 0.56
    x_mean  = 0.66
    x_sd    = 0.76
    x_min   = 0.86
    x_max   = 0.96
    col_xs = {"n": x_n, "Mean": x_mean, "SD": x_sd, "Min": x_min, "Max": x_max}

    # rules
    def hrule(y, lw=1.4):
        ax.plot([0.0, 1.0], [y, y], color="black",
                linewidth=lw, transform=ax.transAxes,
                clip_on=False, solid_capstyle="butt")

    hrule(top_y, lw=1.7)                              # top rule

    # column headers
    header_y = top_y - row_h * 0.7
    ax.text(x_label, header_y, "Variable",
            ha="left", va="center", fontsize=10, fontweight="bold")
    for hdr, x in col_xs.items():
        ax.text(x, header_y, hdr,
                ha="right", va="center", fontsize=10, fontweight="bold")
    hrule(top_y - row_h, lw=0.8)                      # mid rule

    # data rows
    y = top_y - row_h * 1.5
    for kind, label, n, mean, sd, mn, mx in rows:
        if kind == "HEADER":
            ax.text(x_label, y, label,
                    ha="left", va="center",
                    fontsize=9.5, style="italic", color="#333333")
        else:
            ax.text(x_label, y, label,
                    ha="left", va="center", fontsize=9.5)
            ax.text(x_n,    y, n,    ha="right", va="center", fontsize=9.5)
            ax.text(x_mean, y, mean, ha="right", va="center", fontsize=9.5)
            ax.text(x_sd,   y, sd,   ha="right", va="center", fontsize=9.5)
            ax.text(x_min,  y, mn,   ha="right", va="center", fontsize=9.5)
            ax.text(x_max,  y, mx,   ha="right", va="center", fontsize=9.5)
        y -= row_h

    hrule(bottom_y, lw=1.7)                           # bottom rule

    # footnote
    ax.text(0.0, bottom_y - 0.025,
            "N, Mean, and SD computed on non-missing observations. "
            "Real wages deflated by CPI-U to 2024 USD. "
            "Hospital-level COVID and HCAHPS data attached as described in legend.",
            ha="left", va="top", fontsize=7.5, style="italic", color="#444444",
            wrap=True)

    fig.savefig(out_path, dpi=220, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print(f"  wrote {out_path}")


def csv_table(df, groups, out_path):
    """Also write a tidy CSV with the same content + grouping column."""
    rows = []
    for grp_name, vars_ in groups:
        for col, label, scale, dec in vars_:
            if col not in df.columns:
                continue
            s = pd.to_numeric(df[col], errors="coerce").dropna() / scale
            if len(s) == 0:
                rows.append({"group": grp_name, "variable": label,
                             "n": 0, "mean": None, "sd": None,
                             "min": None, "max": None})
            else:
                rows.append({"group": grp_name, "variable": label,
                             "n": len(s),
                             "mean": round(s.mean(), max(dec, 3)),
                             "sd":   round(s.std(),  max(dec, 3)),
                             "min":  round(s.min(),  max(dec, 3)),
                             "max":  round(s.max(),  max(dec, 3))})
    out = pd.DataFrame(rows)
    out.to_csv(out_path, index=False)
    print(f"  wrote {out_path}")


def main():
    msa = pd.read_csv(ROOT / "master_panel.csv")
    msa_rows = build_rows(msa, MSA_GROUPS)
    csv_table(msa, MSA_GROUPS, ROOT / "summary-stats-msa-lvl.csv")
    render_pub_table(
        msa_rows,
        "Table 1.  Summary statistics — MSA panel",
        f"N = {len(msa)} MSA-years across {msa['area_title'].nunique()} "
        f"Michigan MSAs, {msa['year'].min()}–{msa['year'].max()}.",
        ROOT / "summary-stats-msa-lvl.png")

    # Hospital-level panel has been retired from the project; skip if absent.
    hosp_path = ROOT / "hospital_panel.csv"
    if hosp_path.exists():
        hosp = pd.read_csv(hosp_path)
        hosp_rows = build_rows(hosp, HOSP_GROUPS)
        csv_table(hosp, HOSP_GROUPS, ROOT / "summary-stats-hospital-lvl.csv")
        render_pub_table(
            hosp_rows,
            "Table 2.  Summary statistics — Hospital panel",
            f"N = {len(hosp)} hospital-years across "
            f"{hosp['facility_id'].nunique()} Michigan hospitals, "
            f"{hosp['year'].min()}–{hosp['year'].max()}.",
            ROOT / "summary-stats-hospital-lvl.png")


if __name__ == "__main__":
    main()
