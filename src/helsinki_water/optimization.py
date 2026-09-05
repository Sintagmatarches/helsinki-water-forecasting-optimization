from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, cast

import numpy as np
import pandas as pd
from ortools.sat.python import cp_model


@dataclass(frozen=True)
class DecisionAssumptions:
    budget_hours: float
    false_positive_cost: float
    missed_m3_cost: float
    labor_hour_cost: float
    persistence_months: int
    zone_activation_hours: float
    monthly_capacity: int
    max_per_site: int
    interval_multiplier: float = 1.0


def assumptions_from_config(raw: dict[str, float | int]) -> DecisionAssumptions:
    return DecisionAssumptions(
        budget_hours=float(raw["budget_hours"]),
        false_positive_cost=float(raw["false_positive_cost"]),
        missed_m3_cost=float(raw["missed_m3_cost"]),
        labor_hour_cost=float(raw["labor_hour_cost"]),
        persistence_months=int(raw["persistence_months"]),
        zone_activation_hours=float(raw["zone_activation_hours"]),
        monthly_capacity=int(raw["monthly_capacity"]),
        max_per_site=int(raw["max_per_site"]),
        interval_multiplier=float(raw.get("interval_multiplier", 1.0)),
    )


def anomaly_candidates(
    monitoring: pd.DataFrame,
    metadata: pd.DataFrame,
    interval_multiplier: float = 1.0,
) -> pd.DataFrame:
    work = monitoring.loc[monitoring["site"] != "PORTFOLIO_TOTAL"].copy()
    radius = work["interval_q"] * work["scale_m3"] * interval_multiplier
    work["upper_for_decision_m3"] = work["forecast_m3"] + radius
    work = work.loc[work["actual_m3"] > work["upper_for_decision_m3"]].copy()
    work["excess_m3"] = (work["actual_m3"] - work["forecast_m3"]).clip(lower=0.0)
    work["standardized_excess"] = work["excess_m3"] / work["scale_m3"].clip(lower=1e-9)
    work["confirmation_weight"] = np.select(
        [work["standardized_excess"] >= 2.5, work["standardized_excess"] >= 1.5],
        [0.75, 0.50],
        default=0.25,
    )
    work = work.merge(metadata, left_on="site", right_on="property_name", validate="many_to_one")
    work["inspection_hours"] = (
        1.5 + work["total_area_m2"].clip(lower=0.0, upper=12_000.0) / 12_000.0 * 1.5
    ).round(2)
    work["candidate_id"] = work["site"] + "|" + work["target_month"]
    return work.sort_values(["target_month", "site"]).reset_index(drop=True)


def _value(candidates: pd.DataFrame, assumptions: DecisionAssumptions) -> pd.Series:
    gross = (
        candidates["confirmation_weight"]
        * candidates["excess_m3"]
        * assumptions.persistence_months
        * assumptions.missed_m3_cost
    )
    false_positive = (1.0 - candidates["confirmation_weight"]) * assumptions.false_positive_cost
    labor = candidates["inspection_hours"] * assumptions.labor_hour_cost
    return gross - false_positive - labor


def _summarize(
    policy: str,
    candidates: pd.DataFrame,
    selected_indices: list[int],
    assumptions: DecisionAssumptions,
) -> dict[str, Any]:
    selected = candidates.loc[selected_indices].copy() if selected_indices else candidates.iloc[0:0]
    zones = int(selected["inspection_zone"].nunique())
    hours = float(selected["inspection_hours"].sum() + zones * assumptions.zone_activation_hours)
    return {
        "policy": policy,
        "selectedCount": int(len(selected)),
        "selectedCandidateIds": selected["candidate_id"].tolist(),
        "technicianHours": hours,
        "activatedZones": zones,
        "expectedDecisionValue": float(selected["decision_value"].sum()),
        "capturedObservedExcessM3": float(selected["excess_m3"].sum()),
    }


def optimize(candidates: pd.DataFrame, assumptions: DecisionAssumptions) -> dict[str, Any]:
    if candidates.empty:
        empty = _summarize("optimized", candidates.assign(decision_value=[]), [], assumptions)
        baseline = dict(empty, policy="baseline")
        return {
            "candidateCount": 0,
            "assumptions": assumptions.__dict__,
            "baseline": baseline,
            "optimized": empty,
            "improvementPct": 0.0,
        }
    # Solver variables are positional; caller DataFrame labels need not be.
    work = candidates.reset_index(drop=True).copy()
    work["decision_value"] = _value(work, assumptions)
    scale = 100
    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"candidate_{index}") for index in work.index]
    zones = sorted(work["inspection_zone"].unique())
    zone_active = {zone: model.new_bool_var(f"zone_{zone}") for zone in zones}
    budget_units = int(round(assumptions.budget_hours * scale))
    model.add(
        sum(
            int(round(work.loc[index, "inspection_hours"] * scale)) * selected[index]
            for index in work.index
        )
        + sum(
            int(round(assumptions.zone_activation_hours * scale)) * zone_active[zone]
            for zone in zones
        )
        <= budget_units
    )
    for index in work.index:
        model.add(selected[index] <= zone_active[str(work.loc[index, "inspection_zone"])])
    for _, group in work.groupby("target_month"):
        model.add(sum(selected[index] for index in group.index) <= assumptions.monthly_capacity)
    for _, group in work.groupby("site"):
        model.add(sum(selected[index] for index in group.index) <= assumptions.max_per_site)
    model.maximize(
        sum(
            int(round(work.loc[index, "decision_value"] * scale)) * selected[index]
            for index in work.index
        )
    )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 20260830
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("Inspection optimization did not find a feasible solution")
    optimized_indices = [index for index in work.index if solver.value(selected[index])]

    baseline_indices: list[int] = []
    used_hours = 0.0
    used_zones: set[str] = set()
    month_counts: dict[str, int] = {}
    site_counts: dict[str, int] = {}
    for index, row in work.sort_values(
        ["standardized_excess", "excess_m3"], ascending=False
    ).iterrows():
        month = str(row["target_month"])
        site = str(row["site"])
        zone = str(row["inspection_zone"])
        extra_zone = 0.0 if zone in used_zones else assumptions.zone_activation_hours
        proposed = used_hours + float(row["inspection_hours"]) + extra_zone
        if proposed > assumptions.budget_hours + 1e-9:
            continue
        if month_counts.get(month, 0) >= assumptions.monthly_capacity:
            continue
        if site_counts.get(site, 0) >= assumptions.max_per_site:
            continue
        baseline_indices.append(cast(int, index))
        used_hours = proposed
        used_zones.add(zone)
        month_counts[month] = month_counts.get(month, 0) + 1
        site_counts[site] = site_counts.get(site, 0) + 1

    baseline = _summarize(
        "highest standardized residual first", work, baseline_indices, assumptions
    )
    optimized = _summarize("CP-SAT expected-value policy", work, optimized_indices, assumptions)
    baseline_value = float(baseline["expectedDecisionValue"])
    improvement = (
        100.0 * (float(optimized["expectedDecisionValue"]) - baseline_value) / abs(baseline_value)
        if abs(baseline_value) > 1e-9
        else 0.0
    )
    if abs(improvement) < 1e-9:
        improvement = 0.0
    return {
        "candidateCount": int(len(work)),
        "assumptions": assumptions.__dict__,
        "baseline": baseline,
        "optimized": optimized,
        "improvementPct": improvement,
    }


def sensitivity(
    monitoring: pd.DataFrame,
    metadata: pd.DataFrame,
    base: DecisionAssumptions,
) -> list[dict[str, Any]]:
    scenarios: list[tuple[str, DecisionAssumptions]] = [("base", base)]
    for value in (4.0, 6.0, 8.0, 20.0):
        scenarios.append((f"budget_hours={value:g}", replace(base, budget_hours=value)))
    for value in (0.0, 150.0):
        scenarios.append(
            (f"false_positive_cost={value:g}", replace(base, false_positive_cost=value))
        )
    for value in (2.0, 10.0):
        scenarios.append((f"missed_m3_cost={value:g}", replace(base, missed_m3_cost=value)))
    for value in (0.75, 1.5):
        scenarios.append(
            (f"interval_multiplier={value:g}", replace(base, interval_multiplier=value))
        )
    for value in (2, 6):
        scenarios.append((f"persistence_months={value}", replace(base, persistence_months=value)))
    for value in (0.5, 2.0):
        scenarios.append(
            (f"zone_activation_hours={value:g}", replace(base, zone_activation_hours=value))
        )

    results: list[dict[str, Any]] = []
    for label, assumptions in scenarios:
        candidates = anomaly_candidates(monitoring, metadata, assumptions.interval_multiplier)
        result = optimize(candidates, assumptions)
        results.append(
            {
                "scenario": label,
                "candidateCount": result["candidateCount"],
                "improvementPct": result["improvementPct"],
                "baselineValue": result["baseline"]["expectedDecisionValue"],
                "optimizedValue": result["optimized"]["expectedDecisionValue"],
                "baselineExcessM3": result["baseline"]["capturedObservedExcessM3"],
                "optimizedExcessM3": result["optimized"]["capturedObservedExcessM3"],
            }
        )
    return results
