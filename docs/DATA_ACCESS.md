# Data access and provenance

This project reproduces from **derived** analytic panels that are committed to
the repo. The **raw** sources used to build those panels are not committed:
some are proprietary and cannot be redistributed, and others are large. This
document lists every source, its license status, and where to obtain it.

## What is committed

| Path | Contents | Status |
|---|---|---|
| `data/analytic/regression-data-base.csv` | Canonical county x year panel (83 counties, 2010-2023, ~140 columns). Feeds the main regression tables. | committed (derived aggregate) |
| `data/analytic/claude_merge_recon_neigh_w_final_reg_v2.csv` | Panel used by the mechanism / policy-lever models and the maps. | committed (derived aggregate) |
| `data/analytic/final-regressions-data.csv` | Panel snapshot used by the heatmap notebook. | committed (derived aggregate) |
| `data/analytic/full-in-progress.rebuilt.csv` | Intermediate build reference. | committed |
| `data/shp/cb_2022_us_county_20m.*` | US Census cartographic county boundaries. | committed (public domain) |

These aggregated panels are sufficient to reproduce every result in the paper.

## What is NOT committed (raw / licensed)

Held locally in `data/raw/` (gitignored). To rebuild the panels from scratch
you must obtain these yourself:

| Source | Used for | License | How to obtain |
|---|---|---|---|
| **Lightcast** job postings | RN/LPN job-posting outcomes and posted wages | Proprietary (subscription) | Lightcast (formerly Emsi Burning Glass); institutional license required |
| **Michigan Nurse Map** licensed nurse counts | Legacy licensed-nurse outcome + age distribution | Restricted use (MI DLARA) | Michigan Dept. of Licensing and Regulatory Affairs |
| **ACS 5-Year** (tables + PUMS) | Demographics, education, wages | Public | Census API, `api.census.gov/data/{year}/acs/acs5` (needs a free `CENSUS_API_KEY`) |
| **County Health Rankings** | Health-demand measures (`chr_*`) | Public | countyhealthrankings.org |
| **AHRF** | Facilities, providers, county typology | Public | HRSA Area Health Resources Files |
| **IPEDS** completions | Nursing training pipeline | Public | NCES IPEDS |
| **HCRIS** | Hospital financial aggregates | Public | CMS Healthcare Cost Report Information System |
| **OEWS** | RN/LPN wages by MSA | Public | BLS Occupational Employment and Wage Statistics |

## Rebuilding the panels (advanced)

The build scripts live in `src/` (for example `regressors_data_script.py`,
`build_lightcast_panel.py`, `merge_lightcast_into_panel.py`,
`recover_2018_rows.py`). They expect the raw inputs in `data/raw/` and a
`CENSUS_API_KEY` in the environment. Because the Lightcast and Nurse Map inputs
cannot be redistributed, `make data` does not run automatically for outside
users; it prints these instructions instead. See the source comments in each
script for exact input filenames.
