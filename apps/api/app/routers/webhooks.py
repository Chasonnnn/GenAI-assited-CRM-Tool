"""Webhooks router - external service integrations."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.db.models import MetaPageMapping
from app.db.enums import JobType
from app.services import job_service, meta_api

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/meta")
async def verify_meta_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta webhook verification endpoint.
    
    When you configure the webhook in Meta, it sends a GET request
    with a challenge that must be echoed back as PLAIN TEXT (not JSON).
    """
    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return PlainTextResponse(challenge or "")
    
    logger.warning(f"Meta webhook verification failed: mode={mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta")
async def receive_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Meta Lead Ads webhook.
    
    Security:
    - Validates X-Hub-Signature-256 HMAC (except in test mode)
    - Validates payload size
    - Validates page_id is mapped
    
    Processing:
    - Enqueues async jobs for lead fetching (idempotent via DB constraint)
    - Returns 200 fast before heavy DB work
    """
    # 1. Check payload size
    content_length = request.headers.get("content-length", "0")
    try:
        if int(content_length) > settings.META_WEBHOOK_MAX_PAYLOAD_BYTES:
            raise HTTPException(413, "Payload too large")
    except ValueError:
        pass
    
    # 2. Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    # 3. Validate signature (skip in test mode)
    if not settings.META_TEST_MODE:
        if not signature:
            logger.warning("Meta webhook missing signature")
            raise HTTPException(403, "Missing signature")
        if not meta_api.verify_signature(body, signature):
            logger.warning("Meta webhook invalid signature")
            raise HTTPException(403, "Invalid signature")
    
    # 4. Parse payload
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    
    # 5. Validate object type
    if data.get("object") != "page":
        logger.warning(f"Meta webhook invalid object: {data.get('object')}")
        raise HTTPException(400, f"Invalid object: {data.get('object')}")
    
    # 6. Process entries
    jobs_created = 0
    jobs_skipped = 0
    
    for entry in data.get("entry", []):
        page_id = str(entry.get("id", ""))
        if not page_id:
            continue
        
        # Validate page_id is mapped to an org
        mapping = db.query(MetaPageMapping).filter(
            MetaPageMapping.page_id == page_id,
            MetaPageMapping.is_active == True,
        ).first()
        
        if not mapping:
            logger.info(f"Meta webhook: unmapped page_id={page_id}")
            continue
        
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            
            value = change.get("value", {})
            leadgen_id = value.get("leadgen_id")
            
            if not leadgen_id:
                logger.warning("Meta webhook: missing leadgen_id in change")
                continue
            
            # Idempotent job creation via DB unique constraint
            job_key = f"meta_lead_fetch:{page_id}:{leadgen_id}"
            
            try:
                job_service.schedule_job(
                    db=db,
                    org_id=mapping.organization_id,
                    job_type=JobType.META_LEAD_FETCH,
                    payload={
                        "leadgen_id": leadgen_id,
                        "page_id": page_id,
                    },
                    idempotency_key=job_key,
                )
                jobs_created += 1
                logger.info(f"Meta webhook: enqueued job for leadgen_id={leadgen_id}")
            except IntegrityError:
                db.rollback()
                jobs_skipped += 1
                logger.info(f"Meta webhook: duplicate job skipped for leadgen_id={leadgen_id}")
    
    return {
        "status": "ok",
        "jobs_enqueued": jobs_created,
        "jobs_skipped": jobs_skipped,
    }


# =============================================================================
# Dev/Test endpoint for simulating Meta webhook
# =============================================================================

@router.post("/meta/simulate", include_in_schema=False)
async def simulate_meta_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Simulate a Meta webhook for testing.
    
    Only works in test mode. Requires X-Dev-Secret header.
    """
    if not settings.META_TEST_MODE:
        raise HTTPException(403, "Only available in test mode")
    
    dev_secret = request.headers.get("X-Dev-Secret", "")
    if dev_secret != settings.DEV_SECRET:
        raise HTTPException(403, "Invalid dev secret")
    
    # Create a mock webhook payload
    import uuid
    mock_leadgen_id = str(uuid.uuid4())
    
    # Find any active page mapping (or use mock)
    mapping = db.query(MetaPageMapping).filter(
        MetaPageMapping.is_active == True
    ).first()
    
    page_id = mapping.page_id if mapping else "mock_page_456"
    org_id = mapping.organization_id if mapping else None
    
    if not org_id:
        raise HTTPException(400, "No active page mapping found. Create one first.")
    
    # Enqueue the job
    job_key = f"meta_lead_fetch:{page_id}:{mock_leadgen_id}"
    
    try:
        job = job_service.schedule_job(
            db=db,
            org_id=org_id,
            job_type=JobType.META_LEAD_FETCH,
            payload={
                "leadgen_id": mock_leadgen_id,
                "page_id": page_id,
            },
            idempotency_key=job_key,
        )
        
        return {
            "status": "ok",
            "job_id": str(job.id),
            "leadgen_id": mock_leadgen_id,
            "page_id": page_id,
            "message": "Job enqueued. Run worker to process.",
        }
    except IntegrityError:
        db.rollback()
        return {"status": "ok", "message": "Duplicate job already exists"}
