#!/usr/bin/env python
"""Bubble charts: RN / LPN supply vs aging demand (share 75+), MI counties 2023.

Two side-by-side panels (RN | LPN). x = share of population aged 75+, y = nurses
per 100,000 residents, bubble size = total population, color = metro (RUCC 1-3)
vs nonmetro (RUCC 4-9), with a dashed line at the median 75+ share. Companion to
the 65+ version. Saves to figures/.
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd
import scienceplots  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'figures'; FIG.mkdir(exist_ok=True)

AGE = 'share_75plus'           # swap to 'share_65plus' for the 65+ version
AGE_LABEL = '75+'
YEAR = 2023

METRO = '#3f6fa3'              # RUCC 1-3 (deeper blue, less washed out)
NONMETRO = '#c0664f'         # RUCC 4-9 (deeper terracotta)
ALPHA = 0.78                  # less translucent than before

# scientific / LaTeX-style serif fonts (no system LaTeX required)
plt.style.use(['science', 'no-latex', 'grid'])
plt.rcParams.update({
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'savefig.facecolor': 'white', 'font.size': 11,
    'font.family': 'serif',
})

d = pd.read_csv(ROOT / 'data' / 'analytic' / 'claude_merge_recon_neigh_w_final_reg_v2.csv',
                dtype={'fips': str}, low_memory=False)
s = d[d['year'] == YEAR].copy()
s['metro'] = s['rural_urban_contnm'] <= 3          # RUCC 1-3 = metro
s['rn_per_10k']  = s['rn_per_100k']  / 10
s['lpn_per_10k'] = s['lpn_per_100k'] / 10
med = s[AGE].median()
size = s['pop_total'] / 550.0                       # bubble area ~ population


def place_labels(ax, pts, dx_frac=0.012, gap_frac=0.050, fontsize=8.5):
    """Label points to the right with leader lines, spreading y to avoid overlap."""
    if not pts:
        return
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    dx = (x1 - x0) * dx_frac; gap = (y1 - y0) * gap_frac
    pts = sorted(pts, key=lambda p: p[1])            # by y
    ys = [p[1] for p in pts]
    for i in range(1, len(ys)):                      # push apart upward
        if ys[i] - ys[i - 1] < gap:
            ys[i] = ys[i - 1] + gap
    overflow = ys[-1] - (y1 - gap * 0.5)             # keep inside the axes
    if overflow > 0:
        ys = [y - overflow for y in ys]
    for (x, y, name), ty in zip(pts, ys):
        ax.annotate(name, xy=(x, y), xytext=(x + dx, ty), textcoords='data',
                    fontsize=fontsize, va='center', ha='left', color='#1a1a1a',
                    arrowprops=dict(arrowstyle='-', lw=0.5, color='#9a9a9a',
                                    shrinkA=1, shrinkB=3))


fig, axes = plt.subplots(1, 2, figsize=(20, 9.5))

specs = [('rn_per_10k', 'RNs per 10,000 Residents',
          'RN Supply vs. Aging Demand, MI Counties (2023)', 'upper left'),
         ('lpn_per_10k', 'LPNs per 10,000 Residents',
          'LPN Supply vs. Aging Demand, MI Counties (2023)', 'upper right')]

for ax, (yvar, ylab, title, legloc) in zip(axes, specs):
    for is_metro, color in [(True, METRO), (False, NONMETRO)]:
        sub = s[s['metro'] == is_metro]
        ax.scatter(sub[AGE], sub[yvar], s=size[sub.index], c=color,
                   alpha=ALPHA, edgecolors='white', linewidths=0.8, zorder=3)
    ax.axvline(med, color='#333333', ls='--', lw=1.3, zorder=2)

    # label the most-aged counties (right tail), de-overlapped
    pts = [(r[AGE], r[yvar], r['county_name']) for _, r in s.nlargest(8, AGE).iterrows()]
    place_labels(ax, pts)

    ax.set_xlabel(f'Share of Population Age {AGE_LABEL} (%)', fontsize=13)
    ax.set_ylabel(ylab, fontsize=13)
    ax.set_title(title, fontsize=15, fontweight='bold', pad=12)
    ax.grid(True, ls=':', lw=0.6, alpha=0.5)

    handles = [
        Line2D([0], [0], marker='o', linestyle='', markerfacecolor=METRO,
               markeredgecolor='white', markersize=11, label='Metro (RUCC 1–3)'),
        Line2D([0], [0], marker='o', linestyle='', markerfacecolor=NONMETRO,
               markeredgecolor='white', markersize=11, label='Nonmetro (RUCC 4–9)'),
        Line2D([0], [0], color='#333333', ls='--', lw=1.3,
               label=f'Median share {AGE_LABEL} ({med:.1f}%)'),
    ]
    ax.legend(handles=handles, loc=legloc, fontsize=10.5, frameon=True,
              framealpha=0.95, edgecolor='#cccccc', handletextpad=0.6,
              borderpad=0.8, labelspacing=0.6)

plt.tight_layout(w_pad=2.5)
out = FIG / f'scatter_supply_vs_aging_{AGE_LABEL.replace("+", "plus")}_{YEAR}.png'
plt.savefig(out, dpi=220, bbox_inches='tight', facecolor='white')
print('saved', out)
