"""Dev-only helpers for local seeding and diagnostics."""

from sqlalchemy.orm import Session

from app.db.enums import AuthProvider, Role
from app.db.models import AuthIdentity, Membership, Organization, User
from app.services import org_service


def seed_test_data(db: Session) -> dict:
    """Create test org/users for local development (idempotent)."""
    existing = org_service.get_org_by_slug(db, "test-org")
    if existing:
        return {"status": "already_seeded", "org_id": str(existing.id)}

    org = Organization(name="Test Organization", slug="test-org")
    db.add(org)
    db.flush()

    users_data = [
        ("admin@test.com", "Test Admin", Role.ADMIN),
        ("intake@test.com", "Test Intake", Role.INTAKE_SPECIALIST),
        ("specialist@test.com", "Test Case Manager", Role.CASE_MANAGER),
    ]

    created_users: list[dict[str, str]] = []
    for email, name, role in users_data:
        user = User(email=email, display_name=name)
        db.add(user)
        db.flush()

        identity = AuthIdentity(
            user_id=user.id,
            provider=AuthProvider.GOOGLE.value,
            provider_subject=f"test-sub-{email}",
            email=email,
        )
        db.add(identity)

        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role=role.value,
        )
        db.add(membership)

        created_users.append(
            {
                "email": email,
                "user_id": str(user.id),
                "role": role.value,
            }
        )

    db.commit()

    return {
        "status": "seeded",
        "org_id": str(org.id),
        "org_slug": "test-org",
        "users": created_users,
    }
