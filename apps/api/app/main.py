from fastapi import FastAPI
from sqlalchemy import text
from app.db.session import engine

app = FastAPI(title="CRM API")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}