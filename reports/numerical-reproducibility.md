# Cross-platform numerical reproducibility audit

## Acceptance failure

Run `33368618971` preserved `linux-evidence-v1.0.0`. It was compared row-for-row with the committed Windows artifact from commit `1861521`. Schema, identity columns, row count, actual values and seasonal scales were identical.

The failing `final-intervals.csv:lower_m3` comparison was not an isolated arithmetic-rounding error:

| Column | Changed rows / 108 | Worst absolute difference | Worst relative difference |
|---|---:|---:|---:|
| `forecast_m3` | 107 | 0.74 m³ | <0.01 |
| `interval_q` | 108 | 0.07 | 0.03 |
| `lower_m3` | 88 | 9.32 m³ | 0.66 near zero |
| `upper_m3` | 108 | 8.48 m³ | 0.02 |
| `interval_width_m3` | 108 | 17.16 m³ | 0.03 |

Six lower bounds exceeded the former `rtol=0.05`, `atol=0.5 m³` policy. They were the rows that made the column-level verifier fail:

| CSV row | Site | Target | Horizon | Windows reference | Linux run | Absolute difference | Relative to Linux |
|---:|---|---|---:|---:|---:|---:|---:|
| 29 | Taivallahden | 2018-04 | 4 | 35.93 | 40.26 | 4.33 m³ | 10.76% |
| 30 | Taivallahden | 2018-05 | 5 | 6.87 | 11.38 | 4.51 m³ | 39.66% |
| 53 | Kontula | 2018-04 | 4 | 37.29 | 39.93 | 2.64 m³ | 6.60% |
| 54 | Kontula | 2018-05 | 5 | 12.94 | 15.58 | 2.63 m³ | 16.90% |
| 66 | Crusell | 2018-05 | 5 | 23.63 | 25.48 | 1.85 m³ | 7.25% |
| 103 | Portfolio total | 2018-06 | 6 | 159.19 | 168.23 | 9.04 m³ | 5.37% |

The maximum `lower_m3` difference across all rows was 9.32 m³ for the portfolio total in 2018-05, although that row remained inside the old relative tolerance. The largest relative difference was Taivallahden 2018-05: 39.66% relative to Linux, or 65.68% relative to the smaller Windows reference. Thus the apparent 66% worst case is a near-zero-bound denominator effect, not a 66% forecast shift.

## Root cause isolation

The finite-sample conformal function uses a sorted order statistic and performs no interpolation. Reordering its inputs produces the same quantile. The input row order and residual sort were therefore not causal.

The h4–6 calibration bucket contains 168 property residuals, so the 90% finite-sample rank is 153. On Windows the 153rd standardized residual was 2.7334; on Linux it was 2.6643. Several development ETS residuals moved materially: the largest same-row standardized-error changes were 0.44, 0.43 and 0.43. This changed which observation occupied rank 153.

Model-by-model comparison of 486 stored forecasts isolated the drift:

| Model | Mean absolute cross-platform forecast difference | Maximum |
|---|---:|---:|
| Optimizer-fitted ETS | 0.73 m³ | 14.40 m³ |
| Harmonic Ridge | 0.00 m³ | 0.00 m³ |
| Paper SARIMA | 0.00 m³ | 0.00 m³ |
| Seasonal naïve | 0.00 m³ | 0.00 m³ |

The cause was `statsmodels` Holt–Winters parameter optimization, whose numerical search followed different paths across the Windows and Linux numerical stacks. The uncertainty layer correctly propagated those different forecast residuals; changing quantile interpolation or widening interval tolerance would have masked the upstream model-fitting instability.

After replacing that optimizer, run `33370355865` confirmed that ETS, interval, anomaly and optimization artifacts no longer moved. The newly strict verifier then exposed a separate, much smaller variation in the paper-reproduction SARIMA maximum-likelihood fit: 481 SARIMA forecasts changed, with maximum absolute difference 0.00173864 m³ and maximum relative difference 0.003012%. Forty-two SARIMA-derived JSON metrics changed; their maxima were 0.0000118493 m³ absolute and 0.00004185% relative. Serialized SARIMA AIC changed by at most 0.0000001551, or 2.75×10⁻⁸%. Harmonic Ridge had 45 nonzero differences no larger than 1.14×10⁻¹³ m³; naïve and deterministic ETS were exact.

The SARIMA method deliberately retains `statsmodels` maximum-likelihood estimation because optimizer-based SARIMA fitting is the algorithm reproduced from the paper. Replacing it with a different finite-grid estimator would change the scientific reproduction rather than fix the original interval instability. Its remaining sub-millilitre forecast variation is therefore measured numerical-platform behavior and is isolated in verification policy rather than rounded away.

## Production fix

`ets` remains an additive-error, damped-additive-trend, additive-seasonal ETS model. Its coefficients are now selected by a declared finite grid:

- alpha: 0.10, 0.25, 0.50, 0.75;
- beta: 0.01, 0.05, 0.15;
- gamma: 0.05, 0.20, 0.40;
- damping phi: 0.90, 0.95, 0.98.

Initial level, trend and seasonal states use fixed formulas and `math.fsum`; every candidate is evaluated with sequential scalar arithmetic and deterministic SSE/model-parameter tie-breaking. No external optimizer, BLAS or LAPACK call is used by ETS fitting. Forecast values are not rounded.

The conformal order statistic now explicitly uses a stable sort and documents that interpolation is not performed.

## Verification policy after the fix

- JSON schema, strings, booleans and integer evidence: exact.
- CSV schema, row count and identity/non-numeric columns: exact. SARIMA model-detail structure and orders are exact; its AIC is parsed and compared numerically.
- `interval_q`, `lower_m3`, `upper_m3`, `interval_width_m3`: `rtol=1e-12`, `atol=1e-9 m³`.
- Ordinary numeric evidence: `rtol=1e-9`, `atol=1e-9`.
- Paper-SARIMA raw forecasts only: `rtol=5e-5`, `atol=1e-6 m³`; measured worst case was `3.012e-5` relative.
- Paper-SARIMA-derived JSON metrics only: `rtol=1e-6`, `atol=1e-9`; measured worst case was `4.185e-7` relative.
- SARIMA model identity and selected `(p,d,q)(P,D,Q)12` orders remain exact; AIC is parsed and compared numerically at the ordinary `1e-9` policy.
- PNG byte equality is not required because font rasterization is platform-specific; expected files and minimum valid sizes are checked.

This policy is substantially stricter than the rejected 5% / 0.5 m³ global tolerance and is scoped to the actual numerical contracts.

## Scientific impact

The model-selection rule still selects ETS on development data. Recomputed evidence changed and was updated everywhere:

- property holdout ETS MASE: 0.793;
- 90% property coverage: 97.92%;
- mean property interval width: 162.74 m³;
- anomaly count: 3;
- anomaly residual total: 207.62 m³;
- base optimization gain: 0%;
- binding 8-hour sensitivity gain: 14.59%.

The original artifacts were not retained as if they came from the corrected method.
