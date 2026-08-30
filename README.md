# Helsinki Water — Forecasting + Optimization

[![CI](https://github.com/Sintagmatarches/helsinki-water-forecasting-optimization/actions/workflows/ci.yml/badge.svg)](https://github.com/Sintagmatarches/helsinki-water-forecasting-optimization/actions/workflows/ci.yml)

Decision-science case study built from **real monthly water-meter observations** for eight City of Helsinki school/service properties. It connects temporal forecasting, conformal uncertainty, anomaly triage and constrained inspection planning in one reproducible pipeline.

The scope is deliberately precise: this is municipal-property consumption, not total HSY network demand, and a statistical anomaly is not called a confirmed leak.

## Verified evidence

| Layer | Versioned result |
|---|---|
| Data | 864 observations; 8 properties × 108 months; Jan 2010–Dec 2018; unit `M3`; no missing property-months |
| Development selection | ETS won seven-origin expanding backtesting: MASE **1.099**, vs SARIMA 1.219, harmonic Ridge 1.392, seasonal naïve 1.393 |
| Sealed 2018, properties | Selected ETS: MAE **24.52 m³**, RMSE 32.62, sMAPE 24.93%, MASE **0.812** across 96 forecasts |
| Honest negative result | Paper-derived SARIMA scored better ex post on property MASE (**0.734**), but was not substituted after seeing the holdout |
| Aggregate 2018 | ETS MASE **0.571**, MAE 66.23 m³ across 12 forecasts |
| 90% intervals | Property coverage **98.96%**, mean width **167.31 m³**; over-conservative, with h2–3 coverage 93.75% |
| Difficult periods | High-demand MAE **43.07 m³** vs 22.83 otherwise; high-demand interval coverage 100%, but width rose to 199.73 m³ |
| Anomaly layer | **3 statistical high-use signals**, 217.38 m³ total observed residual excess; zero confirmed-leak labels |
| Optimization | Base: **0.00%** gain because all three candidates fit; best tested one-factor scenario: **11.21%** expected-value gain |
| Paper-to-code | First-half 2018 property MASE: reproduced SARIMA **0.708** vs ETS 0.785; SARIMA won 4/8 sites, ETS won 4/8 and the aggregate |

Every number above is read from [`artifacts/v1.0.0/metrics.json`](artifacts/v1.0.0/metrics.json); underlying forecasts and decisions are committed as CSV.

![Forecast benchmark](artifacts/v1.0.0/figures/forecast-benchmark.png?v=20260830-helsinki-water-v1)

## What was built

- Reproducible acquisition from the City of Helsinki Nuuka Open API, with ignored raw responses, committed curated data and SHA-256 provenance.
- Strict complete-panel validation before modeling.
- Seasonal naïve, additive damped ETS, independently implemented AIC-selected SARIMA and harmonic Ridge approaches.
- Chronological development backtests and a sealed 2018 test year; no future-derived features or retrospective model switch.
- Scale-normalized conformal intervals calibrated only from development residuals and evaluated by horizon, season and high demand.
- One-step statistical anomaly monitoring, with language that separates a signal, possible operational risk and a confirmed leak.
- OR-Tools CP-SAT inspection allocation using anomaly magnitude, uncertainty-derived screening, assumed confirmation weights, costs, technician hours, zone activation, monthly capacity and per-site limits.
- One-factor sensitivity analysis that shows when optimization helps and, more importantly here, when it does not.
- Independent method reproduction of Ristow, Henning & Kalbusch (2021), with setup differences and failed assumptions documented.

![Sealed aggregate forecast](artifacts/v1.0.0/figures/aggregate-holdout.png?v=20260830-helsinki-water-v1)

## Data decision

The feasibility audit rejected the tempting but unsupported claim that a public high-frequency HSY network-demand history exists. HSY's public basic water-supply series is annual; HEKA's public water series is also too short and annual. The closest defensible source is HRI's catalogue of the City of Helsinki Nuuka API, which exposes actual monthly water-meter observations for municipal properties.

The study fixes a complete 2010–2018 panel. Later records were not appended because the API audit found irregular billing timestamps, gaps and changing reporting regimes. See [`reports/feasibility-audit.md`](reports/feasibility-audit.md).

## Decision formulation

For candidate inspection `i`, the assumed expected net value is:

```text
confirmation_weight_i × excess_m3_i × persistence × missed_m3_cost
− (1 − confirmation_weight_i) × false_positive_cost
− inspection_hours_i × labor_hour_cost
```

CP-SAT maximizes the sum of selected values under a technician-hour budget, zone setup time, monthly capacity and per-site limits. Confirmation weights are declared scenario assumptions—not learned probabilities. The baseline simply takes highest standardized residual first.

In the base case all three candidates fit in 8.13 of 12 available hours, so both policies are identical. At a lower missed-volume value (or one-month persistence), the optimizer rejects a negative-value inspection and improves assumed expected value by 11.21%, while capturing less raw excess. That is the correct trade-off under those assumptions, not evidence of realized savings.

![Optimization sensitivity](artifacts/v1.0.0/figures/optimization-sensitivity.png?v=20260830-helsinki-water-v1)

## Reproduce

Python 3.12+; no credentials required.

```bash
python -m pip install -e '.[dev]'
python -m helsinki_water.cli acquire  # refresh real source + hashes
python -m helsinki_water.cli run      # deterministic evidence tables
python -m helsinki_water.cli report   # deterministic figures
pytest
ruff check .
mypy src
```

`python -m helsinki_water.cli run` uses the committed curated snapshot, so result reproduction does not depend on the live API remaining unchanged. `acquire` intentionally refreshes the source and must pass the same validation contract.

## Read the evidence

- [`reports/scientific-report.md`](reports/scientific-report.md) — full methods, equations, results, failure analysis and limitations
- [`reports/feasibility-audit.md`](reports/feasibility-audit.md) — official-source audit and data boundary
- [`reports/paper-reproduction.md`](reports/paper-reproduction.md) — exact paper, reproduced method and non-equivalences
- [`artifacts/v1.0.0/`](artifacts/v1.0.0/) — machine-readable metrics, predictions, anomalies, scenarios and figures
- [`src/helsinki_water/`](src/helsinki_water/) — acquisition, validation, models, uncertainty and optimization package

Dependency versions are pinned. Local reruns are byte-stable; CI also performs a semantic artifact comparison because ETS optimization and font rendering can differ slightly across operating systems and BLAS implementations.

## What this project proves—and does not

It demonstrates a leakage-safe monthly forecasting and decision pipeline on a bounded official Helsinki property panel. It shows that model choice can reverse on a sealed future period, high-demand errors are larger, nominal uncertainty can be too wide, and optimization has no automatic value when constraints do not bind.

It does **not** prove network-level water-demand accuracy, leak detection performance, calibrated failure probabilities, causal savings or deployed operational impact. No external deployment is claimed.

Data: City of Helsinki Nuuka Open API via Helsinki Region Infoshare, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Code: MIT.
