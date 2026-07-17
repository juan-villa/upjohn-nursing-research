# =============================================================================
# The Geography of Care in Michigan: reproducibility pipeline
#
# Reproduces the results in the paper from the committed analytic panels in
# data/analytic/. No API keys or licensed raw data required.
#
#   make setup      install Python dependencies
#   make results    reproduce the paper's regression tables + map  (default)
#   make mechanism  run the fixed-effects models -> outputs/mechanism_model_results.csv
#   make tables     render the paper's regression tables -> outputs/appendix_tables.tex
#   make figures    render the county nurse-supply map -> figures/heatmap_rn_lpn_per_100k_2023.png
#   make paper      compile paper/*.tex -> PDF (needs a LaTeX install)
#   make check      verify inputs + Python deps are present
#   make clean      remove regenerable caches
# =============================================================================

PY        := python3
NB        := jupyter nbconvert --to notebook --execute --inplace \
             --ExecutePreprocessor.timeout=600
PANEL     := data/analytic/michigan_nurse_county_panel.csv
MECH_OUT  := outputs/mechanism_model_results.csv
PAPER_TEX := michigan_nurse_workforce

.DEFAULT_GOAL := help
.PHONY: help setup results mechanism tables figures paper clean check

help:
	@grep -E '^#   make ' Makefile | sed 's/^#  //'

setup:
	$(PY) -m pip install -r requirements.txt

# ---- Full reproduction of the paper's results -----------------------------
results: tables figures
	@echo ">> Paper tables (outputs/) and map (figures/) regenerated."

# ---- Fixed-effects / policy-lever models ----------------------------------
mechanism: $(MECH_OUT)
$(MECH_OUT): $(PANEL) notebooks/mechanism_models.ipynb
	cd notebooks && $(NB) mechanism_models.ipynb
	@echo ">> Model results written to $(MECH_OUT)"

# ---- Regression tables (the paper's Table 3-7 numbers) --------------------
tables: mechanism
	$(PY) src/make_appendix_tables.py    # -> outputs/appendix_tables.tex
	@echo ">> Regression tables written to outputs/appendix_tables.tex"

# ---- County nurse-supply map (the paper's only figure) --------------------
# The notebook also renders other maps locally; only the paper's map is tracked
# (see .gitignore).
figures:
	cd notebooks && $(NB) nurse_supply_maps.ipynb
	@echo ">> Map written to figures/heatmap_rn_lpn_per_100k_2023.png"

# ---- Compile the paper ----------------------------------------------------
paper:
	-cd paper && pdflatex -interaction=nonstopmode $(PAPER_TEX).tex
	-cd paper && bibtex $(PAPER_TEX)
	-cd paper && pdflatex -interaction=nonstopmode $(PAPER_TEX).tex
	-cd paper && pdflatex -interaction=nonstopmode $(PAPER_TEX).tex
	@test -f paper/$(PAPER_TEX).pdf && echo ">> Built paper/$(PAPER_TEX).pdf"

check:
	@test -f $(PANEL) && echo "ok: analytic panel present"
	@test -f data/shp/cb_2022_us_county_20m.shp && echo "ok: county shapefile present"
	@$(PY) -c "import pandas, numpy, matplotlib, statsmodels, geopandas; print('ok: python deps present')"

clean:
	rm -rf tmp/matplotlib */__pycache__ src/__pycache__ \
	       notebooks/.ipynb_checkpoints
	@echo ">> Cleaned regenerable caches."
