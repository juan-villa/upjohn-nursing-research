"""Create polished PNG regression tables for proposal submission."""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("tmp/matplotlib").resolve()))

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "analytic" / "regression-data-base.csv"
OUT_DIR = ROOT / "figures-submission"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# The canonical panel uses different names for a few ACS controls than the
# original build did; alias them so the specifications below are unchanged.
_COLUMN_ALIASES = {
    "share_65plus": "pct_65plus",
    "bachelors_plus_share": "pct_bachelors_plus",
    "uninsured_rate": "pct_uninsured",
}


def prepare_data() -> pd.DataFrame:
    df = pd.read_csv(DATA, dtype={"fips": str})
    df = df.rename(columns={k: v for k, v in _COLUMN_ALIASES.items()
                            if k in df.columns and v not in df.columns})

    if "nurse_total_count" not in df.columns:
        df["nurse_total_count"] = df["rn_licensed_county"] + df["lpn_licensed_county"]
    if "rn_per_100k" not in df.columns:
        df["rn_per_100k"] = df["rn_licensed_county"] / df["pop_total"] * 100_000
    if "lpn_per_100k" not in df.columns:
        df["lpn_per_100k"] = df["lpn_licensed_county"] / df["pop_total"] * 100_000
    if "nurse_total_per_100k" not in df.columns:
        df["nurse_total_per_100k"] = df["nurse_total_count"] / df["pop_total"] * 100_000

    df["log_pop_total"] = np.log(df["pop_total"])
    df["median_hh_income_10k"] = df["median_hh_income"] / 10_000
    df["median_home_value_100k"] = df["median_home_value"] / 100_000
    df["hosp_beds_per_100k"] = df["hosp_beds"] / df["pop_total"] * 100_000
    df["nurs_fac_beds_per_100k"] = df["nurs_fac_beds"] / df["pop_total"] * 100_000
    df["ipeds_rn_per_100k"] = df["ipeds_completions_rn"] / df["pop_total"] * 100_000
    df["ipeds_lpn_per_100k"] = df["ipeds_completions_lpn"] / df["pop_total"] * 100_000
    return df


CORE_COVARIATES = [
    "log_pop_total",
    "pct_65plus",
    "pct_25_54",
    "unemployment_rate",
    "lfp_rate",
    "pct_bachelors_plus",
    "pct_uninsured",
    "poverty_rate",
    "pct_white",
    "pct_black",
    "pct_hispanic",
    "median_hh_income_10k",
    "median_home_value_100k",
    "mean_commute_minutes",
]

POLICY_COVARIATES = [
    "ipeds_rn_per_100k",
    "ipeds_lpn_per_100k",
    "chr_pct_fair_poor_health",
    "chr_preventable_hosp_rate",
    "chr_pcp_rate",
    "hosp_beds_per_100k",
    "nurs_fac_beds_per_100k",
    "hpsa_prim_care",
]

LABELS = {
    "log_pop_total": "Log population",
    "pct_65plus": "% age 65+",
    "pct_25_54": "% age 25-54",
    "unemployment_rate": "Unemployment rate",
    "lfp_rate": "Labor-force participation",
    "pct_bachelors_plus": "% bachelor's or higher",
    "pct_uninsured": "% uninsured",
    "poverty_rate": "Poverty rate",
    "pct_white": "% White",
    "pct_black": "% Black",
    "pct_hispanic": "% Hispanic",
    "median_hh_income_10k": "Median HH income ($10k)",
    "median_home_value_100k": "Median home value ($100k)",
    "mean_commute_minutes": "Mean commute minutes",
    "ipeds_rn_per_100k": "RN completions per 100k",
    "ipeds_lpn_per_100k": "LPN completions per 100k",
    "chr_pct_fair_poor_health": "% fair/poor health",
    "chr_preventable_hosp_rate": "Preventable hosp. rate",
    "chr_pcp_rate": "Primary care physician rate",
    "hosp_beds_per_100k": "Hospital beds per 100k",
    "nurs_fac_beds_per_100k": "Nursing facility beds per 100k",
    "hpsa_prim_care": "Primary care HPSA",
}


def fit_model(df: pd.DataFrame, dep: str, covariates: list[str], two_way_fe: bool = False):
    cols = [dep, "fips", "year"] + covariates
    model_data = df[cols].replace([np.inf, -np.inf], np.nan).dropna().copy()
    rhs = " + ".join(covariates)
    if two_way_fe:
        rhs += " + C(fips) + C(year)"
    res = smf.ols(f"{dep} ~ {rhs}", data=model_data).fit(
        cov_type="cluster",
        cov_kwds={"groups": model_data["fips"]},
    )
    return res, model_data


def stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def coef_cell(res, term: str) -> str:
    if term not in res.params.index:
        return ""
    coef = res.params[term]
    se = res.bse[term]
    p = res.pvalues[term]
    return f"{coef:,.2f}{stars(p)}\n({se:,.2f})"


def year_label(data: pd.DataFrame) -> str:
    years = sorted(data["year"].astype(int).unique().tolist())
    ranges = []
    start = prev = years[0]
    for year in years[1:]:
        if year == prev + 1:
            prev = year
            continue
        ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = year
    ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(ranges)


def render_table(
    table: pd.DataFrame,
    title: str,
    subtitle: str,
    note: str,
    out_path: Path,
    figsize: tuple[float, float],
    col_widths: list[float],
) -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
            "mathtext.fontset": "dejavuserif",
            "axes.unicode_minus": False,
        }
    )

    fig, ax = plt.subplots(figsize=figsize)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(
        0.0,
        1.04,
        title,
        transform=ax.transAxes,
        fontsize=20,
        fontweight="bold",
        va="bottom",
        color="#111827",
    )
    ax.text(
        0.0,
        1.005,
        subtitle,
        transform=ax.transAxes,
        fontsize=11.5,
        va="bottom",
        color="#374151",
    )

    mpl_table = ax.table(
        cellText=table.values,
        colLabels=table.columns,
        cellLoc="center",
        colLoc="center",
        loc="upper left",
        bbox=[0, 0.105, 1, 0.865],
        colWidths=col_widths,
    )
    mpl_table.auto_set_font_size(False)
    mpl_table.set_fontsize(9.2)

    header_color = "#111827"
    stripe = "#f8fafc"
    label_fill = "#f1f5f9"
    border = "#d1d5db"

    for (row, col), cell in mpl_table.get_celld().items():
        cell.set_edgecolor(border)
        cell.set_linewidth(0.55)
        if row == 0:
            cell.set_facecolor(header_color)
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(9.4)
            cell.set_height(0.062)
        else:
            if col == 0:
                cell.set_facecolor(label_fill)
                cell.get_text().set_ha("left")
                cell.get_text().set_weight("bold" if table.iloc[row - 1, 0] in {"Model details", "Observations", "Counties", "Adjusted R²"} else "normal")
            elif row % 2 == 0:
                cell.set_facecolor(stripe)
            else:
                cell.set_facecolor("white")
            cell.set_height(0.056)

    ax.plot([0, 1], [0.982, 0.982], transform=ax.transAxes, color="#111827", lw=1.4)
    ax.plot([0, 1], [0.104, 0.104], transform=ax.transAxes, color="#111827", lw=1.1)
    ax.text(
        0.0,
        0.055,
        note,
        transform=ax.transAxes,
        fontsize=8.6,
        color="#374151",
        va="top",
        wrap=True,
    )

    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main_table(df: pd.DataFrame) -> Path:
    outcomes = [
        ("rn_per_100k", "RN ratio"),
        ("lpn_per_100k", "LPN ratio"),
        ("nurse_total_per_100k", "Total ratio"),
    ]

    models = []
    for dep, label in outcomes:
        models.append((f"OLS\n{label}", *fit_model(df, dep, CORE_COVARIATES, two_way_fe=False), False))
    for dep, label in outcomes:
        models.append((f"Two-way FE\n{label}", *fit_model(df, dep, CORE_COVARIATES, two_way_fe=True), True))

    rows = []
    for term in CORE_COVARIATES:
        rows.append([LABELS[term]] + [coef_cell(res, term) for _, res, _, _ in models])

    rows.append(["Model details"] + [""] * len(models))
    rows.append(["Observations"] + [f"{int(res.nobs):,}" for _, res, _, _ in models])
    rows.append(["Counties"] + [f"{data['fips'].nunique():,}" for _, _, data, _ in models])
    rows.append(["County FE"] + ["Yes" if fe else "No" for _, _, _, fe in models])
    rows.append(["Year FE"] + ["Yes" if fe else "No" for _, _, _, fe in models])
    rows.append(["Adjusted R²"] + [f"{res.rsquared_adj:.3f}" for _, res, _, _ in models])

    table = pd.DataFrame(rows, columns=["Covariate"] + [m[0] for m in models])
    out = OUT_DIR / "table_1_main_ratio_regressions.png"
    render_table(
        table,
        "Table 1. Main Nurse Shortage Ratio Regressions",
        "Dependent variables are licensed nurses per 100,000 residents. Standard errors are clustered by county.",
        "Notes: Each coefficient is shown with clustered standard error in parentheses. * p<0.10, ** p<0.05, *** p<0.01. "
        "Two-way FE models include county and year fixed effects. Main sample covers available outcome years: 2012-2017, 2019, 2020, 2022, and 2023.",
        out,
        figsize=(17.5, 11.5),
        col_widths=[0.23] + [0.128] * 6,
    )
    return out


def extended_table(df: pd.DataFrame) -> Path:
    covariates = CORE_COVARIATES + POLICY_COVARIATES
    outcomes = [
        ("rn_per_100k", "RN ratio"),
        ("lpn_per_100k", "LPN ratio"),
        ("nurse_total_per_100k", "Total ratio"),
    ]
    models = [(label, *fit_model(df, dep, covariates, two_way_fe=False)) for dep, label in outcomes]

    keep_terms = [
        "ipeds_rn_per_100k",
        "ipeds_lpn_per_100k",
        "chr_pct_fair_poor_health",
        "chr_preventable_hosp_rate",
        "chr_pcp_rate",
        "hosp_beds_per_100k",
        "nurs_fac_beds_per_100k",
        "hpsa_prim_care",
        "pct_uninsured",
        "poverty_rate",
    ]
    rows = []
    for term in keep_terms:
        rows.append([LABELS[term]] + [coef_cell(res, term) for _, res, _ in models])

    rows.append(["Model details"] + [""] * len(models))
    rows.append(["Core demographic controls"] + ["Yes"] * len(models))
    rows.append(["Observations"] + [f"{int(res.nobs):,}" for _, res, _ in models])
    rows.append(["Counties"] + [f"{data['fips'].nunique():,}" for _, _, data in models])
    rows.append(["Years"] + [year_label(data) for _, _, data in models])
    rows.append(["Adjusted R²"] + [f"{res.rsquared_adj:.3f}" for _, res, _ in models])

    table = pd.DataFrame(rows, columns=["Covariate"] + [m[0] for m in models])
    out = OUT_DIR / "table_2_extended_policy_sensitivity.png"
    render_table(
        table,
        "Table 2. Extended Policy and Health-System Sensitivity",
        "Dependent variables are licensed nurses per 100,000 residents. Extended covariates are informative but restrict the usable sample.",
        "Notes: OLS estimates with county-clustered standard errors in parentheses. * p<0.10, ** p<0.05, *** p<0.01. "
        "Core demographic controls are included but not displayed. The sample is shorter than Table 1 mainly because selected CHR measures are incomplete before 2015 and nurse outcomes are unavailable in 2021; read as hypothesis-generating.",
        out,
        figsize=(12.8, 9.2),
        col_widths=[0.36, 0.21, 0.21, 0.21],
    )
    return out


if __name__ == "__main__":
    data = prepare_data()
    outputs = [main_table(data), extended_table(data)]
    for path in outputs:
        print(path)
