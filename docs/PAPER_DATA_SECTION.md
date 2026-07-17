# Data

## Panel structure

The analysis uses a balanced panel of Michigan's 83 counties observed
annually from 2010 through 2023 (1,162 county-year observations across
100 variables). Each row represents a single county in a single year.
Variables are drawn from nine public federal data systems and one
manually compiled licensure dataset; all but the licensure dataset are
reproducible through a single automated pull script
(`scripts/regressors_data_script.py`) using the publicly documented APIs
and bulk-download endpoints described below.

## Data sources

### Outcomes — nursing supply (manual compilation)

The dependent variables — county-level counts and per-capita rates of
licensed Registered Nurses (RNs) and Licensed Practical Nurses (LPNs),
together with their age distributions — were compiled by hand from
Michigan Department of Licensing and Regulatory Affairs (LARA) licensure
records. LARA does not publish a clean county-year time series; the
underlying licensure registry was queried at multiple snapshot dates,
de-duplicated on license number, and geocoded to county of practice.
Age-bracket shares (`rn_age_under35_pct`, `rn_age_55plus_pct`, and the
LPN equivalents) summarise the workforce-aging dimension central to the
study. Per-100,000 rates use ACS 5-year total population in the
denominator. These columns are the only ones not reproducible from
automated public pulls.

### Demographic and socioeconomic controls — U.S. Census Bureau, American Community Survey 5-Year Estimates (ACS5)

Population structure, income, housing, education, health insurance,
labor-force participation, commuting behaviour, poverty, and
race/ethnicity composition are sourced from the Census Bureau's ACS
5-year API. The 5-year file is used rather than the 1-year file because
1-year estimates are suppressed for any county with population below
65,000, which would exclude most of rural Michigan. Variables are
constructed from detail tables as follows:

| Construct | ACS table | Formula |
|---|---|---|
| `pop_total` | B01001_001E | Raw |
| `pct_65plus` | B01001 | (males 65+ + females 65+) ÷ total pop × 100 |
| `pct_25_54` | B01001 | (males 25–54 + females 25–54) ÷ total pop × 100 |
| `median_hh_income` | B19013_001E | Raw, nominal dollars |
| `median_gross_rent` | B25064_001E | Raw |
| `median_home_value` | B25077_001E | Raw |
| `unemployment_rate` | B23025 | Unemployed ÷ civilian labor force × 100 |
| `lfp_rate` | B23025 / B01001 | In labor force ÷ total pop × 100 |
| `pct_bachelors_plus` | B15003 (≥2012); B15002 (2010–11) | Bachelor's-or-higher ÷ pop 25+ × 100 |
| `pct_uninsured` | B27001 (≥2012) | Sum of uninsured age-sex cells ÷ universe × 100 |
| `pct_commute_30plus` | B08303 | Workers with 30+ min commute ÷ workers 16+ × 100 |
| `mean_commute_minutes` | B08136 / B08101 | Aggregate travel minutes ÷ workers |
| `rent_burden_pct` | B25070 | Renter households spending ≥30% income on rent |
| `own_burden_pct` | B25091 | Owner households spending ≥30% income on housing |
| `poverty_rate` | B17001 | Population below poverty ÷ total × 100 |
| `pct_white/black/asian` | B02001 | Race share of total × 100 |
| `pct_hispanic` | B03003 | Hispanic share of total × 100 |

**Time coverage caveat.** Several ACS tables were not published in the
earliest years of the panel: B15003 (educational attainment) and B27001
(health insurance) were introduced in the 2012 release, and B23025
(labor force) in 2011. For 2010–2011 educational attainment, we
substitute B15002, which uses different bracket structure but yields a
comparable bachelor's-or-higher share. No backfill exists for the
2010–2011 uninsured-rate or 2010 unemployment cells, which are recorded
as missing. The 5-year ACS file additionally suppresses
`B08136_001E` (aggregate travel time) for small counties to protect
respondent confidentiality, causing `mean_commute_minutes` to be missing
for roughly half of Michigan counties in any given year. This is a
property of the source and not the result of any analytic choice.

### Health workforce and facility infrastructure — HRSA Area Health Resources Files (AHRF)

County-level counts of hospitals (`hosp`), hospital beds (`hosp_beds`),
hospital admissions (`hosp_adm`), nursing facilities and beds
(`nurs_fac`, `nurs_fac_beds`), critical-access hospitals
(`critcl_access_hosp`), federally qualified health centers
(`fedly_qualfd_hlth_ctr`), community mental health centers
(`comn_mentl_hlth_ctr`), rural health clinics (`rural_hlth_clincs`), and
National Health Service Corps sites (`nhsc_sites`, `nhsc_fte_provdrs`)
are drawn from the Health Resources & Services Administration's
**Area Health Resources Files** (AHRF), an annually released
county-level compendium. Physician counts by specialty
(`md_nf_*`, `phys_nf_prim_care_*`, `do_nf_activ`), short-term general
hospital staffing (`stgh_aprn_*`, `stgh_nursng_asst_ft_incl_nh`,
`stgh_fte_lpnlvn_incl_nh`), and Medicare fee-for-service utilisation
measures (`medcr_ffs_eligbl_medcd_pct`, `medcr_ffs_hosp_readm_rate`,
`medcr_ffs_prev_hosp_rate`) are similarly AHRF-sourced. AHRF
distributes data as fixed-width ASCII files paired with SAS layout
documents; these are parsed with a custom parser
(`scripts/parse_ahrf_asc.py`) that reads the SAS INPUT block to locate
each field. Coverage runs annually but variables can be released with
1–2 year lags depending on the upstream administrative source.

### Health-system designations — HRSA Bureau of Health Workforce

Health Professional Shortage Area (HPSA) designations are pulled from
HRSA's Data Warehouse. We obtain three separate per-discipline files:
primary care (`hpsa_prim_care`), dental health (`hpsa_dent`), and
mental health (`hpsa_mentl_hlth`). Each county-year value is the count
of currently-designated HPSAs in that county. Because HRSA publishes
only the current snapshot rather than a designation history, these
values are applied as time-invariant within the panel window; this
follows standard practice in the rural-health literature given the
slow turnover of HPSA designations.

### Educational pipeline — IPEDS Completions Survey (NCES)

Annual counts of nursing credentials awarded by Michigan postsecondary
institutions come from the National Center for Education Statistics'
Integrated Postsecondary Education Data System (IPEDS) Completions
file. Credentials are bucketed by Classification of Instructional
Programs (CIP) code: 51.3801 (Registered Nursing,
`ipeds_completions_rn`), 51.3901 (LPN, `ipeds_completions_lpn`),
51.3902 (Nursing Assistant/Aide, `ipeds_completions_cna`), and the
remainder of the 51.39 family (`ipeds_completions_other_nursing`).
Institutions are mapped to their county of operation using the IPEDS
Institutional Directory (HD) file for the same release year, so
counts reflect program location rather than student origin.
`ipeds_completions_total` is the sum across the four buckets.

### Chronic disease and population health — County Health Rankings (CHR)

Headline County Health Rankings measures are sourced from the
University of Wisconsin Population Health Institute and the Robert
Wood Johnson Foundation's annual analytic data release. The columns
prefixed `chr_` include premature death rate
(`chr_premature_death_rate`), preventable hospital-stay rate
(`chr_preventable_hosp_rate`), self-reported fair/poor health
(`chr_pct_fair_poor_health`), low-birthweight rate, primary-care
physician and dentist provider rates, percent uninsured (`chr_pct_uninsured`,
distinct from the ACS measure and based on CDC SAHIE), adult smoking
and obesity prevalence, average mentally-unhealthy days per month, and
percent of children in poverty. CHR releases are dated by publication
year but the underlying source-year for each measure varies (a feature
of CHR's roll-up methodology). The CHR website blocks scripted
downloads; the annual analytic CSVs are obtained manually and cached
locally for the rebuild script.

### County typologies — USDA Economic Research Service

Persistent structural characteristics of each county come from USDA
ERS county-classification files: the 2013 Rural-Urban Continuum Code
(`rural_urban_contnm`, a 1–9 metropolitan-to-rural ordinal scale), the
2013 Urban Influence Code (`urban_influnc`), and the 2015 Economic
Dependence and Policy Typology release. Typology indicators include
the dominant economic activity (`econ_depndnt_typolgy`,
`mfg_depndnt_typolgy`, `recrtn_typolgy`) and policy-relevant
classifications (`hi_povty_typolgy`, `prstnt_povty_typolgy`,
`popn_loss_typolgy`, `retrmnt_destntn_typolgy`). These designations
are revised infrequently (roughly once per decade) and are treated as
time-invariant within the panel.

### Core-Based Statistical Area assignments — OMB

Each county's metropolitan/micropolitan affiliation (`cbsa`,
`cbsa_name`, `cbsa_ind`) comes from the most recent OMB CBSA delineation
file (vintage 2023). Counties not assigned to a CBSA are non-core and
appear as missing on these fields. Roughly 39% of Michigan
county-year observations fall outside a CBSA, reflecting the state's
substantial rural geography.

### Land area and density — Census Gazetteer

County land area in square miles (`land_area_mi2`) comes from the 2020
Census Gazetteer Files. Population density
(`popn_densty_per_squr_mi`) is computed as ACS 5-year total population
divided by land area; it therefore varies year-over-year even though
the denominator is fixed.

## Time coverage and missing observations

The panel covers 2010 through 2023 inclusive (14 years). All 83
Michigan counties are present in every year, yielding a balanced
83 × 14 = 1,162-row spine. The cells that are nonetheless missing
reflect documented coverage limits of the source data rather than
analytical exclusions:

| Variable group | Years missing | Reason |
|---|---|---|
| ACS uninsured (`pct_uninsured`) | 2010, 2011 | Table B27001 introduced in 2012 ACS5 |
| ACS unemployment / LFP | 2010 | Table B23025 introduced in 2011 ACS5 |
| ACS mean commute time | All years, ~50% of counties | Census suppression for small counties |
| AHRF physician specialty cells | Selected years | Variable retirements in AHRF source |
| CBSA fields | All years, ~39% of counties | Non-core counties have no CBSA assignment |
| 2018 across multiple sources | 2018 only | Coincident gap in earlier panel build; available in rebuild |

All other variables are populated for the full 83 × 14 grid where the
underlying source supports it.

## Reproducibility

With the exception of the manually compiled LARA nursing licensure
columns and two sources that block scripted downloads (CHR and AHRF,
which require manual one-time file deposits in `data/cache/`), the
entire 90-column regressor block was assembled from public sources by
a build script that caches all downloads locally for replication.
The build chain and its documentation are retained by the author; the
published repository ships the resulting analytic panel (see
`DATA_ACCESS.md`).
