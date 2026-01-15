"""Meta sync service for hierarchy, spend, and forms.

Handles syncing data from Meta Marketing API:
- Hierarchy sync: Campaigns, AdSets, Ads
- Spend sync: Daily spend data with breakdowns
- Form sync: Lead gen form metadata with versioning
"""

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_token
from app.db.models import (
    Surrogate,
    MetaAd,
    MetaAdAccount,
    MetaAdSet,
    MetaCampaign,
    MetaDailySpend,
    MetaForm,
    MetaFormVersion,
    MetaPageMapping,
)
from app.services import meta_api
from app.types import JsonObject

logger = logging.getLogger(__name__)

# Breakdown types to fetch (separate calls, no cross-dim)
SPEND_BREAKDOWN_TYPES = [
    "_total",  # No breakdown - aggregate totals
    "publisher_platform",  # facebook, instagram, audience_network
    "platform_position",  # feed, stories, reels, etc.
    "age",  # 18-24, 25-34, 35-44, etc.
    "region",  # US states (no fallback to country)
]


# =============================================================================
# Hierarchy Sync (Campaigns, AdSets, Ads)
# =============================================================================


async def sync_hierarchy(
    db: Session,
    ad_account: MetaAdAccount,
    full_sync: bool = False,
) -> dict:
    """
    Sync campaign/adset/ad hierarchy from Meta.

    Args:
        db: Database session
        ad_account: MetaAdAccount with credentials
        full_sync: If True, fetch all entities. If False, delta sync.

    Returns:
        {"campaigns": N, "adsets": N, "ads": N, "error": str | None}
    """
    result = {"campaigns": 0, "adsets": 0, "ads": 0, "error": None}

    # Get access token
    if not ad_account.system_token_encrypted:
        result["error"] = "No system token configured"
        return result

    try:
        access_token = decrypt_token(ad_account.system_token_encrypted)
    except Exception as e:
        result["error"] = f"Failed to decrypt token: {e}"
        return result

    # Determine updated_since for delta sync
    updated_since = None
    if not full_sync and ad_account.hierarchy_synced_at:
        updated_since = ad_account.hierarchy_synced_at

    ad_account_external_id = ad_account.ad_account_external_id
    org_id = ad_account.organization_id

    # Sync campaigns
    campaigns_data, error = await meta_api.fetch_campaigns(
        ad_account_external_id, access_token, updated_since=updated_since
    )
    if error:
        result["error"] = f"Campaign fetch failed: {error}"
        _record_sync_error(db, ad_account, error)
        return result

    campaign_map = {}  # external_id -> internal_id
    for camp_data in campaigns_data or []:
        campaign = _upsert_campaign(db, ad_account, org_id, camp_data)
        if campaign:
            campaign_map[camp_data["id"]] = campaign.id
            result["campaigns"] += 1

    # Sync adsets
    adsets_data, error = await meta_api.fetch_adsets(
        ad_account_external_id, access_token, updated_since=updated_since
    )
    if error:
        result["error"] = f"AdSet fetch failed: {error}"
        _record_sync_error(db, ad_account, error)
        return result

    adset_map = {}  # external_id -> internal_id
    for adset_data in adsets_data or []:
        adset = _upsert_adset(db, ad_account, org_id, adset_data, campaign_map)
        if adset:
            adset_map[adset_data["id"]] = adset.id
            result["adsets"] += 1

    # Sync ads
    ads_data, error = await meta_api.fetch_ads(
        ad_account_external_id, access_token, updated_since=updated_since
    )
    if error:
        result["error"] = f"Ad fetch failed: {error}"
        _record_sync_error(db, ad_account, error)
        return result

    for ad_data in ads_data or []:
        ad = _upsert_ad(db, ad_account, org_id, ad_data, campaign_map, adset_map)
        if ad:
            result["ads"] += 1

    # Update watermark
    ad_account.hierarchy_synced_at = datetime.now(timezone.utc)
    ad_account.last_error = None
    ad_account.last_error_at = None
    db.commit()

    logger.info(
        f"Hierarchy sync complete for {ad_account_external_id}: "
        f"{result['campaigns']} campaigns, {result['adsets']} adsets, {result['ads']} ads"
    )

    return result


def _upsert_campaign(
    db: Session,
    ad_account: MetaAdAccount,
    org_id: UUID,
    data: JsonObject,
) -> MetaCampaign | None:
    """Upsert a campaign from Meta data."""
    external_id = data.get("id")
    if not external_id:
        return None

    campaign = db.scalar(
        select(MetaCampaign).where(
            MetaCampaign.organization_id == org_id,
            MetaCampaign.ad_account_id == ad_account.id,
            MetaCampaign.campaign_external_id == external_id,
        )
    )

    updated_time = meta_api.parse_meta_timestamp(data.get("updated_time"))

    if campaign:
        campaign.campaign_name = data.get("name", campaign.campaign_name)
        campaign.objective = data.get("objective")
        campaign.status = data.get("status", "UNKNOWN")
        campaign.updated_time = updated_time
        campaign.synced_at = datetime.now(timezone.utc)
    else:
        campaign = MetaCampaign(
            organization_id=org_id,
            ad_account_id=ad_account.id,
            campaign_external_id=external_id,
            campaign_name=data.get("name", "Unknown Campaign"),
            objective=data.get("objective"),
            status=data.get("status", "UNKNOWN"),
            updated_time=updated_time,
        )
        db.add(campaign)

    db.flush()
    return campaign


def _upsert_adset(
    db: Session,
    ad_account: MetaAdAccount,
    org_id: UUID,
    data: JsonObject,
    campaign_map: dict[str, UUID],
) -> MetaAdSet | None:
    """Upsert an adset from Meta data."""
    external_id = data.get("id")
    campaign_external_id = data.get("campaign_id")
    if not external_id or not campaign_external_id:
        return None

    # Find campaign internal ID
    campaign_id = campaign_map.get(campaign_external_id)
    if not campaign_id:
        # Campaign not in this sync - try to find existing
        campaign = db.scalar(
            select(MetaCampaign).where(
                MetaCampaign.organization_id == org_id,
                MetaCampaign.ad_account_id == ad_account.id,
                MetaCampaign.campaign_external_id == campaign_external_id,
            )
        )
        if campaign:
            campaign_id = campaign.id
            campaign_map[campaign_external_id] = campaign_id
        else:
            logger.warning(
                f"AdSet {external_id} references unknown campaign {campaign_external_id}"
            )
            return None

    adset = db.scalar(
        select(MetaAdSet).where(
            MetaAdSet.organization_id == org_id,
            MetaAdSet.ad_account_id == ad_account.id,
            MetaAdSet.adset_external_id == external_id,
        )
    )

    updated_time = meta_api.parse_meta_timestamp(data.get("updated_time"))
    targeting = data.get("targeting", {})
    targeting_geo = targeting.get("geo_locations") if targeting else None

    if adset:
        adset.adset_name = data.get("name", adset.adset_name)
        adset.campaign_id = campaign_id
        adset.campaign_external_id = campaign_external_id
        adset.targeting_geo = targeting_geo
        adset.status = data.get("status", "UNKNOWN")
        adset.updated_time = updated_time
        adset.synced_at = datetime.now(timezone.utc)
    else:
        adset = MetaAdSet(
            organization_id=org_id,
            ad_account_id=ad_account.id,
            adset_external_id=external_id,
            adset_name=data.get("name", "Unknown AdSet"),
            campaign_id=campaign_id,
            campaign_external_id=campaign_external_id,
            targeting_geo=targeting_geo,
            status=data.get("status", "UNKNOWN"),
            updated_time=updated_time,
        )
        db.add(adset)

    db.flush()
    return adset


def _upsert_ad(
    db: Session,
    ad_account: MetaAdAccount,
    org_id: UUID,
    data: JsonObject,
    campaign_map: dict[str, UUID],
    adset_map: dict[str, UUID],
) -> MetaAd | None:
    """Upsert an ad from Meta data."""
    external_id = data.get("id")
    adset_external_id = data.get("adset_id")
    campaign_external_id = data.get("campaign_id")
    if not external_id or not adset_external_id or not campaign_external_id:
        return None

    # Find internal IDs
    campaign_id = campaign_map.get(campaign_external_id)
    adset_id = adset_map.get(adset_external_id)

    # Try to find existing if not in maps
    if not campaign_id:
        campaign = db.scalar(
            select(MetaCampaign).where(
                MetaCampaign.organization_id == org_id,
                MetaCampaign.ad_account_id == ad_account.id,
                MetaCampaign.campaign_external_id == campaign_external_id,
            )
        )
        if campaign:
            campaign_id = campaign.id
            campaign_map[campaign_external_id] = campaign_id

    if not adset_id:
        adset = db.scalar(
            select(MetaAdSet).where(
                MetaAdSet.organization_id == org_id,
                MetaAdSet.ad_account_id == ad_account.id,
                MetaAdSet.adset_external_id == adset_external_id,
            )
        )
        if adset:
            adset_id = adset.id
            adset_map[adset_external_id] = adset_id

    if not campaign_id or not adset_id:
        logger.warning(f"Ad {external_id} references unknown campaign/adset")
        return None

    ad = db.scalar(
        select(MetaAd).where(
            MetaAd.organization_id == org_id,
            MetaAd.ad_account_id == ad_account.id,
            MetaAd.ad_external_id == external_id,
        )
    )

    updated_time = meta_api.parse_meta_timestamp(data.get("updated_time"))

    if ad:
        ad.ad_name = data.get("name", ad.ad_name)
        ad.adset_id = adset_id
        ad.campaign_id = campaign_id
        ad.adset_external_id = adset_external_id
        ad.campaign_external_id = campaign_external_id
        ad.status = data.get("status", "UNKNOWN")
        ad.updated_time = updated_time
        ad.synced_at = datetime.now(timezone.utc)
    else:
        ad = MetaAd(
            organization_id=org_id,
            ad_account_id=ad_account.id,
            ad_external_id=external_id,
            ad_name=data.get("name", "Unknown Ad"),
            adset_id=adset_id,
            campaign_id=campaign_id,
            adset_external_id=adset_external_id,
            campaign_external_id=campaign_external_id,
            status=data.get("status", "UNKNOWN"),
            updated_time=updated_time,
        )
        db.add(ad)

    db.flush()
    return ad


def link_surrogates_to_campaigns(db: Session, org_id: UUID) -> int:
    """
    Backfill campaign/adset external IDs on surrogates.

    Joins Surrogate.meta_ad_external_id → MetaAd → campaign/adset.
    Only updates surrogates where campaign_external_id is NULL.

    Returns: Number of surrogates updated
    """
    # Find surrogates needing backfill
    surrogates_query = select(Surrogate).where(
        Surrogate.organization_id == org_id,
        Surrogate.meta_ad_external_id.isnot(None),
        Surrogate.meta_campaign_external_id.is_(None),
    )

    surrogates = db.scalars(surrogates_query).all()
    updated = 0

    for surrogate in surrogates:
        # Find the ad
        ad = db.scalar(
            select(MetaAd).where(
                MetaAd.organization_id == org_id,
                MetaAd.ad_external_id == surrogate.meta_ad_external_id,
            )
        )
        if ad:
            surrogate.meta_campaign_external_id = ad.campaign_external_id
            surrogate.meta_adset_external_id = ad.adset_external_id
            updated += 1

    if updated > 0:
        db.commit()
        logger.info(f"Backfilled campaign info for {updated} surrogates in org {org_id}")

    return updated


# =============================================================================
# Spend Sync
# =============================================================================


async def sync_spend(
    db: Session,
    ad_account: MetaAdAccount,
    date_start: date,
    date_end: date,
    breakdowns: list[str] | None = None,
) -> dict:
    """
    Sync daily spend data from Meta.

    Args:
        db: Database session
        ad_account: MetaAdAccount with credentials
        date_start: Start date for sync
        date_end: End date for sync
        breakdowns: List of breakdown types to sync (default: all)

    Returns:
        {"rows_synced": N, "campaigns": N, "error": str | None}
    """
    result = {"rows_synced": 0, "campaigns": 0, "error": None}

    if not ad_account.system_token_encrypted:
        result["error"] = "No system token configured"
        return result

    try:
        access_token = decrypt_token(ad_account.system_token_encrypted)
    except Exception as e:
        result["error"] = f"Failed to decrypt token: {e}"
        return result

    breakdown_types = breakdowns or SPEND_BREAKDOWN_TYPES
    ad_account_external_id = ad_account.ad_account_external_id
    org_id = ad_account.organization_id
    campaign_set = set()

    for breakdown_type in breakdown_types:
        # Determine Meta API breakdown parameter
        if breakdown_type == "_total":
            meta_breakdowns = None
        else:
            meta_breakdowns = [breakdown_type]

        # Fetch insights with daily granularity
        insights, error = await meta_api.fetch_ad_account_insights(
            ad_account_external_id,
            access_token,
            date_start=date_start.isoformat(),
            date_end=date_end.isoformat(),
            level="campaign",
            time_increment=1,  # Daily
            breakdowns=meta_breakdowns,
        )

        if error:
            result["error"] = f"Spend fetch failed for {breakdown_type}: {error}"
            _record_sync_error(db, ad_account, error)
            return result

        # Upsert spend rows
        for row in insights or []:
            spend_row = _upsert_spend_row(db, ad_account, org_id, row, breakdown_type)
            if spend_row:
                result["rows_synced"] += 1
                campaign_set.add(row.get("campaign_id"))

    result["campaigns"] = len(campaign_set)

    # Update watermark
    ad_account.spend_synced_at = datetime.now(timezone.utc)
    ad_account.last_error = None
    ad_account.last_error_at = None
    db.commit()

    logger.info(
        f"Spend sync complete for {ad_account_external_id}: "
        f"{result['rows_synced']} rows, {result['campaigns']} campaigns"
    )

    return result


def _upsert_spend_row(
    db: Session,
    ad_account: MetaAdAccount,
    org_id: UUID,
    data: JsonObject,
    breakdown_type: str,
) -> MetaDailySpend | None:
    """Upsert a daily spend row."""
    campaign_external_id = data.get("campaign_id")
    campaign_name = data.get("campaign_name", "Unknown Campaign")
    date_str = data.get("date_start")

    if not campaign_external_id or not date_str:
        return None

    try:
        spend_date = date.fromisoformat(date_str)
    except ValueError:
        return None

    # Determine breakdown value
    if breakdown_type == "_total":
        breakdown_value = "_all"
    else:
        breakdown_value = data.get(breakdown_type, "_unknown")

    # Parse metrics
    spend = Decimal(data.get("spend", "0"))
    impressions = int(data.get("impressions", 0))
    reach = int(data.get("reach", 0))
    clicks = int(data.get("clicks", 0))

    # Extract lead count from actions (multiple action types can indicate leads)
    LEAD_ACTION_TYPES = {"lead", "leadgen", "onsite_conversion.lead_grouped"}
    leads = 0
    for action in data.get("actions", []):
        if action.get("action_type") in LEAD_ACTION_TYPES:
            leads += int(action.get("value", 0))  # Sum all lead types

    # Upsert
    existing = db.scalar(
        select(MetaDailySpend).where(
            MetaDailySpend.organization_id == org_id,
            MetaDailySpend.ad_account_id == ad_account.id,
            MetaDailySpend.campaign_external_id == campaign_external_id,
            MetaDailySpend.spend_date == spend_date,
            MetaDailySpend.breakdown_type == breakdown_type,
            MetaDailySpend.breakdown_value == breakdown_value,
        )
    )

    if existing:
        existing.campaign_name = campaign_name
        existing.spend = spend
        existing.impressions = impressions
        existing.reach = reach
        existing.clicks = clicks
        existing.leads = leads
        existing.synced_at = datetime.now(timezone.utc)
        return existing
    else:
        row = MetaDailySpend(
            organization_id=org_id,
            ad_account_id=ad_account.id,
            spend_date=spend_date,
            campaign_external_id=campaign_external_id,
            campaign_name=campaign_name,
            breakdown_type=breakdown_type,
            breakdown_value=breakdown_value,
            spend=spend,
            impressions=impressions,
            reach=reach,
            clicks=clicks,
            leads=leads,
        )
        db.add(row)
        db.flush()
        return row


async def run_spend_sync_schedule(
    db: Session,
    ad_account: MetaAdAccount,
) -> dict:
    """
    Run standard spend sync schedule:
    - Daily: yesterday + rolling 7-day backfill
    - Weekly (Sunday): 90-day backfill
    - Initial: 180-day backfill if no prior sync
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    # Determine date range
    if ad_account.spend_synced_at is None:
        # Initial sync: 180 days
        date_start = today - timedelta(days=180)
        date_end = yesterday
    elif today.weekday() == 6:  # Sunday
        # Weekly backfill: 90 days
        date_start = today - timedelta(days=90)
        date_end = yesterday
    else:
        # Daily: yesterday + 7-day rolling
        date_start = today - timedelta(days=7)
        date_end = yesterday

    return await sync_spend(db, ad_account, date_start, date_end)


# =============================================================================
# Form Sync
# =============================================================================


async def sync_forms(
    db: Session,
    org_id: UUID,
    page_id: str | None = None,
) -> dict:
    """
    Sync form metadata from Meta using PAGE tokens.

    NOTE: Forms sync uses page tokens from meta_page_mappings,
    NOT ad account tokens. Ad accounts don't have page permissions.

    Args:
        db: Database session
        org_id: Organization ID
        page_id: Optional specific page ID (syncs all if None)

    Returns:
        {"forms_synced": N, "versions_created": N, "error": str | None}
    """
    result = {"forms_synced": 0, "versions_created": 0, "error": None}

    # Get page mappings
    query = select(MetaPageMapping).where(
        MetaPageMapping.organization_id == org_id,
        MetaPageMapping.is_active.is_(True),
    )
    if page_id:
        query = query.where(MetaPageMapping.page_id == page_id)

    pages = db.scalars(query).all()

    if not pages:
        result["error"] = "No active page mappings found"
        return result

    for page in pages:
        if not page.access_token_encrypted:
            logger.warning(f"No token for page {page.page_id}")
            continue

        try:
            access_token = decrypt_token(page.access_token_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt token for page {page.page_id}: {e}")
            continue

        # Fetch forms
        forms_data, error = await meta_api.fetch_page_leadgen_forms(page.page_id, access_token)

        if error:
            logger.error(f"Form fetch failed for page {page.page_id}: {error}")
            page.last_error = error
            page.last_error_at = datetime.now(timezone.utc)
            continue

        # Process forms
        for form_data in forms_data or []:
            form, version_created = _upsert_form(db, org_id, page.page_id, form_data)
            if form:
                result["forms_synced"] += 1
                if version_created:
                    result["versions_created"] += 1

        # Update watermark
        page.forms_synced_at = datetime.now(timezone.utc)
        page.last_error = None
        page.last_error_at = None

    db.commit()

    logger.info(
        f"Form sync complete for org {org_id}: "
        f"{result['forms_synced']} forms, {result['versions_created']} new versions"
    )

    return result


def _upsert_form(
    db: Session,
    org_id: UUID,
    page_id: str,
    data: JsonObject,
) -> tuple[MetaForm | None, bool]:
    """
    Upsert form and detect schema changes.

    Returns (form, version_created)
    """
    form_external_id = data.get("id")
    form_name = data.get("name", "Unknown Form")
    questions = data.get("questions", [])

    if not form_external_id:
        return None, False

    # Compute schema hash for change detection
    schema_json = json.dumps(questions, sort_keys=True)
    schema_hash = hashlib.sha256(schema_json.encode()).hexdigest()

    # Find or create form
    form = db.scalar(
        select(MetaForm).where(
            MetaForm.organization_id == org_id,
            MetaForm.page_id == page_id,
            MetaForm.form_external_id == form_external_id,
        )
    )

    version_created = False

    if form:
        form.form_name = form_name
        form.synced_at = datetime.now(timezone.utc)
        form.updated_at = datetime.now(timezone.utc)
    else:
        form = MetaForm(
            organization_id=org_id,
            page_id=page_id,
            form_external_id=form_external_id,
            form_name=form_name,
        )
        db.add(form)
        db.flush()

    # Check for schema change (via hash uniqueness)
    existing_version = db.scalar(
        select(MetaFormVersion).where(
            MetaFormVersion.form_id == form.id,
            MetaFormVersion.schema_hash == schema_hash,
        )
    )

    if not existing_version:
        # New schema version
        max_version = (
            db.scalar(
                select(func.max(MetaFormVersion.version_number)).where(
                    MetaFormVersion.form_id == form.id
                )
            )
            or 0
        )

        new_version = MetaFormVersion(
            form_id=form.id,
            version_number=max_version + 1,
            field_schema=questions,
            schema_hash=schema_hash,
        )
        db.add(new_version)
        db.flush()

        form.current_version_id = new_version.id
        version_created = True

    return form, version_created


# =============================================================================
# Helpers
# =============================================================================


def _record_sync_error(db: Session, ad_account: MetaAdAccount, error: str) -> None:
    """Record sync error on ad account."""
    ad_account.last_error = error[:500]
    ad_account.last_error_at = datetime.now(timezone.utc)
    db.commit()


def get_active_ad_accounts(db: Session, org_id: UUID | None = None) -> list[MetaAdAccount]:
    """Get active ad accounts, optionally filtered by org."""
    query = select(MetaAdAccount).where(MetaAdAccount.is_active.is_(True))
    if org_id:
        query = query.where(MetaAdAccount.organization_id == org_id)
    return list(db.scalars(query).all())
