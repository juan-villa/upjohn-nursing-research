# Project handoff — Michigan nursing labor market panel

A fresh Claude Code session should read this file first. It describes the
project, the data, and where things live. It deliberately does **not**
prescribe next steps — the analyst is reassessing direction.

## What this project is

Course: **GSE 580**. The project studies the Michigan nursing labor market
at the MSA level using a panel of administrative and survey data. The
working analysis file is `notebooks/regressions.ipynb`; the assembled
panel is `master_panel.csv`.

## The panel at a glance

- **Units:** 14 Michigan Metropolitan Statistical Areas (CBSA names as of
  2024 OMB delineations). The full list and CBSA crosswalk lives in
  `scripts/pulls/_common.py` (`CBSA` and `MI_COUNTY_TO_MSA`).
- **Time:** annual, 2015–2024 (10 years). Smaller MSAs (Jackson, Midland,
  Monroe, Niles) have fewer years because of BLS wage-cell suppression or
  ACS 1-year publication thresholds.
- **Rows:** 115 unbalanced MSA-year observations.
- **Primary outcome:** `contract_labor_share` — share of nursing labor
  outlay paid to agency/contract staff, derived from CMS HCRIS Worksheet
  S-3 Part II. Interpreted as a revealed shortage measure.
- **Other RN-stock measures:** `tot_emp`, `loc_quotient`, `h_median`,
  `h_median_real` from BLS OEWS.

Full variable dictionary: `MASTER_PANEL_LEGEND.md`. Read this before
making any modeling decision.

## Data sources currently feeding the panel

| Source | What it provides | Pull script |
|---|---|---|
| BLS OEWS (May, all-areas) | RN employment, wages, location quotient | `scripts/oews_michigan_rn.py` |
| CMS HCRIS (HOSP10 form 2552-10) | hospital wages, contract labor, beds, inpatient days | `scripts/pulls/hcris_hospital.py` |
| HHS Protect | COVID hospital admissions per 100k | `scripts/pulls/hhs_covid.py` |
| ACS 1-year | population, age, insurance, income, rent, LFP, education | `scripts/pulls/` (verify exact file) |
| CDC PLACES | health prevalence (chronic conditions) | `scripts/pulls/cdc_places.py` |
| ANCC + hand-curated | Magnet hospital status, other policy levers | `policy_verified.py`, `policy_levers.csv` |
| State hospital list | hospital → MSA aggregation | `scripts/pulls/hospitals.py`, `data/processed/mi_hospitals.csv` |

The full pipeline is orchestrated by `scripts/pull_all.py` →
`scripts/build_master.py` → `scripts/clean_panel.py`. Raw downloads cache
to `data/cache/`; intermediate per-source CSVs land in `data/processed/`;
the final panel is written to `master_panel.csv` at the repo root.

## Repository layout

```
gse-580-clean/
├── master_panel.csv                # final analysis panel
├── MASTER_PANEL_LEGEND.md          # variable dictionary — read first
├── DATA_SOURCES_MSA.md             # provenance notes per source
├── county-master.csv               # parallel county-level panel (less mature)
├── DATA_SOURCES_COUNTY.md
├── policy_levers.csv               # hand-curated policy data
├── summary-stats-msa-lvl.csv/png
├── notebooks/
│   └── regressions.ipynb           # main analysis notebook
├── scripts/
│   ├── pull_all.py                 # orchestrator
│   ├── build_master.py             # assembles master panel
│   ├── build_county.py             # assembles county panel
│   ├── clean_panel.py              # post-processing
│   ├── oews_michigan_rn.py         # standalone OEWS pull
│   ├── generate_summary_stats.py
│   └── pulls/                      # per-source pull modules
│       ├── _common.py              # CBSA codes, county→MSA map, cache helpers
│       ├── hcris.py, hcris_hospital.py
│       ├── hhs_covid.py
│       ├── cdc_places.py
│       ├── hospitals.py
│       └── policy_verified.py
├── data/
│   ├── cache/                      # raw downloads (HCRIS zips etc.)
│   └── processed/                  # per-source cleaned CSVs
└── literature/                     # background papers
```

## Geographic scope

- 14 Michigan MSAs (full CBSA list in `_common.py`).
- County-level panel (`county-master.csv`) exists in parallel but is less
  mature; the MSA panel is the primary analytic unit.
- Nonmetropolitan Michigan (Upper Peninsula, Northern Lower Peninsula,
  Balance of Lower Peninsula) is **not** currently in the panel even
  though OEWS publishes for those Balance-of-State areas.

## Known properties of the current data that affect modeling

These are facts about the panel, not a to-do list:

- `master_panel.csv` is unbalanced. Suppression in small MSAs creates
  MAR-style missingness in wages and employment.
- CDC PLACES variables are effectively time-invariant within the 2015–2024
  window and will be absorbed by MSA fixed effects.
- `h_median_loo` (leave-one-out mean wage) exists as a candidate instrument
  for own-MSA wage but the first stage is weak in TWFE.
- The 10-year window straddles the COVID shock; year fixed effects absorb
  the level shift but heterogeneous COVID exposure across MSAs is the
  source of identification in much of the existing notebook work.
- HCRIS contract-labor accounting rules were updated by CMS in 2018 (see
  the existing source notes); pre-2018 vs post-2018 values are not
  perfectly comparable.

## How to resume

1. Read `MASTER_PANEL_LEGEND.md` for the variable dictionary.
2. Open `notebooks/regressions.ipynb` to see the current modeling state.
3. Inspect `master_panel.csv` directly — it's small enough to load fully.
4. If you need to rebuild the panel from scratch, the order is
   `python scripts/pull_all.py && python scripts/build_master.py &&
   python scripts/clean_panel.py`. Expect ~15–20 minutes for a full
   refresh (HCRIS downloads dominate).

## Environment

Python 3.13. Required packages: `pandas`, `numpy`, `requests`,
`openpyxl`, `xlrd` (for legacy `.xls` files). No virtual environment is
checked in; the project uses the system Python.

## Things deliberately omitted from this handoff

The project's data-coverage limitations and any specific direction the
analyst may take from here are intentionally not enumerated here so the
next session can read the panel and notebook with fresh eyes.
