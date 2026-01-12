"""Schedule Parser Service.

Uses AI to parse medication schedules, exam dates, and event text into structured task proposals.
"""

import hashlib
import json
import logging
import re
from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.db.enums import TaskType
from app.db.models import Organization
from app.services.ai_provider import ChatMessage, get_provider

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

PARSE_SCHEDULE_SYSTEM_PROMPT = """You are a schedule parser for a surrogacy agency CRM. 
Extract tasks from medication schedules, exam dates, and appointment lists.

Return a JSON array with objects containing:
- title: short task name (max 100 chars)
- description: additional context (optional)
- due_date: YYYY-MM-DD format (or null if not specified)
- due_time: HH:MM format in 24h (or null if not specified)
- task_type: one of [medication, exam, appointment, follow_up, meeting, contact, review, other]
- confidence: 0-1 how confident you are in this extraction

Guidelines:
- Extract ALL dates and events mentioned
- For recurring items (e.g., "daily"), create ONE task for the start date with description noting recurrence
- For relative dates like "Day 5" or "CD12", interpret as days from today unless context suggests otherwise
- "Start [medication]" is a valid task title
- Include clinic names, times, locations in description, not title
- If time is ambiguous (e.g., "morning"), use null for due_time

Return ONLY valid JSON array, no markdown or explanation."""


def _build_user_prompt(text: str, reference_date: date) -> str:
    """Build the user prompt with context."""
    return f"""Today's date is {reference_date.isoformat()}.

Parse the following schedule and extract tasks:

---
{text}
---

Return JSON array of tasks."""


# ============================================================================
# Main Parser Function
# ============================================================================


async def parse_schedule_text(
    db: Session,
    org_id: UUID,
    text: str,
    user_timezone: str | None = None,
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
    if not ai_settings.api_key_encrypted:
        return ParseScheduleResult(
            proposed_tasks=[],
            warnings=warnings + ["AI API key is not configured"],
            assumed_timezone=timezone,
            assumed_reference_date=reference_date,
        )

    # Truncate text to prevent abuse (max 10000 chars)
    text = text[:10000]

    # Log metadata only (no PII)
    logger.info(f"Parsing schedule: {len(text)} chars, org_id={org_id}")

    proposed_tasks: list[ProposedTask] = []

    try:
        # Decrypt API key
        try:
            api_key = ai_settings_service.decrypt_api_key(ai_settings.api_key_encrypted)
        except Exception:
            return ParseScheduleResult(
                proposed_tasks=[],
                warnings=warnings + ["AI API key could not be decrypted"],
                assumed_timezone=timezone,
                assumed_reference_date=reference_date,
            )

        # Get AI provider
        provider = get_provider(ai_settings.provider, api_key, ai_settings.model)

        # Build messages
        messages = [
            ChatMessage(role="system", content=PARSE_SCHEDULE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=_build_user_prompt(text, reference_date)),
        ]

        # Call AI
        response = await provider.chat(
            messages=messages, max_tokens=2000, temperature=0.3
        )
        content = response.content

        # Parse response - extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"\[[\s\S]*\]", content)
        if not json_match:
            warnings.append("AI did not return valid JSON. Please try rephrasing.")
            return ParseScheduleResult(
                proposed_tasks=[],
                warnings=warnings,
                assumed_timezone=timezone,
                assumed_reference_date=reference_date,
            )

        json_str = json_match.group()
        raw_tasks = json.loads(json_str)

        # Convert to ProposedTask objects
        for raw_task in raw_tasks:
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
                    warnings.append(
                        f"Unknown task type '{task_type_str}', using 'other'"
                    )

                proposed_task = ProposedTask(
                    title=raw_task.get("title", "Untitled Task")[:255],
                    description=raw_task.get("description"),
                    due_date=due_date,
                    due_time=due_time,
                    task_type=task_type,
                    confidence=float(raw_task.get("confidence", 0.8)),
                )
                proposed_tasks.append(proposed_task)

            except Exception as e:
                logger.warning(f"Failed to parse task: {e}")
                warnings.append(f"Failed to parse one task: {str(e)}")

        logger.info(f"Parsed {len(proposed_tasks)} tasks, {len(warnings)} warnings")

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        warnings.append("AI response was not valid JSON. Please try again.")
    except Exception as e:
        logger.error(f"Schedule parsing error: {e}")
        warnings.append(f"Parsing error: {str(e)}")

    return ParseScheduleResult(
        proposed_tasks=proposed_tasks,
        warnings=warnings,
        assumed_timezone=timezone,
        assumed_reference_date=reference_date,
    )
