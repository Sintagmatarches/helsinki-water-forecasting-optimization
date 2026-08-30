# Scientific report

## 1. Problem formulation

The project asks two linked questions for a fixed portfolio of City of Helsinki public properties:

1. Given monthly water use observed through month `t`, what is the next 1–12 month forecast and its uncertainty?
2. When one-step observations exceed their forecast uncertainty envelope, which candidates should a limited inspection team review?

The intended contribution is methodological evidence for time-series forecasting, statistical uncertainty, anomaly screening, mathematical optimization and paper-to-code reproduction. It is not a claim about total Helsinki demand or the hydraulic state of the HSY network.

## 2. Data provenance and feasibility

The source audit is recorded in [`feasibility-audit.md`](feasibility-audit.md). The final source is the City of Helsinki Nuuka Open API dataset catalogued by Helsinki Region Infoshare under CC BY 4.0. The study panel has 864 monthly observations: eight properties, January 2010–December 2018, 108 months per property, unit `M3`.

The data contract requires exactly the eight versioned property names, exactly one row for every property-month in the fixed period, finite strictly positive values, the declared unit and no duplicate keys. Acquisition stores ignored raw responses, writes compact processed CSVs, records request parameters and SHA-256 hashes, then runs this contract.

A repeated source query caused one preliminary candidate to lose its 2018 records; the gate rejected it before modeling. This is direct evidence that external open-data APIs need validation rather than implicit trust.

### Scope boundary

HSY's public basic water-supply data are annual from 2010, and public HEKA water records located during the audit are annual for 2015–2018. Neither supports the requested forecasting design. The selected Nuuka data measure public-property meters, not households, districts, pressure zones or network inflow. “Helsinki Water” therefore refers only to this declared Helsinki property portfolio.

FMI weather data are available, but v1 remains univariate. The two reviewed portfolio repositories already demonstrate weather joins and geospatial modeling; the evidence gap here is temporal validation, statistical uncertainty and prescriptive analytics.

## 3. Forecasting methodology

Four approaches are fitted independently to each property and the portfolio total:

1. **Seasonal naïve:** `forecast(t+h) = actual(t+h−12)`.
2. **ETS:** additive error, damped additive trend and additive 12-month seasonality, ETS(A,Ad,A).
3. **Paper-derived SARIMA:** six declared monthly seasonal ARIMA candidates; the converged minimum-AIC candidate is selected on training data only.
4. **Harmonic Ridge:** recursive regularized regression using lags 1, 2 and 12, trailing 3- and 12-month means, annual sine/cosine terms and trend.

No model accesses future observations. Recursive Ridge predictions are appended only after generation. Scaling and all state-space estimation happen inside each training window.

## 4. Temporal validation

Development uses seven expanding-window origins—2015-12 through 2017-06 in three-month steps—with a six-month horizon. Model selection minimizes pooled property-level development MASE, then MAE, then model name as a deterministic tie-breaker.

All of 2018 is sealed until that rule selects a model. The final test starts after 2017-12 and forecasts 12 months. The selected model is not changed after observing 2018.

Metrics are MAE, RMSE, sMAPE and MASE. MASE uses the mean absolute 12-month seasonal difference in that training window.

## 5. Forecasting results

### Development model selection

| Model | N | MAE m³ | RMSE m³ | sMAPE | MASE |
|---|---:|---:|---:|---:|---:|
| ETS | 336 | 32.69 | 53.18 | 35.93% | **1.099** |
| Paper SARIMA | 336 | 37.09 | 57.91 | 37.32% | 1.219 |
| Harmonic Ridge | 336 | 42.02 | 62.24 | 39.17% | 1.392 |
| Seasonal naïve | 336 | 42.76 | 66.05 | 39.62% | 1.393 |

ETS wins the prespecified rule, although its development MASE remains above 1.

### Sealed 2018 property panel

| Model | N | MAE m³ | RMSE m³ | sMAPE | MASE |
|---|---:|---:|---:|---:|---:|
| Paper SARIMA | 96 | **22.53** | **31.83** | **23.66%** | **0.734** |
| ETS (selected) | 96 | 24.52 | 32.62 | 24.93% | 0.812 |
| Seasonal naïve | 96 | 26.69 | 45.18 | 23.99% | 0.889 |
| Harmonic Ridge | 96 | 27.74 | 39.10 | 27.39% | 0.890 |

SARIMA is better ex post on the property panel but is not retrospectively promoted. The divergence between development and holdout is a negative result about selection stability.

On the aggregate 2018 series, ETS did win: MAE 66.23 m³ and MASE 0.571, versus SARIMA MAE 79.68 m³ and MASE 0.687.

### Error and residual analysis

- Winter MAE: 20.40 m³; shoulder: 25.64; summer: 26.38.
- Months above each property's pre-2018 90th percentile: MAE 43.07 m³, versus 22.83 otherwise.
- Development ETS residuals: Jarque–Bera p = 2.37×10⁻¹⁴⁸; Ljung–Box lag-6 p = 1.23×10⁻⁴⁶.

High-use periods are harder, and ideal Gaussian independent-error assumptions are rejected.

## 6. Statistical uncertainty

The pipeline uses pooled scale-normalized conformal residuals from development only. Nonconformity for observation `i` is `abs(actual − forecast) / seasonal_scale`. Finite-sample quantiles are estimated separately for h1, h2–3, h4–6 and h7–12. Each interval is `forecast ± quantile × training seasonal scale`, clipped below at zero.

This is a practical pooled approximation. Serial dependence and heterogeneous properties weaken exact exchangeability guarantees.

### Final interval behavior

- Nominal level: 90%.
- Property coverage: **98.96%** across 96 forecasts; mean width **167.31 m³**.
- h1: 100% / 122.28 m³; h2–3: 93.75% / 181.93 m³.
- h4–6: 100% / 158.58 m³; h7–12: 100% / 174.31 m³.
- High-demand months: 100% / 199.73 m³; other months: 98.86% / 164.37 m³.
- Aggregate: 100% coverage and 652.41 m³ mean width.

The method misses one h2–3 observation but is otherwise excessively wide. Coverage above nominal is not automatic success: sharpness is poor and operational selectivity is limited.

## 7. Anomaly and possible operational risk

The system refits ETS at each month-end in 2018 and predicts one month ahead. A statistical high-use anomaly is declared only when the next observation exceeds the 90% conformal upper bound.

| Property / month | Actual m³ | Forecast m³ | Positive residual m³ | Standardized excess |
|---|---:|---:|---:|---:|
| Kontulan ala-aste / 2018-05 | 185 | 114.80 | 70.20 | 1.96 |
| Suutarilan portfolio / 2018-06 | 265 | 176.85 | 88.15 | 2.69 |
| Tammisalo / 2018-07 | 78 | 18.97 | 59.03 | 2.65 |

The three signals contain 217.38 m³ of observed positive forecast residual. That is not estimated leakage. There are no confirmed leak labels, maintenance outcomes or causal counterfactuals, so precision, recall and leak-detection claims are unavailable.

## 8. Prescriptive optimization

For candidate `i`, the assumed expected decision value is:

```text
weight_i × excess_i × persistence × missed_volume_value
− (1 − weight_i) × false_positive_cost
− inspection_hours_i × labor_hour_cost
```

Weights come from declared standardized-excess bands; they are scenario assumptions, not calibrated probabilities. Binary inspection and zone-activation variables maximize summed value subject to technician hours, zone setup time, monthly capacity and per-site limits. OR-Tools CP-SAT uses one worker and a fixed seed.

The comparison baseline greedily considers highest standardized residual first under the same constraints.

### Base result

With a 12-hour budget, all three candidates require 8.13 hours across two zones. Both policies select all three, score assumed expected value 983.49 and cover 217.38 m³ of residual excess. Improvement is **0.00%** because the constraints do not force a meaningful choice.

## 9. Sensitivity and scenarios

| One-factor change | Candidates | Gain over baseline | Interpretation |
|---|---:|---:|---|
| Budget 4 / 8 / 20 h | 3 | 0% | Greedy ordering remains optimal |
| False-positive cost 0 / 150 | 3 | 0% | Same decisions remain positive |
| Missed-volume value 1 | 3 | **11.21%** | Optimizer excludes a negative-value review |
| Missed-volume value 10 | 3 | 0% | All reviews become valuable |
| Interval multiplier 0.75 | 5 | 0% | More signals; all fit and order agrees |
| Interval multiplier 1.5 | 0 | 0% | Wider uncertainty suppresses all signals |
| Persistence 1 month | 3 | **11.21%** | Same regime as low missed-volume value |
| Persistence 6 months | 3 | 0% | All reviews become valuable |
| Zone setup 0.5 / 2 h | 3 | 0% | No policy reversal |

In the 11.21% scenario, optimized expected value is 122.99 versus 110.60, but it chooses only two candidates and covers 147.17 m³ rather than 217.38 m³. Optimization improves the declared objective, not every secondary measure. Its advantage disappears in most scenarios because the candidate set is small and constraints are usually non-binding.

## 10. Paper-to-code reproduction

The selected peer-reviewed paper is Ristow, Henning & Kalbusch (2021), “Models for forecasting water demand using time series analysis: a case study in Southern Brazil,” *Journal of Water, Sanitation and Hygiene for Development* 11(2), 231–240, DOI 10.2166/washdev.2021.208.

The reproduced component is the paper's AIC-selected seasonal ARIMA decision path on monthly water use, compared with ETS and accompanied by residual diagnostics. No author code is imported. Exact differences are in [`paper-reproduction.md`](paper-reproduction.md).

For the paper-aligned first six months of 2018:

- Property panel: SARIMA MASE 0.708, MAE 22.17 m³; ETS MASE 0.785, MAE 24.22 m³.
- Property wins: SARIMA 4/8, ETS 4/8.
- Aggregate: ETS MASE 0.588, MAE 68.12 m³; SARIMA MASE 0.732, MAE 84.88 m³.

This is a mixed method reproduction, not an exact replication or a universal ranking. Geography, aggregation, meter regime, time span and software differ from the Brazilian study.

## 11. Engineering quality

- `src/` package layout, typed modules and CLI.
- Deterministic seeds and declared candidate grid.
- Automated validation and seven unit tests.
- Ruff and strict mypy in CI.
- GitHub Actions reruns metrics and figures, enforces exact artifact structure and identity fields, and checks numerical evidence within a narrow tolerance for cross-platform BLAS differences.
- Versioned JSON, CSV and PNG outputs.
- Raw responses, environments, caches and secrets excluded from git.
- No credentials or manual access required.

## 12. Assumptions, limitations and failures

1. Public-property consumption is not a network-demand dataset.
2. Billing corrections, closures, renovations or occupancy may explain values; metadata cannot separate them.
3. Selecting a complete panel creates survivorship bias.
4. Pooled conformal residuals mix heterogeneous sites and retain temporal-dependence limitations.
5. Intervals are over-conservative, reducing alert sensitivity.
6. There are no leak labels.
7. Confirmation weights, persistence and costs must be replaced by operational estimates before use.
8. Base optimization advantage is zero; a general improvement claim would be false.
9. Development model selection is unstable relative to the future property panel.
10. No external production deployment or realized savings are claimed.

## 13. Supported conclusion

Official Helsinki meter data support a reproducible, leakage-safe monthly forecasting study. The evidence shows that model rankings can reverse on untouched future data, high-demand errors are larger, uncertainty must be evaluated for sharpness as well as coverage, residual alerts are not leaks, and optimization helps only when assumptions and constraints create a real trade-off.

Broader claims remain unsupported.
