"""Pure classification contracts; synthetic IDs only, no app imports or database."""

import copy
import unittest
from datetime import UTC, datetime

from collector import aggregate_summary, classify_record, primitive

A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"
M = "00000000-0000-0000-0000-000000000003"
EARLY = "2026-01-01T00:00:00.000000+00:00"
ASSIGNED = "2026-01-02T00:00:00.000000+00:00"
APPROVED = "2026-01-03T00:00:00.000000+00:00"
LATE = "2026-01-04T00:00:00.000000+00:00"


def fixture():
    return {
        "current_owner": {"type": "user", "id": A},
        "phase_requires_review": False,
        "is_archived": False,
        "status_history": [
            {
                "approval_crossing_current_configuration": True,
                "recorded_at": APPROVED,
                "effective_at": APPROVED,
                "is_undo": False,
                "changed_by_user_id": B,
            }
        ],
        "ownership_activity": [
            {
                "at": ASSIGNED,
                "event_type": "assigned",
                "from_type": None,
                "from_id": None,
                "to_type": "user",
                "to_id": A,
                "required_references_valid": True,
            }
        ],
        "existing_review": None,
        "collaborators": [],
    }


MEMBERS = {
    A: {
        "membership_id": M,
        "role": "intake_specialist",
        "membership_active": True,
        "user_active": True,
    }
}


class ClassificationTests(unittest.TestCase):
    def test_assignment_and_role_observation_are_candidate_not_verified(self):
        # A valid assignment and role audit are observations, not proof that no
        # unlogged workflow assignment or membership reactivation intervened.
        role = {
            A: [
                {
                    "at": EARLY,
                    "event_type": "user_role_changed",
                    "old_role": "case_manager",
                    "new_role": "intake_specialist",
                }
            ]
        }
        result = classify_record(fixture(), MEMBERS, role)
        self.assertEqual(result["historical_classification"], "candidate")
        self.assertEqual(result["candidate_user_id"], A)
        self.assertEqual(
            result["candidate_role_evidence"], "audited_intake_observation"
        )
        self.assertIsNone(result["verification_basis"])
        self.assertEqual(
            result["current_direct_owner"]["classification"],
            "verified_current_metadata",
        )
        self.assertFalse(result["current_direct_owner"]["historical_ownership_proven"])

    def test_stage_actor_and_current_owner_cannot_replace_missing_history(self):
        record = fixture()
        record["ownership_activity"] = []
        result = classify_record(record, MEMBERS, {})
        self.assertEqual(result["historical_classification"], "ambiguous")
        self.assertIsNone(result["candidate_user_id"])
        self.assertTrue(result["current_direct_owner"]["scope_preservation_candidate"])
        self.assertIn("no_recorded_user_owner_at_approval", result["reasons"])

    def test_approval_time_and_cycle_ambiguity(self):
        for case in ("same_timestamp", "backdated", "missing", "multiple", "undo"):
            with self.subTest(case=case):
                record = fixture()
                if case == "same_timestamp":
                    record["ownership_activity"][0]["at"] = APPROVED
                elif case == "backdated":
                    record["status_history"][0]["effective_at"] = EARLY
                elif case == "missing":
                    record["status_history"] = []
                elif case == "multiple":
                    record["status_history"].append(
                        copy.deepcopy(record["status_history"][0])
                    )
                else:
                    record["status_history"][0]["is_undo"] = True
                self.assertEqual(
                    classify_record(record, MEMBERS, {})["historical_classification"],
                    "ambiguous",
                )

    def test_role_ambiguity_and_inactive_user_prevent_candidate_classification(self):
        cases = [
            [
                {
                    "at": APPROVED,
                    "event_type": "user_role_changed",
                    "old_role": "case_manager",
                    "new_role": "intake_specialist",
                }
            ],
            [
                {
                    "at": EARLY,
                    "event_type": "user_role_changed",
                    "old_role": "case_manager",
                    "new_role": "intake_specialist",
                },
                {
                    "at": LATE,
                    "event_type": "user_role_changed",
                    "old_role": "admin",
                    "new_role": "case_manager",
                },
            ],
            [
                {
                    "at": EARLY,
                    "event_type": "user_deactivated",
                    "old_role": None,
                    "new_role": None,
                }
            ],
        ]
        for events in cases:
            with self.subTest(events=events):
                self.assertEqual(
                    classify_record(fixture(), MEMBERS, {A: events})[
                        "historical_classification"
                    ],
                    "ambiguous",
                )
        inactive = copy.deepcopy(MEMBERS)
        inactive[A]["user_active"] = False
        result = classify_record(fixture(), inactive, {})
        self.assertEqual(result["historical_classification"], "ambiguous")
        self.assertFalse(result["current_direct_owner"]["scope_preservation_candidate"])

    def test_conflicting_chain_is_ambiguous_even_if_target_remains_same(self):
        record = fixture()
        event = copy.deepcopy(record["ownership_activity"][0])
        event.update(at="2026-01-02T12:00:00.000000+00:00", from_type="user", from_id=B)
        record["ownership_activity"].append(event)
        result = classify_record(record, MEMBERS, {})
        self.assertEqual(result["historical_classification"], "ambiguous")
        self.assertIn("recorded_ownership_chain_conflict", result["reasons"])

    def test_only_valid_existing_human_review_can_supply_verification(self):
        record = fixture()
        record["existing_review"] = {
            "fingerprint_matches": True,
            "decision": "retain_verified_owner",
            "retained_user_id": A,
            "has_evidence_reference": True,
        }
        record["collaborators"] = [{"user_id": A, "membership_id": M}]
        self.assertEqual(
            classify_record(record, MEMBERS, {})["historical_classification"],
            "verified",
        )
        for case in (
            "stale",
            "missing_evidence",
            "wrong_membership",
            "missing_collaborator",
            "unknown_phase",
        ):
            with self.subTest(case=case):
                invalid = copy.deepcopy(record)
                if case == "stale":
                    invalid["existing_review"]["fingerprint_matches"] = False
                elif case == "missing_evidence":
                    invalid["existing_review"]["has_evidence_reference"] = False
                elif case == "wrong_membership":
                    invalid["collaborators"][0]["membership_id"] = B
                elif case == "missing_collaborator":
                    invalid["collaborators"] = []
                else:
                    invalid["phase_requires_review"] = True
                self.assertNotEqual(
                    classify_record(invalid, MEMBERS, {})["historical_classification"],
                    "verified",
                )

    def test_aggregate_stdout_excludes_identifiers_and_metadata(self):
        record = fixture()
        record["review_classification"] = classify_record(record, MEMBERS, {})
        summary = aggregate_summary(
            {"organization_id": B, "records": [record], "role_history": []}
        )
        self.assertEqual(summary["handoff_records"], 1)
        self.assertEqual(summary["historical_classification"], {"candidate": 1})
        self.assertNotIn(A, repr(summary))
        self.assertNotIn(B, repr(summary))
        self.assertNotIn(APPROVED, repr(summary))

    def test_timestamp_normalization_preserves_subsecond_order(self):
        exact = primitive(datetime(2026, 1, 1, tzinfo=UTC))
        later = primitive(
            datetime(2026, 1, 1, microsecond=1, tzinfo=UTC).replace(tzinfo=None)
        )
        self.assertLess(exact, later)
        self.assertEqual(exact, "2026-01-01T00:00:00.000000+00:00")


if __name__ == "__main__":
    unittest.main()
