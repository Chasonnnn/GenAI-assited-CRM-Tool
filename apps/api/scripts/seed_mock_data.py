"""
Seed script to create high-volume mock data for local testing.
Run with: python -m scripts.seed_mock_data
"""

import json
import os
import random
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.core.encryption import hash_email, hash_phone
from sqlalchemy import func
from app.db.session import SessionLocal
from app.db.models import (
    EntityNote,
    IntendedParentStatusHistory,
    Match,
    Membership,
    Organization,
    PipelineStage,
    IntendedParent,
    Surrogate,
    SurrogateActivityLog,
    SurrogateContactAttempt,
    SurrogateStatusHistory,
    User,
)
from app.db.enums import (
    ContactMethod,
    ContactOutcome,
    IntendedParentStatus,
    MatchStatus,
    Role,
    SurrogateActivityType,
    SurrogateSource,
)
from app.services import dev_service, match_service, pipeline_service, template_seeder

# Sample data pools
FIRST_NAMES_FEMALE = [
    "Emma",
    "Olivia",
    "Ava",
    "Isabella",
    "Sophia",
    "Mia",
    "Charlotte",
    "Amelia",
    "Harper",
    "Evelyn",
    "Abigail",
    "Emily",
    "Elizabeth",
    "Sofia",
    "Madison",
    "Avery",
    "Ella",
    "Scarlett",
    "Grace",
    "Victoria",
    "Riley",
    "Aria",
    "Luna",
    "Chloe",
    "Penelope",
    "Layla",
    "Riley",
    "Zoey",
    "Nora",
    "Lily",
    "Eleanor",
    "Hannah",
    "Lillian",
    "Addison",
    "Aubrey",
    "Ellie",
    "Stella",
    "Natalie",
    "Zoe",
    "Leah",
    "Hazel",
    "Violet",
    "Aurora",
    "Savannah",
    "Audrey",
    "Brooklyn",
    "Bella",
    "Claire",
    "Skylar",
    "Lucy",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
    "Young",
    "Allen",
    "King",
    "Wright",
    "Scott",
    "Torres",
    "Nguyen",
    "Hill",
    "Flores",
    "Green",
    "Adams",
    "Nelson",
    "Baker",
    "Rivera",
    "Campbell",
    "Mitchell",
    "Carter",
]

PARTNER_NAMES_MALE = [
    "James",
    "John",
    "Robert",
    "Michael",
    "William",
    "David",
    "Richard",
    "Joseph",
    "Thomas",
    "Christopher",
    "Daniel",
    "Matthew",
    "Anthony",
    "Mark",
    "Steven",
    "Andrew",
    "Joshua",
    "Kenneth",
    "Kevin",
    "Brian",
    "George",
    "Timothy",
    "Ronald",
]

STATES = [
    "CA",
    "TX",
    "FL",
    "NY",
    "PA",
    "IL",
    "OH",
    "GA",
    "NC",
    "MI",
    "NJ",
    "VA",
    "WA",
    "AZ",
    "MA",
    "TN",
    "IN",
    "MO",
    "MD",
    "WI",
    "CO",
    "MN",
    "SC",
    "AL",
    "LA",
    "KY",
    "OR",
    "OK",
    "CT",
    "UT",
]

RACES = [
    "White",
    "Black or African American",
    "Hispanic or Latino",
    "Asian",
    "Native American",
    "Pacific Islander",
    "Mixed Race",
    "Other",
]

INSURANCE_COMPANIES = [
    "Blue Cross Blue Shield",
    "UnitedHealthcare",
    "Aetna",
    "Cigna",
    "Humana",
    "Kaiser Permanente",
    "Anthem",
    "Molina Healthcare",
    "Centene",
    "Oscar Health",
]

CLINIC_NAMES = [
    "Pacific Fertility Center",
    "Shady Grove Fertility",
    "CCRM Fertility",
    "Boston IVF",
    "RMA of New York",
    "Fertility Institute of San Diego",
    "HRC Fertility",
    "Spring Fertility",
    "Kindbody",
    "Progyny Fertility",
]

HOSPITAL_NAMES = [
    "Good Samaritan Hospital",
    "St. Joseph's Medical Center",
    "Cedar-Sinai Medical Center",
    "Northwestern Memorial Hospital",
    "Massachusetts General Hospital",
    "Cleveland Clinic",
    "Johns Hopkins Hospital",
    "Mayo Clinic",
    "UCLA Medical Center",
    "Stanford Hospital",
    "Mount Sinai Hospital",
    "NewYork-Presbyterian Hospital",
]

IP_STATUSES = [
    IntendedParentStatus.NEW.value,
    IntendedParentStatus.READY_TO_MATCH.value,
    IntendedParentStatus.MATCHED.value,
    IntendedParentStatus.DELIVERED.value,
]

SURROGATE_SOURCES = [
    SurrogateSource.MANUAL.value,
    SurrogateSource.META.value,
    SurrogateSource.WEBSITE.value,
    SurrogateSource.REFERRAL.value,
    SurrogateSource.AGENCY.value,
]
TERMINAL_STAGE_SLUGS = {"lost", "disqualified"}
PREGNANCY_STAGE_SLUGS = {
    "transfer_cycle",
    "second_hcg_confirmed",
    "heartbeat_confirmed",
    "ob_care_established",
    "anatomy_scanned",
    "delivered",
}

STAGE_WEIGHTS_BY_SLUG = {
    "new_unread": 8,
    "contacted": 6,
    "qualified": 6,
    "application_submitted": 5,
    "interview_scheduled": 4,
    "under_review": 4,
    "approved": 4,
    "ready_to_match": 5,
    "matched": 4,
    "medical_clearance_passed": 3,
    "legal_clearance_passed": 3,
    "transfer_cycle": 2,
    "second_hcg_confirmed": 2,
    "heartbeat_confirmed": 2,
    "ob_care_established": 1,
    "anatomy_scanned": 1,
    "delivered": 1,
    "lost": 1,
    "disqualified": 1,
}

SUPPORTED_ACTIVITY_MODES = {"rich_core"}
SUPPORTED_MATCH_MODES = {"balanced"}
IP_STATUS_FLOW = [
    IntendedParentStatus.NEW.value,
    IntendedParentStatus.READY_TO_MATCH.value,
    IntendedParentStatus.MATCHED.value,
    IntendedParentStatus.DELIVERED.value,
]
MATCH_STATUS_FLOW = [
    MatchStatus.PROPOSED.value,
    MatchStatus.REVIEWING.value,
    MatchStatus.ACCEPTED.value,
    MatchStatus.REJECTED.value,
    MatchStatus.CANCELLED.value,
]
MATCH_ACCEPTABLE_SURROGATE_STAGES = {"approved", "ready_to_match"}


def mask_email(email: str) -> str:
    """Mask email to avoid logging raw PII."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def random_phone() -> str:
    """Generate random US phone number in E.164 format."""
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"


def random_email(first: str, last: str, idx: int) -> str:
    """Generate random email."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"]
    return f"{first.lower()}.{last.lower()}{idx}@{random.choice(domains)}"


def random_date_of_birth(min_age: int = 21, max_age: int = 36) -> date:
    """Generate random DOB for given age range."""
    today = date.today()
    days_offset = random.randint(min_age * 365, max_age * 365)
    return today - timedelta(days=days_offset)


def random_address() -> tuple[str, str | None, str, str, str]:
    """Generate random address components (line1, line2, city, state, postal)."""
    streets = ["Main St", "Oak Ave", "Park Blvd", "Elm Drive", "Cedar Lane", "Maple Way"]
    cities = ["Springfield", "Riverside", "Franklin", "Clinton", "Greenville", "Madison"]
    state = random.choice(STATES)
    line2 = None
    if random.random() < 0.35:
        line2 = f"Suite {random.randint(100, 999)}"
    return (
        f"{random.randint(100, 9999)} {random.choice(streets)}",
        line2,
        random.choice(cities),
        state,
        f"{random.randint(10000, 99999)}",
    )


def email_from_name(name: str, prefix: str = "info") -> str:
    """Create a stable email domain from a name."""
    safe = "".join(c for c in name.lower() if c.isalnum())
    if not safe:
        safe = "provider"
    return f"{prefix}@{safe}.com"


def _next_number(values: list[str], prefix: str, fallback: int) -> int:
    """Get next numeric ID for a prefixed identifier."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    numbers = []
    for value in values:
        match = pattern.match(value or "")
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=fallback - 1) + 1


def get_next_surrogate_number(db, org_id: UUID) -> int:
    """Get next surrogate number for the org."""
    values = [
        row[0]
        for row in db.query(Surrogate.surrogate_number)
        .filter(Surrogate.organization_id == org_id)
        .all()
    ]
    return _next_number(values, "S", 10001)


def get_next_intended_parent_number(db, org_id: UUID) -> int:
    """Get next intended parent number for the org."""
    values = [
        row[0]
        for row in db.query(IntendedParent.intended_parent_number)
        .filter(IntendedParent.organization_id == org_id)
        .all()
    ]
    return _next_number(values, "I", 10001)


def _repeat_balanced(items: list[str], count: int) -> list[str]:
    if count <= 0:
        return []
    result = []
    while len(result) < count:
        result.extend(items)
    result = result[:count]
    random.shuffle(result)
    return result


def _weighted_stage_targets(stages: list[PipelineStage], count: int) -> list[PipelineStage]:
    if count <= 0:
        return []

    targets: list[PipelineStage] = []
    if count >= len(stages):
        targets.extend(stages)
        remaining = count - len(stages)
    else:
        targets.extend(random.sample(stages, count))
        remaining = 0

    if remaining > 0:
        weights = [
            STAGE_WEIGHTS_BY_SLUG.get(stage.slug, 2 if stage.stage_type != "terminal" else 1)
            for stage in stages
        ]
        targets.extend(random.choices(stages, weights=weights, k=remaining))

    random.shuffle(targets)
    return targets


def build_stage_path(
    stages_sorted: list[PipelineStage], target: PipelineStage
) -> list[PipelineStage]:
    """Build a realistic stage path ending at target."""
    if target.slug in TERMINAL_STAGE_SLUGS:
        cutoff = random.randint(2, max(2, min(6, len(stages_sorted) - 2)))
        return stages_sorted[:cutoff] + [target]
    try:
        index = next(i for i, stage in enumerate(stages_sorted) if stage.id == target.id)
    except StopIteration:
        return [target]
    return stages_sorted[: index + 1]


def create_status_history(
    db,
    org_id: UUID,
    owner_id: UUID,
    surrogate_id: UUID,
    stage_path: list[PipelineStage],
    created_at: datetime,
) -> dict[str, datetime]:
    """Create status history entries for the stage path."""
    now = datetime.now(timezone.utc)
    cursor = created_at + timedelta(days=random.randint(0, 3))
    contact_times: dict[str, datetime] = {}
    previous = None
    for stage in stage_path:
        effective_at = min(cursor, now)
        recorded_at = min(effective_at + timedelta(minutes=random.randint(5, 240)), now)
        db.add(
            SurrogateStatusHistory(
                surrogate_id=surrogate_id,
                organization_id=org_id,
                from_stage_id=previous.id if previous else None,
                to_stage_id=stage.id,
                from_label_snapshot=previous.label if previous else None,
                to_label_snapshot=stage.label,
                changed_by_user_id=owner_id,
                reason=None,
                effective_at=effective_at,
                recorded_at=recorded_at,
                changed_at=effective_at,
            )
        )
        if stage.slug == "contacted":
            contact_times["contacted_at"] = effective_at
        previous = stage
        cursor = min(effective_at + timedelta(days=random.randint(3, 18)), now)
    contact_times["last_stage_at"] = cursor
    return contact_times


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]*>", "", value).strip()


def _pick_owner(users_by_role: dict[str, User], fallback_user: User | None) -> User:
    weighted_roles = [
        (Role.INTAKE_SPECIALIST.value, 45),
        (Role.CASE_MANAGER.value, 30),
        (Role.ADMIN.value, 15),
        (Role.DEVELOPER.value, 10),
    ]
    users = []
    weights = []
    for role_value, weight in weighted_roles:
        user = users_by_role.get(role_value)
        if user:
            users.append(user)
            weights.append(weight)
    if users:
        return random.choices(users, weights=weights, k=1)[0]

    if users_by_role:
        return random.choice(list(users_by_role.values()))

    if fallback_user:
        return fallback_user

    raise ValueError("No owner user available for seeding")


def _log_surrogate_activity(
    db,
    *,
    surrogate: Surrogate,
    actor_user: User,
    created_at: datetime,
    assigned_at: datetime | None,
    contacted_at: datetime | None,
    is_reached: bool,
    activity_mode: str,
) -> None:
    if activity_mode not in SUPPORTED_ACTIVITY_MODES:
        raise ValueError(
            f"Unsupported SEED_ACTIVITY_MODE={activity_mode}. "
            f"Supported: {sorted(SUPPORTED_ACTIVITY_MODES)}"
        )

    now = datetime.now(timezone.utc)
    created_event_time = min(created_at + timedelta(minutes=5), now)

    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=surrogate.organization_id,
            activity_type=SurrogateActivityType.SURROGATE_CREATED.value,
            actor_user_id=actor_user.id,
            details={"source": surrogate.source},
            created_at=created_event_time,
        )
    )

    if assigned_at:
        db.add(
            SurrogateActivityLog(
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                activity_type=SurrogateActivityType.ASSIGNED.value,
                actor_user_id=actor_user.id,
                details={"to_user_id": str(surrogate.owner_id)},
                created_at=min(max(assigned_at, created_event_time), now),
            )
        )

    note_time = min(created_event_time + timedelta(days=random.randint(1, 7)), now)
    note = EntityNote(
        organization_id=surrogate.organization_id,
        entity_type="surrogate",
        entity_id=surrogate.id,
        author_id=actor_user.id,
        content=f"<p>Seed note for {surrogate.surrogate_number}: profile reviewed.</p>",
        created_at=note_time,
    )
    db.add(note)
    db.flush()
    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=surrogate.organization_id,
            activity_type=SurrogateActivityType.NOTE_ADDED.value,
            actor_user_id=actor_user.id,
            details={
                "note_id": str(note.id),
                "preview": _strip_html(note.content)[:120],
            },
            created_at=note_time,
        )
    )

    info_edit_time = min(note_time + timedelta(hours=random.randint(2, 24)), now)
    db.add(
        SurrogateActivityLog(
            surrogate_id=surrogate.id,
            organization_id=surrogate.organization_id,
            activity_type=SurrogateActivityType.INFO_EDITED.value,
            actor_user_id=actor_user.id,
            details={"changes": {"state": "[redacted]", "phone": "[redacted]"}},
            created_at=info_edit_time,
        )
    )

    if surrogate.is_priority:
        db.add(
            SurrogateActivityLog(
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                activity_type=SurrogateActivityType.PRIORITY_CHANGED.value,
                actor_user_id=actor_user.id,
                details={"is_priority": True},
                created_at=min(info_edit_time + timedelta(minutes=15), now),
            )
        )

    if is_reached:
        attempted_at = contacted_at or assigned_at or created_event_time
        attempted_at = min(attempted_at, now)

        db.add(
            SurrogateContactAttempt(
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                attempted_by_user_id=actor_user.id,
                contact_methods=[ContactMethod.PHONE.value],
                outcome=ContactOutcome.REACHED.value,
                notes="Reached during seeded follow-up",
                attempted_at=attempted_at,
                surrogate_owner_id_at_attempt=surrogate.owner_id,
            )
        )
        db.add(
            SurrogateActivityLog(
                surrogate_id=surrogate.id,
                organization_id=surrogate.organization_id,
                activity_type=SurrogateActivityType.CONTACT_ATTEMPT.value,
                actor_user_id=actor_user.id,
                details={
                    "contact_methods": [ContactMethod.PHONE.value],
                    "outcome": ContactOutcome.REACHED.value,
                    "note_preview": "Reached during seeded follow-up",
                    "attempted_at": attempted_at.isoformat(),
                },
                created_at=attempted_at,
            )
        )


def create_surrogates(
    db,
    org_id: UUID,
    owner_id: UUID,
    stages_sorted: list[PipelineStage],
    count: int = 40,
    users_by_role: dict[str, User] | None = None,
    activity_mode: str = "rich_core",
) -> list[Surrogate]:
    """Create mock surrogates with status history and rich activity logs."""
    print(f"Creating {count} surrogates...")

    if count <= 0:
        return []

    users_by_role = users_by_role or {}
    fallback_user = db.query(User).filter(User.id == owner_id).first()

    next_number = get_next_surrogate_number(db, org_id)
    stage_by_slug = {stage.slug: stage for stage in stages_sorted}
    contacted_stage = stage_by_slug.get("contacted")
    targets = _weighted_stage_targets(stages_sorted, count)
    created_surrogates: list[Surrogate] = []

    for i, stage in enumerate(targets):
        first = random.choice(FIRST_NAMES_FEMALE)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        email = random_email(first, last, i + 1)
        phone = random_phone()
        dob = random_date_of_birth(21, 36)
        state = random.choice(STATES)
        owner_user = _pick_owner(users_by_role, fallback_user)

        # Address components for clinics/hospitals
        clinic_addr = random_address()
        monitoring_addr = random_address()
        ob_addr = random_address()
        hospital_addr = random_address()
        created_min = 10 + stage.order * 5
        created_max = created_min + 120
        created_at = datetime.now(timezone.utc) - timedelta(
            days=random.randint(created_min, created_max)
        )
        assigned_at = created_at + timedelta(days=random.randint(0, 14))

        pregnancy_start = date.today() - timedelta(days=random.randint(30, 220))
        pregnancy_due = pregnancy_start + timedelta(days=280)
        stage_path = build_stage_path(stages_sorted, stage)

        surrogate_id = uuid4()
        contact_times = create_status_history(
            db=db,
            org_id=org_id,
            owner_id=owner_user.id,
            surrogate_id=surrogate_id,
            stage_path=stage_path,
            created_at=created_at,
        )

        is_reached = bool(contacted_stage and stage.order >= contacted_stage.order)

        last_contacted_at = contact_times.get("last_stage_at") if is_reached else None
        contacted_at = contact_times.get("contacted_at")

        # Campaign metadata (30% of records)
        meta_ad = None
        meta_form = None
        meta_campaign = None
        meta_adset = None
        if random.random() < 0.3:
            meta_ad = f"ad_{random.randint(1000, 9999)}"
            meta_form = f"form_{random.randint(1000, 9999)}"
            meta_campaign = f"camp_{random.randint(1000, 9999)}"
            meta_adset = f"adset_{random.randint(1000, 9999)}"

        # Pregnancy fields for later stages
        pregnancy_start_date = pregnancy_start if stage.slug in PREGNANCY_STAGE_SLUGS else None
        pregnancy_due_date = pregnancy_due if stage.slug in PREGNANCY_STAGE_SLUGS else None
        actual_delivery_date = None
        if stage.slug == "delivered":
            delivered_start = date.today() - timedelta(days=random.randint(250, 330))
            pregnancy_start_date = delivered_start
            pregnancy_due_date = delivered_start + timedelta(days=280)
            actual_delivery_date = min(
                date.today(),
                pregnancy_due_date + timedelta(days=random.randint(-10, 10)),
            )

        surrogate = Surrogate(
            id=surrogate_id,
            surrogate_number=f"S{next_number + i}",
            organization_id=org_id,
            stage_id=stage.id,
            status_label=stage.label,
            source=random.choice(SURROGATE_SOURCES),
            is_priority=random.random() < 0.2,  # 20% priority
            owner_type="user",
            owner_id=owner_user.id,
            created_by_user_id=owner_user.id,
            meta_ad_external_id=meta_ad,
            meta_form_id=meta_form,
            meta_campaign_external_id=meta_campaign,
            meta_adset_external_id=meta_adset,
            # Contact info
            full_name=full_name,
            email=email,
            email_hash=hash_email(email),
            phone=phone,
            phone_hash=hash_phone(phone),
            state=state,
            # Demographics
            date_of_birth=dob,
            race=random.choice(RACES),
            height_ft=Decimal(str(round(random.uniform(5.0, 6.0), 1))),
            weight_lb=random.randint(110, 180),
            # Eligibility
            is_age_eligible=True,
            is_citizen_or_pr=random.random() > 0.1,  # 90% citizen/PR
            has_child=True,
            is_non_smoker=random.random() > 0.05,  # 95% non-smoker
            has_surrogate_experience=random.random() < 0.3,  # 30% experienced
            num_deliveries=random.randint(1, 4),
            num_csections=random.randint(0, 2),
            # Insurance
            insurance_company=random.choice(INSURANCE_COMPANIES),
            insurance_plan_name=f"{random.choice(['PPO', 'HMO', 'EPO'])} {random.choice(['Gold', 'Silver', 'Platinum'])}",
            insurance_phone=random_phone(),
            insurance_policy_number=f"POL{random.randint(100000, 999999)}",
            insurance_member_id=f"MBR{random.randint(10000000, 99999999)}",
            insurance_group_number=f"GRP{random.randint(1000, 9999)}",
            insurance_subscriber_name=full_name,
            insurance_subscriber_dob=dob,
            # IVF Clinic
            clinic_name=random.choice(CLINIC_NAMES),
            clinic_address_line1=clinic_addr[0],
            clinic_address_line2=clinic_addr[1],
            clinic_city=clinic_addr[2],
            clinic_state=clinic_addr[3],
            clinic_postal=clinic_addr[4],
            clinic_phone=random_phone(),
            clinic_email=email_from_name(random.choice(CLINIC_NAMES)),
            # Monitoring Clinic
            monitoring_clinic_name=f"{random.choice(['Womens', 'Family', 'Advanced', 'Premier'])} Fertility Center",
            monitoring_clinic_address_line1=monitoring_addr[0],
            monitoring_clinic_address_line2=monitoring_addr[1],
            monitoring_clinic_city=monitoring_addr[2],
            monitoring_clinic_state=monitoring_addr[3],
            monitoring_clinic_postal=monitoring_addr[4],
            monitoring_clinic_phone=random_phone(),
            monitoring_clinic_email=email_from_name("Monitoring Clinic"),
            # OB Provider
            ob_provider_name=f"Dr. {random.choice(FIRST_NAMES_FEMALE)} {random.choice(LAST_NAMES)}",
            ob_clinic_name=f"{random.choice(LAST_NAMES)} Women's Health",
            ob_address_line1=ob_addr[0],
            ob_address_line2=ob_addr[1],
            ob_city=ob_addr[2],
            ob_state=ob_addr[3],
            ob_postal=ob_addr[4],
            ob_phone=random_phone(),
            ob_email=email_from_name("ob"),
            # Delivery Hospital
            delivery_hospital_name=random.choice(HOSPITAL_NAMES),
            delivery_hospital_address_line1=hospital_addr[0],
            delivery_hospital_address_line2=hospital_addr[1],
            delivery_hospital_city=hospital_addr[2],
            delivery_hospital_state=hospital_addr[3],
            delivery_hospital_postal=hospital_addr[4],
            delivery_hospital_phone=random_phone(),
            delivery_hospital_email=email_from_name(random.choice(HOSPITAL_NAMES), prefix="labor"),
            # Pregnancy tracking
            pregnancy_start_date=pregnancy_start_date,
            pregnancy_due_date=pregnancy_due_date,
            actual_delivery_date=actual_delivery_date,
            # Contact tracking
            contact_status="reached" if is_reached else "unreached",
            assigned_at=assigned_at,
            contacted_at=contacted_at,
            last_contacted_at=last_contacted_at,
            last_contact_method=random.choice(["email", "phone", "note"]) if is_reached else None,
            # Timestamps
            created_at=created_at,
            updated_at=max(created_at, contact_times.get("last_stage_at", created_at)),
        )

        db.add(surrogate)
        db.flush()
        _log_surrogate_activity(
            db,
            surrogate=surrogate,
            actor_user=owner_user,
            created_at=created_at,
            assigned_at=assigned_at,
            contacted_at=contacted_at,
            is_reached=is_reached,
            activity_mode=activity_mode,
        )
        created_surrogates.append(surrogate)

    db.commit()
    print(f"Created {count} surrogates")
    return created_surrogates


def _build_ip_targets(count: int) -> list[str]:
    if count <= 0:
        return []
    if count >= len(IP_STATUS_FLOW):
        targets = IP_STATUS_FLOW.copy()
        remaining = count - len(IP_STATUS_FLOW)
        targets.extend(random.choices(IP_STATUS_FLOW, weights=[4, 3, 2, 1], k=remaining))
        random.shuffle(targets)
        return targets
    return random.sample(IP_STATUS_FLOW, count)


def _build_ip_status_path(target_status: str) -> list[str]:
    idx = IP_STATUS_FLOW.index(target_status)
    return IP_STATUS_FLOW[: idx + 1]


def _create_ip_status_history(
    db,
    *,
    intended_parent: IntendedParent,
    actor_user_id: UUID,
    created_at: datetime,
    target_status: str,
) -> None:
    now = datetime.now(timezone.utc)
    path = _build_ip_status_path(target_status)
    previous = None
    cursor = created_at + timedelta(days=random.randint(0, 2))

    for status in path:
        effective_at = min(cursor, now)
        recorded_at = min(effective_at + timedelta(minutes=random.randint(5, 120)), now)
        db.add(
            IntendedParentStatusHistory(
                intended_parent_id=intended_parent.id,
                changed_by_user_id=actor_user_id,
                old_status=previous,
                new_status=status,
                reason="Seeded status progression",
                changed_at=effective_at,
                effective_at=effective_at,
                recorded_at=recorded_at,
            )
        )
        previous = status
        cursor = min(effective_at + timedelta(days=random.randint(7, 45)), now)


def create_intended_parents(
    db,
    org_id: UUID,
    owner_id: UUID,
    count: int = 40,
    users_by_role: dict[str, User] | None = None,
) -> list[IntendedParent]:
    """Create mock intended parents with complete data and status history."""
    print(f"Creating {count} intended parents...")

    if count <= 0:
        return []

    users_by_role = users_by_role or {}
    fallback_user = db.query(User).filter(User.id == owner_id).first()
    targets = _build_ip_targets(count)
    next_number = get_next_intended_parent_number(db, org_id)
    created_ips: list[IntendedParent] = []
    for i, target_status in enumerate(targets):
        # Create couples - both partners' names
        first1 = random.choice(FIRST_NAMES_FEMALE + PARTNER_NAMES_MALE)
        first2 = random.choice(FIRST_NAMES_FEMALE + PARTNER_NAMES_MALE)
        last = random.choice(LAST_NAMES)
        full_name = f"{first1} & {first2} {last}"

        email = random_email(first1, last, i + 100)
        phone = random_phone()
        state = random.choice(STATES)
        owner_user = _pick_owner(users_by_role, fallback_user)
        created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(5, 540))

        intended_parent = IntendedParent(
            id=uuid4(),
            organization_id=org_id,
            intended_parent_number=f"I{next_number + i}",
            # Contact info
            full_name=full_name,
            email=email,
            email_hash=hash_email(email),
            phone=phone,
            phone_hash=hash_phone(phone),
            state=state,
            # Budget (varies from $80K to $200K)
            budget=Decimal(str(random.randint(80000, 200000))),
            # Internal notes
            notes_internal=f"Initial inquiry via {random.choice(['website', 'referral', 'phone'])}. "
            + f"Looking to start journey {random.choice(['immediately', 'within 3 months', 'within 6 months'])}. "
            + f"Preference for {random.choice(['experienced', 'first-time', 'no preference'])} surrogate.",
            # Status & workflow
            status=target_status,
            owner_type="user",
            owner_id=owner_user.id,
            # Activity tracking
            last_activity=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30)),
            # Timestamps
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
        )

        db.add(intended_parent)
        db.flush()
        _create_ip_status_history(
            db,
            intended_parent=intended_parent,
            actor_user_id=owner_user.id,
            created_at=created_at,
            target_status=target_status,
        )
        created_ips.append(intended_parent)

    db.commit()
    print(f"Created {count} intended parents")
    return created_ips


def _pick_actor(
    users_by_role: dict[str, User],
    preferred_roles: list[str],
    fallback: User | None = None,
) -> User:
    for role in preferred_roles:
        user = users_by_role.get(role)
        if user:
            return user
    if users_by_role:
        return next(iter(users_by_role.values()))
    if fallback:
        return fallback
    raise ValueError("No actor user available")


def _build_match_targets(count: int, mode: str) -> list[str]:
    if mode not in SUPPORTED_MATCH_MODES:
        raise ValueError(
            f"Unsupported SEED_MATCH_MODE={mode}. Supported: {sorted(SUPPORTED_MATCH_MODES)}"
        )
    return _repeat_balanced(MATCH_STATUS_FLOW, count)


def create_matches(
    db,
    *,
    org_id: UUID,
    users_by_role: dict[str, User],
    count: int = 20,
    mode: str = "balanced",
) -> list[Match]:
    """Create matches across balanced statuses for testing."""
    print(f"Creating {count} matches with mode={mode}...")

    if count <= 0:
        return []

    surrogate_rows = (
        db.query(Surrogate, PipelineStage.slug)
        .join(PipelineStage, Surrogate.stage_id == PipelineStage.id)
        .filter(
            Surrogate.organization_id == org_id,
            Surrogate.is_archived.is_(False),
        )
        .all()
    )
    ips = (
        db.query(IntendedParent)
        .filter(
            IntendedParent.organization_id == org_id,
            IntendedParent.is_archived.is_(False),
        )
        .all()
    )
    if not surrogate_rows or not ips:
        print("Skipping matches (requires seeded surrogates and intended parents).")
        return []

    general_surrogates = [s for s, slug in surrogate_rows if slug not in TERMINAL_STAGE_SLUGS]
    accepted_surrogates = [
        s for s, slug in surrogate_rows if slug in MATCH_ACCEPTABLE_SURROGATE_STAGES
    ]
    if not accepted_surrogates:
        accepted_surrogates = general_surrogates

    proposer = _pick_actor(
        users_by_role,
        [Role.CASE_MANAGER.value, Role.ADMIN.value, Role.DEVELOPER.value],
    )
    reviewer = _pick_actor(
        users_by_role,
        [Role.ADMIN.value, Role.DEVELOPER.value, Role.CASE_MANAGER.value],
        fallback=proposer,
    )
    decider = _pick_actor(
        users_by_role,
        [Role.DEVELOPER.value, Role.ADMIN.value, Role.CASE_MANAGER.value],
        fallback=proposer,
    )
    if reviewer.id == proposer.id:
        for user in users_by_role.values():
            if user.id != proposer.id:
                reviewer = user
                break

    targets = _build_match_targets(count, mode=mode)
    used_pairs: set[tuple[UUID, UUID]] = set()
    used_accepted_surrogates: set[UUID] = set()
    created_matches: list[Match] = []

    for target_status in targets:
        created = False
        for _ in range(120):
            pool = accepted_surrogates if target_status == MatchStatus.ACCEPTED.value else general_surrogates
            if target_status == MatchStatus.ACCEPTED.value:
                pool = [s for s in pool if s.id not in used_accepted_surrogates]
            if not pool:
                break

            surrogate = random.choice(pool)
            intended_parent = random.choice(ips)
            pair = (surrogate.id, intended_parent.id)
            if pair in used_pairs:
                continue
            used_pairs.add(pair)

            existing = match_service.get_existing_match(
                db,
                org_id=org_id,
                surrogate_id=surrogate.id,
                intended_parent_id=intended_parent.id,
            )
            if existing:
                continue

            match = match_service.create_match(
                db=db,
                org_id=org_id,
                surrogate_id=surrogate.id,
                intended_parent_id=intended_parent.id,
                proposed_by_user_id=proposer.id,
                compatibility_score=round(random.uniform(60, 99), 2),
                notes=f"Seed {target_status} scenario",
            )

            if target_status == MatchStatus.PROPOSED.value:
                created_matches.append(match)
                created = True
                break

            if target_status == MatchStatus.REVIEWING.value:
                match = match_service.mark_match_reviewing_if_needed(
                    db=db,
                    match=match,
                    actor_user_id=reviewer.id,
                    org_id=org_id,
                )
                created_matches.append(match)
                created = True
                break

            if target_status == MatchStatus.ACCEPTED.value:
                try:
                    match = match_service.accept_match(
                        db=db,
                        match=match,
                        actor_user_id=decider.id,
                        actor_role=Role.DEVELOPER.value,
                        org_id=org_id,
                        notes="Seed accepted match",
                    )
                except ValueError:
                    try:
                        match_service.cancel_match(
                            db=db,
                            match=match,
                            actor_user_id=decider.id,
                            org_id=org_id,
                        )
                    except Exception:
                        pass
                    continue
                used_accepted_surrogates.add(surrogate.id)
                created_matches.append(match)
                created = True
                break

            if target_status == MatchStatus.REJECTED.value:
                if reviewer.id != proposer.id and random.random() < 0.6:
                    match = match_service.mark_match_reviewing_if_needed(
                        db=db,
                        match=match,
                        actor_user_id=reviewer.id,
                        org_id=org_id,
                    )
                match = match_service.reject_match(
                    db=db,
                    match=match,
                    actor_user_id=decider.id,
                    org_id=org_id,
                    rejection_reason="Seed rejection for test coverage",
                    notes="Seed rejected scenario",
                )
                created_matches.append(match)
                created = True
                break

            if target_status == MatchStatus.CANCELLED.value:
                if reviewer.id != proposer.id and random.random() < 0.6:
                    match = match_service.mark_match_reviewing_if_needed(
                        db=db,
                        match=match,
                        actor_user_id=reviewer.id,
                        org_id=org_id,
                    )
                match_service.cancel_match(
                    db=db,
                    match=match,
                    actor_user_id=decider.id,
                    org_id=org_id,
                )
                db.refresh(match)
                created_matches.append(match)
                created = True
                break

        if not created:
            print(f"  - skipped one {target_status} match (candidate constraints)")

    print(f"Created {len(created_matches)} matches")
    return created_matches


def _load_users_by_role(db, org_id: UUID) -> dict[str, User]:
    rows = (
        db.query(Membership.role, User)
        .join(User, Membership.user_id == User.id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
        )
        .all()
    )
    users_by_role: dict[str, User] = {}
    for role_value, user in rows:
        users_by_role.setdefault(role_value, user)
    return users_by_role


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw}") from exc


def _build_summary(db, org_id: UUID, users_by_role: dict[str, User]) -> dict:
    stage_rows = (
        db.query(PipelineStage.slug, func.count(Surrogate.id))
        .join(Surrogate, Surrogate.stage_id == PipelineStage.id)
        .filter(Surrogate.organization_id == org_id)
        .group_by(PipelineStage.slug)
        .all()
    )
    ip_rows = (
        db.query(IntendedParent.status, func.count(IntendedParent.id))
        .filter(IntendedParent.organization_id == org_id)
        .group_by(IntendedParent.status)
        .all()
    )
    match_rows = (
        db.query(Match.status, func.count(Match.id))
        .filter(Match.organization_id == org_id)
        .group_by(Match.status)
        .all()
    )
    login_ids = {
        user.email: str(user.id)
        for user in sorted(users_by_role.values(), key=lambda item: item.email.lower())
    }
    return {
        "org_id": str(org_id),
        "surrogates_total": int(
            db.query(func.count(Surrogate.id)).filter(Surrogate.organization_id == org_id).scalar() or 0
        ),
        "surrogate_status_history_total": int(
            db.query(func.count(SurrogateStatusHistory.id))
            .filter(SurrogateStatusHistory.organization_id == org_id)
            .scalar()
            or 0
        ),
        "surrogate_activity_total": int(
            db.query(func.count(SurrogateActivityLog.id))
            .filter(SurrogateActivityLog.organization_id == org_id)
            .scalar()
            or 0
        ),
        "intended_parents_total": int(
            db.query(func.count(IntendedParent.id))
            .filter(IntendedParent.organization_id == org_id)
            .scalar()
            or 0
        ),
        "matches_total": int(
            db.query(func.count(Match.id)).filter(Match.organization_id == org_id).scalar() or 0
        ),
        "surrogate_stage_counts": {slug: int(count) for slug, count in stage_rows},
        "intended_parent_status_counts": {status: int(count) for status, count in ip_rows},
        "match_status_counts": {status: int(count) for status, count in match_rows},
        "login_as_user_ids": login_ids,
    }


def _ensure_context(db, org_slug: str | None) -> tuple[Organization, dict[str, User]]:
    if org_slug:
        org = db.query(Organization).filter(Organization.slug == org_slug).first()
        if not org:
            raise ValueError(f"Organization not found for slug: {org_slug}")
    else:
        seed_info = dev_service.seed_test_data(db)
        org = db.query(Organization).filter(Organization.id == UUID(seed_info["org_id"])).first()
        if not org:
            raise ValueError("Failed to resolve seeded test organization")

    users_by_role = _load_users_by_role(db, org.id)
    if not users_by_role:
        raise ValueError("No active users found for organization")
    return org, users_by_role


def main():
    """Main entry point."""
    print("Seeding mock data...")

    db = SessionLocal()

    try:
        seed_random = _env_int("SEED_RANDOM_SEED", 20260224)
        random.seed(seed_random)

        org_slug = os.getenv("SEED_ORG_SLUG")
        org, users_by_role = _ensure_context(db, org_slug)
        print(f"Using organization: {org.name} ({org.id})")
        print(f"Seed random: {seed_random}")

        actor = _pick_actor(
            users_by_role,
            [Role.DEVELOPER.value, Role.ADMIN.value, Role.CASE_MANAGER.value],
        )
        print(f"Using actor: {mask_email(actor.email)} ({actor.id})")

        pipeline = pipeline_service.get_or_create_default_pipeline(db, org.id, actor.id)
        print(f"Using pipeline: {pipeline.name}")

        stages_sorted = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == pipeline.id)
            .order_by(PipelineStage.order.asc())
            .all()
        )

        if not stages_sorted:
            print("ERROR: No pipeline stages found.")
            return

        print(f"Using pipeline stages: {len(stages_sorted)}")

        template_result = template_seeder.seed_all(db, org.id, actor.id)
        print(
            f"Seeded templates: {template_result['templates_created']}, workflows: {template_result['workflows_created']}"
        )

        org.signature_company_name = org.name
        org.signature_address = "123 Market St, Austin, TX"
        org.signature_phone = "+1 (512) 555-0199"
        org.signature_website = "https://surrogacycrm.test"
        org.signature_primary_color = "#0ea5e9"
        org.signature_disclaimer = (
            "This message contains confidential information intended only for the recipient."
        )
        org.signature_social_links = [
            {"platform": "linkedin", "url": "https://linkedin.com/company/surrogacy-crm"},
            {"platform": "instagram", "url": "https://instagram.com/surrogacy-crm"},
        ]
        actor.signature_name = actor.display_name
        actor.signature_title = "Case Manager"
        actor.signature_phone = "+1 (512) 555-0142"
        actor.signature_linkedin = "https://linkedin.com/in/case-manager"
        actor.signature_twitter = "https://twitter.com/surrogacycrm"

        db.commit()

        surrogate_count = _env_int("SEED_SURROGATES", 500)
        intended_parent_count = _env_int("SEED_INTENDED_PARENTS", 10)
        default_match_count = max(10, min(40, max(1, intended_parent_count) * 3))
        match_count = _env_int("SEED_MATCH_COUNT", default_match_count)
        match_mode = os.getenv("SEED_MATCH_MODE", "balanced")
        activity_mode = os.getenv("SEED_ACTIVITY_MODE", "rich_core")

        print(
            "Config:",
            json.dumps(
                {
                    "SEED_SURROGATES": surrogate_count,
                    "SEED_INTENDED_PARENTS": intended_parent_count,
                    "SEED_MATCH_MODE": match_mode,
                    "SEED_MATCH_COUNT": match_count,
                    "SEED_ACTIVITY_MODE": activity_mode,
                },
                sort_keys=True,
            ),
        )

        create_surrogates(
            db,
            org.id,
            actor.id,
            stages_sorted,
            count=surrogate_count,
            users_by_role=users_by_role,
            activity_mode=activity_mode,
        )
        if intended_parent_count > 0:
            create_intended_parents(
                db,
                org.id,
                actor.id,
                count=intended_parent_count,
                users_by_role=users_by_role,
            )
        if match_count > 0 and intended_parent_count > 0:
            create_matches(
                db=db,
                org_id=org.id,
                users_by_role=users_by_role,
                count=match_count,
                mode=match_mode,
            )

        summary = _build_summary(db, org.id, users_by_role)
        print("\nMock data seeded successfully!")
        print("SEED_SUMMARY " + json.dumps(summary, sort_keys=True))

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
