"""Party rules for a match: one class per party kind.

Each party owns its row lock, accept eligibility, and stage moves on accept and
on approved cancellation. Stage moves return the after-commit effects of the
underlying stage service.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.stage_definitions import INTENDED_PARENT_PIPELINE_ENTITY
from app.db.models import Donor, IntendedParent, Match, StatusChangeRequest, Surrogate
from app.services import match_queries

Effect = tuple[str, Callable[[], None]]


class Party:
    kind: str
    model: type

    def party_id(self, match: Match) -> UUID | None:
        raise NotImplementedError

    def lock(self, db: Session, match: Match) -> None:
        """Take the row lock once, in the engine's fixed party order.

        FOR NO KEY UPDATE serializes transitions on the party but does not block the
        FOR KEY SHARE that activity inserts take on their foreign keys, so writing
        history for another match's party cannot deadlock against this lock.
        """
        model = self.model
        db.query(model).filter(
            model.id == self.party_id(match), model.organization_id == match.organization_id
        ).populate_existing().with_for_update(key_share=True).one()

    def accept_warning(self, db: Session, match: Match) -> str | None:
        raise NotImplementedError

    def on_accept(
        self, db: Session, match: Match, *, actor_user_id: UUID, actor_role, now: datetime
    ) -> list[Effect]:
        return []

    def on_cancel_approved(
        self,
        db: Session,
        match: Match,
        *,
        request: StatusChangeRequest,
        actor_user_id: UUID,
        now: datetime,
    ) -> list[Effect]:
        return []


class SurrogateParty(Party):
    kind = "surrogate"
    model = Surrogate

    def party_id(self, match: Match) -> UUID | None:
        return match.surrogate_id

    def accept_warning(self, db: Session, match: Match) -> str | None:
        surrogate = match_queries.get_surrogate_with_stage(
            db, match.surrogate_id, match.organization_id
        )
        return _stage_warning(surrogate, "Surrogate", {"ready_to_match"})

    def on_accept(
        self, db: Session, match: Match, *, actor_user_id: UUID, actor_role, now: datetime
    ) -> list[Effect]:
        """Move the surrogate to Matched."""
        from app.services import pipeline_service, surrogate_status_service

        surrogate = match_queries.get_surrogate_with_stage(
            db, match.surrogate_id, match.organization_id
        )
        if not surrogate:
            return []
        current_stage = surrogate.stage
        pipeline_id = current_stage.pipeline_id if current_stage else None
        if not pipeline_id:
            pipeline_id = pipeline_service.get_or_create_default_pipeline(
                db, match.organization_id, actor_user_id
            ).id
        matched_stage = pipeline_service.get_stage_by_system_role(db, pipeline_id, "matched")
        if not matched_stage or not matched_stage.is_active or matched_stage.deleted_at:
            raise ValueError("Surrogate Matched stage not found")
        if surrogate.stage_id == matched_stage.id:
            return []
        _authorize_stage_move(db, match, actor_user_id, "surrogate", surrogate, matched_stage)
        result = surrogate_status_service.change_status(
            db=db,
            surrogate=surrogate,
            new_stage_id=matched_stage.id,
            user_id=actor_user_id,
            user_role=actor_role,
            reason="Match accepted",
            commit=False,
        )
        if result["status"] != "applied":
            db.rollback()
            raise ValueError("Surrogate stage requires approval before accepting this match")
        return list(result.get("after_commit_effects", []))

    def on_cancel_approved(
        self,
        db: Session,
        match: Match,
        *,
        request: StatusChangeRequest,
        actor_user_id: UUID,
        now: datetime,
    ) -> list[Effect]:
        """Return the surrogate to Ready to Match. The stage history credits the approver."""
        from app.services import pipeline_service, surrogate_status_service

        surrogate = match_queries.get_surrogate_with_stage(
            db, match.surrogate_id, match.organization_id
        )
        if not surrogate or not surrogate.stage:
            raise ValueError("Match participants not found")
        old_stage = surrogate.stage
        ready = pipeline_service.get_stage_by_system_role(db, old_stage.pipeline_id, "handoff")
        if not ready:
            raise ValueError("Ready to match stage not found")
        if old_stage.id == ready.id:
            return []
        _authorize_stage_move(db, match, actor_user_id, "surrogate", surrogate, ready)
        result = surrogate_status_service.apply_status_change(
            db=db,
            surrogate=surrogate,
            new_stage=ready,
            current_stage=old_stage,
            old_stage_id=surrogate.stage_id,
            old_label=surrogate.status_label,
            old_slug=old_stage.slug,
            user_id=actor_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            request_id=request.id,
            approved_by_user_id=actor_user_id,
            approved_at=now,
            requested_at=request.requested_at,
            commit=False,
        )
        return list(result.get("after_commit_effects", []))


class DonorParty(Party):
    """Donors can retain multiple active matches at Matched."""

    kind = "donor"
    model = Donor

    def party_id(self, match: Match) -> UUID | None:
        return match.donor_id

    def accept_warning(self, db: Session, match: Match) -> str | None:
        donor = match_queries.get_donor(db, match.donor_id, match.organization_id)
        ready = "available" if donor and donor.donor_type == "sperm" else "ready_to_match"
        eligible = {ready}
        if match_queries.has_other_committed_match_for_donor(db, match):
            eligible.add("matched")
        return _stage_warning(donor, "Donor", eligible)

    def _move(self, db, match, *, actor_user_id, now, role, request=None) -> list[Effect]:
        from app.services import donor_service, pipeline_service, workflow_triggers

        donor = match_queries.get_donor(db, match.donor_id, match.organization_id)
        if not donor or not donor.stage:
            raise ValueError("Match participants not found")
        old_stage = donor.stage
        if role == "handoff" and not pipeline_service.stage_matches_system_role(
            old_stage, "matched", donor.pipeline_entity_type
        ):
            return []
        target = pipeline_service.get_stage_by_system_role(
            db, old_stage.pipeline_id, role, donor.pipeline_entity_type
        )
        if not target or not target.is_active or target.deleted_at:
            raise ValueError(f"Donor {role} stage not found")
        if old_stage.id == target.id:
            return []
        _authorize_stage_move(db, match, actor_user_id, "donor", donor, target)
        donor_service.apply_status_change(
            db,
            donor=donor,
            old_stage=old_stage,
            new_stage=target,
            user_id=actor_user_id,
            reason=request.reason if request else "Match accepted",
            effective_at=request.effective_at if request else now,
            recorded_at=now,
            request_id=request.id if request else None,
            requested_at=request.requested_at if request else None,
            approved_by_user_id=actor_user_id if request else None,
            approved_at=now if request else None,
            emit_workflow_events=False,
            commit=False,
        )
        return [
            (
                "donor_stage_changed",
                lambda: workflow_triggers.trigger_donor_stage_changed(
                    db, donor, old_stage=old_stage, new_stage=target
                ),
            )
        ]

    def on_accept(self, db, match, *, actor_user_id, actor_role, now) -> list[Effect]:
        return self._move(db, match, actor_user_id=actor_user_id, now=now, role="matched")

    def on_cancel_approved(self, db, match, *, request, actor_user_id, now) -> list[Effect]:
        if match_queries.has_other_committed_match_for_donor(db, match):
            return []
        return self._move(
            db, match, actor_user_id=actor_user_id, now=now, role="handoff", request=request
        )


class IntendedParentParty(Party):
    kind = "intended_parent"
    model = IntendedParent

    def party_id(self, match: Match) -> UUID | None:
        return match.intended_parent_id

    def accept_warning(self, db: Session, match: Match) -> str | None:
        ip = match_queries.get_intended_parent(db, match.intended_parent_id, match.organization_id)
        return _stage_warning(ip, "Intended parent", {"ready_to_match", "matched"})

    def on_accept(
        self, db: Session, match: Match, *, actor_user_id: UUID, actor_role, now: datetime
    ) -> list[Effect]:
        """Move an eligible intended parent to Matched unless already there."""
        from app.services import intended_parent_status_service, pipeline_service

        ip = match_queries.get_intended_parent(db, match.intended_parent_id, match.organization_id)
        if not ip:
            return []
        current = intended_parent_status_service.get_current_stage(db, ip)
        if pipeline_service.stage_matches_system_role(
            current, "matched", INTENDED_PARENT_PIPELINE_ENTITY
        ):
            return []
        matched = pipeline_service.get_stage_by_system_role(
            db, current.pipeline_id, "matched", INTENDED_PARENT_PIPELINE_ENTITY
        )
        if not matched or not matched.is_active or matched.deleted_at:
            raise ValueError("Intended parent Matched stage not found")
        _authorize_stage_move(db, match, actor_user_id, "intended_parent", ip, matched)
        intended_parent_status_service.apply_status_change(
            db=db,
            ip=ip,
            old_stage=current,
            new_stage=matched,
            user_id=actor_user_id,
            reason="Match accepted",
            effective_at=now,
            recorded_at=now,
            commit=False,
        )
        return []

    def on_cancel_approved(
        self,
        db: Session,
        match: Match,
        *,
        request: StatusChangeRequest,
        actor_user_id: UUID,
        now: datetime,
    ) -> list[Effect]:
        """Return a Matched intended parent to handoff after its last committed match ends."""
        from app.services import intended_parent_status_service, pipeline_service

        ip = match_queries.get_intended_parent(db, match.intended_parent_id, match.organization_id)
        if not ip:
            raise ValueError("Match participants not found")
        remaining = match_queries.has_other_committed_match_for_intended_parent(db, match)
        old_stage = intended_parent_status_service.get_current_stage(db, ip)
        if remaining or not pipeline_service.stage_matches_system_role(
            old_stage, "matched", INTENDED_PARENT_PIPELINE_ENTITY
        ):
            return []
        ready = pipeline_service.get_stage_by_system_role(
            db, old_stage.pipeline_id, "handoff", INTENDED_PARENT_PIPELINE_ENTITY
        )
        if not ready:
            raise ValueError("Ready to match stage not found")
        if old_stage.id == ready.id:
            return []
        _authorize_stage_move(db, match, actor_user_id, "intended_parent", ip, ready)
        intended_parent_status_service.apply_status_change(
            db=db,
            ip=ip,
            old_stage=old_stage,
            new_stage=ready,
            user_id=actor_user_id,
            reason=request.reason,
            effective_at=request.effective_at,
            recorded_at=now,
            request_id=request.id,
            approved_by_user_id=actor_user_id,
            approved_at=now,
            requested_at=request.requested_at,
            commit=False,
        )
        return []


SURROGATE = SurrogateParty()
DONOR = DonorParty()
INTENDED_PARENT = IntendedParentParty()


def primary(match: Match) -> Party:
    """The surrogate or donor side of the match."""
    return DONOR if match.donor_id else SURROGATE


def parties(match: Match) -> list[Party]:
    """Parties in the engine's fixed lock order: surrogate or donor, then intended parent."""
    return [primary(match), INTENDED_PARENT]


def _stage_warning(record, label: str, eligible: set[str]) -> str | None:
    stage = record.stage if record else None
    if stage and stage.stage_key in eligible and stage.is_active and not stage.deleted_at:
        return None
    current = stage.label if stage else "an unknown stage"
    return f"{label} at {current} is not eligible to accept"


def accept_eligibility_warnings(db: Session, match: Match) -> list[str]:
    return [warning for party in parties(match) if (warning := party.accept_warning(db, match))]


def _authorize_stage_move(db, match, actor_user_id, kind, record, target, *, preview=False) -> None:
    from app.services import (
        approval_handoff_service,
        permission_service,
        pipeline_semantics_service,
    )

    member = permission_service.get_membership_for_user(db, match.organization_id, actor_user_id)
    permission = f"change_{kind}_status"
    if not member or not permission_service.check_permission(
        db, match.organization_id, actor_user_id, member.role, permission
    ):
        raise ValueError(f"Missing permission: {permission}")
    uses_record_policy = approval_handoff_service.authorize_stage_change(
        db,
        record=record,
        kind=kind,
        target_stage=target,
        user_id=actor_user_id,
        lock_configuration=not preview,
    )
    if not uses_record_policy and not pipeline_semantics_service.can_role_access_stage(
        member.role,
        target,
        feature_config=pipeline_semantics_service.get_pipeline_feature_config(target.pipeline),
        mutation=True,
    ):
        raise ValueError(f"Role not permitted to change {kind.replace('_', ' ')} stage")


def check_accept_stage_changes(db: Session, match: Match, actor_user_id: UUID) -> None:
    """Read-only counterpart of the accept hooks, also used before engine writes."""
    from app.services import permission_policy_service, permission_service, pipeline_service

    member = permission_service.get_membership_for_user(db, match.organization_id, actor_user_id)
    for party in parties(match):
        record = (
            db.query(party.model)
            .filter(
                party.model.id == party.party_id(match),
                party.model.organization_id == match.organization_id,
            )
            .one_or_none()
        )
        if not record or not record.stage:
            raise ValueError("Match participants not found")
        entity = record.pipeline_entity_type if party.kind == "donor" else party.kind
        if pipeline_service.stage_matches_system_role(record.stage, "matched", entity):
            continue
        target = pipeline_service.get_stage_by_system_role(
            db, record.stage.pipeline_id, "matched", entity
        )
        if not target or not target.is_active or target.deleted_at:
            label = (
                "Intended parent" if party.kind == "intended_parent" else party.kind.capitalize()
            )
            raise ValueError(f"{label} Matched stage not found")
        _authorize_stage_move(db, match, actor_user_id, party.kind, record, target, preview=True)
        if (
            party.kind == "surrogate"
            and member
            and member.role == "case_manager"
            and not permission_policy_service.is_enabled(db, match.organization_id)
            and (record.owner_type != "user" or record.owner_id != actor_user_id)
        ):
            raise ValueError("Surrogate must be claimed before changing stage")
