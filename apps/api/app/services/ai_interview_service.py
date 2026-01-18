"""AI Interview Analysis Service.

Provides AI-powered summarization for interviews using configured AI provider.
"""

import json
import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SurrogateInterview, InterviewNote, Surrogate
from app.services.ai_provider import ChatMessage, get_provider
from app.services.ai_settings_service import (
    get_ai_settings,
    get_decrypted_key,
    is_consent_required,
)
from app.services.ai_usage_service import log_usage

logger = logging.getLogger(__name__)

NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


INTERVIEW_SUMMARY_PROMPT = """Analyze the following interview transcript and notes for a surrogacy candidate.

TRANSCRIPT:
{transcript}

INTERVIEWER NOTES:
{notes}

Provide a structured analysis in JSON format with exactly these fields:
{{
    "summary": "2-3 paragraph summary of the interview",
    "key_points": ["list of 3-5 key points discussed"],
    "concerns": ["list of any concerns or red flags, empty if none"],
    "sentiment": "one of: positive, neutral, mixed, concerning",
    "follow_up_items": ["list of recommended follow-up actions"]
}}

Be objective and professional. Focus on factual observations from the conversation.
Do not include any personally identifiable information (PII) in your response.
Respond ONLY with the JSON object, no additional text."""


ALL_INTERVIEWS_SUMMARY_PROMPT = """Analyze the following interview transcripts and notes for a surrogacy candidate across multiple interviews.

{interviews_content}

Provide a comprehensive analysis in JSON format with exactly these fields:
{{
    "overall_summary": "2-3 paragraph summary of all interviews combined",
    "timeline": [
        {{"date": "YYYY-MM-DD", "type": "phone/video/in_person", "key_point": "main takeaway"}}
    ],
    "recurring_themes": ["themes that appeared across multiple interviews"],
    "candidate_strengths": ["positive qualities observed"],
    "areas_of_concern": ["concerns or issues to address, empty if none"],
    "recommended_actions": ["next steps based on all interviews"]
}}

Be objective and professional. Focus on patterns and progression across interviews.
Do not include any personally identifiable information (PII) in your response.
Respond ONLY with the JSON object, no additional text."""


class AIInterviewError(Exception):
    """Error during AI interview analysis."""

    pass


def _truncate_text(text: str, max_chars: int = 50000) -> str:
    """Truncate text to stay within token limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... truncated for length ...]"


def _parse_json_response(content: str) -> dict:
    """Parse JSON from AI response, handling potential formatting issues."""
    # Remove markdown code blocks if present
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        return json.loads(content.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise AIInterviewError("Failed to parse AI response")


def _extend_known_names_from_text(
    known_names: list[str],
    text: str | None,
    max_names: int = 20,
) -> None:
    """Add likely full names from text to known_names for anonymization."""
    if not text:
        return
    count = 0
    for match in NAME_PATTERN.finditer(text):
        candidate = match.group(1).strip()
        if candidate and candidate not in known_names:
            known_names.append(candidate)
            count += 1
        if count >= max_names:
            break


def _strip_html(content: str) -> str:
    """Convert HTML content into readable text for AI prompts."""
    import re
    import html as html_module

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", content, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return html_module.unescape(text)


async def summarize_interview(
    db: Session,
    interview: SurrogateInterview,
    org_id: UUID,
    user_id: UUID,
) -> dict:
    """
    Generate AI summary for a single interview.

    Args:
        db: Database session
        interview: The interview to summarize
        org_id: Organization ID
        user_id: User requesting the summary

    Returns:
        dict with summary, key_points, concerns, sentiment, follow_up_items
    """
    # Get AI settings
    ai_settings = get_ai_settings(db, org_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise AIInterviewError("AI features are not enabled for this organization")
    if is_consent_required(ai_settings):
        raise AIInterviewError("AI consent has not been accepted for this organization")

    api_key = get_decrypted_key(ai_settings)
    if not api_key:
        raise AIInterviewError("AI API key not configured")

    # Get transcript text
    transcript = interview.transcript_text or ""
    if not transcript:
        raise AIInterviewError("Interview has no transcript to summarize")

    pii_mapping = None
    known_names: list[str] = []
    if ai_settings.anonymize_pii:
        from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

        pii_mapping = PIIMapping()
        surrogate = (
            db.query(Surrogate)
            .filter(Surrogate.id == interview.surrogate_id, Surrogate.organization_id == org_id)
            .first()
        )
        if surrogate and surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())
        _extend_known_names_from_text(known_names, transcript)
        transcript = anonymize_text(transcript, pii_mapping, known_names)

    # Get notes
    notes = db.scalars(
        select(InterviewNote).where(
            InterviewNote.interview_id == interview.id,
            InterviewNote.organization_id == org_id,
        )
    ).all()
    notes_text = "\n".join([_strip_html(n.content) for n in notes]) if notes else "No notes"
    if ai_settings.anonymize_pii and pii_mapping:
        _extend_known_names_from_text(known_names, notes_text)
        notes_text = anonymize_text(notes_text, pii_mapping, known_names)

    # Build prompt
    prompt = INTERVIEW_SUMMARY_PROMPT.format(
        transcript=_truncate_text(transcript),
        notes=_truncate_text(notes_text, 5000),
    )

    # Get AI provider
    provider = get_provider(
        provider_name=ai_settings.provider,
        api_key=api_key,
        model=ai_settings.model,
    )

    # Call AI
    messages = [
        ChatMessage(role="system", content="You are an expert interview analyst."),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.chat(
            messages=messages,
            temperature=0.3,  # Lower for more consistent output
            max_tokens=2000,
        )

        # Parse response
        result = _parse_json_response(response.content)
        if ai_settings.anonymize_pii and pii_mapping:
            result = rehydrate_data(result, pii_mapping)

        # Record usage
        log_usage(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
        )

        return {
            "interview_id": str(interview.id),
            "summary": result.get("summary", ""),
            "key_points": result.get("key_points", []),
            "concerns": result.get("concerns", []),
            "sentiment": result.get("sentiment", "neutral"),
            "follow_up_items": result.get("follow_up_items", []),
        }

    except Exception as e:
        logger.exception("Error generating interview summary")
        raise AIInterviewError(f"Failed to generate summary: {str(e)}")


async def summarize_all_interviews(
    db: Session,
    surrogate_id: UUID,
    org_id: UUID,
    user_id: UUID,
) -> dict:
    """
    Generate AI summary for all interviews of a surrogate.

    Args:
        db: Database session
        surrogate_id: Surrogate ID
        org_id: Organization ID
        user_id: User requesting the summary

    Returns:
        dict with overall_summary, timeline, themes, strengths, concerns, actions
    """
    # Get AI settings
    ai_settings = get_ai_settings(db, org_id)
    if not ai_settings or not ai_settings.is_enabled:
        raise AIInterviewError("AI features are not enabled for this organization")
    if is_consent_required(ai_settings):
        raise AIInterviewError("AI consent has not been accepted for this organization")

    api_key = get_decrypted_key(ai_settings)
    if not api_key:
        raise AIInterviewError("AI API key not configured")

    # Get all interviews for the surrogate
    interviews = db.scalars(
        select(SurrogateInterview)
        .where(
            SurrogateInterview.surrogate_id == surrogate_id,
            SurrogateInterview.organization_id == org_id,
        )
        .order_by(SurrogateInterview.conducted_at)
    ).all()

    if not interviews:
        raise AIInterviewError("No interviews found for this surrogate")

    pii_mapping = None
    known_names: list[str] = []
    if ai_settings.anonymize_pii:
        from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_data

        pii_mapping = PIIMapping()
        surrogate = (
            db.query(Surrogate)
            .filter(Surrogate.id == surrogate_id, Surrogate.organization_id == org_id)
            .first()
        )
        if surrogate and surrogate.full_name:
            known_names.append(surrogate.full_name)
            known_names.extend(surrogate.full_name.split())

    # Build content for all interviews
    interviews_content = []
    for interview in interviews:
        transcript = interview.transcript_text or "No transcript"
        notes = db.scalars(
            select(InterviewNote).where(
                InterviewNote.interview_id == interview.id,
                InterviewNote.organization_id == org_id,
            )
        ).all()
        notes_text = "\n".join([_strip_html(n.content) for n in notes]) if notes else "No notes"
        if ai_settings.anonymize_pii and pii_mapping:
            _extend_known_names_from_text(known_names, transcript)
            _extend_known_names_from_text(known_names, notes_text)
            transcript = anonymize_text(transcript, pii_mapping, known_names)
            notes_text = anonymize_text(notes_text, pii_mapping, known_names)

        interviews_content.append(
            f"""--- Interview {len(interviews_content) + 1} ---
Date: {interview.conducted_at.strftime("%Y-%m-%d")}
Type: {interview.interview_type}
Duration: {interview.duration_minutes or "unknown"} minutes

Transcript:
{_truncate_text(transcript, 10000)}

Notes:
{_truncate_text(notes_text, 2000)}
"""
        )

    combined_content = "\n\n".join(interviews_content)

    # Build prompt
    prompt = ALL_INTERVIEWS_SUMMARY_PROMPT.format(
        interviews_content=_truncate_text(combined_content, 60000)
    )

    # Get AI provider
    provider = get_provider(
        provider_name=ai_settings.provider,
        api_key=api_key,
        model=ai_settings.model,
    )

    # Call AI
    messages = [
        ChatMessage(
            role="system",
            content="You are an expert interview analyst specializing in candidate evaluation.",
        ),
        ChatMessage(role="user", content=prompt),
    ]

    try:
        response = await provider.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=3000,
        )

        # Parse response
        result = _parse_json_response(response.content)
        if ai_settings.anonymize_pii and pii_mapping:
            result = rehydrate_data(result, pii_mapping)

        # Record usage
        log_usage(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
        )

        return {
            "surrogate_id": str(surrogate_id),
            "interview_count": len(interviews),
            "overall_summary": result.get("overall_summary", ""),
            "timeline": result.get("timeline", []),
            "recurring_themes": result.get("recurring_themes", []),
            "candidate_strengths": result.get("candidate_strengths", []),
            "areas_of_concern": result.get("areas_of_concern", []),
            "recommended_actions": result.get("recommended_actions", []),
        }

    except Exception as e:
        logger.exception("Error generating all interviews summary")
        raise AIInterviewError(f"Failed to generate summary: {str(e)}")
