"""
Seed script to create 40 mock surrogates and 40 mock intended parents with complete data.
Run with: python -m scripts.seed_mock_data
"""

import os
import random
import hashlib
import re
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models import (
    Organization,
    User,
    Surrogate,
    IntendedParent,
    PipelineStage,
    SurrogateStatusHistory,
)
from app.services import pipeline_service
from app.services import template_seeder

# Sample data pools
FIRST_NAMES_FEMALE = [
    "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia", "Charlotte", "Amelia",
    "Harper", "Evelyn", "Abigail", "Emily", "Elizabeth", "Sofia", "Madison",
    "Avery", "Ella", "Scarlett", "Grace", "Victoria", "Riley", "Aria", "Luna",
    "Chloe", "Penelope", "Layla", "Riley", "Zoey", "Nora", "Lily", "Eleanor",
    "Hannah", "Lillian", "Addison", "Aubrey", "Ellie", "Stella", "Natalie",
    "Zoe", "Leah", "Hazel", "Violet", "Aurora", "Savannah", "Audrey", "Brooklyn",
    "Bella", "Claire", "Skylar", "Lucy"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Rivera", "Campbell", "Mitchell", "Carter"
]

PARTNER_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Steven",
    "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald"
]

STATES = [
    "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT"
]

RACES = [
    "White", "Black or African American", "Hispanic or Latino", "Asian",
    "Native American", "Pacific Islander", "Mixed Race", "Other"
]

INSURANCE_COMPANIES = [
    "Blue Cross Blue Shield", "UnitedHealthcare", "Aetna", "Cigna", "Humana",
    "Kaiser Permanente", "Anthem", "Molina Healthcare", "Centene", "Oscar Health"
]

CLINIC_NAMES = [
    "Pacific Fertility Center", "Shady Grove Fertility", "CCRM Fertility",
    "Boston IVF", "RMA of New York", "Fertility Institute of San Diego",
    "HRC Fertility", "Spring Fertility", "Kindbody", "Progyny Fertility"
]

HOSPITAL_NAMES = [
    "Good Samaritan Hospital", "St. Joseph's Medical Center", "Cedar-Sinai Medical Center",
    "Northwestern Memorial Hospital", "Massachusetts General Hospital",
    "Cleveland Clinic", "Johns Hopkins Hospital", "Mayo Clinic", "UCLA Medical Center",
    "Stanford Hospital", "Mount Sinai Hospital", "NewYork-Presbyterian Hospital"
]

IP_STATUSES = ["inquiry", "in_progress", "approved", "matched", "closed"]

SURROGATE_SOURCES = ["website", "referral", "social_media", "agency", "other"]
TERMINAL_STAGE_SLUGS = {"lost", "disqualified"}
PREGNANCY_STAGE_SLUGS = {
    "transfer_cycle",
    "second_hcg_confirmed",
    "heartbeat_confirmed",
    "ob_care_established",
    "anatomy_scanned",
    "delivered",
}


def mask_email(email: str) -> str:
    """Mask email to avoid logging raw PII."""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def hash_pii(value: str) -> str:
    """Create a hash for PII fields."""
    return hashlib.sha256(value.encode()).hexdigest()[:64]


def random_phone() -> str:
    """Generate random US phone number in E.164 format."""
    return f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"


def random_email(first: str, last: str, idx: int) -> str:
    """Generate random email."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"]
    return f"{first.lower()}.{last.lower()}{idx}@{random.choice(domains)}"


def random_date_of_birth(min_age: int = 21, max_age: int = 42) -> date:
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
        f"{random.randint(10000, 99999)}"
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


def get_next_surrogate_number(db, org_id: uuid4) -> int:
    """Get next surrogate number for the org."""
    values = [
        row[0]
        for row in db.query(Surrogate.surrogate_number)
        .filter(Surrogate.organization_id == org_id)
        .all()
    ]
    return _next_number(values, "S", 10001)


def get_next_intended_parent_number(db, org_id: uuid4) -> int:
    """Get next intended parent number for the org."""
    values = [
        row[0]
        for row in db.query(IntendedParent.intended_parent_number)
        .filter(IntendedParent.organization_id == org_id)
        .all()
    ]
    return _next_number(values, "I", 10001)


def pick_stage(stages: list[PipelineStage]) -> PipelineStage:
    """Pick a stage using weighted distribution."""
    weights_by_slug = {
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
    weights = [
        weights_by_slug.get(stage.slug, 2 if stage.stage_type != "terminal" else 1)
        for stage in stages
    ]
    return random.choices(stages, weights=weights, k=1)[0]


def build_stage_path(stages_sorted: list[PipelineStage], target: PipelineStage) -> list[PipelineStage]:
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
    org_id: uuid4,
    owner_id: uuid4,
    surrogate_id: uuid4,
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


def create_surrogates(
    db,
    org_id: uuid4,
    owner_id: uuid4,
    stages_sorted: list[PipelineStage],
    count: int = 40,
):
    """Create mock surrogates with complete data."""
    print(f"Creating {count} surrogates...")

    next_number = get_next_surrogate_number(db, org_id)
    stage_by_slug = {stage.slug: stage for stage in stages_sorted}
    contacted_stage = stage_by_slug.get("contacted")

    for i in range(count):
        first = random.choice(FIRST_NAMES_FEMALE)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        email = random_email(first, last, i + 1)
        phone = random_phone()
        dob = random_date_of_birth(21, 40)
        state = random.choice(STATES)
        
        # Address components for clinics/hospitals
        clinic_addr = random_address()
        monitoring_addr = random_address()
        ob_addr = random_address()
        hospital_addr = random_address()
        stage = pick_stage(stages_sorted)
        created_min = 10 + stage.order * 5
        created_max = created_min + 120
        created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(created_min, created_max))
        assigned_at = created_at + timedelta(days=random.randint(0, 14))

        pregnancy_start = date.today() - timedelta(days=random.randint(30, 220))
        pregnancy_due = pregnancy_start + timedelta(days=280)
        stage_path = build_stage_path(stages_sorted, stage)

        surrogate_id = uuid4()
        contact_times = create_status_history(
            db=db,
            org_id=org_id,
            owner_id=owner_id,
            surrogate_id=surrogate_id,
            stage_path=stage_path,
            created_at=created_at,
        )

        is_reached = False
        if contacted_stage:
            is_reached = stage.order >= contacted_stage.order

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
            owner_id=owner_id,
            created_by_user_id=owner_id,
            meta_ad_external_id=meta_ad,
            meta_form_id=meta_form,
            meta_campaign_external_id=meta_campaign,
            meta_adset_external_id=meta_adset,
            
            # Contact info
            full_name=full_name,
            email=email,
            email_hash=hash_pii(email.lower()),
            phone=phone,
            phone_hash=hash_pii(phone),
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
            monitoring_clinic_name=f"{random.choice(['Women\'s', 'Family', 'Advanced', 'Premier'])} Fertility Center",
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
    
    db.commit()
    print(f"Created {count} surrogates")


def create_intended_parents(db, org_id: uuid4, owner_id: uuid4, count: int = 40):
    """Create mock intended parents with complete data."""
    print(f"Creating {count} intended parents...")

    next_number = get_next_intended_parent_number(db, org_id)
    for i in range(count):
        # Create couples - both partners' names
        first1 = random.choice(FIRST_NAMES_FEMALE + PARTNER_NAMES_MALE)
        first2 = random.choice(FIRST_NAMES_FEMALE + PARTNER_NAMES_MALE)
        last = random.choice(LAST_NAMES)
        full_name = f"{first1} & {first2} {last}"
        
        email = random_email(first1, last, i + 100)
        phone = random_phone()
        state = random.choice(STATES)
        
        intended_parent = IntendedParent(
            id=uuid4(),
            organization_id=org_id,
            intended_parent_number=f"I{next_number + i}",
            
            # Contact info
            full_name=full_name,
            email=email,
            email_hash=hash_pii(email.lower()),
            phone=phone,
            phone_hash=hash_pii(phone),
            state=state,
            
            # Budget (varies from $80K to $200K)
            budget=Decimal(str(random.randint(80000, 200000))),
            
            # Internal notes
            notes_internal=f"Initial inquiry via {random.choice(['website', 'referral', 'phone'])}. " +
                          f"Looking to start journey {random.choice(['immediately', 'within 3 months', 'within 6 months'])}. " +
                          f"Preference for {random.choice(['experienced', 'first-time', 'no preference'])} surrogate.",
            
            # Status & workflow
            status=random.choice(IP_STATUSES),
            owner_type="user",
            owner_id=owner_id,
            
            # Activity tracking
            last_activity=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30)),
            
            # Timestamps
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(5, 540)),
            updated_at=datetime.now(timezone.utc),
        )
        
        db.add(intended_parent)
    
    db.commit()
    print(f"Created {count} intended parents")


def main():
    """Main entry point."""
    print("Seeding mock data...")
    
    db = SessionLocal()
    
    try:
        # Get organization (prefer explicit slug if provided)
        org_slug = os.getenv("SEED_ORG_SLUG")
        if org_slug:
            org = db.query(Organization).filter(Organization.slug == org_slug).first()
        else:
            org = db.query(Organization).first()
        if not org:
            print("ERROR: No organization found. Run create-org first.")
            return
        
        print(f"Using organization: {org.name} ({org.id})")
        
        # Get user (owner for all records)
        user = db.query(User).filter(User.email != "system@internal").first()
        if not user:
            user = db.query(User).first()
        if not user:
            print("ERROR: No user found.")
            return
        
        print(f"Using user as owner: {mask_email(user.email)} ({user.id})")
        
        # Get the default pipeline stage for surrogates
        pipeline = pipeline_service.get_or_create_default_pipeline(db, org.id, user.id)
        
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

        # Seed system templates & workflows (idempotent)
        template_result = template_seeder.seed_all(db, org.id, user.id)
        print(f"Seeded templates: {template_result['templates_created']}, workflows: {template_result['workflows_created']}")

        # Seed signature defaults for org and user
        org.signature_company_name = org.name
        org.signature_address = "123 Market St, Austin, TX"
        org.signature_phone = "+1 (512) 555-0199"
        org.signature_website = "https://surrogacycrm.test"
        org.signature_primary_color = "#0ea5e9"
        org.signature_disclaimer = "This message contains confidential information intended only for the recipient."
        org.signature_social_links = [
            {"platform": "linkedin", "url": "https://linkedin.com/company/surrogacy-crm"},
            {"platform": "instagram", "url": "https://instagram.com/surrogacy-crm"},
        ]
        user.signature_name = user.display_name
        user.signature_title = "Case Manager"
        user.signature_phone = "+1 (512) 555-0142"
        user.signature_linkedin = "https://linkedin.com/in/case-manager"
        user.signature_twitter = "https://twitter.com/surrogacycrm"

        db.commit()

        # Create mock data
        surrogate_count = int(os.getenv("SEED_SURROGATES", "40"))
        intended_parent_count = int(os.getenv("SEED_INTENDED_PARENTS", "40"))
        create_surrogates(db, org.id, user.id, stages_sorted, count=surrogate_count)
        if intended_parent_count > 0:
            create_intended_parents(db, org.id, user.id, count=intended_parent_count)
        
        print("\nMock data seeded successfully!")
        print(f"  - {surrogate_count} surrogates created")
        if intended_parent_count > 0:
            print(f"  - {intended_parent_count} intended parents created")
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
