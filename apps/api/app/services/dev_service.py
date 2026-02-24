"""Dev-only helpers for local seeding and diagnostics."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.enums import AuthProvider, Role
from app.db.models import AuthIdentity, Membership, Organization, User
from app.services import org_service

TEST_ORG_SLUG = "test-org"
TEST_ORG_NAME = "Test Organization"
SEED_USERS: list[tuple[str, str, Role]] = [
    ("admin@test.com", "Test Admin", Role.ADMIN),
    ("intake@test.com", "Test Intake", Role.INTAKE_SPECIALIST),
    ("specialist@test.com", "Test Case Manager", Role.CASE_MANAGER),
    ("developer@test.com", "Test Developer", Role.DEVELOPER),
]


def _get_or_create_org(db: Session) -> tuple[Organization, bool]:
    org = org_service.get_org_by_slug(db, TEST_ORG_SLUG)
    if org:
        return org, False

    org = Organization(name=TEST_ORG_NAME, slug=TEST_ORG_SLUG)
    db.add(org)
    db.flush()
    return org, True


def _get_or_create_user(db: Session, email: str, display_name: str) -> tuple[User, bool]:
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    created = False
    if not user:
        user = User(email=email, display_name=display_name, is_active=True)
        db.add(user)
        db.flush()
        created = True
    else:
        if user.display_name != display_name:
            user.display_name = display_name
        if not user.is_active:
            user.is_active = True
    return user, created


def _ensure_identity(db: Session, user: User, email: str) -> bool:
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.user_id == user.id,
            AuthIdentity.provider == AuthProvider.GOOGLE.value,
        )
        .first()
    )
    if identity:
        if identity.email != email:
            identity.email = email
        return False

    db.add(
        AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.GOOGLE.value,
            provider_subject=f"test-sub-{email}",
            email=email,
        )
    )
    return True


def _ensure_membership(db: Session, user_id, org_id, role: Role) -> bool:
    membership = db.query(Membership).filter(Membership.user_id == user_id).first()
    if not membership:
        db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=role.value,
                is_active=True,
            )
        )
        return True

    changed = False
    if membership.organization_id != org_id:
        membership.organization_id = org_id
        changed = True
    if membership.role != role.value:
        membership.role = role.value
        changed = True
    if not membership.is_active:
        membership.is_active = True
        changed = True
    return changed


def seed_test_data(db: Session) -> dict:
    """Create/repair test org users for local development (idempotent)."""
    org, org_created = _get_or_create_org(db)
    changed = org_created

    users_payload: list[dict[str, str]] = []
    for email, name, role in SEED_USERS:
        user, user_created = _get_or_create_user(db, email=email, display_name=name)
        changed = changed or user_created
        changed = _ensure_identity(db, user, email) or changed
        changed = _ensure_membership(db, user.id, org.id, role) or changed
        users_payload.append(
            {
                "email": email,
                "user_id": str(user.id),
                "role": role.value,
            }
        )

    db.commit()
    users_payload.sort(key=lambda item: item["email"])

    return {
        "status": "seeded" if changed else "already_seeded",
        "org_id": str(org.id),
        "org_slug": TEST_ORG_SLUG,
        "users": users_payload,
    }
