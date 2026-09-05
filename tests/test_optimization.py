from __future__ import annotations

import pandas as pd
import pytest

from helsinki_water.optimization import DecisionAssumptions, optimize


@pytest.mark.parametrize("index", [[0, 1, 2], [2, 5, 9], ["a", "b", "c"], [0, 0, 0]])
def test_optimized_policy_is_feasible_and_not_worse_than_greedy(index: list[object]) -> None:
    candidates = pd.DataFrame(
        {
            "candidate_id": ["A|2018-01", "B|2018-01", "C|2018-02"],
            "site": ["A", "B", "C"],
            "target_month": ["2018-01", "2018-01", "2018-02"],
            "inspection_zone": ["west", "west", "east"],
            "inspection_hours": [2.0, 2.0, 2.0],
            "confirmation_weight": [0.25, 0.75, 0.75],
            "excess_m3": [100.0, 60.0, 55.0],
            "standardized_excess": [3.0, 2.5, 2.0],
        },
        index=index,
    )
    assumptions = DecisionAssumptions(5.0, 10.0, 5.0, 1.0, 3, 1.0, 2, 1)
    result = optimize(candidates, assumptions)
    assert result["optimized"]["technicianHours"] <= 5.0
    assert (
        result["optimized"]["expectedDecisionValue"] >= result["baseline"]["expectedDecisionValue"]
    )
    assert result == optimize(candidates.reset_index(drop=True), assumptions)
