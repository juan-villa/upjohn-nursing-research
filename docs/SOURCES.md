# Data Sources — Michigan Nursing Labor Market Panel

## Primary Outcome
**Lightcast Job Postings** (proprietary)  
RN and LPN job postings by county, 2010–2023. Includes posting-implied wages.  
Coverage: 83 Michigan counties × 14 years (2018 included).

## Legacy Outcome
**Michigan Nurse Map** — MI Dept. of Licensing & Regulatory Affairs  
Licensed RN and LPN counts by county, with age distribution.  
Coverage: 2012–2023, excluding 2018 and 2021 (no source files available).

## Demographics
**American Community Survey (ACS) 5-Year Estimates** — U.S. Census Bureau  
`api.census.gov/data/{year}/acs/acs5`  
Variables: population, age structure, income, housing costs, labor force, race/ethnicity, education, commute, insurance, disability.  
Coverage: 2010–2023.

## Health Outcomes & Access
**County Health Rankings (CHR)** — University of Wisconsin Population Health Institute  
`countyhealthrankings.org`  
Variables: premature death rate, preventable hospitalization, fair/poor health, obesity, smoking, mental health days, PCP rate, dentist rate, uninsured rate, low birthweight, child poverty.  
Coverage: 2010–2023 (sparse pre-2015 for some measures).

## Nursing Education
**IPEDS Completions** — National Center for Education Statistics  
`nces.ed.gov/ipeds`  
Variables: nursing program completions by CIP code (RN 51.3801, LPN 51.3901, CNA 51.3902) aggregated to county.  
Coverage: 2010–2023.

## Health Workforce & Facilities
**Area Health Resources File (AHRF)** — HRSA Bureau of Health Workforce  
`data.hrsa.gov/data/download?data=AHRF`  
Variables: hospitals, nursing facilities, physicians, critical access hospitals, FQHCs, rural health clinics, NHSC sites, Medicare utilization, typology codes, HPSA designations.  
Coverage: 2010–2023 (time-varying via year-suffix columns; time-invariant broadcast across years).

## Wages
**Occupational Employment and Wage Statistics (OEWS)** — U.S. Bureau of Labor Statistics  
`bls.gov/oes`  
Variables: RN (SOC 29-1141) and LPN (SOC 29-2061) employment, mean/median hourly and annual wages by MSA. Non-MSA counties assigned Balance of Lower Peninsula nonmetro value.  
Coverage: 2010–2023.

**ACS Public Use Microdata Sample (PUMS)** — U.S. Census Bureau  
`census.gov/programs-surveys/acs/data/pums`  
Variables: RN (OCC 3255) and LPN (OCC 3500) real median hourly wages, mapped from PUMA to county.  
Coverage: 2010–2023.

## Hospital Financials
**HCRIS (Hospital Cost Report Information System)** — CMS  
`cms.gov` HOSP10 form 2552-10  
Variables: operating margin, overhead ratio, net income per bed, total beds, hospital count per county.  
Coverage: 2012–2023. *Note: skipped in current build; columns are NaN.*

## Nursing Home Supply
**CMS Nursing Home Provider Info** — Centers for Medicare & Medicaid Services  
`data.cms.gov/provider-data`  
Variables: certified nursing home beds per county, normalized by ACS pop 65+.  
Coverage: Time-invariant snapshot broadcast across all years.

## Instrumental Variable
**Bartik Shift-Share IV** — Derived  
County-level hospital employment share (QCEW 2014, NAICS 622) × national OEWS RN/LPN wage growth.  
Sources: BLS Quarterly Census of Employment and Wages (QCEW) + national OEWS.  
Coverage: 2010–2023.

## Nursing Workforce Projections (Literature)
- Zhang et al. (2018). *American Journal of Medical Quality*, 33(3), 229–236.
- Juraschek et al. (2012). *American Journal of Medical Quality*, 27(3), 241–249.
- Buerhaus et al. (2024). *JAMA Health Forum*, 5(2). https://jamanetwork.com/journals/jama-health-forum/fullarticle/2815057
- HRSA (2025). *Nurse Workforce Projections 2023–2038 Fact Sheet.* https://bhw.hrsa.gov/sites/default/files/bureau-health-workforce/data-research/nursing-projections-factsheet.pdf
