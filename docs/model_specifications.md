## Model Specifications

All models share the two-way fixed-effects structure:

$$Y_{it} = \alpha_i + \lambda_t + \mathbf{X}_{it}'\boldsymbol{\beta} + \varepsilon_{it}$$

where $\alpha_i$ absorbs time-invariant county heterogeneity (geography, persistent infrastructure, historical composition) and $\lambda_t$ absorbs Michigan-wide shocks (ACA, COVID, federal policy cycles). Standard errors are clustered at the county level. The headline LPN pipeline coefficient uses wild-cluster bootstrap (Rademacher, $B=999$, $G=83$) as the preferred finite-cluster inference.

**Shared notation:**
- $i$ = county, $t$ = year
- $\mathbf{D}_{it} = (S^{75+}_{it},\; S^{65\text{-}74}_{it},\; g_{it})$ — demand shifters: share of population aged 75+, share aged 65–74, population growth rate
- $\mathbf{K}_{it} = (H^{\text{hosp}}_{it},\; H^{\text{NH}}_{it})$ — healthcare capacity: hospital beds per 1k residents, nursing-home beds per 1k residents aged 65+
- $\mathbf{Z}_{it} = (\text{Pov}_{it},\; \text{Educ}_{it})$ — structural disadvantage: poverty rate, bachelor's degree share
- $P_{i,t-1}$ — IPEDS nursing completions per 10k residents, lagged one year (occupation-specific)

---

### Section 1 — Baseline Distribution (Headline Specification)

$$\boxed{Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \delta\, P_{i,t-1} + \varepsilon_{it}}$$

where $Y_{it} \in \{\text{RN}_{it},\; \text{LPN}_{it}\}$ (licensed nurses per 10,000 residents, LARA). The coefficient $\delta$ is the headline causal-leaning estimate: $\hat{\delta}_{\text{LPN}} = 0.416$ (bootstrap $p = 0.057$); $\hat{\delta}_{\text{RN}} \approx 0$ (null). No lagged dependent variable — the preferred specification to avoid Nickell bias.

---

### Section 2 — Vacancy-Pressure Models

$$\text{Post}_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \gamma_1\,\text{HPSA}_{it} + \gamma_2\,Y_{i,t-1} + \gamma_3\,P_{i,t-1} + \varepsilon_{it}$$

where $\text{Post}_{it} \in \{\text{RN postings}_{it},\; \text{LPN postings}_{it}\}$ (Lightcast, per 10,000 residents). $Y_{i,t-1}$ controls for lagged own-supply; $P_{i,t-1}$ controls for the training pipeline. HPSA is conditioning context only — endogenous to the shortage outcome and not interpreted causally. A log-posting robustness variant replaces $\text{Post}_{it}$ with $\log(1 + \text{Post}_{it})$.

---

### Section 3 — Training-Capacity Models

**Headline:** Section 1 above is the pre-specified training-capacity headline. Section 3 adds a lagged dependent variable and additional controls as a robustness column:

$$Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \rho\,Y_{i,t-1} + \beta_u\,\text{Unemp}_{it} + \beta_a\,A^{<35}_{i,t-1} + \delta\,P_{i,t-1} + \varepsilon_{it}$$

The lagged dependent variable $Y_{i,t-1}$ induces Nickell bias under TWFE with finite $T$; $\hat{\delta}_{\text{LPN}} = 0.264$ here versus $0.416$ in Section 1. **Do not report this as the headline.** Two additional robustness variants:

$$\text{Lag-2:}\quad Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \delta_2\,P_{i,t-2} + \varepsilon_{it}$$

$$\text{Pre-trends:}\quad Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \sum_{k\,=\,-2}^{2}\,\delta_k\,P_{i,t-k} + \varepsilon_{it}$$

Parallel trends requires $\hat{\delta}_{-1} \approx \hat{\delta}_{-2} \approx 0$. Results: lead 1 $= -0.043$ ($p=0.688$), lead 2 $= +0.158$ ($p=0.195$) — pre-trends pass.

---

### Section 4 — Retention-Pressure Models

$$Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \rho\,Y_{i,t-1} + \boldsymbol{\gamma}'\mathbf{A}_{i,t-1} + \varepsilon_{it}$$

where $\mathbf{A}_{i,t-1}$ is a vector of lagged workforce age-composition variables (share of nurses aged 55+; share aged under 35). These capture retirement-wave risk and career-entry momentum respectively. Coefficients are interpreted descriptively — workforce composition and supply levels are co-determined. A secondary variant adds $\text{PT share}_{i,t-1}$ (RN part-time share) as a utilization-gap signal.

---

### Section 5 — Employer-Capacity Models

$$Y_{it} = \alpha_i + \lambda_t + \mathbf{D}_{it}'\boldsymbol{\beta}_D + \mathbf{K}_{it}'\boldsymbol{\beta}_K + \mathbf{Z}_{it}'\boldsymbol{\beta}_Z + \rho\,Y_{i,t-1} + \beta_m\,M_{it} + \varepsilon_{it}$$

where $M_{it}$ is the county-level weighted-mean hospital operating margin (CMS HCRIS). Data coverage is approximately 61% of county-years (2012–2023); the estimating sample is materially smaller than Sections 1–3. Results are **exploratory** — operating margin and nurse supply are co-determined, and the available sample does not support causal inference. A robustness variant adds overhead ratio; post-estimation diagnostics examine outlier and thin-year sensitivity.
