from datetime import datetime, timezone

from app.db.enums import WorkflowConditionOperator
from app.services import workflow_triggers
from app.services.workflow_engine import engine


def test_should_run_cron_weekday_mapping():
    # 2026-01-05 is a Monday
    now = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)

    assert workflow_triggers._should_run_cron("0 9 * * 1", now, "UTC") is True
    assert workflow_triggers._should_run_cron("0 9 * * 2", now, "UTC") is False


def test_should_run_cron_sunday_aliases():
    # 2026-01-04 is a Sunday
    now = datetime(2026, 1, 4, 9, 0, tzinfo=timezone.utc)

    assert workflow_triggers._should_run_cron("0 9 * * 0", now, "UTC") is True
    assert workflow_triggers._should_run_cron("0 9 * * 7", now, "UTC") is True


def test_evaluate_condition_in_handles_csv_values():
    assert engine._evaluate_condition(
        WorkflowConditionOperator.IN.value,
        "TX",
        "TX, CA",
    )
    assert not engine._evaluate_condition(
        WorkflowConditionOperator.NOT_IN.value,
        "TX",
        "TX, CA",
    )
