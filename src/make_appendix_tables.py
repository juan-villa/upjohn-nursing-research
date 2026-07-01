#!/usr/bin/env python
"""Generate LaTeX appendix tables from the v3 mechanism-model results CSV."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = pd.read_csv(ROOT / 'outputs' / 'mechanism_model_results.csv')

PRETTY = {
    'share_75plus': 'Share aged 75$+$ (pp)',
    'share_65_74': 'Share aged 65--74 (pp)',
    'population_growth_rate': 'Population growth rate',
    'hosp_beds_per_1k': 'Hospital beds per 1{,}000',
    'nh_beds_per_65plus_ahrf': 'NH beds per 1{,}000 (65$+$)',
    'poverty_rate': 'Poverty rate (pp)',
    'bachelors_plus_share': "Bachelor's$+$ share (pp)",
    'hpsa_prim_care': 'HPSA (primary care)',
    'rn_per_10k_lag1': 'RN supply ($t-1$)',
    'lpn_per_10k_lag1': 'LPN supply ($t-1$)',
    'unemployment_rate': 'Unemployment rate',
    'rn_age_55plus_pct_lag1': 'RN aged 55$+$ share ($t-1$)',
    'rn_age_under35_pct_lag1': 'RN aged $<$35 share ($t-1$)',
    'lpn_age_55plus_pct_lag1': 'LPN aged 55$+$ share ($t-1$)',
    'lpn_age_under35_pct_lag1': 'LPN aged $<$35 share ($t-1$)',
    'mean_commute_minutes': 'Mean commute (min)',
    'operating_margin_wmean': 'Operating margin (wtd.\\ mean)',
    'single_hospital_county': 'Single-hospital county',
    'ipeds_rn_per_10k_lag1': 'IPEDS RN grads/10k ($t-1$)',
    'ipeds_lpn_per_10k_lag1': 'IPEDS LPN grads/10k ($t-1$)',
    'log_ipeds_lpn': 'log IPEDS LPN completions',
    'log_pop': 'log population (offset)',
    'const': 'Constant',
}
THREE_DP = {'ipeds_rn_per_10k_lag1', 'ipeds_lpn_per_10k_lag1', 'log_ipeds_lpn',
            'ipeds_lpn_per_10k_lag2', 'ipeds_lpn_per_10k_lead1', 'ipeds_lpn_per_10k_lead2',
            'rn_age_55plus_pct_lag1', 'rn_age_under35_pct_lag1',
            'lpn_age_55plus_pct_lag1', 'lpn_age_under35_pct_lag1'}


def star(p):
    if pd.isna(p): return ''
    return ('^{***}' if p < .001 else '^{**}' if p < .01 else
            '^{*}' if p < .05 else '^{\\dagger}' if p < .10 else '')


def dp(v): return 3 if v in THREE_DP else 2


def row(label, variable):
    m = R[(R.label == label) & (R.variable == variable)]
    if m.empty: return None
    return m.iloc[0]


def cell(label, variable):
    r = row(label, variable)
    if r is None: return '', ''
    d = dp(variable)
    return f'${r.coef:.{d}f}{star(r.p)}$', f'({r.se:.{d}f})'


def footer(label):
    r = R[R.label == label].iloc[0]
    return int(r.n), int(r.counties), r.within_r2


def two_occ_table(rn_label, lpn_label, varlist, caption, lab, rn_head, lpn_head):
    lines = [r'\begin{table}[!htbp]', r'\centering', f'\\caption{{{caption}}}',
             f'\\label{{{lab}}}', r'\small', r'\begin{tabular}{lcccc}', r'\toprule',
             f' & \\multicolumn{{2}}{{c}}{{{rn_head}}} & \\multicolumn{{2}}{{c}}{{{lpn_head}}} \\\\',
             r'\cmidrule(lr){2-3}\cmidrule(lr){4-5}',
             r'Variable & Coef. & (SE) & Coef. & (SE) \\', r'\midrule']
    for v in varlist:
        rc, rs = cell(rn_label, v); lc, ls = cell(lpn_label, v)
        if not rc and not lc: continue
        lines.append(f'{PRETTY.get(v, v)} & {rc or "---"} & {rs} & {lc or "---"} & {ls} \\\\')
    rn_n, rn_g, rn_r2 = footer(rn_label); lpn_n, lpn_g, lpn_r2 = footer(lpn_label)
    lines += [r'\midrule',
              r'County \& year FE & Yes & & Yes & \\',
              f'Clusters (county) & {rn_g} & & {lpn_g} & \\\\',
              f'Observations & {rn_n} & & {lpn_n} & \\\\',
              f'Within $R^{{2}}$ & {rn_r2:.3f} & & {lpn_r2:.3f} & \\\\',
              r'\bottomrule', r'\end{tabular}', r'\end{table}']
    return '\n'.join(lines)


out = []

# ---- A1 Baseline ----
base_vars = ['share_75plus', 'share_65_74', 'population_growth_rate',
             'hosp_beds_per_1k', 'nh_beds_per_65plus_ahrf', 'poverty_rate',
             'bachelors_plus_share', 'ipeds_rn_per_10k_lag1', 'ipeds_lpn_per_10k_lag1']
out.append(two_occ_table('Baseline RN supply', 'Baseline LPN supply', base_vars,
                         'Baseline distribution models (two-way fixed effects)',
                         'tab:baseline', 'RN per 10{,}000', 'LPN per 10{,}000'))

# ---- A3 Vacancy ----
vac_vars = ['share_75plus', 'share_65_74', 'population_growth_rate', 'hpsa_prim_care',
            'hosp_beds_per_1k', 'nh_beds_per_65plus_ahrf', 'poverty_rate',
            'bachelors_plus_share', 'rn_per_10k_lag1', 'lpn_per_10k_lag1',
            'ipeds_rn_per_10k_lag1', 'ipeds_lpn_per_10k_lag1']
out.append(two_occ_table('Vacancy pressure - RN postings', 'Vacancy pressure - LPN postings',
                         vac_vars, 'Vacancy-pressure models (postings per 10{,}000, TWFE)',
                         'tab:vacancy', 'RN postings', 'LPN postings'))

# ---- A5 Retention ----
ret_vars = ['share_75plus', 'share_65_74', 'population_growth_rate', 'hosp_beds_per_1k',
            'nh_beds_per_65plus_ahrf', 'poverty_rate', 'bachelors_plus_share',
            'rn_per_10k_lag1', 'lpn_per_10k_lag1', 'ipeds_rn_per_10k_lag1',
            'ipeds_lpn_per_10k_lag1', 'rn_age_55plus_pct_lag1', 'rn_age_under35_pct_lag1',
            'lpn_age_55plus_pct_lag1', 'lpn_age_under35_pct_lag1', 'mean_commute_minutes']
out.append(two_occ_table('Retention pressure - RN supply', 'Retention pressure - LPN supply',
                         ret_vars, 'Retention-pressure models (two-way fixed effects)',
                         'tab:retention', 'RN per 10{,}000', 'LPN per 10{,}000'))

# ---- A6 Employer ----
emp_vars = ['share_75plus', 'share_65_74', 'population_growth_rate', 'hosp_beds_per_1k',
            'nh_beds_per_65plus_ahrf', 'poverty_rate', 'bachelors_plus_share',
            'rn_per_10k_lag1', 'lpn_per_10k_lag1', 'ipeds_rn_per_10k_lag1',
            'ipeds_lpn_per_10k_lag1', 'operating_margin_wmean', 'single_hospital_county']
out.append(two_occ_table('Employer capacity - RN supply', 'Employer capacity - LPN supply',
                         emp_vars, 'Employer-capacity models (two-way fixed effects)',
                         'tab:employer', 'RN per 10{,}000', 'LPN per 10{,}000'))


# ---- A2 Between-county (pooled) baseline comparison ----
def pooled_table():
    rn_t, rn_p = 'No-FE compare [rn_per_10k] - TWFE', 'No-FE compare [rn_per_10k] - pooled OLS'
    lp_t, lp_p = 'No-FE compare [lpn_per_10k] - TWFE', 'No-FE compare [lpn_per_10k] - pooled OLS'
    vars_ = ['share_75plus', 'share_65_74', 'hosp_beds_per_1k', 'nh_beds_per_65plus_ahrf',
             'poverty_rate', 'bachelors_plus_share', 'ipeds_rn_per_10k_lag1', 'ipeds_lpn_per_10k_lag1']
    L = [r'\begin{table}[!htbp]', r'\centering',
         r'\caption{Within-county (TWFE) vs.\ between-county (pooled OLS) baseline estimates}',
         r'\label{tab:pooled}', r'\small', r'\begin{tabular}{lcccc}', r'\toprule',
         r' & \multicolumn{2}{c}{RN per 10{,}000} & \multicolumn{2}{c}{LPN per 10{,}000} \\',
         r'\cmidrule(lr){2-3}\cmidrule(lr){4-5}',
         r'Variable & TWFE & Pooled & TWFE & Pooled \\', r'\midrule']
    for v in vars_:
        rt, _ = cell(rn_t, v); rp, _ = cell(rn_p, v)
        lt, _ = cell(lp_t, v); lp, _ = cell(lp_p, v)
        if not (rt or rp or lt or lp): continue
        L.append(f'{PRETTY.get(v, v)} & {rt or "---"} & {rp or "---"} & {lt or "---"} & {lp or "---"} \\\\')
    L += [r'\midrule', r'County \& year FE & Yes & No & Yes & No \\',
          r'\bottomrule', r'\end{tabular}',
          r'\par\medskip\footnotesize\textit{Notes:} Pooled columns add a constant and '
          r'recover between-county variation; they are descriptive benchmarks subject to '
          r'cross-sectional omitted-variable bias, not more credible than the TWFE estimates.',
          r'\end{table}']
    return '\n'.join(L)


out.append(pooled_table())


# ---- A4 Training specifications (pipeline coefficient across specs) ----
def training_table():
    def c(label, var):
        cc, ss = cell(label, var)
        return (cc or '---'), (ss or '')
    boot = row('Wild-cluster bootstrap - LPN training pipeline (CGM Rademacher, null imposed, B=999)',
               'ipeds_lpn_per_10k_lag1')
    rows = [
        ('Baseline (no lagged DV)',
         c('Baseline LPN supply', 'ipeds_lpn_per_10k_lag1'),
         c('Baseline RN supply', 'ipeds_rn_per_10k_lag1')),
        ('Training spec (lagged DV)',
         c('Training capacity - LPN supply', 'ipeds_lpn_per_10k_lag1'),
         c('Training capacity - RN supply', 'ipeds_rn_per_10k_lag1')),
        ('Two-year lag (baseline)',
         c('LPN pipeline - lag 2 (baseline)', 'ipeds_lpn_per_10k_lag2'), ('---', '')),
        ('Log-count (common denom.)',
         c('Training capacity - LPN count (common-denominator robustness)', 'log_ipeds_lpn'),
         ('---', '')),
    ]
    L = [r'\begin{table}[!htbp]', r'\centering',
         r'\caption{Training-pipeline coefficient across specifications}',
         r'\label{tab:training}', r'\small', r'\begin{tabular}{lcccc}', r'\toprule',
         r' & \multicolumn{2}{c}{IPEDS LPN/10k ($t-1$)} & \multicolumn{2}{c}{IPEDS RN/10k ($t-1$)} \\',
         r'\cmidrule(lr){2-3}\cmidrule(lr){4-5}',
         r'Specification & Coef. & (SE) & Coef. & (SE) \\', r'\midrule']
    for name, (lc, ls), (rc, rs) in rows:
        L.append(f'{name} & {lc} & {ls} & {rc} & {rs} \\\\')
    L.append(f'\\quad Wild-cluster bootstrap $p$ & \\multicolumn{{2}}{{c}}{{${boot.p:.3f}$}} & '
             r'\multicolumn{2}{c}{---} \\')
    # urbanicity panel
    msa = row('LPN training - MSA only (51)', 'ipeds_lpn_per_10k_lag1')
    rur = row('LPN training - Rural only (32)', 'ipeds_lpn_per_10k_lag1')
    intr = row('LPN training x rural interaction', 'rural_x_ipeds_lpn')
    L += [r'\midrule', r'\multicolumn{5}{l}{\textit{Urbanicity (LPN pipeline)}} \\',
          f'\\quad MSA only (51) & ${msa.coef:.3f}{star(msa.p)}$ & ({msa.se:.3f}) & & \\\\',
          f'\\quad Rural only (32)$^{{a}}$ & ${rur.coef:.3f}{star(rur.p)}$ & ({rur.se:.3f}) & & \\\\',
          f'\\quad Rural $\\times$ pipeline & ${intr.coef:.3f}{star(intr.p)}$ & ({intr.se:.3f}) & & \\\\',
          r'\bottomrule', r'\end{tabular}',
          r'\par\medskip\footnotesize\textit{Notes:} County and year FE, county-clustered SEs. '
          r'Baseline uses the Table~\ref{tab:baseline} controls; the training spec adds a lagged '
          r'dependent variable, lagged entry-age share, and unemployment. Log-count uses '
          r'$\log(1+\text{LPN count})$ with $\log(\text{pop})$ offset (a log--log elasticity). '
          r'$^{a}$ identified off a single rural program county. '
          r'$^{\dagger}p<.10$, $^{*}p<.05$, $^{**}p<.01$, $^{***}p<.001$.',
          r'\end{table}']
    return '\n'.join(L)


out.append(training_table())


# ---- Pre-trends (leads & lags) ----
def pretrends_table():
    lbl = 'Pre-trends: LPN training leads and lags (baseline controls)'
    order = [('ipeds_lpn_per_10k_lead2', 'IPEDS LPN ($t+2$)'),
             ('ipeds_lpn_per_10k_lead1', 'IPEDS LPN ($t+1$)'),
             ('ipeds_lpn_per_10k_lag1', 'IPEDS LPN ($t-1$)'),
             ('ipeds_lpn_per_10k_lag2', 'IPEDS LPN ($t-2$)')]
    L = [r'\begin{table}[!htbp]', r'\centering',
         r'\caption{Leads-and-lags (pre-trends) test, LPN pipeline}',
         r'\label{tab:pretrends}', r'\small', r'\begin{tabular}{lcc}', r'\toprule',
         r'Term & Coef. & (SE) \\', r'\midrule']
    for v, pretty in order:
        r = row(lbl, v)
        if r is None: continue
        L.append(f'{pretty} & ${r.coef:.3f}{star(r.p)}$ & ({r.se:.3f}) \\\\')
    L += [r'\bottomrule', r'\end{tabular}',
          r'\par\medskip\footnotesize\textit{Notes:} Two-way FE, county-clustered SEs. '
          r'Insignificant leads ($t+1$, $t+2$) indicate no pre-trends; significant lags support '
          r'a forward-looking pipeline. $^{*}p<.05$, $^{**}p<.01$.',
          r'\end{table}']
    return '\n'.join(L)


out.append(pretrends_table())

text = '\n\n'.join(out)
(ROOT / 'outputs' / 'appendix_tables.tex').write_text(text)
print(text)
