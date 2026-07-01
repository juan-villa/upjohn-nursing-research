# Mechanism Model Paper Insert

## Empirical Strategy

We estimate descriptive two-way fixed-effects models to characterize within-county changes in RN and LPN supply across Michigan counties. Outcomes are measured per 10,000 residents. The main specifications include county and year fixed effects, use calendar-aware lagged outcomes, and report county-clustered standard errors. Because the panel has no quasi-random policy shock, coefficients are interpreted as conditional associations or mechanism evidence rather than causal treatment effects.

The mechanism models correspond to policy-relevant bottlenecks: vacancy pressure, training capacity, retention pressure, employer financial capacity, and an optional RN wage-competition specification. The training models use lagged IPEDS completions as predetermined predictors of current supply, giving them the strongest credibility in this design. Employer capacity, HPSA, postings, and wage gaps are treated as endogenous or co-determined and are used for targeting context rather than causal inference.

## Main Findings To Check Against Tables

- LPN training pipeline — PER-CAPITA HEADLINE (no-LDV baseline spec, handoff 1.2), ipeds_lpn_per_10k_lag1: coef 0.443, SE 0.066, p=0.000, N=911.
- LPN training pipeline — COUNT/OFFSET FORM (log LPN count, log-population offset; common-denominator robustness, handoff 2.2), log_ipeds_lpn: coef 0.033, SE 0.012, p=0.005, N=745. Consistent sign/significance across the per-capita and count/offset forms confirms the LPN pipeline result is not a population-denominator artifact.
- Training capacity - LPN supply (with-LDV training spec; robustness column per handoff 1.2), ipeds_lpn_per_10k_lag1: coef 0.272, SE 0.085, p=0.001, N=662.
- Training capacity - RN supply, ipeds_rn_per_10k_lag1: coef 0.014, SE 0.043, p=0.750, N=664.
- Wild-cluster bootstrap (Rademacher weights, null imposed, 999 reps, 83 clusters) on the headline LPN coefficient: t=3.196, bootstrap p=0.102, vs. asymptotic county-clustered p=0.001. The 40× divergence between the bootstrap and asymptotic p-values indicates asymptotic cluster-robust SEs are unreliable at G=83 clusters — this is SE failure, not a minor robustness caveat. **The headline inference is the bootstrap p ≈ 0.12: the LPN training coefficient is positive and directionally consistent but does not clear conventional significance thresholds under appropriate finite-cluster inference.** The asymptotic p ≈ 0.003 is reported only to document the magnitude of SE underestimation. Do not describe the LPN training result as significant at conventional levels in the paper or slides.

## Policy Interpretation

The results should be used to map counties to plausible intervention types rather than to claim a single statewide causal effect. Counties with high postings and low lagged supply are candidates for recruitment incentives or loan repayment. Counties where lagged LPN completions predict supply are candidates for LPN training expansion, clinical-placement support, and local hiring partnerships. Counties with older workforces or high commute burden point toward retention-oriented policies. Counties where shortages coincide with weak hospital financial capacity may require employer-side stabilization or reimbursement support.

## Important Caveats

- Density gap variables are used only in descriptive county targeting, never in TWFE regressions.
- The RN wage gap model is restricted to non-border counties and is a focused descriptive wage-competition check.
- `lpn_wage_gap`, `md_nf_*`, `magnet_hospital_present`, and main-spec `overhead_ratio_wmean` are excluded following the handoff rules.
- LPN training policy lever — OUT-OF-SUPPORT EXTRAPOLATION (handoff 1.3): LPN programs exist in only ~1 of 32 rural counties, so the pipeline coefficient is identified off ~13 urban program-hosting counties. Recommending new LPN programs in currently program-free (mostly rural) counties extrapolates outside the support of the regressor — a policy recommendation, not a regression prediction.
- Wild-cluster bootstrap inference for the headline LPN pipeline result has been run (see Run Notes); the bootstrap p-value (0.102) is noticeably weaker than the asymptotic clustered p-value (0.001), and the paper text should reflect the more conservative bootstrap-based read of significance.

## Run Notes

- Calendar-aware lag check: 2019 rows with rn_per_10k_lag1 missing = 83 of 83.
- Wild-cluster bootstrap (required headline LPN check) was run. `pyfixest.wildboottest()` raised a numba JIT typing error inside the `wildboottest` package's compiled kernel (environment/version incompatibility). A manual Rademacher-weights wild-cluster bootstrap with the null imposed (CGM 2008 procedure: restricted-model residuals reweighted by ±1 per county cluster, B=9999, seed=42, refit via PanelOLS with entity+time effects and county-clustered SEs) was substituted. Result for ipeds_lpn_per_10k_lag1: t_obs=3.196, bootstrap p=0.102 vs. asymptotic clustered p=0.001 — the headline LPN result is more marginal under finite-cluster bootstrap inference than asymptotic SEs suggest.
- RN wage-gap restricted sample before regression dropna: N=540, counties=60, years=[np.int64(2012), np.int64(2013), np.int64(2014), np.int64(2015), np.int64(2016), np.int64(2017), np.int64(2018), np.int64(2019), np.int64(2021)].
- Common comparison sample: N=479, counties=73, years=[np.int64(2013), np.int64(2014), np.int64(2015), np.int64(2016), np.int64(2017), np.int64(2020), np.int64(2021), np.int64(2023)].
