import time
from app.db.session import SessionLocal
from app.services.permission_service import seed_role_defaults
from app.db.models import Organization
import uuid

db = SessionLocal()
org = db.query(Organization).first()

start = time.time()
if org:
    seed_role_defaults(db, org.id)
end = time.time()
print(f"Time: {end-start}")
