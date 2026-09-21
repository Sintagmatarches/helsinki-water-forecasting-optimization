from __future__ import annotations

import math
import re
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

    def __post_init__(self) -> None:
        """Reject unsafe split designs before acquisition or expensive fitting."""
        def month(value: str) -> int:
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
                raise ValueError(f"Invalid ISO month: {value}")
            return int(value[:4]) * 12 + int(value[5:]) - 1

        start, end = month(self.start_month), month(self.end_month)
        first, last = month(self.development_first_origin), month(self.development_last_origin)
        final = month(self.final_origin)
        for name in ("development_step_months", "development_horizon", "final_horizon"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not start <= first <= last < final < end:
            raise ValueError("Origins must be ordered within the observed data window")
        if last + self.development_horizon > final:
            raise ValueError("Development targets overlap the sealed final holdout")
        if final + self.final_horizon > end:
            raise ValueError("Final targets extend beyond observed data")
        if not math.isfinite(self.interval_alpha) or not 0 < self.interval_alpha < 1:
            raise ValueError("interval_alpha must be finite and strictly between zero and one")
        if not self.properties or len(set(self.properties)) != len(self.properties):
            raise ValueError("Properties must be nonempty and unique")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.version):
            raise ValueError("version must be a safe artifact directory name")
        if any(not math.isfinite(value) or value < 0 for value in self.optimization.values()):
            raise ValueError("Optimization assumptions must be finite and nonnegative")


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
