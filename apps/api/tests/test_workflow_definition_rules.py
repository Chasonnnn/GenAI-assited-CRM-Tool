"""Behavior contracts for workflow definition rules without database access."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.db.enums import WorkflowTriggerType
from app.services.workflow_definition_rules import (
    normalize_actions_for_trigger,
    validate_trigger_config,
)


def test_normalization_copies_actions_without_rewriting_or_deep_copying():
    actions = [
        {"action_type": "update_status", "stage_id": "stage", "metadata": {"source": "test"}},
        {"action_type": "create_intake_lead"},
        {"action_type": "auto_match_submission"},
    ]
    original = deepcopy(actions)

    normalized = normalize_actions_for_trigger(WorkflowTriggerType.SURROGATE_CREATED, actions)

    assert actions == original
    assert normalized == original
    assert normalized is not actions
    assert all(copy is not source for copy, source in zip(normalized, actions, strict=True))
    assert normalized[0]["metadata"] is actions[0]["metadata"]


@pytest.mark.parametrize(
    "action_types",
    [
        [],
        ["create_intake_lead"],
        ["auto_match_submission"],
        ["auto_match_submission", "add_note", "create_intake_lead"],
        # Existing definitions compare the first occurrence of each action only.
        ["auto_match_submission", "create_intake_lead", "auto_match_submission"],
    ],
)
def test_form_submission_preserves_allowed_action_order(action_types):
    actions = [{"action_type": action_type} for action_type in action_types]

    assert normalize_actions_for_trigger(WorkflowTriggerType.FORM_SUBMITTED, actions) == actions


def test_form_submission_rejects_create_before_match_without_mutating_input():
    actions = [
        {"action_type": "create_intake_lead"},
        {"action_type": "add_note", "content": "Keep this order"},
        {"action_type": "auto_match_submission"},
    ]
    original = deepcopy(actions)

    with pytest.raises(ValueError) as error:
        normalize_actions_for_trigger(WorkflowTriggerType.FORM_SUBMITTED, actions)

    assert str(error.value) == (
        "For form_submitted workflows, auto_match_submission must be placed before "
        "create_intake_lead"
    )
    assert actions == original


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
        (
            WorkflowTriggerType.FORM_STARTED,
            {"form_id": "00000000-0000-0000-0000-000000000001"},
        ),
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
        (WorkflowTriggerType.FORM_STARTED, {}, "form_id", "Field required"),
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
