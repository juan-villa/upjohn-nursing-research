# Rebuilding `full-in-progress.csv` from public sources

This README is written for someone who has **never run a Python script before**.
Follow the steps in order. Each step has a copy/paste command.

The script you'll run is `scripts/regressors_data_script.py`. It pulls
Michigan county-year data from federal sources and writes
`full-in-progress.rebuilt.csv`. The manual nurse-count columns
(RN/LPN licensed counts, age %, per-100k rates) are **not** rebuilt — those
were compiled by hand. The script can copy them over from the existing
`full-in-progress.csv` for you.

### Two modes (the script picks automatically)

| Mode | When | What you get |
|---|---|---|
| **AHRF mode** | At least one `AHRF*.asc` + matching `.sas` file in `data/cache/` | Full coverage 1999–2025 (depending on which AHRF releases you've cached). AHRF supplies facility, workforce, HPSA, Medicare, basic demographic, and typology columns. ACS, IPEDS, CHR layer on top for granular detail. |
| **Fallback mode** | No AHRF files present | Coverage 2010–2023 only. Pulls facility/HPSA/CBSA/typology data from individual federal APIs. |

The script announces which mode it's in at the top of every run.

---

## Step 1 — Install Python (one time)

You need **Python 3.10 or newer**.

- **Mac**: open the Terminal app and run `python3 --version`. If it prints
  3.10 or higher, skip ahead. Otherwise install from
  <https://www.python.org/downloads/macos/>.
- **Windows**: install from <https://www.python.org/downloads/windows/>.
  When the installer opens, **check the box "Add Python to PATH"** before
  clicking Install.

Open a new terminal window after installing so the new Python is found.

---

## Step 2 — Install the script's dependencies (one time)

From the project folder (the folder containing `full-in-progress.csv`),
run **one** of these:

**Mac / Linux:**
```bash
pip3 install -r requirements.txt
```

**Windows:**
```bat
pip install -r requirements.txt
```

If you see "pip: command not found", try `python3 -m pip install -r requirements.txt`.

---

## Step 3 — Run the script

From the project folder:

**Mac / Linux:**
```bash
python3 scripts/regressors_data_script.py --preserve-manual
```

**Windows:**
```bat
python scripts\regressors_data_script.py --preserve-manual
```

A Census API key is already bundled in the script — no setup required.

Expected run time: **5–15 minutes** depending on internet speed. Most of
the time is spent downloading large IPEDS zip files (one per year). All
downloads are cached in `data/cache/` — re-running is fast.

When it finishes you'll see:
```
Wrote .../full-in-progress.rebuilt.csv: (1162, 100)
Missingness (top 15):
…
```

Open `full-in-progress.rebuilt.csv` in Excel to confirm it looks right.

---

## Step 4 — Two sources need a manual download (optional)

The script pulls **8 sources** automatically. **2 sources** require manual
downloads because the providers block scripted access:

### A. County Health Rankings (CHR)
The `chr_*` columns (premature death rate, % adult smoking, etc.) need
the CHR analytic CSVs. Without them, those columns will be blank.

For each year 2010–2023 you want to populate:
1. Go to
   <https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation>
2. Find the year's release. Download the **"Analytic Data" CSV** (NOT
   the Excel "rankings" file).
3. Save it to `data/cache/` and rename it to `chr_2010.csv`, `chr_2011.csv`,
   etc. — one file per year.
4. Re-run the script; CHR data will now populate.

### B. AHRF (Area Health Resources Files) — strongly recommended

AHRF is HRSA's official compendium that bundles data from ~50 federal
sources into one county-year file with ~6,000+ variables. Loading even
**one** AHRF release switches the script into AHRF mode and unlocks
1999–2025 coverage for facilities, workforce, HPSA designations,
Medicare measures, and basic demographics. Loading multiple releases
gives the freshest value for each variable (HRSA periodically revises
historical estimates).

1. Go to <https://data.hrsa.gov/topics/health-workforce/ahrf>.
2. For each release you want (e.g. 2023–2024, 2024–2025, plus any
   historical releases for backfill), click "Download" and complete
   the form. You'll receive a ZIP.
3. Extract the ZIP. Inside you'll find two files per release:
   `AHRF20XX.asc` (large, ~100–300 MB) and `AHRF20XX.sas`.
4. Copy **both** files into `data/cache/`. Filenames must contain a
   4-digit year so the script can rank releases.
5. Re-run the script. You'll see `AHRF mode` in the banner.

Without any AHRF files, the script falls back to pulling
facility/HPSA/CBSA/typology data from individual APIs (covers
2010–2023 only).

---

## What if something goes wrong?

The script prints a short status line for each source. If you see `FAIL`
next to a source name, that source was skipped — the rest of the script
keeps running. Common causes:

| Message | What to do |
|---|---|
| `Missing required Python package: …` | Re-run Step 2. |
| `No key provided` | Re-run Step 3 and paste the key when prompted. |
| `The Census API rejected your key` | The bundled key was revoked. Email Juan for a replacement. |
| `IPEDS 2023: FAIL` | NCES sometimes posts a year late. Safe to ignore for the latest year. |
| `AHRF: no .asc files in data/cache` | Step 5B not done. Skip if you don't need those columns. |
| `CHR: no local files found` | Step 5A not done. Skip if you don't need those columns. |

If something else fails, the full error message includes a Python
traceback. Email it to Juan with the command you ran.

---

## What columns come from where

| Source (script section) | Columns produced |
|---|---|
| `acs`  — Census ACS 5-year API | pop_total, pop_65plus, pct_65plus, pop_25_54, pct_25_54, median_hh_income, median_gross_rent, median_home_value, unemployment_rate, lfp_rate, pct_bachelors_plus, pct_uninsured, pct_commute_30plus, mean_commute_minutes, rent_burden_pct, own_burden_pct, poverty_rate, pct_white/black/asian/hispanic |
| `ipeds` — NCES IPEDS bulk | ipeds_completions_cna / lpn / rn / other_nursing / total |
| `chr` — manual CSVs | chr_premature_death_rate, chr_preventable_hosp_rate, chr_pct_fair_poor_health, chr_pct_low_birthweight, chr_pcp_rate, chr_dentist_rate, chr_pct_uninsured, chr_pct_adult_smoking, chr_pct_adult_obesity, chr_avg_mental_unhealthy_days, chr_pct_children_in_poverty |
| `ahrf` — manual .asc/.sas | comn_mentl_hlth_ctr, critcl_access_hosp, do_nf_activ, fedly_qualfd_hlth_ctr, hosp, hosp_adm, hosp_beds, md_nf_*, medcr_*, nhsc_*, nurs_fac*, per_cap_persnl_incom, phys_nf_*, popn_est, rural_hlth_clincs, stgh_*, vetn_popn_est |
| `ers` — USDA ERS bulk | rural_urban_contnm, urban_influnc, econ_depndnt_typolgy, mfg_depndnt_typolgy, recrtn_typolgy, popn_loss_typolgy, retrmnt_destntn_typolgy, prstnt_povty_typolgy, hi_povty_typolgy |
| `gaz` — Census Gazetteer | land_area_mi2, popn_densty_per_squr_mi |
| `cbsa` — OMB delineations | cbsa, cbsa_name, cbsa_ind |
| `hpsa` — HRSA HPSA files | hpsa_prim_care, hpsa_dent, hpsa_mentl_hlth |
| **Manual (NOT rebuilt)** | rn_licensed_county, rn_age_under35_pct, rn_age_55plus_pct, lpn_licensed_county, lpn_age_under35_pct, lpn_age_55plus_pct, nurse_total_count, rn_per_100k, lpn_per_100k, nurse_total_per_100k |

---

## Running just one source (for debugging)

```bash
python3 scripts/regressors_data_script.py --only acs
python3 scripts/regressors_data_script.py --only gaz,cbsa,hpsa
```
