# `michigan_nurse_county_panel.csv` — Data Dictionary

**Panel structure**: 83 Michigan counties × 13 years (2010–2023, with 2018 absent from underlying AHRF spine). 1,079 rows × 131 columns.

**Unit conventions**:
- Outcomes per 100,000 residents
- Pipeline measures per 10,000 residents
- Density measures per 1,000 residents
- Wage in nominal annual dollars (or hourly where noted)

## Panel keys

| Column | Type | Description |
|---|---|---|
| `fips` | str (5-digit) | County FIPS code, zero-padded |
| `county_name` | str | County name (no "County" suffix) |
| `year` | int | Calendar year |

## Outcomes

| Column | Type | Source | Description |
|---|---|---|---|
| `rn_per_100k` | float | MI nurse licensure / state board | RN density per 100,000 residents |
| `lpn_per_100k` | float | same | LPN density per 100,000 residents |
| `rn_licensed_county` | float | same | Count of licensed RNs residing in county |
| `lpn_licensed_county` | float | same | Count of licensed LPNs |
| `nurse_total_count` | float | derived | RN + LPN |
| `nurse_total_per_100k` | float | derived | RN/100K + LPN/100K |
| `rn_age_under35_pct`, `rn_age_55plus_pct` | float | state board surveys | RN age structure (sparse: only certain years) |
| `lpn_age_under35_pct`, `lpn_age_55plus_pct` | float | same | LPN age structure (sparse) |

## Demand-side covariates

| Column | Source | Description | Causal-credibility |
|---|---|---|---|
| `share_65plus` | ACS-direct, B01001 → AHRF fallback | Share of population aged 65+ (%) | Causal-leaning (predetermined demographic) |
| `pct_25_54` | ACS B01001 | Share aged 25–54 (%) | Same |
| `disability_rate` | ACS-direct, C18120 → AHRF fallback | % of civilian noninstitutionalized 18–64 with a disability | Causal-leaning |
| `uninsured_rate` | ACS-direct, B27001 | % uninsured (population-wide) | Causal-leaning |
| `poverty_rate` | ACS B17001 → AHRF SAIPE fallback | % below federal poverty line | Causal-leaning |
| `bachelors_plus_share` | ACS B15003 (modern) + B15002 (legacy 2010–11) → AHRF fallback | % of adults 25+ with bachelor's degree or higher | Causal-leaning |

## Supply-side covariates

| Column | Source | Description | Causal-credibility |
|---|---|---|---|
| `ipeds_rn_per_10k_lag1` | IPEDS CIP 51.3801, lagged 1 yr, per 10K | **Defensible causal — RN pipeline (null at all tested lags due to mobility)** | |
| `ipeds_lpn_per_10k_lag1` | IPEDS CIP 51.3901, lagged 1 yr, per 10K | **Defensible causal — LPN pipeline (+4.31, p<.001)** | |
| `hpsa_prim_care` | HRSA HPSA designation count | Primary-care shortage designation (count) | **Endogenous** — mechanically tied to physician shortage |
| `hosp_beds_per_1k` | AHRF (hosp_beds / popn_est × 1000) | Hospital beds per 1,000 residents | **Endogenous** — capacity / supply simultaneity |
| `nh_beds_per_65plus_cms` | CMS NH Provider Info snapshot (time-invariant) | Certified nursing-home beds per 1,000 aged 65+ | **Endogenous** |
| `nh_beds_per_65plus_ahrf` | AHRF (nurs_fac_beds / pop_65plus × 1000) | Same concept, year-varying | **Endogenous** |
| `magnet_hospital_present` | ANCC × CBSA crosswalk → 0 for non-Magnet counties | Binary: county is in a CBSA with a Magnet hospital | **Selection on outcome** |
| `rn_pums_wage`, `lpn_pums_wage` | ACS PUMS, PUMA × occupation × year, mapped to counties | Median hourly wage in ADJINC-deflated harmonized dollars | **Endogenous** (simultaneous price determination) |
| `rn_a_median`, `lpn_a_median`, `rn_h_median`, `lpn_h_median` | OEWS MSA-level, mapped to counties via `MI_COUNTY_TO_MSA` | OEWS median annual/hourly wage | **Endogenous** (MSA-level, even less identification than PUMS) |
| `rn_tot_emp`, `lpn_tot_emp` | OEWS | MSA-level employment count | Endogenous |
| `rn_a_mean`, `rn_h_mean`, `lpn_a_mean`, `lpn_h_mean` | OEWS | Mean wage variants | Endogenous |

## Disadvantage / structural controls

| Column | Source | Description |
|---|---|---|
| `median_hh_income` | ACS B19013 | Median household income |
| `median_gross_rent` | ACS B25064 | Median gross rent |
| `median_home_value` | ACS B25077 | Median home value |
| `unemployment_rate` | ACS B23025 | Unemployment rate (%) |
| `lfp_rate` | ACS B23025 | Labor-force participation rate (%) |
| `rent_burden_pct` | ACS B25070 | % renters paying ≥30% of income for rent |
| `own_burden_pct` | ACS B25091 | % owners with mortgages paying ≥30% of income |
| `mean_commute_minutes`, `pct_commute_30plus` | ACS B08303/B08136 | Commute duration measures |

## Hospital cost / interaction terms

| Column | Source | Description | Causal status |
|---|---|---|---|
| `has_medicare_hospital` | Rebuilt from `n_hospitals > 0` (year-varying) | Binary: 1 if county had a Medicare-billing hospital in year t | Mostly time-invariant; identifies in cross-section only |
| `overhead_ratio_wmean` | HCRIS county panel | Weighted-mean hospital overhead cost ratio | **Endogenous** (reverse causation through contract-labor accounting) |
| `has_med_hosp_x_overhead` | `has_medicare_hospital × overhead_ratio_wmean.fillna(0)` | Interaction term | **Degenerate** — collinear with overhead in the Medicare-hospital sub-sample. Not a true slope-difference identifier. |
| `operating_margin_wmean` | HCRIS | Weighted-mean operating margin | Endogenous |
| `net_income_per_bed_wmean` | HCRIS | Weighted-mean net income per bed | Endogenous |
| `total_beds`, `n_hospitals` | HCRIS | Sums across county | NaN for non-Medicare-hospital counties |
| `single_hospital_county` | HCRIS | Boolean | NaN for non-Medicare-hospital counties |

## Instruments

| Column | Source | Description | Status |
|---|---|---|---|
| `bartik_iv` | QCEW 2014 county industry shares × OEWS national RN wage growth | Bartik IV for RN wage | **Weak first stage (F<1) in MI-only sample** |
| `bartik_iv_lpn` | Same shares × national LPN wage growth | Bartik IV for LPN wage | **Weak first stage (F<1)** |

## Demographic shares

`pct_white`, `pct_black`, `pct_asian`, `pct_hispanic` — ACS B02001/B03003 county shares.

## Robustness columns (for lag-5 capacity diagnostic)

| Column | Description |
|---|---|
| `hosp_beds_per_1k_ahrf_lag5` | 5-year lag of AHRF-derived hospital bed density |
| `nh_beds_per_65plus_ahrf_lag5` | 5-year lag of AHRF-derived NH bed density |

## AHRF cryptic names (HRSA convention)

These come from the AHRF parser and inherit HRSA's abbreviated naming. All are time-varying counts unless noted.

| Column | Description |
|---|---|
| `stgh` | Short-Term General Hospitals (count) |
| `stgh_aprn_ft` | STGH full-time Advanced Practice RNs |
| `stgh_aprn_pa` | STGH full-time APRN + Physician Assistant |
| `stgh_fte_lpnlvn_incl_nh` | STGH full-time-equivalent LPN/LVN (including nursing-home staff) |
| `stgh_nursng_asst_ft_incl_nh` | STGH full-time Nursing Assistants (incl. NH) |
| `md_nf_activ` | Active non-federal MDs (count) |
| `md_nf_pc_hosp_all` | Non-federal MDs in patient-care hospital-based positions |
| `md_nf_pc_ofc` | Non-federal MDs in patient-care office-based positions |
| `md_nf_all_med_spec_all_pc`, `md_nf_all_surg_spec_all_pc`, `md_nf_all_oth_spec_all_pc` | Non-federal MDs in medical/surgical/other specialties, patient care |
| `md_nf_fammed_gen_all_pc` | Non-federal MDs in family medicine / general practice, patient care |
| `md_nf_fed_activ` | Active federal MDs |
| `phys_nf_prim_care_pc_exc_rsdt` | Non-federal primary-care physicians excluding residents |
| `phys_nf_prim_care_pc_rsdnt` | Non-federal primary-care physician residents |
| `do_nf_activ` | Active non-federal DOs |
| `medcr_ffs_eligbl_medcd_pct` | Medicare fee-for-service beneficiaries dually eligible for Medicaid (%) |
| `medcr_ffs_hosp_readm_rate` | Medicare FFS hospital readmission rate |
| `medcr_ffs_prev_hosp_rate` | Medicare FFS preventable hospitalization rate |
| `nhsc_sites` | National Health Service Corps sites |
| `nhsc_fte_provdrs` | NHSC FTE providers |
| `nurs_fac` | Nursing facilities (count) |
| `nurs_fac_beds` | Nursing facility beds (count; used for `nh_beds_per_65plus_ahrf`) |
| `hosp` | Hospitals total (count) |
| `hosp_beds` | Hospital beds total (count) |
| `hosp_adm` | Hospital admissions |
| `comn_mentl_hlth_ctr` | Community Mental Health Centers |
| `critcl_access_hosp` | Critical Access Hospitals |
| `fedly_qualfd_hlth_ctr` | Federally Qualified Health Centers |
| `rural_hlth_clincs` | Rural Health Clinics |
| `hpsa_dent` | HPSA dental designation count |
| `hpsa_mentl_hlth` | HPSA mental-health designation count |
| `per_cap_persnl_incom` | Per capita personal income |
| `popn_est` | AHRF county population estimate (Census single-year; differs from ACS `pop_total`) |
| `vetn_popn_est` | Veteran population estimate |
| `popn_densty_per_squr_mi` | Population density per square mile (time-invariant) |
| `land_area_mi2` | Land area in square miles (time-invariant) |

## County Health Rankings (CHR) variables

Prefix `chr_*` indicates CHR source (different sampling frame than ACS). Some columns are sparse (≤80 non-null).

| Column | Description |
|---|---|
| `chr_premature_death_rate` | Years of potential life lost (YPLL) per 100K |
| `chr_preventable_hosp_rate` | Preventable hospitalization rate |
| `chr_pct_fair_poor_health` | % adults reporting fair/poor health |
| `chr_pct_low_birthweight` | % low-birthweight births |
| `chr_pcp_rate`, `chr_dentist_rate` | Primary-care physicians / dentists per 100K |
| `chr_pct_uninsured` | CHR-vintage uninsured rate (differs from ACS-direct `uninsured_rate`) |
| `chr_pct_adult_smoking` | % adult smokers |
| `chr_pct_adult_obesity` | % adult obesity |
| `chr_avg_mental_unhealthy_days` | Mentally unhealthy days/month |
| `chr_pct_children_in_poverty` | % children in poverty |

## IPEDS completions

| Column | Description |
|---|---|
| `ipeds_completions_rn` | Raw RN program completions (CIP 51.3801) |
| `ipeds_completions_lpn` | Raw LPN program completions (CIP 51.3901) |
| `ipeds_completions_cna` | Raw CNA program completions (CIP 51.3902) |
| `ipeds_completions_other_nursing` | Other nursing CIPs (51.39xx not above) — e.g. MSN, NP, nurse anesthetist |
| `ipeds_completions_total` | Sum of above |

## OMB CBSA / USDA ERS typologies

| Column | Type | Description |
|---|---|---|
| `cbsa` | str | OMB CBSA code (NaN for non-metro counties) |
| `cbsa_name` | str | OMB CBSA name |
| `cbsa_ind` | str/int | Metro/Micro indicator |
| `rural_urban_contnm` | int | USDA ERS Rural-Urban Continuum (1=metro core, 9=most rural) — time-invariant |
| `urban_influnc` | int | USDA ERS Urban Influence code — time-invariant |
| `econ_depndnt_typolgy` | int | Economic Dependence Typology — time-invariant |
| `mfg_depndnt_typolgy` | int | Manufacturing Dependence — time-invariant |
| `recrtn_typolgy` | int | Recreation Typology — time-invariant |
| `hi_povty_typolgy` | int | High-Poverty Typology — time-invariant |
| `prstnt_povty_typolgy` | int | Persistent-Poverty Typology — time-invariant |
| `popn_loss_typolgy` | int | Population-Loss Typology — time-invariant |
| `retrmnt_destntn_typolgy` | int | Retirement-Destination Typology — time-invariant |

## Caveats summary

1. **`has_med_hosp_x_overhead` is a degenerate interaction** — collinear with `overhead_ratio_wmean` in the Medicare-hospital sub-sample. Reading it as a slope-difference is incorrect.
2. **`nh_beds_per_65plus_cms` vs `nh_beds_per_65plus_ahrf`** — different sources. CMS is current snapshot (time-invariant); AHRF is year-varying. Regressions in `notebooks/regressions_explore.ipynb` use the AHRF version.
3. **`popn_est` (AHRF) ≠ `pop_total` (ACS)** — different vintages and methodologies (Census single-year estimate vs ACS 5-year midpoint). Derived rates use whichever denominator the producing pipeline chose.
4. **Wage variables are all endogenous.** Both PUMS and OEWS measures are simultaneously determined with supply. Bartik IV first-stage F<1 in MI sample.
5. **OEWS wages are MSA-aggregated**, broadcast to all constituent counties. Within-MSA wage variation across counties = 0.
6. **`has_medicare_hospital` was rebuilt** from `n_hospitals > 0` (year-varying) to match HCRIS data presence. Earlier static-snapshot version had 12 county-years of inconsistency.
7. **2018 is absent** from the underlying AHRF spine; some derived columns will have a 2018 gap.
8. **County FE absorbs** all time-invariant variables in panel regressions. USDA typologies, `land_area_mi2`, `popn_densty_per_squr_mi`, `has_medicare_hospital` (mostly), and Magnet status will yield no coefficient in TWFE.

---

*Generated 2026-06-05. For the build pipeline see `scripts/regressors_data_script.py`; for the analysis specs see `notebooks/regressions_explore.ipynb`.*
