from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import jarque_bera
from statsmodels.stats.diagnostic import acorr_ljungbox

from .backtest import BacktestDesign, metric_summary, panel_series, period_steps, run_backtest
from .config import ROOT, ExperimentConfig
from .data import load_processed
from .optimization import (
    anomaly_candidates,
    assumptions_from_config,
    optimize,
    sensitivity,
)
from .uncertainty import apply_intervals, calibrate, interval_summary
from .validation import validate_water_data


def _json_value(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [_json_value(record) for record in frame.to_dict(orient="records")]


def _error_analysis(final: pd.DataFrame, data: pd.DataFrame, winner: str) -> dict[str, Any]:
    chosen = final.loc[(final["model"] == winner) & (final["site"] != "PORTFOLIO_TOTAL")].copy()
    chosen["absolute_error"] = (chosen["actual_m3"] - chosen["forecast_m3"]).abs()
    chosen["month_number"] = pd.PeriodIndex(chosen["target_month"], freq="M").month
    chosen["season"] = np.select(
        [chosen["month_number"].isin([12, 1, 2]), chosen["month_number"].isin([6, 7, 8])],
        ["winter", "summer"],
        default="shoulder",
    )
    thresholds = (
        data.loc[data["month"] <= pd.Period("2017-12", freq="M")]
        .groupby("property_name")["water_m3"]
        .quantile(0.90)
    )
    chosen["high_demand"] = chosen.apply(
        lambda row: row["actual_m3"] >= thresholds.loc[row["site"]], axis=1
    )
    by_season = (
        chosen.groupby("season")
        .agg(observations=("absolute_error", "size"), mae_m3=("absolute_error", "mean"))
        .reset_index()
    )
    by_extreme = (
        chosen.groupby("high_demand")
        .agg(observations=("absolute_error", "size"), mae_m3=("absolute_error", "mean"))
        .reset_index()
    )
    return {"bySeason": _records(by_season), "byHighDemand": _records(by_extreme)}


def _paper_reproduction(final: pd.DataFrame) -> dict[str, Any]:
    first_half = final.loc[
        (final["horizon"] <= 6) & final["model"].isin(["ets", "sarima_paper"])
    ].copy()
    aggregate = metric_summary(first_half.loc[first_half["site"] == "PORTFOLIO_TOTAL"])
    property_panel = metric_summary(first_half.loc[first_half["site"] != "PORTFOLIO_TOTAL"])
    site_metrics: list[dict[str, Any]] = []
    for site, group in first_half.groupby("site"):
        errors = group.assign(absolute_error=(group["actual_m3"] - group["forecast_m3"]).abs())
        means = errors.groupby("model")["absolute_error"].mean()
        site_metrics.append(
            {
                "site": site,
                "etsMaeM3": float(means.get("ets", np.nan)),
                "sarimaMaeM3": float(means.get("sarima_paper", np.nan)),
                "winner": str(means.idxmin()),
            }
        )
    return {
        "paper": {
            "citation": (
                "Ristow, Henning & Kalbusch (2021), Models for forecasting water "
                "demand using time series analysis: a case study in Southern Brazil"
            ),
            "doi": "10.2166/washdev.2021.208",
            "method": (
                "AIC-selected seasonal ARIMA compared with additive ETS on monthly consumption"
            ),
        },
        "adaptation": (
            "Independent Python implementation; Helsinki public-property panel rather "
            "than Joinville category totals; expanding validation plus a sealed 2018 "
            "horizon rather than one fitted 2013-2017 series per category."
        ),
        "aggregateMetrics": _records(aggregate),
        "propertyPanelMetrics": _records(property_panel),
        "siteResults": site_metrics,
        "sarimaWins": int(sum(item["winner"] == "sarima_paper" for item in site_metrics)),
        "etsWins": int(sum(item["winner"] == "ets" for item in site_metrics)),
    }


def _uncertainty_difficulty(intervals: pd.DataFrame, data: pd.DataFrame) -> list[dict[str, Any]]:
    work = intervals.loc[intervals["site"] != "PORTFOLIO_TOTAL"].copy()
    thresholds = (
        data.loc[data["month"] <= pd.Period("2017-12", freq="M")]
        .groupby("property_name")["water_m3"]
        .quantile(0.90)
    )
    work["high_demand"] = work.apply(
        lambda row: row["actual_m3"] >= thresholds.loc[row["site"]], axis=1
    )
    work["covered"] = (work["actual_m3"] >= work["lower_m3"]) & (
        work["actual_m3"] <= work["upper_m3"]
    )
    work["interval_width_m3"] = work["upper_m3"] - work["lower_m3"]
    summary = (
        work.groupby("high_demand")
        .agg(
            observations=("covered", "size"),
            empirical_coverage=("covered", "mean"),
            mean_width_m3=("interval_width_m3", "mean"),
        )
        .reset_index()
    )
    return _records(summary)


def _residual_diagnostics(dev: pd.DataFrame, winner: str) -> dict[str, Any]:
    chosen = dev.loc[dev["model"] == winner].copy()
    residuals = (chosen["actual_m3"] - chosen["forecast_m3"]).to_numpy(dtype=float)
    jb = jarque_bera(residuals)
    lb = acorr_ljungbox(residuals, lags=[6], return_df=True).iloc[0]
    return {
        "jarqueBeraStatistic": float(jb.statistic),
        "jarqueBeraPValue": float(jb.pvalue),
        "ljungBoxLag6Statistic": float(lb["lb_stat"]),
        "ljungBoxLag6PValue": float(lb["lb_pvalue"]),
        "interpretation": (
            "Small p-values reject the corresponding idealized residual assumption; "
            "diagnostics are reported, not used to hide a model failure."
        ),
    }


def run(config: ExperimentConfig) -> Path:
    np.random.seed(config.seed)
    data, metadata = load_processed(config)
    validation = validate_water_data(data, config)
    series = panel_series(data)
    dev_design = BacktestDesign(
        origins=period_steps(
            config.development_first_origin,
            config.development_last_origin,
            config.development_step_months,
        ),
        horizon=config.development_horizon,
        split="development",
    )
    final_design = BacktestDesign(
        origins=(pd.Period(config.final_origin, freq="M"),),
        horizon=config.final_horizon,
        split="final",
    )
    dev = run_backtest(series, dev_design)
    final = run_backtest(series, final_design)
    dev_site_metrics = metric_summary(dev.loc[dev["site"] != "PORTFOLIO_TOTAL"])
    winner = str(dev_site_metrics.sort_values(["mase", "mae_m3", "model"]).iloc[0]["model"])
    quantiles = calibrate(dev.loc[dev["site"] != "PORTFOLIO_TOTAL"], winner, config.interval_alpha)
    final_winner = final.loc[final["model"] == winner].copy()
    final_intervals = apply_intervals(final_winner, quantiles)

    monitoring_design = BacktestDesign(
        origins=tuple(pd.period_range("2017-12", "2018-11", freq="M")),
        horizon=1,
        split="monitoring",
    )
    monitoring = run_backtest(series, monitoring_design, models=(winner,))
    monitoring_intervals = apply_intervals(monitoring, quantiles)
    candidates = anomaly_candidates(monitoring_intervals, metadata)
    base_assumptions = assumptions_from_config(config.optimization)
    optimization = optimize(candidates, base_assumptions)
    sensitivity_results = sensitivity(monitoring_intervals, metadata, base_assumptions)

    artifacts = ROOT / "artifacts" / config.version
    artifacts.mkdir(parents=True, exist_ok=True)
    predictions = pd.concat([dev, final], ignore_index=True)
    predictions.to_csv(artifacts / "forecast-predictions.csv", index=False, lineterminator="\n")
    final_intervals.to_csv(artifacts / "final-intervals.csv", index=False, lineterminator="\n")
    monitoring_intervals.to_csv(
        artifacts / "monitoring-predictions.csv", index=False, lineterminator="\n"
    )
    candidates.to_csv(artifacts / "statistical-anomalies.csv", index=False, lineterminator="\n")
    pd.DataFrame(sensitivity_results).to_csv(
        artifacts / "optimization-sensitivity.csv", index=False, lineterminator="\n"
    )

    all_metrics = metric_summary(predictions)
    final_metrics = metric_summary(final)
    final_property_intervals = final_intervals.loc[final_intervals["site"] != "PORTFOLIO_TOTAL"]
    final_aggregate_intervals = final_intervals.loc[final_intervals["site"] == "PORTFOLIO_TOTAL"]
    final_property_metrics = metric_summary(final.loc[final["site"] != "PORTFOLIO_TOTAL"])
    final_aggregate_metrics = metric_summary(final.loc[final["site"] == "PORTFOLIO_TOTAL"])
    paper_result = _paper_reproduction(final)
    residual_diagnostics = _residual_diagnostics(dev, winner)
    property_uncertainty = interval_summary(final_property_intervals)
    aggregate_uncertainty = interval_summary(final_aggregate_intervals)
    property_coverage = property_uncertainty["coverage"]
    if not isinstance(property_coverage, (int, float)):
        raise TypeError("Interval coverage must be numeric")
    base_improvement = float(optimization["improvementPct"])
    best_sensitivity_improvement = max(
        (float(item["improvementPct"]) for item in sensitivity_results), default=0.0
    )
    payload = {
        "experimentVersion": config.version,
        "seed": config.seed,
        "dataValidation": validation,
        "validationDesign": {
            "developmentOrigins": [str(item) for item in dev_design.origins],
            "developmentHorizonMonths": dev_design.horizon,
            "finalOrigin": config.final_origin,
            "finalHorizonMonths": config.final_horizon,
            "modelSelectionRule": (
                "Lowest pooled property-level development MASE, then MAE, then model "
                "name; final 2018 is excluded from selection."
            ),
        },
        "developmentMetrics": _records(dev_site_metrics),
        "allSplitMetrics": _records(all_metrics),
        "finalMetrics": _records(final_metrics),
        "finalPropertyMetrics": _records(final_property_metrics),
        "finalAggregateMetrics": _records(final_aggregate_metrics),
        "selectedModel": winner,
        "uncertainty": {
            "method": (
                "90% pooled scale-normalized expanding-backtest conformal intervals, "
                "calibrated by horizon bucket"
            ),
            "alpha": config.interval_alpha,
            "quantilesByHorizon": quantiles,
            "propertyPanelFinal": property_uncertainty,
            "aggregateFinal": aggregate_uncertainty,
            "byHighDemand": _uncertainty_difficulty(final_intervals, data),
        },
        "errorAnalysis": _error_analysis(final, data, winner),
        "residualDiagnostics": residual_diagnostics,
        "anomalyLayer": {
            "definition": (
                "Observed monthly use above the one-step 90% conformal upper bound; "
                "this is a statistical anomaly and possible operational review signal, "
                "not a confirmed leak."
            ),
            "candidateCount": int(len(candidates)),
            "observedExcessM3": float(candidates["excess_m3"].sum()) if len(candidates) else 0.0,
        },
        "optimization": optimization,
        "sensitivity": sensitivity_results,
        "paperReproduction": paper_result,
        "negativeResults": [
            (
                "The development-selected ETS model was retained even though "
                "paper-derived SARIMA achieved lower pooled property MASE on the sealed "
                "2018 holdout."
            ),
            (
                "Nominal 90% property-level intervals achieved "
                f"{100.0 * property_coverage:.2f}% coverage and "
                "were over-conservative rather than well calibrated."
            ),
            (
                "Development ETS residuals rejected both normality and "
                "no-autocorrelation diagnostics; conformal intervals reduce "
                "distributional dependence but do not remove temporal-dependence "
                "limitations."
            ),
            (
                "The optimized policy improved expected decision value by "
                f"{base_improvement:.2f}% in the base scenario; its best tested "
                f"one-factor improvement was {best_sensitivity_improvement:.2f}%, so "
                "optimization value disappears when the candidate set is tiny or "
                "constraints are non-binding."
            ),
            (
                "There are no confirmed leak labels; anomaly findings cannot establish "
                "detector precision, recall, or real leak occurrence."
            ),
        ],
    }
    metrics_path = artifacts / "metrics.json"
    metrics_path.write_text(
        json.dumps(_json_value(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metrics_path
