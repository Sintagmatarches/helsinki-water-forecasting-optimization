# Paper-to-code reproduction protocol

## Paper

Danielle C. M. Ristow, Elisa Henning and Andreza Kalbusch (2021), “Models for forecasting water demand using time series analysis: a case study in Southern Brazil,” *Journal of Water, Sanitation and Hygiene for Development*, 11(2), 231–240. DOI: https://doi.org/10.2166/washdev.2021.208.

The paper is peer reviewed and open access. It models monthly metered water consumption, compares exponential-smoothing state-space models with seasonal ARIMA, uses automatic model selection based on AIC, checks residual normality/autocorrelation and forecasts the first six months of 2018 from pre-2018 observations.

## Independently reproduced method

`sarima_paper` independently implements the paper's key Box–Jenkins decision path in Python:

1. fit a bounded, declared set of plausible monthly SARIMA candidates;
2. select the converged candidate with minimum AIC using training data only;
3. forecast the requested horizon recursively;
4. compare it with additive damped ETS and naïve baselines;
5. report Jarque–Bera and Ljung–Box diagnostics rather than assuming ideal residuals.

No author implementation is imported or copied.

## Differences that prevent an “exact replication” claim

- Joinville data are category-level urban totals from 2013–2017; this project uses eight Helsinki public properties from 2010–2018 plus their bounded aggregate.
- The source institutions, climate, property mix, scale and meter/billing systems differ.
- The paper used R `forecast` automatic procedures; this project uses an explicit auditable candidate set in statsmodels.
- This project adds expanding-window backtests and protects all of 2018 from model selection.

Accordingly, the final report calls the result a **method reproduction on a different official dataset**, never a replication of the paper's reported Brazilian accuracy.

## Measured reproduction result

On the paper-aligned first six months of the sealed 2018 holdout, the reproduced SARIMA method achieved property-panel MASE 0.708 and MAE 22.17 m³, compared with deterministic-grid ETS MASE 0.809 and MAE 24.97 m³. SARIMA won four of eight properties and ETS won the other four. On the portfolio aggregate the ordering reversed: ETS MASE 0.655 versus SARIMA 0.732.

This supports a limited conclusion: the core method was reproduced and was competitive on these data. It does not support a universal SARIMA advantage or an exact replication of the paper. All values come from `artifacts/v1.0.0/metrics.json`.
