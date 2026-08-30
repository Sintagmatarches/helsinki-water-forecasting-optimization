from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ExperimentConfig:
    version: str
    seed: int
    start_month: str
    end_month: str
    development_first_origin: str
    development_last_origin: str
    development_step_months: int
    development_horizon: int
    final_origin: str
    final_horizon: int
    interval_alpha: float
    properties: tuple[str, ...]
    optimization: dict[str, float | int]


def load_config(path: Path | None = None) -> ExperimentConfig:
    target = path or ROOT / "configs" / "experiment.toml"
    with target.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)
    experiment = raw["experiment"]
    return ExperimentConfig(
        version=str(experiment["version"]),
        seed=int(experiment["seed"]),
        start_month=str(experiment["start_month"]),
        end_month=str(experiment["end_month"]),
        development_first_origin=str(experiment["development_first_origin"]),
        development_last_origin=str(experiment["development_last_origin"]),
        development_step_months=int(experiment["development_step_months"]),
        development_horizon=int(experiment["development_horizon"]),
        final_origin=str(experiment["final_origin"]),
        final_horizon=int(experiment["final_horizon"]),
        interval_alpha=float(experiment["interval_alpha"]),
        properties=tuple(str(item["name"]) for item in raw["properties"]),
        optimization=dict(raw["optimization"]),
    )
