"""
Seed script to create 40 mock surrogates and 40 mock intended parents with complete data.
Run with: python -m scripts.seed_mock_data
"""

import os
import random
import hashlib
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from app.db.session import SessionLocal
from app.db.models import Organization, User, Surrogate, IntendedParent, PipelineStage
from app.services import pipeline_service

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


def create_surrogates(db, org_id: uuid4, owner_id: uuid4, stage_id: uuid4, count: int = 40):
    """Create mock surrogates with complete data."""
    print(f"Creating {count} surrogates...")
    
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
        pregnancy_start = date.today() - timedelta(days=random.randint(30, 220))
        pregnancy_due = pregnancy_start + timedelta(days=280)
        
        surrogate = Surrogate(
            id=uuid4(),
            surrogate_number=f"S{10001 + i}",
            organization_id=org_id,
            stage_id=stage_id,
            status_label="New Unread",
            source=random.choice(SURROGATE_SOURCES),
            is_priority=random.random() < 0.2,  # 20% priority
            owner_type="user",
            owner_id=owner_id,
            
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
            pregnancy_start_date=pregnancy_start,
            pregnancy_due_date=pregnancy_due,
            
            # Contact tracking
            contact_status="unreached",
            
            # Timestamps
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90)),
            updated_at=datetime.now(timezone.utc),
        )
        
        db.add(surrogate)
    
    db.commit()
    print(f"Created {count} surrogates")


def create_intended_parents(db, org_id: uuid4, owner_id: uuid4, count: int = 40):
    """Create mock intended parents with complete data."""
    print(f"Creating {count} intended parents...")
    
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
            intended_parent_number=f"I{10001 + i}",
            
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
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 120)),
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
        
        print(f"Using user as owner: {user.email} ({user.id})")
        
        # Get the default pipeline stage for surrogates
        pipeline = pipeline_service.get_or_create_default_pipeline(db, org.id, user.id)
        
        print(f"Using pipeline: {pipeline.name}")
        
        # Get first stage
        first_stage = db.query(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline.id
        ).order_by(PipelineStage.order.asc()).first()
        
        if not first_stage:
            print("ERROR: No pipeline stages found.")
            return
        
        print(f"Using first stage: {first_stage.label} ({first_stage.id})")
        
        # Create mock data
        create_surrogates(db, org.id, user.id, first_stage.id, count=40)
        create_intended_parents(db, org.id, user.id, count=40)
        
        print("\nMock data seeded successfully!")
        print("  - 40 surrogates created")
        print("  - 40 intended parents created")
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
