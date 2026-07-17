# Nurse Workforce Variables — Data Sources

Michigan county-year panel (FIPS state 26, 83 counties). All three variables drawn from the
**Area Health Resources Files (AHRF)**, HRSA Bureau of Health Workforce.
Download portal: https://data.hrsa.gov/data/download

## Variables

| Variable | AHRF label | Original source | Unit |
|---|---|---|---|
| `np_npi` | Nurse Practitioners w/ NPI | CMS National Provider Identifier (NPI) file | Registry stock count, practice/mailing address |
| `stgh_rn_ft_incl_nh` | Registered Nurses, Full-Time (Incl. Nursing Homes; Short-Term General Hospitals) | AHA Annual Survey Database | Facility-reported headcount, hospital county |
| `stgh_rn_pt_incl_nh` | Registered Nurses, Part-Time (Incl. Nursing Homes; Short-Term General Hospitals) | AHA Annual Survey Database | Facility-reported headcount, hospital county |

## AHRF releases used

| Release zip | Provides |
|---|---|
| `AHRF_2024-2025_CSV.zip` | np_npi 2023–2024; RN FT/PT 2022, 2023 |
| `AHRF_2021-2022.ZIP` | np_npi 2010–2021; RN FT/PT 2020 |
| `AHRF_2020-2021.ZIP` | RN FT/PT 2019 |
| `AHRF_2019-2020.ZIP` | RN FT/PT 2018 |

Base path: `https://data.hrsa.gov/DataDownload/AHRF/`

## Year coverage (post-merge)

- **np_npi**: 2010–2021, 2023, 2024 — missing **2022** only.
- **stgh_rn_ft_incl_nh / stgh_rn_pt_incl_nh**: 2018, 2019, 2020, 2022, 2023.

## Coverage limits (not recoverable from AHRF)

- AHRF redistributes only the most recent AHA survey year(s) per release (AHA Annual Survey
  is licensed). RN FT/PT for **2010–2017 and 2021** is therefore unavailable from AHRF;
  it would require a direct **AHA Annual Survey Database** license.
- np_npi 2022 was not retained in any hosted release; HRSA does not host the 2011–2018 or
  2022–2023 county releases.

## Measurement notes

- `np_npi` is a registry **stock** count at the provider's practice/mailing address.
- `stgh_rn_*` are hospital-reported **headcounts** assigned to the hospital's county (not RN
  residence), covering short-term general hospitals + attached nursing homes only — excludes
  clinic, home-health, school, and other RNs. AHA survey nonresponse is imputed, so county
  counts can shift when a hospital's response status changes year to year.
- The two series have different denominators and should not be pooled into a single
  "nurse supply" measure.

## Validation

New 2023 values reproduce the master panel's prior constant `*_23` columns exactly
(0 mismatches across all 83 counties), confirming correct field/year alignment.

## Pipeline

Built with `build_ahrf_nurse_panel.py` (parses AHRF technical-documentation xlsx for field
byte-positions and years, slices fixed-width ASCII / melts CSV releases for Michigan).
Output: `ahrf_mi_nurse_panel_full.csv` → merged into `michigan_nurse_county_panel.csv`.

_Source portal: HRSA AHRF, https://data.hrsa.gov/topics/health-workforce/nchwa/ahrf_
