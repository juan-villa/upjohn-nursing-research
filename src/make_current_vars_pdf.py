"""Generate current_vars.pdf — documentation of every variable in
county_excluding_count.csv: name, source (with URL), description.
"""
from pathlib import Path
import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.lib.enums import TA_LEFT

ROOT = Path("/Users/juanvilla/Documents/gse-580-clean")
CSV = ROOT / "county_excluding_count.csv"
OUT = ROOT / "current_vars.pdf"

ACS_URL = "https://api.census.gov/data/2023/acs/acs5/variables.html"
CHR_URL = "https://www.countyhealthrankings.org/health-data/methodology-and-sources/data-documentation"
IPEDS_URL = "https://nces.ed.gov/ipeds/use-the-data"
AHRF_URL = "https://data.hrsa.gov/topics/health-workforce/ahrf"

# (variable, source short, url, description)
VARS = [
    # ---- identifiers ----
    ("fips", "Census", "https://www.census.gov/library/reference/code-lists/ansi.html",
     "5-digit county FIPS code (state 26 = Michigan)."),
    ("county_name", "AHRF / Census", AHRF_URL,
     "County name (Michigan)."),
    ("year", "—", "",
     "Calendar year (2010–2017, 2019–2023; 2018 excluded to match nurse-license DV gap)."),

    # ---- ACS 5-year ----
    ("pop_total", "ACS 5-yr (B01001_001E)", ACS_URL,
     "Total population (denominator for per-capita measures)."),
    ("pop_65plus", "ACS 5-yr (B01001 sex×age, 65+)", ACS_URL,
     "Population aged 65+, sum of male & female 65+ buckets."),
    ("pct_65plus", "Derived from ACS B01001", ACS_URL,
     "Percent of population aged 65+. Demand-side proxy (older pop. uses more care)."),
    ("pop_25_54", "ACS 5-yr (B01001 sex×age, 25–54)", ACS_URL,
     "Prime working-age population, sum of male & female 25–54 buckets."),
    ("pct_25_54", "Derived from ACS B01001", ACS_URL,
     "Percent of population aged 25–54. Supply-side proxy for workforce."),
    ("median_hh_income", "ACS 5-yr (B19013_001E)", ACS_URL,
     "Median household income, nominal USD."),
    ("median_gross_rent", "ACS 5-yr (B25064_001E)", ACS_URL,
     "Median monthly gross rent, nominal USD."),
    ("median_home_value", "ACS 5-yr (B25077_001E)", ACS_URL,
     "Median owner-occupied home value, nominal USD."),
    ("unemployment_rate", "ACS 5-yr (B23025_005E / B23025_003E)", ACS_URL,
     "Civilian unemployment rate (unemployed / civilian labor force × 100)."),
    ("lfp_rate", "ACS 5-yr (B23025_002E / B01001_001E)", ACS_URL,
     "Labor-force participation rate (LF aged 16+ / total population × 100)."),
    ("pct_bachelors_plus", "ACS 5-yr (B15003_022–025E / B15003_001E)", ACS_URL,
     "Percent of adults 25+ with bachelor's degree or higher. NaN for 2010–2011 "
     "(table B15003 began in 2012)."),
    ("pct_uninsured", "ACS 5-yr (B27001 uninsured cells / B27001_001E)", ACS_URL,
     "Percent of population without health insurance. NaN for 2010–2011 "
     "(table B27001 began in 2012)."),
    ("pct_commute_30plus", "ACS 5-yr (B08303_008–013E / B08303_001E)", ACS_URL,
     "Percent of workers (excl. work-from-home) with commute ≥30 minutes."),
    ("mean_commute_minutes",
     "Derived from ACS 5-yr B08303 bucket distribution", ACS_URL,
     "Mean commute time in minutes, computed as Σ(bucket midpoint × count) "
     "/ B08303_001E. Midpoints used: 2.5, 7, 12, 17, 22, 27, 32, 37, 42, 52, "
     "74.5, 105 minutes (open-ended 90+ bucket capped at 105). Full county "
     "coverage; replaces the B08136/B08101 ratio that was disclosure-suppressed "
     "for ~half of MI counties."),
    ("rent_burden_pct",
     "ACS 5-yr (B25070_007–010E / B25070_001E)", ACS_URL,
     "Percent of renter-occupied households spending 30%+ of household income "
     "on gross rent (sum of 30–34.9%, 35–39.9%, 40–49.9%, 50%+ rows)."),
    ("own_burden_pct",
     "ACS 5-yr (B25091_008–011E / B25091_001E)", ACS_URL,
     "Percent of mortgaged owner-occupied households spending 30%+ of "
     "household income on selected owner costs."),
    ("poverty_rate", "ACS 5-yr (B17001_002E / B17001_001E)", ACS_URL,
     "Percent of population below the federal poverty line."),
    ("pct_white", "ACS 5-yr (B02001_002E / B01001_001E)", ACS_URL,
     "Percent of population reporting White alone."),
    ("pct_black", "ACS 5-yr (B02001_003E / B01001_001E)", ACS_URL,
     "Percent of population reporting Black or African American alone."),
    ("pct_asian", "ACS 5-yr (B02001_005E / B01001_001E)", ACS_URL,
     "Percent of population reporting Asian alone."),
    ("pct_hispanic", "ACS 5-yr (B03002_012E / B01001_001E)", ACS_URL,
     "Percent of population reporting Hispanic or Latino (any race)."),

    # ---- CHR ----
    ("chr_premature_death_rate", "RWJF County Health Rankings", CHR_URL,
     "Years of Potential Life Lost (YPLL) before age 75 per 100,000 population."),
    ("chr_preventable_hosp_rate", "CHR", CHR_URL,
     "Preventable hospitalization rate (ambulatory-care-sensitive admissions "
     "per 1,000 Medicare enrollees)."),
    ("chr_pct_fair_poor_health", "CHR", CHR_URL,
     "Percent of adults reporting fair or poor general health (BRFSS)."),
    ("chr_pct_low_birthweight", "CHR", CHR_URL,
     "Percent of live births with low birth weight (<2,500 g)."),
    ("chr_pcp_rate", "CHR (HRSA Area Health Resource File)", CHR_URL,
     "Primary care physicians per 100,000 population (CHR's PCP rate; distinct "
     "from AHRF physician series below)."),
    ("chr_dentist_rate", "CHR", CHR_URL,
     "Dentists per 100,000 population."),
    ("chr_pct_uninsured", "CHR", CHR_URL,
     "Percent of under-65 population uninsured (Small Area Health Insurance "
     "Estimates)."),
    ("chr_pct_adult_smoking", "CHR", CHR_URL,
     "Percent of adults who currently smoke (BRFSS)."),
    ("chr_pct_adult_obesity", "CHR", CHR_URL,
     "Percent of adults with BMI ≥30 (BRFSS)."),
    ("chr_avg_mental_unhealthy_days", "CHR", CHR_URL,
     "Mean number of mentally unhealthy days reported in past 30 days (BRFSS)."),
    ("chr_pct_children_in_poverty", "CHR", CHR_URL,
     "Percent of children under 18 living in poverty (Census SAIPE)."),

    # ---- IPEDS ----
    ("ipeds_completions_cna", "IPEDS Completions Survey", IPEDS_URL,
     "Total program completions in CNA / nursing-assistant CIP codes at "
     "institutions located in the county that year. 0 = no such program."),
    ("ipeds_completions_lpn", "IPEDS Completions Survey", IPEDS_URL,
     "Total program completions in LPN / LVN CIP codes."),
    ("ipeds_completions_other_nursing", "IPEDS", IPEDS_URL,
     "Completions in nursing CIPs not classified as RN/LPN/CNA (e.g., NP, "
     "research, administration)."),
    ("ipeds_completions_rn", "IPEDS", IPEDS_URL,
     "Total program completions in RN-preparation CIP codes (ADN, BSN, etc.)."),
    ("ipeds_completions_total", "Derived from IPEDS", IPEDS_URL,
     "Sum of all nursing-related completions in the county that year."),

    # ---- AHRF time-varying (2020–2023) ----
    ("phys_nf_prim_care_pc_exc_rsdt", "AHRF (AMA/AOA Masterfile)", AHRF_URL,
     "Active non-federal primary-care physicians (MD + DO), excluding residents. "
     "Headline shortage measure. Available 2020–2023."),
    ("phys_nf_prim_care_pc_rsdnt", "AHRF (AMA/AOA Masterfile)", AHRF_URL,
     "Primary-care residents/fellows (MD + DO). 2020–2023."),
    ("md_nf_activ", "AHRF (AMA Masterfile)", AHRF_URL,
     "Total active non-federal MDs (all specialties). 2020–2023."),
    ("do_nf_activ", "AHRF (AOA Masterfile)", AHRF_URL,
     "Total active non-federal DOs (all specialties). 2020–2023."),
    ("md_nf_fed_activ", "AHRF (AMA)", AHRF_URL,
     "Active federal MDs (VA, military). 2020–2023."),
    ("md_nf_pc_ofc", "AHRF (AMA)", AHRF_URL,
     "Active MDs in office-based patient care. 2020–2023."),
    ("md_nf_pc_hosp_all", "AHRF (AMA)", AHRF_URL,
     "Active MDs in hospital-based patient care. 2020–2023."),
    ("md_nf_all_med_spec_all_pc", "AHRF (AMA)", AHRF_URL,
     "Active MDs in medical specialties (all patient care). 2020–2023."),
    ("md_nf_all_surg_spec_all_pc", "AHRF (AMA)", AHRF_URL,
     "Active MDs in surgical specialties (all patient care). 2020–2023."),
    ("md_nf_all_oth_spec_all_pc", "AHRF (AMA)", AHRF_URL,
     "Active MDs in other specialties (e.g., radiology, anesthesiology). 2020–2023."),
    ("md_nf_fammed_gen_all_pc", "AHRF (AMA)", AHRF_URL,
     "Active MDs in family medicine (general). 2020–2023."),
    ("hosp", "AHRF (AHA Annual Survey)", AHRF_URL,
     "Total hospitals in county (all types). 2020–2023."),
    ("stgh", "AHRF (AHA)", AHRF_URL,
     "Short-term general hospitals. 2020–2023."),
    ("critcl_access_hosp", "AHRF (CMS)", AHRF_URL,
     "Critical-access hospitals (rural facilities ≤25 beds). 2020–2023."),
    ("rural_hlth_clincs", "AHRF (CMS)", AHRF_URL,
     "Rural Health Clinics (Medicare-certified). 2020–2023."),
    ("fedly_qualfd_hlth_ctr", "AHRF (HRSA)", AHRF_URL,
     "Federally Qualified Health Centers (safety-net primary care). 2020–2023."),
    ("comn_mentl_hlth_ctr", "AHRF (HRSA)", AHRF_URL,
     "Community Mental Health Centers. 2020–2023."),
    ("nurs_fac", "AHRF (CMS)", AHRF_URL,
     "Nursing facilities (Medicare/Medicaid-certified). 2020–2023."),
    ("nurs_fac_beds", "AHRF (CMS)", AHRF_URL,
     "Nursing facility beds. 2020–2023."),
    ("hosp_beds", "AHRF (AHA)", AHRF_URL,
     "Total hospital beds. 2020–2023."),
    ("hosp_adm", "AHRF (AHA)", AHRF_URL,
     "Total hospital admissions. 2020–2023."),
    ("nhsc_sites", "AHRF (HRSA NHSC)", AHRF_URL,
     "National Health Service Corps sites. 2020–2023."),
    ("nhsc_fte_provdrs", "AHRF (HRSA NHSC)", AHRF_URL,
     "NHSC full-time-equivalent providers. 2020–2023."),
    ("medcr_ffs_prev_hosp_rate", "AHRF (CMS)", AHRF_URL,
     "Medicare FFS preventable hospitalization rate (ACSC admissions per 1,000 "
     "beneficiaries). 2020–2023."),
    ("medcr_ffs_hosp_readm_rate", "AHRF (CMS)", AHRF_URL,
     "Medicare FFS hospital readmission rate. 2020–2023."),
    ("stgh_fte_lpnlvn_incl_nh", "AHRF (AHA)", AHRF_URL,
     "Hospital-employed LPN/LVN FTEs (including nursing-home subsidiaries). "
     "Overlaps the LPN DV — useful as a control/robustness check."),
    ("stgh_nursng_asst_ft_incl_nh", "AHRF (AHA)", AHRF_URL,
     "Hospital-employed nursing-assistant FTEs (CNA-equivalent)."),
    ("stgh_aprn_ft", "AHRF (AHA)", AHRF_URL,
     "Hospital-employed advanced-practice registered nurses (full-time)."),
    ("stgh_aprn_pa", "AHRF (AHA)", AHRF_URL,
     "Hospital-employed physician assistants (full-time)."),
    ("medcr_ffs_eligbl_medcd_pct", "AHRF (CMS)", AHRF_URL,
     "Percent of Medicare FFS beneficiaries dually eligible for Medicaid. 2020–2023."),
    ("per_cap_persnl_incom", "AHRF (BEA Regional Accounts)", AHRF_URL,
     "Per capita personal income (BEA). 2020–2023."),
    ("vetn_popn_est", "AHRF (VA / Census PEP)", AHRF_URL,
     "Veteran population estimate. 2020–2023."),
    ("popn_est", "AHRF (Census PEP)", AHRF_URL,
     "Population Estimates Program annual total. 2020–2023."),

    # ---- AHRF time-invariant (broadcast across all years) ----
    ("rural_urban_contnm", "AHRF (USDA ERS)", AHRF_URL,
     "Rural-Urban Continuum Code (1–9). 1–3 = metro, 4–9 = nonmetro by adjacency "
     "& population. Broadcast across all years."),
    ("urban_influnc", "AHRF (USDA ERS)", AHRF_URL,
     "Urban Influence Code (1–12). Finer-grained metro/nonmetro typology. "
     "Broadcast."),
    ("cbsa", "AHRF (OMB delineations)", AHRF_URL,
     "5-digit Core-Based Statistical Area code. Broadcast."),
    ("cbsa_name", "AHRF (OMB)", AHRF_URL,
     "CBSA name (e.g., 'Detroit-Warren-Dearborn, MI Metro SA'). Broadcast."),
    ("cbsa_ind", "AHRF (OMB)", AHRF_URL,
     "CBSA indicator: 0 = none, 1 = metro, 2 = micropolitan. Broadcast."),
    ("econ_depndnt_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "County economic-dependence typology code. Broadcast."),
    ("mfg_depndnt_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "Manufacturing-dependent county flag. Broadcast."),
    ("recrtn_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "Recreation-dependent county flag. Broadcast."),
    ("hi_povty_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "High-poverty county flag. Broadcast."),
    ("prstnt_povty_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "Persistent-poverty county flag (≥20% poverty in each of last 4 censuses). "
     "Broadcast."),
    ("popn_loss_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "Population-loss county flag. Broadcast."),
    ("retrmnt_destntn_typolgy", "AHRF (USDA ERS)", AHRF_URL,
     "Retirement-destination county flag. Broadcast."),
    ("hpsa_prim_care", "AHRF (HRSA)", AHRF_URL,
     "Primary-care Health Professional Shortage Area designation (1 = whole, "
     "2 = part county, blank = none). Most-recent vintage broadcast."),
    ("hpsa_dent", "AHRF (HRSA)", AHRF_URL,
     "Dental HPSA designation. Broadcast."),
    ("hpsa_mentl_hlth", "AHRF (HRSA)", AHRF_URL,
     "Mental-health HPSA designation. Broadcast."),
    ("popn_densty_per_squr_mi", "AHRF (Census decennial / PEP)", AHRF_URL,
     "Population per square mile. Broadcast."),
    ("land_area_mi2", "AHRF (Census)", AHRF_URL,
     "County land area in square miles. Broadcast (geographically fixed)."),
]


def main():
    df = pd.read_csv(CSV, nrows=1)
    cols_in_csv = set(df.columns)
    documented = set(v[0] for v in VARS)
    missing_doc = cols_in_csv - documented
    extra_doc = documented - cols_in_csv
    if missing_doc:
        print(f"WARN: columns in CSV not documented: {sorted(missing_doc)}")
    if extra_doc:
        print(f"WARN: documented but not in CSV: {sorted(extra_doc)}")

    doc = SimpleDocTemplate(str(OUT), pagesize=LETTER,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.7*inch, bottomMargin=0.6*inch)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"],
                          fontName="Helvetica", fontSize=8.5, leading=11,
                          alignment=TA_LEFT)
    mono = ParagraphStyle("mono", parent=body, fontName="Courier", fontSize=8.5)
    src_st = ParagraphStyle("src", parent=body, fontName="Helvetica-Oblique",
                             fontSize=8, textColor=colors.HexColor("#1a4d8c"))
    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                        fontName="Helvetica-Bold", fontSize=18, leading=22,
                        spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                        fontName="Helvetica-Bold", fontSize=13,
                        textColor=colors.HexColor("#1a4d8c"),
                        spaceBefore=14, spaceAfter=6)
    note = ParagraphStyle("note", parent=body, fontName="Helvetica-Oblique",
                          fontSize=8.5, textColor=colors.HexColor("#555555"))

    story = []
    story.append(Paragraph("county_excluding_count.csv — Variable Dictionary",
                            h1))
    story.append(Paragraph(
        "Michigan county-year panel of regressors (excludes the licensed-nurse "
        "count DV, which will be added separately). 83 MI counties × 13 years "
        "(2010–2017, 2019–2023) = 1,079 rows × 88 columns. Join key: "
        "<font face=\"Courier\">fips</font> + <font face=\"Courier\">year</font>.",
        body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Sources at a glance.</b> "
        f'ACS 5-year (<a href="{ACS_URL}" color="blue">api.census.gov</a>); '
        f'County Health Rankings (<a href="{CHR_URL}" color="blue">RWJF / UWPHI</a>); '
        f'IPEDS Completions (<a href="{IPEDS_URL}" color="blue">NCES</a>); '
        f'AHRF 2020–2025 (<a href="{AHRF_URL}" color="blue">HRSA</a>).',
        body))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "AHRF time-varying variables are populated for 2020–2023 only "
        "(the AHRF CSV releases on hand). USDA rurality and geographic "
        "typology variables from AHRF are broadcast across all panel years. "
        "ACS B15003 (educational attainment) and B27001 (insurance) tables "
        "began in 2012, so <font face=\"Courier\">pct_bachelors_plus</font> "
        "and <font face=\"Courier\">pct_uninsured</font> are NaN for 2010–2011.",
        note))
    story.append(Spacer(1, 10))

    # Sections
    sections = [
        ("Identifiers", VARS[0:3]),
        ("Demographics, economic & socioeconomic — ACS 5-year", VARS[3:24]),
        ("Health outcomes & behaviors — County Health Rankings", VARS[24:35]),
        ("Nursing pipeline — IPEDS Completions", VARS[35:40]),
        ("Provider supply, facilities, utilization — AHRF (2020–2023)",
         VARS[40:73]),
        ("Geography & rurality typology — AHRF (broadcast all years)",
         VARS[73:]),
    ]

    for sect_title, sect_vars in sections:
        story.append(Paragraph(sect_title, h2))
        data = [["Variable", "Source", "Description"]]
        for name, source, url, desc in sect_vars:
            src_html = (f'<a href="{url}" color="blue">{source}</a>'
                        if url else source)
            data.append([Paragraph(name, mono),
                         Paragraph(src_html, src_st),
                         Paragraph(desc, body)])
        t = Table(data, colWidths=[1.7*inch, 2.0*inch, 3.6*inch], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a4d8c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#1a4d8c")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f3f6fa")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d4dc")),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
