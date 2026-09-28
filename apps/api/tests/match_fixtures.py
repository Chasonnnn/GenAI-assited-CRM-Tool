"""Persist valid match prerequisites without replaying unrelated HTTP workflows."""

import uuid
from datetime import UTC, datetime
from itertools import count

from app.core.deps import COOKIE_NAME
from app.core.encryption import hash_email
from app.core.security import decode_session_token
from app.db.models import IntendedParent, Match, MatchAttempt, Surrogate
from app.services import pipeline_service

_numbers = count(90000)


def seed_surrogate_match(db, client, *, status="under_review") -> Match:
    """Lifecycle behavior stays covered by tests that call the transition endpoints."""
    session = decode_session_token(client.cookies[COOKIE_NAME])
    org_id = uuid.UUID(session["org_id"])
    user_id = uuid.UUID(session["sub"])
    stage_key = "ready_to_match" if status == "under_review" else "matched"
    stages = {}
    for entity_type in ("surrogate", "intended_parent"):
        pipeline = pipeline_service.get_or_create_default_pipeline(
            db, org_id, user_id, entity_type=entity_type
        )
        stages[entity_type] = pipeline_service.get_stage_by_slug(db, pipeline.id, stage_key)

    suffix = f"{next(_numbers):05d}"
    surrogate_email = f"surrogate-{suffix}@example.com"
    ip_email = f"ip-{suffix}@example.com"
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{suffix}",
        full_name="Permission Surrogate",
        email=surrogate_email,
        email_hash=hash_email(surrogate_email),
        stage_id=stages["surrogate"].id,
        status_label=stages["surrogate"].label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
    )
    ip = IntendedParent(
        id=uuid.uuid4(),
        organization_id=org_id,
        intended_parent_number=f"I{suffix}",
        full_name="Permission Intended Parent",
        email=ip_email,
        email_hash=hash_email(ip_email),
        stage_id=stages["intended_parent"].id,
        status=stage_key,
        owner_type="user",
        owner_id=user_id,
    )
    db.add_all([surrogate, ip])
    db.flush()
    match = Match(
        id=uuid.uuid4(),
        organization_id=org_id,
        match_number=f"M{suffix}",
        surrogate_id=surrogate.id,
        intended_parent_id=ip.id,
        status=status,
        proposed_by_user_id=user_id,
        reviewed_by_user_id=user_id if status == "accepted" else None,
        reviewed_at=datetime.now(UTC) if status == "accepted" else None,
    )
    db.add(match)
    db.flush()
    db.commit()
    return match


def seed_attempt(db, match_id, *, attempt_type="embryo_transfer", status="planned") -> MatchAttempt:
    """Attempts have no write API; existing rows still drive completion and cancel rules."""
    match = db.get(Match, uuid.UUID(str(match_id)))
    sequence = db.query(MatchAttempt).filter(MatchAttempt.match_id == match.id).count() + 1
    attempt = MatchAttempt(
        organization_id=match.organization_id,
        match_id=match.id,
        sequence=sequence,
        attempt_type=attempt_type,
        status=status,
    )
    db.add(attempt)
    db.flush()
    return attempt
