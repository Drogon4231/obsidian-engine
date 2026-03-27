"""Tests for cost budget enforcement in cost_tracker.py."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.cost_tracker import (
    check_budget, get_remaining_budget, BudgetExceededError,
    start_run, log_cost, get_cost_estimate,
)


class TestCheckBudget:
    def test_disabled_when_zero(self):
        assert check_budget(0) is True

    def test_disabled_when_negative(self):
        assert check_budget(-10.0) is True

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 5.0})
    def test_within_budget(self, mock_costs):
        assert check_budget(10.0) is True

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 15.0})
    def test_over_budget_raises(self, mock_costs):
        with pytest.raises(BudgetExceededError) as exc_info:
            check_budget(10.0, "Research")
        assert exc_info.value.spent == 15.0
        assert exc_info.value.budget == 10.0
        assert "Research" in str(exc_info.value)

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 10.0})
    def test_exactly_at_budget_passes(self, mock_costs):
        """Exactly at budget is not over — passes."""
        assert check_budget(10.0) is True

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 10.001})
    def test_barely_over_raises(self, mock_costs):
        with pytest.raises(BudgetExceededError):
            check_budget(10.0)

    @patch("clients.claude_client.get_session_costs", side_effect=ImportError("no module"))
    def test_graceful_on_import_error(self, mock_costs):
        """If session costs can't be read, don't block the pipeline."""
        assert check_budget(10.0) is True


class TestGetRemainingBudget:
    def test_disabled_returns_inf(self):
        assert get_remaining_budget(0) == float("inf")

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 3.0})
    def test_returns_remaining(self, mock_costs):
        assert get_remaining_budget(10.0) == 7.0

    @patch("clients.claude_client.get_session_costs", return_value={"usd_total": 15.0})
    def test_returns_zero_when_over(self, mock_costs):
        assert get_remaining_budget(10.0) == 0.0

    @patch("clients.claude_client.get_session_costs", side_effect=Exception("fail"))
    def test_returns_inf_on_error(self, mock_costs):
        assert get_remaining_budget(10.0) == float("inf")


class TestBudgetExceededError:
    def test_is_exception(self):
        err = BudgetExceededError(25.0, 20.0, "Script")
        assert isinstance(err, Exception)
        assert err.spent == 25.0
        assert err.budget == 20.0
        assert err.stage == "Script"
        assert "25.00" in str(err)
        assert "20.00" in str(err)
        assert "Script" in str(err)

    def test_no_stage(self):
        err = BudgetExceededError(5.0, 3.0)
        assert "stage" not in str(err).lower() or err.stage == ""


class TestCostTrackerCore:
    """Verify existing cost tracker functions still work."""

    def test_start_and_estimate(self):
        start_run("Test Topic", "test_budget_run")
        log_cost("test_budget_run", "research", "claude_sonnet", 10000, "tokens")
        estimate = get_cost_estimate("test_budget_run")
        assert estimate["total_cost"] > 0
        assert estimate["entries"] == 1
        assert "research" in estimate["per_stage"]

    def test_estimate_empty_run(self):
        start_run("Empty", "test_empty_run")
        estimate = get_cost_estimate("test_empty_run")
        assert estimate["total_cost"] == 0.0
        assert estimate["entries"] == 0
