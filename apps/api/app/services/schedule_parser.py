"""Schedule Parser Service.

Uses AI to parse medication schedules, exam dates, and event text into structured task proposals.
"""

import hashlib
import logging
from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.db.enums import TaskType
from app.db.models import Organization
from app.services.ai_provider import ChatMessage
from app.services.ai_prompt_registry import get_prompt
from app.services.ai_response_validation import parse_json_array

logger = logging.getLogger(__name__)


# ============================================================================
# Schemas
# ============================================================================


class ProposedTask(BaseModel):
    """A task proposal extracted from schedule text."""

    title: str = Field(..., max_length=255)
    description: str | None = None
    due_date: date | None = None
    due_time: time | None = None
    task_type: TaskType = TaskType.OTHER
    confidence: float = Field(default=0.8, ge=0, le=1)
    dedupe_key: str = ""  # Generated hash for duplicate detection

    def model_post_init(self, __context: object | None) -> None:
        """Generate dedupe_key after initialization."""
        if not self.dedupe_key:
            key_parts = f"{self.title}|{self.due_date}|{self.due_time}"
            self.dedupe_key = hashlib.sha256(key_parts.encode()).hexdigest()[:16]


class ParseScheduleResult(BaseModel):
    """Result of parsing a schedule."""

    proposed_tasks: list[ProposedTask]
    warnings: list[str] = []
    assumed_timezone: str
    assumed_reference_date: date


# ============================================================================
# AI Prompt
# ============================================================================


def _build_user_prompt(text: str, reference_date: date) -> str:
    """Build the user prompt with context."""
    prompt = get_prompt("schedule_parse")
    return prompt.render_user(reference_date=reference_date.isoformat(), text=text)


# ============================================================================
# Main Parser Function
# ============================================================================


async def parse_schedule_text(
    db: Session,
    org_id: UUID,
    text: str,
    user_timezone: str | None = None,
    known_names: list[str] | None = None,
) -> ParseScheduleResult:
    """
    Parse schedule text using AI and extract task proposals.

    Args:
        db: Database session
        org_id: Organization ID for AI settings
        text: The pasted schedule text
        user_timezone: User's timezone (falls back to org timezone)

    Returns:
        ParseScheduleResult with proposed tasks and metadata
    """
    from app.services import ai_settings_service
    from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_text

    # Get organization timezone
    org = db.query(Organization).filter(Organization.id == org_id).first()
    timezone = user_timezone or (org.timezone if org else "UTC")
    warnings: list[str] = []

    # Validate timezone and compute reference date in that timezone
    try:
        tzinfo = ZoneInfo(timezone)
    except Exception:
        warnings.append(f"Invalid timezone '{timezone}', using UTC")
        timezone = "UTC"
        tzinfo = ZoneInfo("UTC")
    reference_date = datetime.now(tzinfo).date()

    # Get AI settings
    ai_settings = ai_settings_service.get_ai_settings(db, org_id)
    if not ai_settings or not ai_settings.is_enabled:
        return ParseScheduleResult(
            proposed_tasks=[],
            warnings=warnings + ["AI is not enabled for this organization"],
            assumed_timezone=timezone,
            assumed_reference_date=reference_date,
        )
    if ai_settings_service.is_consent_required(ai_settings):
        return ParseScheduleResult(
            proposed_tasks=[],
            warnings=warnings + ["AI consent not accepted"],
            assumed_timezone=timezone,
            assumed_reference_date=reference_date,
        )
    # Truncate text to prevent abuse (max 10000 chars)
    text = text[:10000]

    # Log metadata only (no PII)
    logger.info(f"Parsing schedule: {len(text)} chars, org_id={org_id}")

    proposed_tasks: list[ProposedTask] = []
    pii_mapping = PIIMapping() if ai_settings.anonymize_pii else None
    prompt_text = text
    if ai_settings.anonymize_pii and pii_mapping:
        prompt_text = anonymize_text(text, pii_mapping, known_names)

    try:
        provider = ai_settings_service.get_ai_provider_for_settings(ai_settings, org_id)
        if not provider:
            missing_message = (
                "Vertex AI configuration is incomplete"
                if ai_settings.provider == "vertex_wif"
                else "AI API key is not configured"
            )
            return ParseScheduleResult(
                proposed_tasks=[],
                warnings=warnings + [missing_message],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date,
            )

        # Build messages
        prompt = get_prompt("schedule_parse")
        messages = [
            ChatMessage(role="system", content=prompt.system),
            ChatMessage(role="user", content=_build_user_prompt(prompt_text, reference_date)),
        ]

        # Call AI
        response = await provider.chat(messages=messages, max_tokens=2000, temperature=0.3)
        content = response.content

        # Parse response - extract JSON from response (handle markdown code blocks)
        raw_tasks = parse_json_array(content)
        if not raw_tasks:
            warnings.append("AI did not return valid JSON. Please try rephrasing.")
            return ParseScheduleResult(
                proposed_tasks=[],
                warnings=warnings,
                assumed_timezone=timezone,
                assumed_reference_date=reference_date,
            )

        # Convert to ProposedTask objects
        for raw_task in raw_tasks:
            if not isinstance(raw_task, dict):
                warnings.append("Invalid task item skipped")
                continue
            try:
                # Parse date
                due_date = None
                if raw_task.get("due_date"):
                    try:
                        due_date = date.fromisoformat(raw_task["due_date"])
                    except ValueError:
                        warnings.append(
                            f"Invalid date format for '{raw_task.get('title', 'unknown')}': {raw_task.get('due_date')}"
                        )

                # Parse time
                due_time = None
                if raw_task.get("due_time"):
                    try:
                        due_time = time.fromisoformat(raw_task["due_time"])
                    except ValueError:
                        warnings.append(
                            f"Invalid time format for '{raw_task.get('title', 'unknown')}': {raw_task.get('due_time')}"
                        )

                # Parse task type
                task_type_str = raw_task.get("task_type", "other").lower()
                try:
                    task_type = TaskType(task_type_str)
                except ValueError:
                    task_type = TaskType.OTHER
                    warnings.append(f"Unknown task type '{task_type_str}', using 'other'")

                proposed_task = ProposedTask(
                    title=raw_task.get("title", "Untitled Task")[:255],
                    description=raw_task.get("description"),
                    due_date=due_date,
                    due_time=due_time,
                    task_type=task_type,
                    confidence=float(raw_task.get("confidence", 0.8)),
                )
                if ai_settings.anonymize_pii and pii_mapping:
                    proposed_task.title = rehydrate_text(proposed_task.title, pii_mapping)
                    if proposed_task.description:
                        proposed_task.description = rehydrate_text(
                            proposed_task.description, pii_mapping
                        )
                proposed_tasks.append(proposed_task)

            except Exception as e:
                logger.warning(f"Failed to parse task: {e}")
                warnings.append(f"Failed to parse one task: {str(e)}")

        logger.info(f"Parsed {len(proposed_tasks)} tasks, {len(warnings)} warnings")

    except Exception as e:
        logger.error(f"Schedule parsing error: {e}")
        warnings.append(f"Parsing error: {str(e)}")

    return ParseScheduleResult(
        proposed_tasks=proposed_tasks,
        warnings=warnings,
        assumed_timezone=timezone,
        assumed_reference_date=reference_date,
    )
