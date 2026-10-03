"""A failed post-commit side effect cannot suppress the remaining callbacks."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.services import form_routing_service


def test_callbacks_continue_after_each_failure_and_log_only_safe_identifiers(caplog):
    db = Mock()
    submission = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    promotion = Mock(side_effect=RuntimeError("Applicant name and email must not be logged"))
    attribution = Mock(side_effect=ValueError("Private provider response"))
    staff_workflows = Mock()

    form_routing_service.run_after_commit(db, submission, [promotion, attribution, staff_workflows])

    promotion.assert_called_once_with()
    attribution.assert_called_once_with()
    staff_workflows.assert_called_once_with()
    assert db.rollback.call_count == 2
    assert [record.message for record in caplog.records] == [
        f"Submission callback failed: exception={error} submission_id={submission.id} "
        f"organization_id={submission.organization_id}"
        for error in ("RuntimeError", "ValueError")
    ]
