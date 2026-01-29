"""Meta-related job handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)


async def process_meta_lead_fetch(db, job) -> None:
    """
    Process a Meta Lead Ads fetch job.

    1. Get page mapping and decrypt token
    2. Fetch lead details from Meta API
    3. Normalize field data
    4. Store in meta_leads table
    5. Update status on success/failure
    """
    from app.db.models import MetaPageMapping, MetaLead
    from app.services import (
        meta_api,
        meta_lead_service,
        meta_form_mapping_service,
        meta_token_service,
    )

    leadgen_id = job.payload.get("leadgen_id")
    page_id = job.payload.get("page_id")

    if not leadgen_id or not page_id:
        raise Exception("Missing leadgen_id or page_id in job payload")

    # Get page mapping
    mapping = (
        db.query(MetaPageMapping)
        .filter(
            MetaPageMapping.page_id == page_id,
            MetaPageMapping.is_active.is_(True),
        )
        .first()
    )

    if not mapping:
        raise Exception(f"No active mapping for page {page_id}")

    # Resolve access token (page token preferred)
    token_result = meta_token_service.get_token_for_page(db, mapping)
    access_token = token_result.token or ""
    if not access_token:
        mapping.last_error = "No page token available for Meta lead fetch"
        mapping.last_error_at = datetime.now(timezone.utc)
        db.commit()
        raise Exception("No page token available for Meta lead fetch")

    # Fetch lead from Meta API
    lead_data, error = await meta_api.fetch_lead_details(leadgen_id, access_token)

    if error:
        # Update mapping with error
        mapping.last_error = error
        mapping.last_error_at = datetime.now(timezone.utc)
        db.commit()
        if token_result.connection_id:
            meta_token_service.mark_token_error(db, token_result.connection_id, Exception(error))

        # Check if we have an existing meta_lead to update
        existing = (
            db.query(MetaLead)
            .filter(
                MetaLead.organization_id == mapping.organization_id,
                MetaLead.meta_lead_id == leadgen_id,
            )
            .first()
        )
        if existing:
            existing.status = "fetch_failed"
            existing.fetch_error = error
            db.commit()

        raise Exception(error)

    # Normalize field data (scalars for conversion)
    field_data = meta_api.normalize_field_data(lead_data.get("field_data", []))

    # Extract raw field data preserving multi-select arrays (for form analysis)
    field_data_raw = meta_api.extract_field_data_raw(lead_data.get("field_data", []))

    # Add ad_id for campaign tracking (stored in field_data for conversion)
    if lead_data.get("ad_id"):
        field_data["meta_ad_id"] = lead_data["ad_id"]
        field_data_raw["meta_ad_id"] = lead_data["ad_id"]

    # Parse Meta timestamp
    meta_created_time = meta_api.parse_meta_timestamp(lead_data.get("created_time"))

    # Store meta lead (handles dedupe)
    meta_lead, store_error = meta_lead_service.store_meta_lead(
        db=db,
        org_id=mapping.organization_id,
        meta_lead_id=leadgen_id,
        field_data=field_data,
        field_data_raw=field_data_raw,
        raw_payload=None,  # PII minimization - don't store raw
        meta_form_id=lead_data.get("form_id"),
        meta_page_id=page_id,
        meta_created_time=meta_created_time,
    )

    if store_error:
        raise Exception(store_error)

    # Update success tracking (even for idempotent re-stores)
    mapping.last_success_at = datetime.now(timezone.utc)
    mapping.last_error = None
    db.commit()
    if token_result.connection_id:
        meta_token_service.mark_token_valid(db, token_result.connection_id)

    logger.info(f"Meta lead {leadgen_id} stored successfully for org {mapping.organization_id}")

    # Enrich platform attribution if missing (uses cached ad-level insights)
    try:
        meta_lead_service.enrich_platform_from_insights(db, meta_lead)
    except Exception as exc:
        logger.warning(f"Platform enrichment failed for lead {leadgen_id}: {exc}")

    # Auto-convert only if mapping is ready
    if meta_lead.is_converted:
        meta_lead.status = "converted"
        db.commit()
        return "sent"

    form = meta_form_mapping_service.get_form_by_external_id(
        db, mapping.organization_id, meta_lead.meta_form_id
    )
    if not form:
        meta_lead.status = "awaiting_mapping"
        db.commit()
        logger.info(f"Meta lead {leadgen_id} awaiting mapping (form not found)")
        return

    if form.mapping_status != "mapped" or form.mapping_version_id != form.current_version_id:
        meta_lead.status = "awaiting_mapping"
        db.commit()
        reason = "Mapping missing" if form.mapping_status != "mapped" else "Mapping outdated"
        meta_form_mapping_service.ensure_mapping_review_task(db, form, reason=reason)
        logger.info(f"Meta lead {leadgen_id} awaiting mapping for form {form.form_external_id}")
        return

    meta_lead.status = "stored"
    db.commit()

    surrogate, convert_error = meta_lead_service.convert_to_surrogate_with_mapping(
        db=db,
        meta_lead=meta_lead,
        mapping_rules=form.mapping_rules or [],
        unknown_column_behavior=form.unknown_column_behavior or "metadata",
        user_id=None,
    )

    if convert_error:
        logger.warning(f"Meta lead auto-conversion failed: {convert_error}")
        meta_lead.status = "convert_failed"
        db.commit()
    else:
        meta_lead.status = "converted"
        db.commit()
        logger.info(f"Meta lead {leadgen_id} auto-converted to case {surrogate.surrogate_number}")


async def process_meta_lead_reprocess_form(db, job) -> None:
    """
    Reprocess unconverted Meta leads for a specific form after mapping changes.

    Payload:
      - form_id (internal UUID)
    """
    from app.db.models import MetaLead
    from app.services import meta_form_mapping_service, meta_lead_service

    payload = job.payload or {}
    form_id = payload.get("form_id")
    if not form_id:
        raise Exception("Missing form_id in job payload")

    form = meta_form_mapping_service.get_form(db, job.organization_id, UUID(form_id))
    if not form:
        raise Exception(f"Meta form {form_id} not found")

    if form.mapping_status != "mapped" or form.mapping_version_id != form.current_version_id:
        raise Exception("Form mapping is not ready for reprocessing")

    leads = (
        db.query(MetaLead)
        .filter(
            MetaLead.organization_id == job.organization_id,
            MetaLead.meta_form_id == form.form_external_id,
            MetaLead.is_converted.is_(False),
        )
        .order_by(MetaLead.received_at.asc())
        .all()
    )

    for lead in leads:
        lead.status = "stored"
        db.commit()
        surrogate, error = meta_lead_service.convert_to_surrogate_with_mapping(
            db=db,
            meta_lead=lead,
            mapping_rules=form.mapping_rules or [],
            unknown_column_behavior=form.unknown_column_behavior or "metadata",
            user_id=None,
        )
        if error:
            lead.status = "convert_failed"
            db.commit()
            logger.warning(f"Reprocess failed for lead {lead.meta_lead_id}: {error}")
            continue

        lead.status = "converted"
        db.commit()
        logger.info(f"Reprocessed lead {lead.meta_lead_id} to {surrogate.surrogate_number}")


async def process_meta_capi_event(db, job) -> None:
    """
    Process a Meta CAPI conversion event job.

    Payload:
      - meta_lead_id (leadgen id)
      - meta_ad_external_id (for resolving ad account)
      - surrogate_status
      - email, phone (optional)
      - meta_page_id (optional, unused - kept for backward compatibility)

    Ad account resolution:
      meta_ad_external_id → MetaAd → MetaAdAccount
      Uses per-account CAPI config (pixel_id, capi_enabled) + OAuth token.
      Skips if no ad account found or CAPI is disabled for that account.
    """
    from app.db.models import MetaAd, MetaAdAccount
    from app.services import meta_capi

    payload = job.payload or {}
    meta_lead_id = payload.get("meta_lead_id")
    meta_ad_external_id = payload.get("meta_ad_external_id")
    surrogate_status = payload.get("surrogate_status")
    email = payload.get("email")
    phone = payload.get("phone")

    if not meta_lead_id or not surrogate_status:
        raise Exception("Missing meta_lead_id or surrogate_status in job payload")

    # Resolve ad account chain: meta_ad_external_id → MetaAd → MetaAdAccount
    ad_account = None
    if meta_ad_external_id:
        meta_ad = (
            db.query(MetaAd)
            .filter(
                MetaAd.organization_id == job.organization_id,
                MetaAd.ad_external_id == meta_ad_external_id,
            )
            .first()
        )
        if meta_ad:
            ad_account = (
                db.query(MetaAdAccount)
                .filter(
                    MetaAdAccount.id == meta_ad.ad_account_id,
                    MetaAdAccount.is_active.is_(True),
                )
                .first()
            )

    # Skip if no ad account or CAPI not enabled for this account
    if not ad_account:
        logger.info(
            "Skipping CAPI for lead %s: no ad account found (ad_external_id=%s)",
            meta_lead_id,
            meta_ad_external_id,
        )
        return

    if not ad_account.capi_enabled:
        logger.info(
            "Skipping CAPI for lead %s: CAPI disabled for ad account %s",
            meta_lead_id,
            ad_account.ad_account_external_id,
        )
        return

    if not ad_account.pixel_id:
        logger.warning(
            "Skipping CAPI for lead %s: no pixel_id configured for ad account %s",
            meta_lead_id,
            ad_account.ad_account_external_id,
        )
        return

    meta_status = meta_capi.map_surrogate_status_to_meta_status(str(surrogate_status))
    if not meta_status:
        raise Exception(f"Unsupported case status for Meta CAPI: {surrogate_status}")

    success, error = await meta_capi.send_status_event_for_account(
        meta_lead_id=str(meta_lead_id),
        ad_account=ad_account,
        surrogate_status=str(surrogate_status),
        meta_status=meta_status,
        email=str(email) if email else None,
        phone=str(phone) if phone else None,
    )

    if not success:
        # Record error on ad account for observability
        ad_account.last_error = f"CAPI: {error}"
        ad_account.last_error_at = datetime.now(timezone.utc)
        db.commit()
        raise Exception(error or "Meta CAPI failed")


async def process_meta_hierarchy_sync(db, job) -> None:
    """
    Process a META_HIERARCHY_SYNC job - sync campaign/adset/ad hierarchy.

    Payload:
        - ad_account_id: UUID of the MetaAdAccount
        - full_sync: bool (if True, ignore delta and fetch all)
    """
    from app.db.models import MetaAdAccount
    from app.services import meta_sync_service

    payload = job.payload or {}
    ad_account_id = payload.get("ad_account_id")
    full_sync = payload.get("full_sync", False)

    if not ad_account_id:
        raise Exception("Missing ad_account_id in job payload")

    # Get ad account
    ad_account = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.id == UUID(ad_account_id),
            MetaAdAccount.organization_id == job.organization_id,
        )
        .first()
    )

    if not ad_account:
        raise Exception(f"Ad account {ad_account_id} not found")

    if not ad_account.is_active:
        logger.info("Skipping hierarchy sync for inactive ad account %s", ad_account_id)
        return

    logger.info(
        "Starting hierarchy sync for ad account %s (full_sync=%s)",
        ad_account.ad_account_external_id,
        full_sync,
    )

    result = await meta_sync_service.sync_hierarchy(
        db=db,
        ad_account=ad_account,
        full_sync=full_sync,
    )
    if result.get("error"):
        raise Exception(result["error"])

    logger.info(
        "Hierarchy sync complete: campaigns=%s, adsets=%s, ads=%s",
        result.get("campaigns", 0),
        result.get("adsets", 0),
        result.get("ads", 0),
    )

    # Note: Health recording handled centrally by _record_job_success

    # Link cases to campaigns (backfill)
    linked = meta_sync_service.link_surrogates_to_campaigns(db, job.organization_id)
    if linked:
        logger.info("Linked %s cases to campaign data", linked)


async def process_meta_spend_sync(db, job) -> None:
    """
    Process a META_SPEND_SYNC job - sync daily spend data.

    Payload:
        - ad_account_id: UUID of the MetaAdAccount
        - sync_type: 'daily' (default), 'weekly', 'initial'
        - date_start: optional override
        - date_end: optional override
    """
    from datetime import date, timedelta

    from app.db.models import MetaAdAccount
    from app.services import meta_sync_service

    payload = job.payload or {}
    ad_account_id = payload.get("ad_account_id")
    sync_type = payload.get("sync_type", "daily")

    if not ad_account_id:
        raise Exception("Missing ad_account_id in job payload")

    # Get ad account
    ad_account = (
        db.query(MetaAdAccount)
        .filter(
            MetaAdAccount.id == UUID(ad_account_id),
            MetaAdAccount.organization_id == job.organization_id,
        )
        .first()
    )

    if not ad_account:
        raise Exception(f"Ad account {ad_account_id} not found")

    if not ad_account.is_active:
        logger.info("Skipping spend sync for inactive ad account %s", ad_account_id)
        return

    # Determine date range based on sync_type
    today = date.today()

    if payload.get("date_start") and payload.get("date_end"):
        # Override dates
        date_start = date.fromisoformat(payload["date_start"])
        date_end = date.fromisoformat(payload["date_end"])
    elif sync_type == "daily":
        # Yesterday + 7-day rolling backfill
        date_start = today - timedelta(days=7)
        date_end = today - timedelta(days=1)
    elif sync_type == "weekly":
        # 90-day backfill
        date_start = today - timedelta(days=90)
        date_end = today - timedelta(days=1)
    elif sync_type == "initial":
        # 180-day initial load
        date_start = today - timedelta(days=180)
        date_end = today - timedelta(days=1)
    else:
        date_start = today - timedelta(days=7)
        date_end = today - timedelta(days=1)

    logger.info(
        "Starting spend sync for ad account %s (%s: %s to %s)",
        ad_account.ad_account_external_id,
        sync_type,
        date_start,
        date_end,
    )

    result = await meta_sync_service.sync_spend(
        db=db,
        ad_account=ad_account,
        date_start=date_start,
        date_end=date_end,
    )
    if result.get("error"):
        raise Exception(result["error"])

    logger.info(
        "Spend sync complete: rows_synced=%s, campaigns=%s",
        result.get("rows_synced", 0),
        result.get("campaigns", 0),
    )

    # Sync ad-level platform breakdown for deterministic attribution
    platform_result = await meta_sync_service.sync_ad_platform_breakdown(
        db=db,
        ad_account=ad_account,
        date_start=date_start,
        date_end=date_end,
    )
    if platform_result.get("error"):
        raise Exception(platform_result["error"])

    logger.info(
        "Ad platform sync complete: rows_synced=%s, ads=%s",
        platform_result.get("rows_synced", 0),
        platform_result.get("ads", 0),
    )

    # Note: Health recording handled centrally by _record_job_success


async def process_meta_form_sync(db, job) -> None:
    """
    Process a META_FORM_SYNC job - sync form metadata with versioning.

    NOTE: Uses PAGE tokens from meta_page_mappings, NOT ad account tokens.
    Ad accounts don't have page permissions for leadgen_forms endpoint.

    Payload:
        - page_ids: list of page IDs to sync (optional, syncs all active if not provided)
    """
    from app.services import meta_sync_service

    payload = job.payload or {}
    page_ids = payload.get("page_ids")

    logger.info("Starting forms sync for org %s (pages=%s)", job.organization_id, page_ids or "all")

    if page_ids and isinstance(page_ids, list):
        # Sync each specified page
        total_result = {"forms_synced": 0, "versions_created": 0}
        for page_id in page_ids:
            page_result = await meta_sync_service.sync_forms(
                db=db,
                org_id=job.organization_id,
                page_id=page_id,
            )
            if page_result.get("error"):
                raise Exception(page_result["error"])
            total_result["forms_synced"] += page_result.get("forms_synced", 0)
            total_result["versions_created"] += page_result.get("versions_created", 0)
        result = total_result
    else:
        # Sync all pages
        result = await meta_sync_service.sync_forms(
            db=db,
            org_id=job.organization_id,
            page_id=None,
        )
    if result.get("error"):
        raise Exception(result["error"])

    logger.info(
        "Forms sync complete: forms_synced=%s, versions_created=%s",
        result.get("forms_synced", 0),
        result.get("versions_created", 0),
    )

    # Note: Health recording handled centrally by _record_job_success
