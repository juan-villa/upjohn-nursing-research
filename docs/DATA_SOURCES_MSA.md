# Data Sources — MSA panel (`master_panel.csv`)

Where each variable comes from, **and how it is constructed** if the raw source values are transformed before entering the panel.

"Raw" means the value is taken directly from the upstream dataset. Everything else is computed from one or more raw values per the formula given.

148 MSA-years × 37 columns. 14 Michigan MSAs, 2012–2024.

---

## Identifiers

| Variables | Source | Construction |
|---|---|---|
| `year` | — | Calendar year. For HCRIS-derived variables, this is the fiscal-year-end year of the cost report. |
| `area_id`, `area_title` | BLS OEWS | Raw area label; `area_id` is a lowercase slug of `area_title`. |
| `cbsa` | OMB / Census | Raw 5-digit CBSA code per OMB 2023 delineations. |

## RN labor market

| Variables | Source | Construction |
|---|---|---|
| `tot_emp`, `emp_prse`, `loc_quotient`, `h_median` | BLS OEWS, SOC 29-1141 | Raw — filtered to Michigan MSAs and the Registered Nurses SOC code. |
| `h_median_real` | BLS OEWS + BLS CPI-U | `h_median × (CPI_U[2024] / CPI_U[year])`. National CPI-U deflator (regional CPI is not available for all MSAs). |
| `h_median_growth` | derived | Year-over-year percent change in `h_median_real` within each MSA: `pct_change()` after sorting by year. First year per MSA is NaN. |
| `h_median_loo` | derived | Leave-one-out mean across other MI MSAs in the same year: `(Σ h_median_real_year × n − own value) / (n − 1)`. Used as a candidate instrument for own wage. |
| `rn_per_1k_raw` | derived | Naïve RN headcount per 1,000 residents: `tot_emp / pop_total × 1,000`. |
| `effective_pop` | derived | Age-weighted "residents-equivalent" denominator: `pop_under65 + 2 × pop_65to74 + 4 × pop_75plus`. Weights approximate HCUP/NIS hospital-discharge rate ratios by age group. |
| `rn_per_1k_adj` | derived | Demand-weighted RN density: `tot_emp / effective_pop × 1,000`. Indirect age standardization following HRSA workforce-projection methodology. |

## Shortage outcome (HCRIS)

| Variables | Source | Construction |
|---|---|---|
| `contract_labor_share` | CMS HCRIS Form 2552-10, Worksheet S-3 Part II | For each hospital, extract line 1 col 5 (total wages), line 14.01 col 5 (contract DPC labor), line 14.02 col 5 (contract excluded labor). MSA share: `Σ_hospitals (line 14.01 + line 14.02) / Σ_hospitals (line 1 + line 14.01 + line 14.02)`. Wage-weighted so larger hospitals dominate. |
| `n_hospitals_reporting` | CMS HCRIS | Count of unique provider numbers contributing non-zero rows to that MSA-year. |

## Stress (HHS Protect facility data)

| Variables | Source | Construction |
|---|---|---|
| `covid_peak_per_100k` | HHS Protect `anag-cw7u` + ACS pop | Step 1: facility weekly admissions (col `total_adult_patients_hospitalized_confirmed_covid_7_day_avg`) summed across hospitals within MSA via county FIPS → MSA crosswalk. Step 2: divide by MSA population × 100,000. Step 3: take the annual `max()` across weeks. Pre-2020 set to 0. |
| `covid_avg_per_100k` | same | Same as above but `mean()` instead of `max()` over weeks. |

## Demographics (ACS 1-year)

| Variables | Source | Construction |
|---|---|---|
| `pop_total` | ACS B01001_001E | Raw. |
| `pct_65plus` | ACS B01001 | `(Σ males 65+ : 020–025E + Σ females 65+ : 044–049E) / B01001_001E × 100`. |
| `pct_75plus` | ACS B01001 | `(Σ males 75+ : 023–025E + Σ females 75+ : 047–049E) / B01001_001E × 100`. |
| `pct_uninsured` | ACS S2701_C05_001E | Raw — Census-published "percent uninsured" from the subject table. |

## Chronic disease (CDC PLACES)

| Variables | Source | Construction |
|---|---|---|
| `diabetes_pct`, `hypertension_pct`, `mental_distress_pct`, `copd_pct`, `obesity_pct` | CDC PLACES county-level (`swc5-untb`) | County-level prevalence, **population-weighted** to MSA: `Σ_counties (prevalence_c × pop_c) / Σ_counties pop_c`. PLACES doesn't publish a long time series, so these values are a single cross-section attached to every panel year (time-invariant). |

## Economic controls (ACS 1-year)

| Variables | Source | Construction |
|---|---|---|
| `median_hh_income` | ACS B19013_001E | Raw, nominal dollars (not deflated). |
| `median_gross_rent` | ACS B25064_001E | Raw, nominal dollars. |
| `unemployment_rate` | ACS B23025 | `B23025_005E / B23025_003E × 100` (unemployed / civilian labor force). |
| `lfp_rate` | ACS B23025 / B01001 | `B23025_002E / B01001_001E × 100` (population 16+ in labor force / total population). |
| `pct_bachelors_plus` | ACS B15003 | `Σ(B15003_022E..025E) / B15003_001E × 100` (bachelor's + master's + professional + doctorate / population 25+). |

## Hospital supply

| Variables | Source | Construction |
|---|---|---|
| `hospital_count` | CMS HCRIS + CMS Hospital General Info | Count of unique HCRIS-reporting hospitals in the MSA-year. Hospital → MSA mapping uses the hospital's County/Parish from CMS Hospital General Info → county FIPS → CBSA. |
| `hospital_beds` | CMS HCRIS S-3 I line 14 col 2 | Sum of `beds_available` across hospitals in the MSA-year. |
| `beds_per_100k` | derived | `hospital_beds / pop_total × 100,000`. Requires both HCRIS bed sum and ACS population to be non-missing. |

## Policy levers

| Variables | Source | Construction |
|---|---|---|
| `magnet_hospitals` | ANCC Magnet directory (hand-curated) | Cumulative count of ANCC Magnet-certified hospitals in the MSA at year *t*: count of hospitals where the MSA matches and `t >= first_certification_year`. Names matched to MSA manually. |
| `magnet_active` | derived | `1 if magnet_hospitals > 0 else 0`. |

*Note*: Lorna Breen and MIHEF grant exposure variables are pulled by `scripts/pulls/policy_verified.py` and saved to `policy_levers.csv`, but were excluded from `master_panel.csv` because too few MSAs receive these grants (5–7 of 14) for the variables to support quantitative inference. They remain available for descriptive use.
