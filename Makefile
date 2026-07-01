# =============================================================================
# Michigan Nurse Workforce: reproducibility pipeline
#
# Reproduces every table and figure in the paper from the committed analytic
# panels in data/analytic/. No API keys or licensed raw data required for the
# default `results` target.
#
#   make setup      install Python dependencies
#   make results    reproduce ALL paper tables + figures  (default)
#   make mechanism  run mechanism/policy-lever models -> outputs/*.csv
#   make tables     regression tables (submission + appendix) -> figures*/
#   make figures    heatmaps + supply-vs-aging scatter -> figures/
#   make paper      compile paper/*.tex -> PDF (needs a LaTeX install)
#   make clean      remove regenerable artifacts
#   make data       (advanced) rebuild panels from raw sources (see docs)
# =============================================================================

PY      := python3
NB      := jupyter nbconvert --to notebook --execute --inplace \
           --ExecutePreprocessor.timeout=600
ROOT    := $(shell pwd)

MECH_OUT := outputs/mechanism_model_results.csv

.DEFAULT_GOAL := help
.PHONY: help setup results mechanism tables figures paper clean data check

help:
	@grep -E '^#   make ' Makefile | sed 's/^#  //'

setup:
	$(PY) -m pip install -r requirements.txt

# ---- Full reproduction of paper results ------------------------------------
results: mechanism tables figures
	@echo ">> All paper tables and figures regenerated (outputs/, figures/, figures-submission/)."

# ---- Mechanism / policy-lever models (feeds the appendix tables) -----------
mechanism: $(MECH_OUT)
$(MECH_OUT): data/analytic/claude_merge_recon_neigh_w_final_reg_v2.csv \
             notebooks/mechanism_models_policy_levers_v3.ipynb
	cd notebooks && $(NB) mechanism_models_policy_levers_v3.ipynb
	@echo ">> Mechanism outputs written to outputs/"

# ---- Regression tables -----------------------------------------------------
tables: mechanism
	$(PY) src/make_submission_regression_tables.py   # -> figures-submission/table_{1,2}.png
	$(PY) src/make_appendix_tables.py                # -> outputs/appendix_tables.tex
	$(PY) src/render_tables_png.py                   # -> figures/tables/*.png  (needs pdflatex)

# ---- Figures ---------------------------------------------------------------
figures:
	cd notebooks && $(NB) new-heatmaps.ipynb         # -> figures/heatmap_*.png
	$(PY) src/make_supply_vs_aging_scatter.py        # -> figures/scatter_*.png

# ---- Compile the paper -----------------------------------------------------
paper:
	cd paper && pdflatex -interaction=nonstopmode michigan_nurse_workforce_revised-FINAL.tex \
	  && bibtex michigan_nurse_workforce_revised-FINAL || true \
	  && pdflatex -interaction=nonstopmode michigan_nurse_workforce_revised-FINAL.tex \
	  && pdflatex -interaction=nonstopmode michigan_nurse_workforce_revised-FINAL.tex

# ---- Advanced: rebuild analytic panels from raw sources --------------------
# Requires the licensed inputs in data/raw/ and a CENSUS_API_KEY. This does NOT
# run for outside cloners (licensed data is not redistributable). See
# docs/DATA_ACCESS.md for what each source is and how to obtain it.
data:
	@echo "The raw->panel rebuild depends on licensed data (Lightcast, MI Nurse Map)"
	@echo "and a Census API key. See docs/DATA_ACCESS.md. Build scripts live in src/."

clean:
	rm -rf tmp/matplotlib */__pycache__ src/__pycache__ .ipynb_checkpoints \
	       notebooks/.ipynb_checkpoints
	@echo ">> Cleaned regenerable caches (committed result artifacts left in place)."

# quick sanity check that inputs & tools are present
check:
	@test -f data/analytic/regression-data-base.csv && echo "ok: analytic panel present"
	@test -f data/shp/cb_2022_us_county_20m.shp && echo "ok: county shapefile present"
	@$(PY) -c "import pandas, numpy, matplotlib, statsmodels, geopandas; print('ok: python deps present')"
