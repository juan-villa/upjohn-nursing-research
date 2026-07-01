"""
pull_all.py — orchestrator: pull all upstream data and rebuild both panels.

Order:
  1. CMS Hospital General Info → MI hospital → MSA crosswalk
  2. HHS Protect COVID facility → MSA × year peaks
  3. CDC PLACES → MSA-aggregated chronic disease
  4. HCRIS cost reports (heavy: ~15 min) → MSA contract labor + hospital-level FTEs/beds
  5. Verified policy levers (Magnet, Lorna Breen, MIHEF)
  6. OEWS (BLS) RN data + clean panel
  7. build_master.py → master_panel.csv
  8. build_county.py → county-master.csv

Usage:
    python scripts/pull_all.py              # full pipeline
    python scripts/pull_all.py --skip-hcris # skip heavy HCRIS step

Requires environment variable CENSUS_API_KEY.
"""
import argparse
import subprocess
import sys


def run(name, cmd, optional=False):
    print(f"\n{'='*70}\n  STEP: {name}\n{'='*70}")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        msg = f"  STEP FAILED: {name} (return code {r.returncode})"
        if optional:
            print(msg + " — continuing")
        else:
            print(msg)
            sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-hcris", action="store_true")
    args = ap.parse_args()
    py = [sys.executable]

    run("CMS Hospital General Info → MSA crosswalk",
        py + ["-m", "scripts.pulls.hospitals"])
    run("HHS Protect COVID → MSA peaks",
        py + ["-m", "scripts.pulls.hhs_covid"])
    run("CDC PLACES chronic disease → MSA",
        py + ["-m", "scripts.pulls.cdc_places"])
    if not args.skip_hcris:
        run("HCRIS → MSA contract labor",
            py + ["-m", "scripts.pulls.hcris"], optional=True)
        run("HCRIS → hospital-level beds/FTEs",
            py + ["-m", "scripts.pulls.hcris_hospital"], optional=True)
    run("Verified policy levers (Magnet, Lorna Breen, MIHEF)",
        py + ["-m", "scripts.pulls.policy_verified"])
    run("OEWS RN panel",
        py + ["scripts/oews_michigan_rn.py"])
    run("Clean OEWS panel",
        py + ["scripts/clean_panel.py"])
    run("Build master_panel.csv (MSA × year)",
        py + ["scripts/build_master.py"])
    run("Build county-master.csv (county × year)",
        py + ["scripts/build_county.py"])
    print("\nDONE.")


if __name__ == "__main__":
    main()
