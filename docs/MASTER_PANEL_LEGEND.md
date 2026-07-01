# master_panel.csv — Variable Legend

**Coverage:** 115 rows = 14 Michigan MSAs × up to 10 years (2015–2024). Smaller MSAs (Jackson, Midland, Monroe, Niles) have fewer years due to BLS wage suppression or ACS publication thresholds.

## Identifiers

| Variable | Description | Source |
|---|---|---|
| `year` | Calendar year (2015–2024). | — |
| `area_id` | Stable lowercase slug of MSA name (e.g. `ann_arbor_mi`). Use this as the join key for regressions. | — |
| `area_title` | Official BLS MSA name (e.g. `Ann Arbor, MI`). 2024 BLS naming used throughout. | OEWS |
| `cbsa` | 5-digit Census CBSA code. Use to merge with Census/CMS data. | OMB delineations |

## RN labor market — OEWS

| Variable | Description | Notes |
|---|---|---|
| `tot_emp` | Total Registered Nurse employment in the MSA. Headcount, not FTE. | BLS suppresses small cells. |
| `emp_prse` | Percent relative standard error of `tot_emp`. Higher = noisier estimate. | Use as weight or filter. |
| `loc_quotient` | RN concentration relative to U.S. average. LQ=1 matches national; <1 indicates under-supply, >1 indicates over-supply. | — |
| `h_median` | Median hourly RN wage, nominal USD. | — |
| `h_median_real` | Median hourly wage, CPI-U deflated to 2024 USD. | Uses national CPI-U; ideally would use regional. |
| `h_median_growth` | Year-over-year % change in `h_median_real`. Revealed-shortage proxy. | First year of each MSA is NaN. |
| `h_median_loo` | Leave-one-out mean of `h_median_real` across other MI MSAs in the same year. Candidate instrument for wage. | First-stage F is weak; not currently used. |

## Shortage outcome — CMS HCRIS

| Variable | Description | Notes |
|---|---|---|
| `contract_labor_share` | Share of total nursing labor outlay paid as contract/agency labor (vs employed staff). Computed from HCRIS Worksheet S-3 Part II, line 14.01 + 14.02 / (line 1 + 14.01 + 14.02). MSA-aggregated and total-wage-weighted. | **Primary shortage outcome.** Higher = hospitals can't fill positions with staff RNs. |
| `n_hospitals_reporting` | Count of MI hospitals contributing to that MSA-year's HCRIS calculation. | Indicator of HCRIS coverage; small numbers signal noisy estimates. |

## Stress regressor — HHS Protect COVID

| Variable | Description | Notes |
|---|---|---|
| `covid_peak_per_100k` | Annual peak weekly COVID-19 adult hospital admissions per 100,000 population, aggregated from facility-level HHS Protect data. | Primary stress measure. Pre-2020 = 0. |
| `covid_avg_per_100k` | Annual average weekly COVID admissions per 100k. | Smoother variant; useful for robustness. |

## Demographic / demand-side controls — ACS 1-year

| Variable | Description | Source |
|---|---|---|
| `pop_total` | Total MSA population (ACS B01001_001E). | ACS 1-year |
| `pct_65plus` | Percent of population age 65+ (sum of B01001 male/female 65+ buckets). Demand driver. | ACS 1-year |
| `pct_uninsured` | Percent of civilian noninstitutionalized population without health insurance. | ACS S2701 |

## Economic controls — ACS 1-year

| Variable | Description | Source |
|---|---|---|
| `median_hh_income` | Median household income, nominal USD. | ACS B19013 |
| `median_gross_rent` | Median monthly gross rent, nominal USD. Housing-cost proxy. | ACS B25064 |
| `unemployment_rate` | Civilian unemployment rate (%) = unemployed / labor force. | ACS B23025 |
| `lfp_rate` | Labor force participation rate (%) = LF / total pop. | ACS B23025 |
| `pct_bachelors_plus` | Percent of population 25+ with bachelor's degree or higher. Nursing-supply pipeline proxy. | ACS B15003 |

## Policy levers — verified hand-curated

| Variable | Description | Source |
|---|---|---|
| `magnet_hospitals` | Cumulative count of ANCC Magnet-certified hospitals in the MSA in that year. | ANCC public list |
| `magnet_active` | 1 if any Magnet hospital is active in the MSA that year, else 0. | derived |

Lorna Breen and MIHEF grant variables exist in `policy_levers.csv` but were excluded from `master_panel.csv` — too few recipients (5–7 MSAs) to support quantitative inference. Available as descriptive context only.

## What is *not* in this file

- `case_mix_index` — would require CMS IPPS Impact Files (annual xlsx, URLs unstable). Dropped from the master.
- `covid_hosp_per_100k` — old back-compat alias of `covid_peak_per_100k`; removed.
- Hospital bed capacity by MSA — pullable from HHS Protect `total_beds_7_day_avg` if needed.
- Nurse-to-patient ratios — Michigan has no mandate; not collected.
- MHA vacancy rates — would require manual PDF transcription.
