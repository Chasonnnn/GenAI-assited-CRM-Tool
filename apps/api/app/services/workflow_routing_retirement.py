"""Retired routing payloads may remain in history or arrive from older releases."""

RETIRED_ROUTING_ACTIONS = frozenset({"auto_match_submission", "create_intake_lead"})
GENERATED_ROUTING_PREFIX = "shared_intake_routing:"


def has_retired_routing_actions(actions: list[dict] | None) -> bool:
    return any(a.get("action_type") in RETIRED_ROUTING_ACTIONS for a in actions or [])


def strip_retired_routing_actions(actions: list[dict] | None) -> list[dict]:
    return [a for a in actions or [] if a.get("action_type") not in RETIRED_ROUTING_ACTIONS]
