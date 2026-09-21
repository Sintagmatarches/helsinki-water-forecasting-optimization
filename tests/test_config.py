from dataclasses import replace

import pytest

from helsinki_water.config import load_config


def test_committed_design_ends_development_before_holdout() -> None:
    config = load_config()
    assert config.development_last_origin == "2017-06"
    assert config.final_origin == "2017-12"


@pytest.mark.parametrize("changes, message", [
    ({"development_horizon": 7}, "overlap"),
    ({"final_horizon": 13}, "beyond observed"),
    ({"development_step_months": 0}, "positive"),
    ({"interval_alpha": float("nan")}, "interval_alpha"),
    ({"interval_alpha": 1.0}, "interval_alpha"),
    ({"start_month": "2010-13"}, "ISO month"),
    ({"properties": ("duplicate", "duplicate")}, "unique"),
    ({"version": "../../overwrite"}, "version"),
    ({"optimization": {"budget_hours": -1}}, "nonnegative"),
])
def test_invalid_design_is_rejected_before_running(changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(load_config(), **changes)
