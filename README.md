# The Geography of Care in Michigan: Geographic Mismatch and Policy Levers

County-level analysis of Registered Nurse (RN) and Licensed Practical Nurse
(LPN) supply across Michigan's 83 counties, 2012-2023. Two-way fixed-effects
panel models identify which local factors: training pipelines, educational
attainment, demographic demand, and healthcare capacity, predict where nurses
work, and which **policy levers** actually move county-level supply.

> **Headline finding.** Local LPN training output predicts subsequent LPN
> workforce supply, while RN training output shows *no* significant relationship
> with county RN supply, consistent with greater geographic mobility among RNs.
> Expanding local training capacity looks effective for LPN shortages; improving
> RN availability likely requires **both** training *and* retention policy.

📄 The full paper (compiled) is in [`paper/`](paper/).

---

## Reproduce the results

Every table and figure in the paper is regenerated from the committed analytic
panel in [`data/analytic/`](data/analytic/): **no API keys or licensed raw
data required.**

```bash
make setup      # install Python dependencies (into your active environment)
make results    # reproduce ALL paper tables + figures
```

Individual stages:

| Target | What it does | Writes to |
|---|---|---|
| `make mechanism` | Runs the two-way fixed-effects models behind the paper's regression tables | `outputs/mechanism_model_results.csv` |
| `make tables`    | Renders those results as the paper's regression tables | `outputs/appendix_tables.tex` |
| `make figures`   | Renders the county nurse-supply map (the paper's figure) | `figures/heatmap_rn_lpn_per_100k_2023.png` |
| `make paper`     | Compiles the LaTeX source to PDF | `paper/` |
| `make check`     | Verifies inputs + Python deps are present | n/a |
| `make clean`     | Removes regenerable caches | n/a |

Requirements: Python 3.10+, the packages in [`requirements.txt`](requirements.txt),
and (for `make paper`) a LaTeX install providing `pdflatex`.

---

## Repository layout

```
data/
  analytic/   Derived, analysis-ready county panel (committed): the input to every result
  shp/        US Census county cartographic boundaries (public domain), for the map
  raw/        Licensed & intermediate source data (NOT committed; see docs/DATA_ACCESS.md)
src/          make_appendix_tables.py: renders the model results into the paper's tables
notebooks/    mechanism_models (FE models) and nurse_supply_maps (the map)
outputs/      Model results and the rendered regression tables
figures/      The county nurse-supply map used in the paper
paper/        Final manuscript (LaTeX + bibliography + compiled PDF)
docs/         Data dictionary, source documentation, modeling notes
Makefile      Reproducibility pipeline
```

The repository is scoped to what the final paper actually uses: its one map and
the fixed-effects models behind its regression tables. Exploratory notebooks,
alternate figures, and the raw-data build scripts were kept out of the published
tree to keep the reproduction path clear.

## Data & reproducibility notes

- **What's committed:** the *derived* analytic panel (aggregated to county ×
  year), the public Census county shapefile, all code, and all generated
  outputs. These are sufficient to reproduce the paper end-to-end.
- **What's not committed:** the proprietary raw inputs: **Lightcast** job
  postings and the **Michigan Nurse Map** licensed nurse counts, which cannot
  be redistributed. See [`docs/DATA_ACCESS.md`](docs/DATA_ACCESS.md) for each
  source, its license, and how to obtain it.
- **Method:** two-way (county + year) fixed effects with county-clustered
  standard errors; training-pipeline regressors enter with lags to probe a
  forward-looking supply response. See [`docs/`](docs/) for the full data
  dictionary and modeling specifications.

## License

Code is released under the MIT License ([`LICENSE`](LICENSE)). The manuscript
text/figures and the underlying licensed data are **not** covered by that
license and remain the property of their respective owners.
