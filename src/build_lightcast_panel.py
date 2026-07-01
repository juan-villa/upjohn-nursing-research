"""
Parse 1,162 Lightcast Job Postings xlsx files into a tidy county-year panel.

Source layout: data/gerrit_data/Job Postings/{year}/Job_Postings_Table_8_*_{County}_County_MI_*.xlsx
Sheet:        "Job Postings Occ Table"
Schema (consistent across 2010-2023):
    SOC | Occupation | Unique Postings from Jan {Y} - Dec {Y} | Median Annual Advertised Salary | Median Hourly Advertised Salary

Extracts RN (29-1141) and LPN (29-2061) only.

Output: data/lightcast_postings_county_panel.csv with columns:
    fips, county_name, year,
    rn_postings, rn_post_wage_annual, rn_post_wage_hourly,
    lpn_postings, lpn_post_wage_annual, lpn_post_wage_hourly
"""
import pandas as pd
import numpy as np
import glob
import os
import re
import sys

BASE = 'data/gerrit_data/Job Postings'
OUT = 'data/lightcast_postings_county_panel.csv'
RN_SOC, LPN_SOC = '29-1141', '29-2061'

NAME_FIX = {'St Clair': 'St. Clair', 'St Joseph': 'St. Joseph'}

def parse_value(x):
    """Convert 'Insf. Data' and similar strings to NaN; numeric otherwise."""
    if pd.isna(x):
        return np.nan
    if isinstance(x, str):
        s = x.strip()
        if s.lower().startswith('insf') or s == '' or s == '-':
            return np.nan
        try:
            return float(s.replace(',', ''))
        except ValueError:
            return np.nan
    return float(x)

def extract_one(fp, year):
    df = pd.read_excel(fp, sheet_name='Job Postings Occ Table', header=0)
    # Identify the 'Unique Postings from Jan {Y} - Dec {Y}' column dynamically
    postings_col = [c for c in df.columns if str(c).startswith('Unique Postings')]
    if not postings_col:
        return None
    pcol = postings_col[0]
    wcol_ann = 'Median Annual Advertised Salary'
    wcol_hr = 'Median Hourly Advertised Salary'
    rec = {'rn_postings': np.nan, 'rn_post_wage_annual': np.nan, 'rn_post_wage_hourly': np.nan,
           'lpn_postings': np.nan, 'lpn_post_wage_annual': np.nan, 'lpn_post_wage_hourly': np.nan}
    for _, r in df.iterrows():
        soc = str(r.get('SOC', '')).strip()
        if soc == RN_SOC:
            rec['rn_postings'] = parse_value(r[pcol])
            rec['rn_post_wage_annual'] = parse_value(r[wcol_ann])
            rec['rn_post_wage_hourly'] = parse_value(r[wcol_hr])
        elif soc == LPN_SOC:
            rec['lpn_postings'] = parse_value(r[pcol])
            rec['lpn_post_wage_annual'] = parse_value(r[wcol_ann])
            rec['lpn_post_wage_hourly'] = parse_value(r[wcol_hr])
    return rec

def main():
    # FIPS lookup from existing panel
    panel = pd.read_csv('regression-data-base.csv', usecols=['fips', 'county_name'],
                        dtype={'fips': str})
    panel['fips'] = panel['fips'].str.zfill(5)
    name_to_fips = (panel.drop_duplicates(subset=['fips'])
                         .set_index('county_name')['fips'].to_dict())

    rows = []
    year_dirs = sorted(d for d in os.listdir(BASE) if d.isdigit())
    for yr in year_dirs:
        year = int(yr)
        files = sorted(glob.glob(f'{BASE}/{yr}/*.xlsx'))
        for fp in files:
            m = re.search(r'in_(.+?)_County_MI', os.path.basename(fp))
            if not m:
                print(f'WARN: cannot parse county from {fp}', file=sys.stderr)
                continue
            cname_raw = m.group(1).replace('_', ' ')
            cname = NAME_FIX.get(cname_raw, cname_raw)
            fips = name_to_fips.get(cname)
            if fips is None:
                print(f'WARN: no FIPS for {cname!r}', file=sys.stderr)
                continue
            rec = extract_one(fp, year)
            if rec is None:
                continue
            rec.update({'fips': fips, 'county_name': cname, 'year': year})
            rows.append(rec)
        print(f'  {yr}: parsed {len(files)} files', file=sys.stderr)

    out = pd.DataFrame(rows)
    # Tidy column order
    out = out[['fips', 'county_name', 'year',
               'rn_postings', 'rn_post_wage_annual', 'rn_post_wage_hourly',
               'lpn_postings', 'lpn_post_wage_annual', 'lpn_post_wage_hourly']]

    # Some county-years have two xlsx files (different Lightcast vintages with
    # different hashes). When that happens, keep the higher-count record —
    # Lightcast revisions almost always add matched postings, never remove them.
    dup_keys = out[out.duplicated(subset=['fips', 'year'], keep=False)][['fips', 'year']]
    if len(dup_keys):
        print(f'  Found {len(dup_keys)//2} duplicate (fips,year) cells; '
              f'keeping the higher-postings record', file=sys.stderr)
        out = (out.sort_values(['fips', 'year', 'rn_postings'], ascending=[True, True, False])
                   .drop_duplicates(subset=['fips', 'year'], keep='first'))

    out = out.sort_values(['fips', 'year']).reset_index(drop=True)
    out.to_csv(OUT, index=False)

    # Diagnostics
    print(f'\nWrote {OUT}: shape={out.shape}', file=sys.stderr)
    print(f'  Years: {out.year.min()}-{out.year.max()}', file=sys.stderr)
    print(f'  Counties: {out.fips.nunique()}', file=sys.stderr)
    print(f'  RN postings non-null:  {out.rn_postings.notna().sum()}', file=sys.stderr)
    print(f'  LPN postings non-null: {out.lpn_postings.notna().sum()}', file=sys.stderr)
    print(f'  RN annual wage non-null:  {out.rn_post_wage_annual.notna().sum()}', file=sys.stderr)
    print(f'  LPN annual wage non-null: {out.lpn_post_wage_annual.notna().sum()}', file=sys.stderr)
    print(f'\nSample (Wayne County):', file=sys.stderr)
    wayne = out[out.fips == '26163']
    print(wayne.to_string(), file=sys.stderr)

if __name__ == '__main__':
    main()
