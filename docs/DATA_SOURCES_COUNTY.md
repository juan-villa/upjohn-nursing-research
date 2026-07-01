# Data Sources — county panel (`county-master.csv`)

Where each variable comes from, **and how it is constructed** if the raw source values are transformed before entering the panel.

"Raw" means the value is taken directly from the upstream dataset. Everything else is computed from one or more raw values per the formula given.

830 county-years × 22 columns. 83 Michigan counties, 2015–2024.

Note: Counties are smaller than MSAs and many do not contain hospitals.
The hospital-industry variables (NAICS 622) appear only where the BLS
reports activity for that county. Variables marked "ACS 5-year" use the
5-year estimates because the 1-year file is suppressed for counties with
population under 65,000.

---

## Identifiers

| Variables | Source | Construction |
|---|---|---|
| `fips` | Census | 5-digit county FIPS. |
| `county_name` | Census | Raw county name (stripped of "County, Michigan" suffix). |
| `year` | — | Calendar year, 2015–2024. |

## Hospital industry — outcome proxy (BLS QCEW NAICS 622)

| Variables | Source | Construction |
|---|---|---|
| `hosp_emp`, `hosp_wkly_wage`, `hosp_estabs` | BLS QCEW NAICS 622 (Hospitals), ownership 5 (Private) | Raw — annual averages for the hospital industry at county. |
| `hosp_emp_per_100k` | derived | `hosp_emp / pop_total × 100,000`. |
| `hosp_emp_growth` | derived | YoY percent change in `hosp_emp` within county. |
| `hosp_wkly_wage_real` | derived | `hosp_wkly_wage × (CPI_U[2024] / CPI_U[year])`. National CPI-U. |
| `hosp_wkly_wage_growth` | derived | YoY percent change in `hosp_wkly_wage_real` within county. |

## Stress

| Variables | Source | Construction |
|---|---|---|
| `covid_hosp_per_100k` | HHS Protect / CDC NHSN (state aggregate) | State-level annual peak admissions per 100k applied uniformly to all MI counties. **No county-level variation** in this file — for true county variation, aggregate the facility-level HHS Protect data (the same logic used at MSA level in `master_panel.csv`). |

## Chronic disease (CDC PLACES, county level)

| Variables | Source | Construction |
|---|---|---|
| `diabetes_pct`, `hypertension_pct`, `mental_distress_pct` | CDC PLACES county dataset | Raw — county-level prevalence from PLACES. Cross-sectional snapshot attached to all panel years (PLACES doesn't publish a long time series). |

## Demographics (ACS 5-year)

| Variables | Source | Construction |
|---|---|---|
| `pop_total` | ACS 5-year B01001_001E | Raw. |
| `pct_65plus` | ACS 5-year B01001 | `(Σ males 65+ : 020–025E + Σ females 65+ : 044–049E) / B01001_001E × 100`. |
| `pct_uninsured` | ACS 5-year B27001 | `Σ("no insurance" buckets, positions 5, 8, 11, …, 57) / B27001_001E × 100`. Uses detail table for stability across years. |

## Economic controls (ACS 5-year)

| Variables | Source | Construction |
|---|---|---|
| `median_hh_income` | ACS 5-year B19013_001E | Raw, nominal dollars. |
| `median_gross_rent` | ACS 5-year B25064_001E | Raw, nominal dollars. |
| `unemployment_rate` | ACS 5-year B23025 | `B23025_005E / B23025_003E × 100`. |
| `lfp_rate` | ACS 5-year B23025 / B01001 | `B23025_002E / B01001_001E × 100`. |
| `pct_bachelors_plus` | ACS 5-year B15003 | `Σ(B15003_022E..025E) / B15003_001E × 100`. |
