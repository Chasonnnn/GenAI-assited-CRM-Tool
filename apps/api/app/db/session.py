from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

connect_args = {}
if make_url(settings.DATABASE_URL).get_backend_name().startswith("postgresql"):
    connect_args["options"] = "-c timezone=utc"

engine = create_engine(
    settings.DATABASE_URL, pool_pre_ping=True, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
