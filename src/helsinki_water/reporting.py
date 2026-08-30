from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .config import ROOT, ExperimentConfig

COLORS = {
    "navy": "#17324d",
    "blue": "#2789c7",
    "cyan": "#68c7df",
    "sand": "#e6b566",
    "red": "#c95757",
    "gray": "#718096",
}


def _load_metrics(artifacts: Path) -> dict[str, Any]:
    value: object = json.loads((artifacts / "metrics.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("metrics.json must contain a JSON object")
    return value


def _save(figure: Figure, path: Path) -> None:
    figure.savefig(
        path,
        dpi=170,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "helsinki-water v1.0.0"},
    )
    plt.close(figure)


def _benchmark(metrics: dict[str, Any], figures: Path) -> None:
    development = pd.DataFrame(metrics["developmentMetrics"])
    final = pd.DataFrame(metrics["finalPropertyMetrics"])
    order = development.sort_values("mase")["model"].tolist()
    development = development.set_index("model").loc[order]
    final = final.set_index("model").loc[order]
    positions = np.arange(len(order))
    width = 0.36
    figure, axis = plt.subplots(figsize=(9.2, 4.8))
    axis.bar(positions - width / 2, development["mase"], width, label="Development")
    axis.bar(positions + width / 2, final["mase"], width, label="Sealed 2018")
    axis.axhline(1.0, color=COLORS["gray"], linewidth=1, linestyle="--")
    axis.set_xticks(positions, [name.replace("_", "\n") for name in order])
    axis.set_ylabel("MASE (lower is better)")
    axis.set_title("Model selection and the untouched holdout tell different stories")
    axis.legend(frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    _save(figure, figures / "forecast-benchmark.png")


def _aggregate_forecast(artifacts: Path, figures: Path) -> None:
    intervals = pd.read_csv(artifacts / "final-intervals.csv")
    work = intervals.loc[intervals["site"] == "PORTFOLIO_TOTAL"].copy()
    months = pd.to_datetime(work["target_month"])
    figure, axis = plt.subplots(figsize=(9.2, 4.8))
    axis.fill_between(
        months,
        work["lower_m3"].to_numpy(dtype=float),
        work["upper_m3"].to_numpy(dtype=float),
        color=COLORS["cyan"],
        alpha=0.3,
        label="90% conformal interval",
    )
    axis.plot(months, work["actual_m3"], color=COLORS["navy"], marker="o", label="Actual")
    axis.plot(
        months,
        work["forecast_m3"],
        color=COLORS["blue"],
        marker="o",
        label="ETS forecast",
    )
    axis.set_ylabel("Monthly water use (m³)")
    axis.set_title("Sealed 2018 aggregate forecast")
    axis.legend(frameon=False, ncol=3)
    axis.spines[["top", "right"]].set_visible(False)
    _save(figure, figures / "aggregate-holdout.png")


def _uncertainty(metrics: dict[str, Any], figures: Path) -> None:
    summary = pd.DataFrame(metrics["uncertainty"]["propertyPanelFinal"]["byHorizon"])
    labels = summary["horizon_bucket"].tolist()
    positions = np.arange(len(labels))
    figure, coverage_axis = plt.subplots(figsize=(9.2, 4.8))
    width_axis = coverage_axis.twinx()
    coverage_axis.bar(
        positions,
        100 * summary["coverage"],
        color=COLORS["blue"],
        width=0.55,
        label="Empirical coverage",
    )
    width_axis.plot(
        positions,
        summary["mean_width_m3"],
        color=COLORS["sand"],
        marker="o",
        linewidth=2,
        label="Mean width",
    )
    coverage_axis.axhline(90, color=COLORS["gray"], linestyle="--", linewidth=1)
    coverage_axis.set_xticks(positions, labels)
    coverage_axis.set_ylim(0, 105)
    coverage_axis.set_ylabel("Coverage (%)")
    width_axis.set_ylabel("Mean interval width (m³)")
    coverage_axis.set_title("Uncertainty is conservative and horizon-dependent")
    handles = coverage_axis.get_legend_handles_labels()
    handles_2 = width_axis.get_legend_handles_labels()
    coverage_axis.legend(handles[0] + handles_2[0], handles[1] + handles_2[1], frameon=False)
    coverage_axis.spines["top"].set_visible(False)
    width_axis.spines["top"].set_visible(False)
    _save(figure, figures / "uncertainty-by-horizon.png")


def _sensitivity(artifacts: Path, figures: Path) -> None:
    work = pd.read_csv(artifacts / "optimization-sensitivity.csv")
    work = work.iloc[::-1].reset_index(drop=True)
    colors = np.where(work["improvementPct"] > 0.01, COLORS["sand"], COLORS["gray"])
    figure, axis = plt.subplots(figsize=(9.2, 6.5))
    axis.barh(work["scenario"], work["improvementPct"], color=colors)
    axis.set_xlabel("Expected decision-value improvement over greedy baseline (%)")
    axis.set_title("Optimization value vanishes in most tested scenarios")
    axis.spines[["top", "right"]].set_visible(False)
    _save(figure, figures / "optimization-sensitivity.png")


def generate_figures(config: ExperimentConfig) -> Path:
    artifacts = ROOT / "artifacts" / config.version
    figures = artifacts / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    metrics = _load_metrics(artifacts)
    _benchmark(metrics, figures)
    _aggregate_forecast(artifacts, figures)
    _uncertainty(metrics, figures)
    _sensitivity(artifacts, figures)
    return figures
