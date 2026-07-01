"""
Merge data/lightcast_postings_county_panel.csv into regression-data-base.csv.

Adds raw + per-10K-population versions of postings and the advertised-wage columns.
"""
import pandas as pd
import numpy as np

PANEL = 'regression-data-base.csv'
LIGHT = 'data/lightcast_postings_county_panel.csv'

panel = pd.read_csv(PANEL, low_memory=False, dtype={'fips': str})
panel['fips'] = panel['fips'].str.zfill(5)

light = pd.read_csv(LIGHT, dtype={'fips': str})
light['fips'] = light['fips'].str.zfill(5)

# Drop county_name from light to avoid duplicate column
light = light.drop(columns=['county_name'])

# Outer merge — Lightcast covers 2010-2023 (matches panel year range)
before = panel.shape
merged = panel.merge(light, on=['fips', 'year'], how='left')
after = merged.shape
print(f'Merge: {before} -> {after}')

# Per-capita versions (per 10,000 population)
# Use pop_total from existing panel
pop = merged['pop_total'].replace(0, np.nan)
merged['rn_postings_per_10k']  = merged['rn_postings']  / pop * 10000
merged['lpn_postings_per_10k'] = merged['lpn_postings'] / pop * 10000

# Log(1+x) variants — useful for skewed counts in regressions
merged['log_rn_postings']  = np.log1p(merged['rn_postings'])
merged['log_lpn_postings'] = np.log1p(merged['lpn_postings'])

# Diagnostics
print('\nNew columns:')
for c in ['rn_postings', 'lpn_postings',
          'rn_post_wage_annual', 'lpn_post_wage_annual',
          'rn_post_wage_hourly', 'lpn_post_wage_hourly',
          'rn_postings_per_10k', 'lpn_postings_per_10k',
          'log_rn_postings', 'log_lpn_postings']:
    nn = merged[c].notna().sum()
    print(f'  {c:30s}  non-null = {nn}')

print(f'\nTotal panel shape after merge: {merged.shape}')
print(f'  Columns added: {after[1] - before[1] + 4}')  # +4 derived

merged.to_csv(PANEL, index=False)
print(f'\nWrote {PANEL}')
