"""Party rules for a match: one class per party kind.

Each party owns its row lock, accept eligibility, stage moves on accept and on
approved cancellation, and the attempt types it allows. Stage moves return the
after-commit effects of the underlying stage service.
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

    def check_accept(self, db: Session, match: Match) -> None:
        """Raise ValueError when this party blocks accepting the match."""

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

    def check_attempt_type(self, attempt_type: str | None) -> None:
        """Raise ValueError for attempt types that belong to the other participant kind."""


class SurrogateParty(Party):
    kind = "surrogate"
    model = Surrogate

    def party_id(self, match: Match) -> UUID | None:
        return match.surrogate_id

    def check_accept(self, db: Session, match: Match) -> None:
        committed = match_queries.get_accepted_match_for_surrogate(
            db, match.organization_id, match.surrogate_id
        )
        if committed and committed.id != match.id:
            raise ValueError("Surrogate already has an accepted match")

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
        if not matched_stage or surrogate.stage_id == matched_stage.id:
            return []
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
        """Return the surrogate to Ready to Match. The stage history credits the requester."""
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
        result = surrogate_status_service.apply_status_change(
            db=db,
            surrogate=surrogate,
            new_stage=ready,
            current_stage=old_stage,
            old_stage_id=surrogate.stage_id,
            old_label=surrogate.status_label,
            old_slug=old_stage.slug,
            user_id=request.requested_by_user_id,
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

    def check_attempt_type(self, attempt_type: str | None) -> None:
        if attempt_type in ("retrieval", "collection"):
            raise ValueError("Retrieval and collection attempts belong to donor cases")


class DonorParty(Party):
    """Donor stage does not move with the match."""

    kind = "donor"
    model = Donor

    def party_id(self, match: Match) -> UUID | None:
        return match.donor_id

    def on_cancel_approved(
        self,
        db: Session,
        match: Match,
        *,
        request: StatusChangeRequest,
        actor_user_id: UUID,
        now: datetime,
    ) -> list[Effect]:
        if not match_queries.get_donor(db, match.donor_id, match.organization_id):
            raise ValueError("Match participants not found")
        return []

    def check_attempt_type(self, attempt_type: str | None) -> None:
        if attempt_type == "embryo_transfer":
            raise ValueError("Embryo transfers belong to surrogate cases")


class IntendedParentParty(Party):
    kind = "intended_parent"
    model = IntendedParent

    def party_id(self, match: Match) -> UUID | None:
        return match.intended_parent_id

    def on_accept(
        self, db: Session, match: Match, *, actor_user_id: UUID, actor_role, now: datetime
    ) -> list[Effect]:
        """Move the intended parent to Matched unless already at or beyond it."""
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
        if matched and current.order < matched.order:
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
        """Return the intended parent to Ready to Match when no other committed match remains."""
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
        intended_parent_status_service.apply_status_change(
            db=db,
            ip=ip,
            old_stage=old_stage,
            new_stage=ready,
            user_id=request.requested_by_user_id,
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
