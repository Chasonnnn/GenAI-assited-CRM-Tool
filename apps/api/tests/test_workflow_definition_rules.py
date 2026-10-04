"""Behavior contracts for workflow definition rules without database access."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.db.enums import WorkflowTriggerType
from app.services.workflow_definition_rules import (
    validate_trigger_config,
)


@pytest.mark.parametrize(
    ("trigger_type", "config"),
    [
        (WorkflowTriggerType.STATUS_CHANGED, {"from_stage_id": None, "to_stage_id": None}),
        (WorkflowTriggerType.DONOR_STAGE_CHANGED, {}),
        (WorkflowTriggerType.SCHEDULED, {"cron": "0 9 * * 1"}),
        (WorkflowTriggerType.TASK_DUE, {"hours_before": "168"}),
        (WorkflowTriggerType.INACTIVITY, {"days": "90"}),
        (WorkflowTriggerType.SURROGATE_UPDATED, {"fields": ["status_label"]}),
        (WorkflowTriggerType.DONOR_UPDATED, {"fields": ["donor_type"]}),
        (WorkflowTriggerType.FORM_SUBMITTED, {"lead_kind": "egg_donor"}),
        (WorkflowTriggerType.INTAKE_LEAD_CREATED, {"lead_type": "sperm_donor"}),
    ],
)
def test_trigger_validation_does_not_normalize_or_add_defaults(trigger_type, config):
    config["extra"] = {"retained": True}
    original = deepcopy(config)

    assert validate_trigger_config(trigger_type, config) is None
    assert config == original


@pytest.mark.parametrize(
    ("trigger_type", "config", "field", "message"),
    [
        (WorkflowTriggerType.STATUS_CHANGED, {"to_stage_id": "invalid"}, "to_stage_id", "UUID"),
        (
            WorkflowTriggerType.DONOR_STAGE_CHANGED,
            {"from_stage_id": "invalid"},
            "from_stage_id",
            "UUID",
        ),
        (WorkflowTriggerType.SCHEDULED, {}, "cron", "Field required"),
        (
            WorkflowTriggerType.SCHEDULED,
            {"cron": "0 9 1 * *"},
            "cron",
            "Cron must use the supported schedule format: minute hour * * weekday",
        ),
        (
            WorkflowTriggerType.SCHEDULED,
            {"cron": "0 9 * * *", "timezone": "Not/AZone"},
            "timezone",
            "Timezone must be a valid IANA timezone",
        ),
        (
            WorkflowTriggerType.TASK_DUE,
            {"hours_before": 0},
            "hours_before",
            "greater than or equal to 1",
        ),
        (
            WorkflowTriggerType.TASK_DUE,
            {"hours_before": 169},
            "hours_before",
            "less than or equal to 168",
        ),
        (WorkflowTriggerType.INACTIVITY, {"days": 0}, "days", "greater than or equal to 1"),
        (WorkflowTriggerType.INACTIVITY, {"days": 91}, "days", "less than or equal to 90"),
        (WorkflowTriggerType.SURROGATE_UPDATED, {"fields": []}, "fields", "at least 1 item"),
        (
            WorkflowTriggerType.DONOR_UPDATED,
            {"fields": ["unknown_field"]},
            "fields",
            "Field 'unknown_field' is not allowed",
        ),
        (
            WorkflowTriggerType.FORM_SUBMITTED,
            {"lead_kind": "unknown"},
            "lead_kind",
            "Input should be",
        ),
        (
            WorkflowTriggerType.INTAKE_LEAD_CREATED,
            {"lead_type": "unknown"},
            "lead_type",
            "Input should be",
        ),
    ],
)
def test_invalid_trigger_config_preserves_error_details_and_input(
    trigger_type, config, field, message
):
    original = deepcopy(config)

    with pytest.raises(ValidationError) as error:
        validate_trigger_config(trigger_type, config)

    details = error.value.errors()
    assert details[0]["loc"] == (field,)
    assert message in details[0]["msg"]
    assert config == original


def test_schedule_errors_keep_schema_field_order():
    with pytest.raises(ValidationError) as error:
        validate_trigger_config(
            WorkflowTriggerType.SCHEDULED, {"cron": "invalid", "timezone": "Not/AZone"}
        )

    assert [detail["loc"] for detail in error.value.errors()] == [("cron",), ("timezone",)]


def test_trigger_without_config_schema_leaves_arbitrary_config_unchanged():
    config = {"hours_before": -1, "fields": [], "metadata": {"source": "test"}}
    original = deepcopy(config)

    assert validate_trigger_config(WorkflowTriggerType.TASK_OVERDUE, config) is None
    assert config == original


def test_retired_form_started_trigger_is_rejected():
    with pytest.raises(ValueError, match="form_started is no longer available"):
        validate_trigger_config(
            WorkflowTriggerType.FORM_STARTED,
            {"form_id": "00000000-0000-0000-0000-000000000001"},
        )
