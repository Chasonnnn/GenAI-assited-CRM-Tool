"""PDF export service using Playwright for headless rendering."""

import asyncio
import base64
import html
import math
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_export_token
from app.db.models import Attachment, SurrogateInterview, FormSubmission
from app.services import (
    form_service,
    interview_service,
    journey_service,
    profile_service,
    tiptap_service,
)


# Chart colors matching frontend design system
CHART_COLORS = [
    "#3b82f6",  # Blue
    "#22c55e",  # Green
    "#f59e0b",  # Amber
    "#a855f7",  # Purple
    "#06b6d4",  # Cyan
    "#ef4444",  # Red
    "#ec4899",  # Pink
    "#8b5cf6",  # Violet
]


async def _render_html_to_pdf(html_content: str) -> bytes:
    """Render HTML content to PDF using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "0.75in", "bottom": "0.75in", "left": "0.75in", "right": "0.75in"},
        )
        await browser.close()
        return pdf_bytes


async def _render_url_to_pdf(url: str) -> bytes:
    """Render a URL to PDF using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(url, wait_until="networkidle")
        await page.emulate_media(media="screen")
        await page.wait_for_selector("[data-journey-print='ready']")
        pdf_bytes = await page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "0.75in", "bottom": "0.75in", "left": "0.75in", "right": "0.75in"},
        )
        await browser.close()
        return pdf_bytes


def _load_file_bytes(storage_key: str) -> tuple[bytes | None, str | None]:
    """Load file bytes from configured storage backend."""
    from app.services.attachment_service import (
        _get_local_storage_path,
        _get_s3_client,
        _get_storage_backend,
    )

    backend = _get_storage_backend()
    if backend == "s3":
        bucket = getattr(settings, "S3_BUCKET", "crm-attachments")
        try:
            obj = _get_s3_client().get_object(Bucket=bucket, Key=storage_key)
        except Exception:
            return None, None
        return obj["Body"].read(), obj.get("ContentType")

    path = os.path.join(_get_local_storage_path(), storage_key)
    if not os.path.exists(path):
        return None, None
    with open(path, "rb") as f:
        return f.read(), None


def _build_file_section(
    files: list[dict[str, Any]],
    hidden: bool,
) -> str:
    """Render file attachment section."""
    if not files:
        return ""

    if hidden:
        return """
        <div class="section">
            <h2>Attachments</h2>
            <div class="field-row">
                <span class="field-label">Attachments</span>
                <span class="field-value masked">********</span>
            </div>
        </div>
        """

    items_html = ""
    for file in files:
        filename = html.escape(file["filename"])
        size_label = _format_file_size(file["file_size"])
        items_html += f"""
        <div class="attachment">
            <div class="attachment-title">{filename}</div>
            <div class="attachment-meta">{size_label}</div>
        </div>
        """

        if file["content_type"].startswith("image/") and file.get("data_url"):
            items_html += f"""
            <div class="attachment-image">
                <img src="{file["data_url"]}" alt="{filename}" />
            </div>
            """

    return f"""
    <div class="section">
        <h2>Attachments</h2>
        {items_html}
    </div>
    """


def _generate_submission_html(
    title: str,
    surrogate_name: str,
    org_name: str,
    schema: dict[str, Any],
    answers: dict[str, Any],
    files: list[dict[str, Any]],
    hidden_fields: set[str] | None = None,
) -> str:
    """Generate HTML for submission/profile export."""
    hidden_fields = hidden_fields or set()
    pages = schema.get("pages") or []

    sections_html = ""
    for page in pages:
        page_title = html.escape(page.get("title") or "Section")
        fields_html = ""

        for field in page.get("fields") or []:
            field_key = field.get("key", "")
            label = html.escape(field.get("label") or field_key)
            is_hidden = field_key in hidden_fields

            if field.get("type") == "file":
                value_display = (
                    '<span class="masked">********</span>'
                    if is_hidden
                    else f'<span class="muted">{len(files)} file(s) attached</span>'
                )
            elif is_hidden:
                value_display = '<span class="masked">********</span>'
            else:
                raw_value = answers.get(field_key)
                value_display = _format_value(raw_value)

            fields_html += f"""
            <div class="field-row">
                <span class="field-label">{label}</span>
                <span class="field-value">{value_display}</span>
            </div>
            """

        sections_html += f"""
        <div class="section">
            <h2>{page_title}</h2>
            {fields_html}
        </div>
        """

    file_field_keys = {
        field.get("key")
        for page in pages
        for field in page.get("fields") or []
        if field.get("type") == "file"
    }
    attachments_hidden = bool(file_field_keys) and file_field_keys.issubset(hidden_fields)

    attachments_html = _build_file_section(files, hidden=attachments_hidden)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(title)} - {html.escape(surrogate_name)}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
            background: white;
        }}
        .header {{
            border-bottom: 2px solid #14b8a6;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 22pt;
            font-weight: 600;
            color: #0f172a;
        }}
        .header .subtitle {{
            font-size: 10pt;
            color: #64748b;
            margin-top: 4px;
        }}
        .muted {{
            color: #94a3b8;
        }}
        .section {{
            margin-bottom: 24px;
            page-break-inside: avoid;
        }}
        .section h2 {{
            font-size: 13pt;
            font-weight: 600;
            color: #14b8a6;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }}
        .field-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .field-row:last-child {{
            border-bottom: none;
        }}
        .field-label {{
            font-weight: 500;
            color: #64748b;
            flex-shrink: 0;
        }}
        .field-value {{
            text-align: right;
            color: #1e293b;
            max-width: 60%;
        }}
        .masked {{
            font-family: monospace;
            color: #94a3b8;
            letter-spacing: 2px;
        }}
        .attachment {{
            margin-bottom: 8px;
        }}
        .attachment-title {{
            font-weight: 600;
            color: #0f172a;
        }}
        .attachment-meta {{
            font-size: 9pt;
            color: #94a3b8;
        }}
        .attachment-image {{
            margin: 12px 0 20px;
        }}
        .attachment-image img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 9pt;
            color: #94a3b8;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(surrogate_name)}</h1>
        <div class="subtitle">{html.escape(title)} • {datetime.now().strftime("%B %d, %Y")}{" • " + html.escape(org_name) if org_name else ""}</div>
    </div>
    
    {sections_html}

    {attachments_html}
    
    <div class="footer">
        Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} • Confidential
    </div>
</body>
</html>"""


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


def _build_transcript_html(interview_data: dict[str, Any]) -> str:
    transcript_json = interview_data.get("transcript_json")
    transcript_text = ""
    if transcript_json:
        try:
            transcript_text = tiptap_service.tiptap_to_text(transcript_json)
        except Exception:
            transcript_text = ""

    if not transcript_text:
        if interview_data.get("is_transcript_offloaded"):
            return '<div class="muted">Transcript is stored externally.</div>'
        return '<div class="muted">No transcript available.</div>'

    escaped = html.escape(transcript_text).replace("\n", "<br>")
    return f'<div class="transcript">{escaped}</div>'


def _render_note_html(note: dict[str, Any], depth: int = 0) -> str:
    author = html.escape(note.get("author_name") or "Unknown")
    created_at = _format_datetime(note.get("created_at"))
    anchor_text = note.get("anchor_text") or "General"
    anchor = html.escape(anchor_text)
    content = note.get("content") or ""
    content_html = content or '<span class="muted">—</span>'
    margin = depth * 16

    replies_html = ""
    for reply in note.get("replies") or []:
        replies_html += _render_note_html(reply, depth + 1)

    return f"""
    <div class="note" style="margin-left: {margin}px;">
        <div class="note-meta">
            <span class="note-author">{author}</span>
            <span class="note-date">{created_at}</span>
        </div>
        <div class="note-anchor">Anchor: {anchor}</div>
        <div class="note-content">{content_html}</div>
    </div>
    {replies_html}
    """


def _build_notes_html(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return '<div class="muted">No notes.</div>'
    return "".join(_render_note_html(note) for note in notes)


def _build_attachments_html(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return '<div class="muted">No attachments.</div>'

    items = ""
    for attachment in attachments:
        filename = html.escape(attachment.get("filename") or "Unknown file")
        size = _format_file_size(int(attachment.get("file_size") or 0))
        items += f"<li>{filename} • {size}</li>"
    return f'<ul class="attachment-list">{items}</ul>'


def _generate_interview_export_html(
    title: str,
    surrogate_name: str,
    org_name: str,
    exports: list[dict[str, Any]],
) -> str:
    sections_html = ""
    for index, payload in enumerate(exports, start=1):
        interview = payload["interview"]
        notes_html = _build_notes_html(payload.get("notes") or [])
        attachments_html = _build_attachments_html(payload.get("attachments") or [])
        transcript_html = _build_transcript_html(interview)

        conducted_at = _format_datetime(interview.get("conducted_at"))
        conducted_by = html.escape(interview.get("conducted_by_name") or "Unknown")
        interview_type = html.escape(interview.get("interview_type") or "Interview")
        status = html.escape(interview.get("status") or "unknown")
        duration = interview.get("duration_minutes")
        duration_label = f"{duration} min" if duration else "—"

        sections_html += f"""
        <div class="section">
            <h2>Interview {index}</h2>
            <div class="field-row">
                <span class="field-label">Type</span>
                <span class="field-value">{interview_type}</span>
            </div>
            <div class="field-row">
                <span class="field-label">Status</span>
                <span class="field-value">{status}</span>
            </div>
            <div class="field-row">
                <span class="field-label">Conducted At</span>
                <span class="field-value">{conducted_at}</span>
            </div>
            <div class="field-row">
                <span class="field-label">Conducted By</span>
                <span class="field-value">{conducted_by}</span>
            </div>
            <div class="field-row">
                <span class="field-label">Duration</span>
                <span class="field-value">{duration_label}</span>
            </div>

            <div class="section-block">
                <h3>Transcript</h3>
                {transcript_html}
            </div>

            <div class="section-block">
                <h3>Notes</h3>
                {notes_html}
            </div>

            <div class="section-block">
                <h3>Attachments</h3>
                {attachments_html}
            </div>
        </div>
        """
        if index < len(exports):
            sections_html += '<div class="page-break"></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(title)} - {html.escape(surrogate_name)}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
            background: white;
        }}
        .header {{
            border-bottom: 2px solid #14b8a6;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 22pt;
            font-weight: 600;
            color: #0f172a;
        }}
        .header .subtitle {{
            font-size: 10pt;
            color: #64748b;
            margin-top: 4px;
        }}
        .muted {{
            color: #94a3b8;
        }}
        .section {{
            margin-bottom: 24px;
            page-break-inside: avoid;
        }}
        .section h2 {{
            font-size: 13pt;
            font-weight: 600;
            color: #14b8a6;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }}
        .field-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px solid #f1f5f9;
        }}
        .field-row:last-child {{
            border-bottom: none;
        }}
        .field-label {{
            font-weight: 500;
            color: #64748b;
            flex-shrink: 0;
        }}
        .field-value {{
            text-align: right;
            color: #1e293b;
            max-width: 60%;
        }}
        .section-block {{
            margin-top: 16px;
        }}
        .section-block h3 {{
            font-size: 11pt;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 8px;
        }}
        .transcript {{
            white-space: pre-wrap;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            background: #f8fafc;
            color: #0f172a;
        }}
        .note {{
            border-left: 3px solid #14b8a6;
            padding-left: 12px;
            margin-bottom: 12px;
        }}
        .note-meta {{
            font-size: 9pt;
            color: #64748b;
            display: flex;
            justify-content: space-between;
        }}
        .note-anchor {{
            font-size: 9pt;
            color: #64748b;
            margin-bottom: 6px;
        }}
        .note-content {{
            color: #0f172a;
        }}
        .attachment-list {{
            padding-left: 16px;
        }}
        .attachment-list li {{
            margin-bottom: 4px;
        }}
        .page-break {{
            page-break-after: always;
        }}
        .footer {{
            margin-top: 24px;
            font-size: 9pt;
            color: #94a3b8;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(title)}</h1>
        <div class="subtitle">{html.escape(org_name)} • {html.escape(surrogate_name)}</div>
    </div>

    {sections_html}

    <div class="footer">
        Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} • Confidential
    </div>
</body>
</html>"""


def _format_value(value: Any) -> str:
    """Format a value for HTML display."""
    if value is None or value == "":
        return '<span style="color: #94a3b8;">—</span>'

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, list):
        if not value:
            return '<span style="color: #94a3b8;">—</span>'
        return html.escape(", ".join(str(v) for v in value))

    return html.escape(str(value))


def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _collect_submission_files(files) -> list[dict[str, Any]]:
    file_entries: list[dict[str, Any]] = []
    for file_record in files:
        if file_record.quarantined:
            continue
        data_url = None
        if file_record.content_type.startswith("image/"):
            content, detected_type = _load_file_bytes(file_record.storage_key)
            if content:
                encoded = base64.b64encode(content).decode("ascii")
                mime = detected_type or file_record.content_type
                data_url = f"data:{mime};base64,{encoded}"

        file_entries.append(
            {
                "filename": file_record.filename,
                "content_type": file_record.content_type,
                "file_size": file_record.file_size,
                "storage_key": file_record.storage_key,
                "data_url": data_url,
            }
        )
    return file_entries


def export_submission_pdf(
    db: Session,
    submission_id: uuid.UUID,
    org_id: uuid.UUID,
    surrogate_name: str,
    org_name: str = "",
) -> bytes:
    """Export a form submission as PDF."""
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.id == submission_id,
            FormSubmission.organization_id == org_id,
        )
        .first()
    )
    if not submission:
        raise ValueError("Submission not found")

    schema = submission.schema_snapshot or {}
    files = form_service.list_submission_files(db, org_id, submission.id)
    file_entries = _collect_submission_files(files)

    html_content = _generate_submission_html(
        title="Application Export",
        surrogate_name=surrogate_name,
        org_name=org_name,
        schema=schema,
        answers=submission.answers_json or {},
        files=file_entries,
    )

    loop = asyncio.new_event_loop()
    try:
        pdf_bytes = loop.run_until_complete(_render_html_to_pdf(html_content))
    finally:
        loop.close()

    return pdf_bytes


def export_profile_pdf(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
    surrogate_name: str,
    org_name: str = "",
) -> bytes:
    """
    Export a case profile as PDF.

    Args:
        db: Database session
        org_id: Organization ID
        surrogate_id: Surrogate ID
        surrogate_name: Display name for the case
        org_name: Organization name for header

    Returns:
        PDF file content as bytes
    """
    # Get profile data
    profile_data = profile_service.get_profile_data(db, org_id, surrogate_id)
    hidden_fields = set(profile_data.get("hidden_fields") or [])

    base_submission_id = profile_data.get("base_submission_id")
    if not base_submission_id:
        raise ValueError("No submission available for export")

    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.id == base_submission_id,
            FormSubmission.organization_id == org_id,
        )
        .first()
    )
    if not submission:
        raise ValueError("Submission not found")

    schema = submission.schema_snapshot or {}
    files = form_service.list_submission_files(db, org_id, submission.id)
    file_entries = _collect_submission_files(files)

    html_content = _generate_submission_html(
        title="Profile Card Export",
        surrogate_name=surrogate_name,
        org_name=org_name,
        schema=schema,
        answers=profile_data.get("merged_view") or {},
        files=file_entries,
        hidden_fields=hidden_fields,
    )

    # Render to PDF (run async in sync context)
    loop = asyncio.new_event_loop()
    try:
        pdf_bytes = loop.run_until_complete(_render_html_to_pdf(html_content))
    finally:
        loop.close()

    return pdf_bytes


def export_interview_pdf(
    db: Session,
    org_id: uuid.UUID,
    interview: SurrogateInterview,
    surrogate_name: str,
    org_name: str,
    current_user_id: uuid.UUID,
) -> bytes:
    """Export a single interview as PDF."""
    exports = interview_service.build_interview_exports(
        db=db,
        org_id=org_id,
        interviews=[interview],
        current_user_id=current_user_id,
    )
    payload = exports.get(interview.id)
    if not payload:
        raise ValueError("Interview not found")

    html_content = _generate_interview_export_html(
        title="Interview Export",
        surrogate_name=surrogate_name,
        org_name=org_name,
        exports=[payload],
    )

    loop = asyncio.new_event_loop()
    try:
        pdf_bytes = loop.run_until_complete(_render_html_to_pdf(html_content))
    finally:
        loop.close()

    return pdf_bytes


def export_interviews_pdf(
    db: Session,
    org_id: uuid.UUID,
    interviews: list[SurrogateInterview],
    surrogate_name: str,
    org_name: str,
    current_user_id: uuid.UUID,
) -> bytes:
    """Export all interviews for a case as a single PDF."""
    if not interviews:
        raise ValueError("No interviews found")

    exports = interview_service.build_interview_exports(
        db=db,
        org_id=org_id,
        interviews=interviews,
        current_user_id=current_user_id,
    )
    ordered_exports = [exports[interview.id] for interview in interviews if interview.id in exports]
    if not ordered_exports:
        raise ValueError("No interviews found")

    html_content = _generate_interview_export_html(
        title="Interview Export",
        surrogate_name=surrogate_name,
        org_name=org_name,
        exports=ordered_exports,
    )

    loop = asyncio.new_event_loop()
    try:
        pdf_bytes = loop.run_until_complete(_render_html_to_pdf(html_content))
    finally:
        loop.close()

    return pdf_bytes


# =============================================================================
# SVG Chart Generation Utilities
# =============================================================================


def _generate_horizontal_bar_chart_svg(
    data: list[dict],
    label_key: str,
    value_key: str,
    title: str,
    color: str = "#22c55e",
    width: int = 500,
    height: int = 200,
) -> str:
    """Generate SVG horizontal bar chart (for Team Performance)."""
    if not data:
        return ""

    display_data = data[:8]
    values = [d.get(value_key, 0) for d in display_data]
    max_value = max(values) if values else 1
    if max_value == 0:
        max_value = 1

    bar_height = 18
    gap = 8
    margin_left = 130
    margin_right = 50
    chart_width = width - margin_left - margin_right

    bars = []
    for i, item in enumerate(display_data):
        label = str(item.get(label_key, "Unknown"))[:22]
        value = item.get(value_key, 0)
        bar_width = (value / max_value) * chart_width if max_value > 0 else 0
        y = 35 + i * (bar_height + gap)
        bar_color = CHART_COLORS[i % len(CHART_COLORS)]

        bars.append(f'''
            <text x="{margin_left - 8}" y="{y + 13}" text-anchor="end" font-size="11" fill="#64748b">{html.escape(label)}</text>
            <rect x="{margin_left}" y="{y}" width="{max(bar_width, 2)}" height="{bar_height}" fill="{bar_color}" rx="4"/>
            <text x="{margin_left + bar_width + 8}" y="{y + 13}" font-size="11" fill="#1e293b">{value}</text>
        ''')

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="20" text-anchor="middle" font-weight="600" font-size="13" fill="#0f172a">{html.escape(title)}</text>
            {"".join(bars)}
        </svg>
    '''


def _generate_vertical_bar_chart_svg(
    data: list[dict],
    label_key: str,
    value_key: str,
    title: str,
    width: int = 500,
    height: int = 280,
) -> str:
    """Generate SVG vertical bar chart (for Surrogates by Stage)."""
    if not data:
        return ""

    display_data = data[:8]
    values = [d.get(value_key, 0) for d in display_data]
    labels = [str(d.get(label_key, "Unknown"))[:12] for d in display_data]
    max_value = max(values) if values else 1
    if max_value == 0:
        max_value = 1

    margin = {"top": 40, "right": 20, "bottom": 60, "left": 40}
    chart_width = width - margin["left"] - margin["right"]
    chart_height = height - margin["top"] - margin["bottom"]

    bar_width = min(50, (chart_width / len(display_data)) * 0.7)
    bar_gap = (chart_width - bar_width * len(display_data)) / (len(display_data) + 1)

    # Grid lines
    grid_lines = []
    for i in range(5):
        y = margin["top"] + (i / 4) * chart_height
        val = int(max_value * (1 - i / 4))
        grid_lines.append(
            f'<line x1="{margin["left"]}" y1="{y}" x2="{width - margin["right"]}" y2="{y}" stroke="#e2e8f0" stroke-width="1"/>'
        )
        grid_lines.append(
            f'<text x="{margin["left"] - 8}" y="{y + 4}" text-anchor="end" font-size="10" fill="#94a3b8">{val}</text>'
        )

    bars = []
    for i, (label, value) in enumerate(zip(labels, values)):
        bar_height_px = (value / max_value) * chart_height if max_value > 0 else 0
        x = margin["left"] + bar_gap + i * (bar_width + bar_gap)
        y = margin["top"] + chart_height - bar_height_px
        color = CHART_COLORS[i % len(CHART_COLORS)]

        bars.append(f'''
            <rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height_px}" fill="{color}" rx="4"/>
            <text x="{x + bar_width / 2}" y="{height - margin["bottom"] + 15}" text-anchor="middle" font-size="9" fill="#64748b" transform="rotate(-30 {x + bar_width / 2} {height - margin["bottom"] + 15})">{html.escape(label)}</text>
        ''')

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="20" text-anchor="middle" font-weight="600" font-size="13" fill="#0f172a">{html.escape(title)}</text>
            {"".join(grid_lines)}
            {"".join(bars)}
        </svg>
    '''


def _generate_line_chart_svg(
    data: list[dict],
    title: str,
    width: int = 500,
    height: int = 200,
) -> str:
    """Generate SVG line chart for trend data."""
    if not data or len(data) < 2:
        return ""

    display_data = data[-14:] if len(data) > 14 else data
    values = [d.get("count", 0) for d in display_data]
    dates = [d.get("date", "")[-5:] for d in display_data]  # MM-DD format

    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    margin = {"top": 35, "right": 20, "bottom": 45, "left": 45}
    chart_width = width - margin["left"] - margin["right"]
    chart_height = height - margin["top"] - margin["bottom"]

    # Calculate points
    points = []
    for i, val in enumerate(values):
        x = margin["left"] + (i / max(len(values) - 1, 1)) * chart_width
        y = margin["top"] + chart_height - (val / max_val) * chart_height
        points.append((x, y))

    # Build path
    path_d = f"M{points[0][0]},{points[0][1]}"
    for x, y in points[1:]:
        path_d += f" L{x},{y}"

    path = f'<path d="{path_d}" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'

    # Grid lines
    grid_lines = []
    for i in range(5):
        y = margin["top"] + (i / 4) * chart_height
        grid_lines.append(
            f'<line x1="{margin["left"]}" y1="{y}" x2="{width - margin["right"]}" y2="{y}" stroke="#e2e8f0" stroke-width="1"/>'
        )

    # Dots and x-axis labels
    dots = []
    labels = []
    for i, ((x, y), val, date) in enumerate(zip(points, values, dates)):
        dots.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#3b82f6"/>')
        dots.append(f'<circle cx="{x}" cy="{y}" r="2" fill="white"/>')
        # Show every other label if many points
        if i % 2 == 0 or len(values) <= 7:
            labels.append(
                f'<text x="{x}" y="{height - 12}" text-anchor="middle" font-size="9" fill="#64748b">{date}</text>'
            )

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="20" text-anchor="middle" font-weight="600" font-size="13" fill="#0f172a">{html.escape(title)}</text>
            {"".join(grid_lines)}
            {path}
            {"".join(dots)}
            {"".join(labels)}
        </svg>
    '''


def _generate_pie_chart_svg(
    data: list[dict],
    label_key: str,
    value_key: str,
    title: str,
    colors: list[str] | None = None,
    width: int = 500,
    height: int = 220,
) -> str:
    """Generate SVG pie chart with legend."""
    if not data:
        return ""

    colors = colors or CHART_COLORS
    display_data = data[:6]
    values = [d.get(value_key, 0) for d in display_data]
    labels = [str(d.get(label_key, "Unknown"))[:18] for d in display_data]
    total = sum(values)

    if total == 0:
        return ""

    cx, cy, r = 130, 120, 75
    current_angle = -90  # Start from top

    slices = []
    legend = []

    for i, (label, value) in enumerate(zip(labels, values)):
        if value == 0:
            continue

        pct = value / total
        angle = pct * 360
        end_angle = current_angle + angle
        large_arc = 1 if angle > 180 else 0
        color = colors[i % len(colors)]

        # Calculate arc path
        x1 = cx + r * math.cos(math.radians(current_angle))
        y1 = cy + r * math.sin(math.radians(current_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))

        if pct >= 0.999:  # Full circle
            slices.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
        else:
            slices.append(f'''
                <path d="M{cx},{cy} L{x1},{y1} A{r},{r} 0 {large_arc},1 {x2},{y2} Z"
                      fill="{color}" stroke="white" stroke-width="2"/>
            ''')

        # Legend entry
        ly = 35 + i * 24
        legend.append(f'''
            <rect x="280" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>
            <text x="300" y="{ly + 11}" font-size="11" fill="#1e293b">{html.escape(label)} ({value})</text>
        ''')

        current_angle = end_angle

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="20" text-anchor="middle" font-weight="600" font-size="13" fill="#0f172a">{html.escape(title)}</text>
            {"".join(slices)}
            {"".join(legend)}
        </svg>
    '''


# =============================================================================
# AI Insights Computation
# =============================================================================


def _compute_insights(trend_data: list, surrogates_by_status: list) -> dict:
    """Compute AI insights from trend and status data (mirrors frontend logic)."""
    insights = {
        "trend": "Trend: not enough data yet.",
        "anomaly": "Anomalies: not enough daily data.",
        "bottleneck": "Bottleneck: no dominant stage yet.",
    }

    # Trend computation
    if trend_data and len(trend_data) >= 2:
        midpoint = len(trend_data) // 2
        first_half = sum(d.get("count", 0) for d in trend_data[:midpoint])
        second_half = sum(d.get("count", 0) for d in trend_data[midpoint:])

        if first_half == 0:
            pct = 100 if second_half > 0 else 0
        else:
            pct = round(((second_half - first_half) / first_half) * 100)

        if pct >= 0:
            insights["trend"] = f"Trend: up {pct}% vs prior period."
        else:
            insights["trend"] = f"Trend: down {abs(pct)}% vs prior period."

    # Anomaly detection
    if trend_data and len(trend_data) >= 4:
        counts = [d.get("count", 0) for d in trend_data]
        average = sum(counts) / len(counts) if counts else 0

        if average > 0:
            max_point = max(trend_data, key=lambda x: x.get("count", 0))
            min_point = min(trend_data, key=lambda x: x.get("count", 0))

            spike_delta = (max_point.get("count", 0) - average) / average
            dip_delta = (average - min_point.get("count", 0)) / average

            if spike_delta >= 0.6:
                date = max_point.get("date", "")[-5:]
                insights["anomaly"] = (
                    f"Anomaly: spike on {date} ({max_point.get('count', 0)} surrogates, +{round(spike_delta * 100)}% vs avg)."
                )
            elif dip_delta >= 0.6:
                date = min_point.get("date", "")[-5:]
                insights["anomaly"] = (
                    f"Anomaly: dip on {date} ({min_point.get('count', 0)} surrogates, -{round(dip_delta * 100)}% vs avg)."
                )
            else:
                insights["anomaly"] = "Anomalies: no major spikes or dips."
        else:
            insights["anomaly"] = "Anomalies: no volume yet."

    # Bottleneck detection
    if surrogates_by_status:
        total = sum(item.get("count", 0) for item in surrogates_by_status)
        if total > 0:
            top = max(surrogates_by_status, key=lambda x: x.get("count", 0))
            top_pct = round((top.get("count", 0) / total) * 100)
            status_name = top.get("status", "Unknown").replace("_", " ").title()
            insights["bottleneck"] = (
                f"Bottleneck: {status_name} holds {top_pct}% of active surrogates."
            )

    return insights


# =============================================================================
# Funnel Chart SVG
# =============================================================================


def _generate_funnel_svg(
    data: list,
    title: str = "Conversion Funnel",
    width: int = 500,
    height: int = 300,
) -> str:
    """Generate SVG funnel chart."""
    if not data:
        return ""

    # Filter to stages with counts
    stages = [d for d in data if d.get("count", 0) > 0 or d.get("stage")]
    if not stages:
        return ""

    max_count = max((d.get("count", 0) for d in stages), default=1) or 1
    margin = {"top": 40, "right": 120, "bottom": 20, "left": 20}
    chart_width = width - margin["left"] - margin["right"]
    chart_height = height - margin["top"] - margin["bottom"]

    stage_height = chart_height / len(stages)
    funnel_colors = ["#3b82f6", "#06b6d4", "#22c55e", "#84cc16", "#eab308", "#f97316"]

    shapes = []
    for i, stage in enumerate(stages):
        count = stage.get("count", 0)
        label = stage.get("stage", stage.get("label", f"Stage {i + 1}"))
        pct = stage.get("percentage", (count / max_count * 100) if max_count > 0 else 0)

        # Calculate trapezoid widths (narrowing as we go down)
        top_width = chart_width * (1 - i * 0.12)
        bottom_width = chart_width * (1 - (i + 1) * 0.12)

        y = margin["top"] + i * stage_height
        top_x = margin["left"] + (chart_width - top_width) / 2
        bottom_x = margin["left"] + (chart_width - bottom_width) / 2

        color = funnel_colors[i % len(funnel_colors)]

        # Draw trapezoid
        shapes.append(f'''
            <polygon points="{top_x},{y} {top_x + top_width},{y} {bottom_x + bottom_width},{y + stage_height} {bottom_x},{y + stage_height}"
                     fill="{color}" stroke="white" stroke-width="2"/>
            <text x="{margin["left"] + chart_width / 2}" y="{y + stage_height / 2 + 5}"
                  text-anchor="middle" font-size="12" fill="white" font-weight="600">{count}</text>
        ''')

        # Label on the right
        shapes.append(f'''
            <text x="{width - margin["right"] + 10}" y="{y + stage_height / 2 + 5}"
                  font-size="10" fill="#64748b">{html.escape(str(label)[:20])} ({pct:.0f}%)</text>
        ''')

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="20" text-anchor="middle" font-weight="600" font-size="13" fill="#0f172a">{html.escape(title)}</text>
            {"".join(shapes)}
        </svg>
    '''


# =============================================================================
# US Map SVG (Simplified)
# =============================================================================

# Simplified US state paths (centroids for circles instead of full paths for simplicity)
US_STATE_POSITIONS = {
    "AL": (530, 340),
    "AK": (135, 445),
    "AZ": (195, 320),
    "AR": (455, 310),
    "CA": (105, 250),
    "CO": (270, 250),
    "CT": (620, 175),
    "DE": (605, 220),
    "FL": (570, 400),
    "GA": (550, 340),
    "HI": (230, 445),
    "ID": (175, 145),
    "IL": (480, 230),
    "IN": (510, 230),
    "IA": (430, 195),
    "KS": (360, 265),
    "KY": (525, 270),
    "LA": (455, 375),
    "ME": (645, 105),
    "MD": (590, 225),
    "MA": (635, 165),
    "MI": (515, 165),
    "MN": (410, 135),
    "MS": (490, 345),
    "MO": (440, 265),
    "MT": (220, 105),
    "NE": (350, 210),
    "NV": (150, 220),
    "NH": (630, 140),
    "NJ": (610, 200),
    "NM": (250, 320),
    "NY": (595, 165),
    "NC": (575, 290),
    "ND": (350, 110),
    "OH": (540, 225),
    "OK": (375, 310),
    "OR": (120, 130),
    "PA": (575, 200),
    "RI": (635, 175),
    "SC": (565, 320),
    "SD": (350, 155),
    "TN": (515, 295),
    "TX": (340, 380),
    "UT": (205, 230),
    "VT": (620, 130),
    "VA": (575, 255),
    "WA": (135, 85),
    "WV": (555, 250),
    "WI": (460, 155),
    "WY": (260, 175),
    "DC": (595, 235),
}


def _generate_us_map_svg(
    data: list,
    title: str = "Surrogates by State",
    width: int = 700,
    height: int = 480,
) -> str:
    """Generate simplified US map with state circles colored by case count."""
    if not data:
        return ""

    # Build state -> count mapping
    state_counts = {d.get("state", ""): d.get("count", 0) for d in data}
    max_count = max(state_counts.values(), default=1) or 1

    # Color scale from light to dark blue
    def get_color(count: int) -> str:
        if count == 0:
            return "#f1f5f9"  # Light gray for no surrogates
        intensity = count / max_count
        if intensity < 0.25:
            return "#bfdbfe"  # blue-200
        elif intensity < 0.5:
            return "#60a5fa"  # blue-400
        elif intensity < 0.75:
            return "#3b82f6"  # blue-500
        else:
            return "#1d4ed8"  # blue-700

    circles = []
    for state, (x, y) in US_STATE_POSITIONS.items():
        count = state_counts.get(state, 0)
        color = get_color(count)
        radius = 12 if count > 0 else 8

        circles.append(f'''
            <circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="#fff" stroke-width="1"/>
            <text x="{x}" y="{y + 4}" text-anchor="middle" font-size="8" fill="{"#fff" if count > 0 else "#64748b"}" font-weight="500">{state}</text>
        ''')

    # Legend
    legend = f"""
        <g transform="translate(580, 400)">
            <text x="0" y="0" font-size="10" fill="#64748b" font-weight="600">Legend</text>
            <circle cx="10" cy="20" r="8" fill="#f1f5f9" stroke="#e2e8f0"/>
            <text x="25" y="24" font-size="9" fill="#64748b">0</text>
            <circle cx="10" cy="40" r="8" fill="#bfdbfe"/>
            <text x="25" y="44" font-size="9" fill="#64748b">1-{max(1, int(max_count * 0.25))}</text>
            <circle cx="10" cy="60" r="8" fill="#3b82f6"/>
            <text x="25" y="64" font-size="9" fill="#64748b">{int(max_count * 0.5)}-{max_count}</text>
        </g>
    """

    return f'''
        <svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <text x="{width / 2}" y="25" text-anchor="middle" font-weight="600" font-size="14" fill="#0f172a">{html.escape(title)}</text>
            {"".join(circles)}
            {legend}
        </svg>
    '''


# =============================================================================
# Analytics Report Export
# =============================================================================


def _generate_analytics_html(
    summary: dict,
    surrogates_by_status: list,
    surrogates_by_assignee: list,
    trend_data: list,
    meta_performance: dict | None,
    org_name: str,
    date_range: str,
    funnel_data: list | None = None,
    state_data: list | None = None,
    performance_data: dict | None = None,
    meta_spend: dict | None = None,
) -> str:
    """Generate HTML for analytics report."""
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # Key Metrics table (including ad spend if available)
    ad_spend_cards = ""
    if meta_spend and meta_spend.get("total_spend", 0) > 0:
        total_spend = meta_spend.get("total_spend", 0)
        cost_per_lead = meta_spend.get("cost_per_lead")
        cpl_display = f"${cost_per_lead:.2f}" if cost_per_lead else "N/A"
        ad_spend_cards = f"""
        <div class="metric-card">
            <div class="metric-value">${total_spend:,.0f}</div>
            <div class="metric-label">Total Ad Spend</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{cpl_display}</div>
            <div class="metric-label">Cost Per Lead</div>
        </div>
        """

    metrics_html = f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-value">{summary.get("total_surrogates", 0)}</div>
            <div class="metric-label">Total Surrogates</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{summary.get("new_this_period", 0)}</div>
            <div class="metric-label">New This Period</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{summary.get("qualified_rate", 0):.1f}%</div>
            <div class="metric-label">Qualified Rate</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{summary.get("pending_tasks", 0)}</div>
            <div class="metric-label">Pending Tasks</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{summary.get("overdue_tasks", 0)}</div>
            <div class="metric-label">Overdue Tasks</div>
        </div>
        {ad_spend_cards}
    </div>
    """

    # AI Insights section
    insights = _compute_insights(trend_data, surrogates_by_status)
    insights_html = f"""
    <div class="insights-box">
        <div class="insight-item">
            <span class="insight-icon">📈</span>
            <span>{html.escape(insights.get("trend", ""))}</span>
        </div>
        <div class="insight-item">
            <span class="insight-icon">⚠️</span>
            <span>{html.escape(insights.get("anomaly", ""))}</span>
        </div>
        <div class="insight-item">
            <span class="insight-icon">🚧</span>
            <span>{html.escape(insights.get("bottleneck", ""))}</span>
        </div>
    </div>
    """

    # Surrogates by Stage section (vertical bar chart like frontend)
    status_section = ""
    if surrogates_by_status:
        # Format status labels like frontend does
        formatted_status = [
            {
                "status": item.get("status", "Unknown").replace("_", " ").title(),
                "count": item.get("count", 0),
            }
            for item in surrogates_by_status
        ]
        status_chart = _generate_vertical_bar_chart_svg(
            formatted_status, "status", "count", "Surrogates by Stage"
        )

        status_section = f"""
        <div class="section">
            <h2>Surrogates by Stage</h2>
            <div class="chart-container">{status_chart}</div>
        </div>
        """

    # Surrogates Trend section
    trend_section = ""
    if trend_data and len(trend_data) >= 2:
        trend_chart = _generate_line_chart_svg(trend_data, "New Surrogates Over Time")
        trend_section = f"""
        <div class="section">
            <h2>Surrogates Trend</h2>
            <div class="chart-container">{trend_chart}</div>
        </div>
        """

    # Team Performance section (horizontal bar chart like frontend)
    team_section = ""
    if surrogates_by_assignee:
        # Format assignee labels like frontend (use email prefix or name)
        formatted_assignees = []
        for item in surrogates_by_assignee[:5]:
            email = item.get("user_email") or ""
            name = email.split("@")[0] if email else item.get("display_name") or "Unassigned"
            formatted_assignees.append({"member": name, "count": item.get("count", 0)})

        team_chart = _generate_horizontal_bar_chart_svg(
            formatted_assignees, "member", "count", "Team Performance"
        )

        team_section = f"""
        <div class="section">
            <h2>Team Performance</h2>
            <div class="chart-container">{team_chart}</div>
        </div>
        """

    # Meta Performance section (pie/donut chart like frontend)
    meta_section = ""
    if meta_performance and meta_performance.get("leads_received", 0) > 0:
        leads_received = meta_performance.get("leads_received", 0)
        leads_qualified = meta_performance.get("leads_qualified", 0)
        leads_converted = meta_performance.get("leads_converted", 0)
        conv_rate = meta_performance.get("conversion_rate", 0)

        # Build pie chart data like frontend (Not Qualified, Qualified Only, Converted)
        not_qualified = max(0, leads_received - leads_qualified)
        qualified_only = max(0, leads_qualified - leads_converted)

        meta_pie_data = [
            {"name": "Not Qualified", "value": not_qualified},
            {"name": "Qualified Only", "value": qualified_only},
            {"name": "Converted", "value": leads_converted},
        ]
        # Filter out zero values
        meta_pie_data = [d for d in meta_pie_data if d["value"] > 0]

        meta_chart = _generate_pie_chart_svg(
            meta_pie_data,
            "name",
            "value",
            "Meta Lead Ads Performance",
            colors=["#94a3b8", "#3b82f6", "#22c55e"],
        )

        avg_hours = meta_performance.get("avg_time_to_convert_hours")
        avg_text = (
            f"Avg {int(avg_hours / 24)} days to convert" if avg_hours else "No conversion data yet"
        )

        meta_section = f"""
        <div class="section">
            <h2>Meta Lead Ads Performance</h2>
            <div class="chart-container">{meta_chart}</div>
            <div class="meta-stats">
                <p><strong>{leads_received}</strong> leads received &bull; <strong>{conv_rate:.1f}%</strong> conversion rate</p>
                <p class="meta-note">{avg_text}</p>
            </div>
        </div>
        """

    # Conversion Funnel section
    funnel_section = ""
    if funnel_data:
        funnel_chart = _generate_funnel_svg(funnel_data, "Conversion Funnel")
        funnel_section = f"""
        <div class="section">
            <h2>Conversion Funnel</h2>
            <div class="chart-container">{funnel_chart}</div>
        </div>
        """

    # Individual Performance Table section
    performance_section = ""
    if performance_data and performance_data.get("data"):
        perf_rows = ""
        for user in performance_data["data"]:
            user_name = html.escape(user.get("user_name", "Unknown"))
            total = user.get("total_surrogates", 0)
            contacted = user.get("contacted", 0)
            qualified = user.get("qualified", 0)
            matched = user.get("matched", 0)
            application_submitted = user.get("application_submitted", 0)
            lost = user.get("lost", 0)
            conv_rate = user.get("conversion_rate", 0)
            avg_match = user.get("avg_days_to_match")
            avg_match_str = f"{avg_match:.1f}" if avg_match else "—"
            avg_apply = user.get("avg_days_to_application_submitted")
            avg_apply_str = f"{avg_apply:.1f}" if avg_apply else "—"

            perf_rows += f"""
            <tr>
                <td>{user_name}</td>
                <td class="text-center">{total}</td>
                <td class="text-center">{contacted}</td>
                <td class="text-center">{qualified}</td>
                <td class="text-center">{matched}</td>
                <td class="text-center">{application_submitted}</td>
                <td class="text-center">{lost}</td>
                <td class="text-center">{conv_rate:.1f}%</td>
                <td class="text-center">{avg_match_str}</td>
                <td class="text-center">{avg_apply_str}</td>
            </tr>
            """

        # Add unassigned row if there are unassigned surrogates
        unassigned = performance_data.get("unassigned", {})
        if unassigned.get("total_surrogates", 0) > 0:
            perf_rows += f"""
            <tr class="unassigned-row">
                <td>Unassigned</td>
                <td class="text-center">{unassigned.get("total_surrogates", 0)}</td>
                <td class="text-center">{unassigned.get("contacted", 0)}</td>
                <td class="text-center">{unassigned.get("qualified", 0)}</td>
                <td class="text-center">{unassigned.get("matched", 0)}</td>
                <td class="text-center">{unassigned.get("application_submitted", 0)}</td>
                <td class="text-center">{unassigned.get("lost", 0)}</td>
                <td class="text-center">—</td>
                <td class="text-center">—</td>
                <td class="text-center">—</td>
            </tr>
            """

        performance_section = f"""
        <div class="section page-break-before">
            <h2>Individual Performance</h2>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Team Member</th>
                        <th class="text-center">Total</th>
                        <th class="text-center">Contacted</th>
                        <th class="text-center">Qualified</th>
                        <th class="text-center">Matched</th>
                        <th class="text-center">Application Submitted</th>
                        <th class="text-center">Lost</th>
                        <th class="text-center">Conv %</th>
                        <th class="text-center">Days to Match</th>
                        <th class="text-center">Days to Apply</th>
                    </tr>
                </thead>
                <tbody>
                    {perf_rows}
                </tbody>
            </table>
        </div>
        """

    # US Map section
    map_section = ""
    if state_data:
        map_chart = _generate_us_map_svg(state_data, "Surrogates by State")
        map_section = f"""
        <div class="section">
            <h2>Geographic Distribution</h2>
            <div class="chart-container map-container">{map_chart}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(org_name)} Analytics Report</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
            background: white;
        }}
        .header {{
            border-bottom: 2px solid #14b8a6;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 22pt;
            font-weight: 600;
            color: #0f172a;
        }}
        .header .subtitle {{
            font-size: 10pt;
            color: #64748b;
            margin-top: 4px;
        }}
        .section {{
            margin-bottom: 28px;
            page-break-inside: avoid;
        }}
        .section h2 {{
            font-size: 14pt;
            font-weight: 600;
            color: #334155;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 8px;
            margin-bottom: 16px;
        }}
        .metrics-grid {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .metric-card {{
            flex: 1;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 24pt;
            font-weight: 700;
            color: #0f172a;
        }}
        .metric-label {{
            font-size: 9pt;
            color: #64748b;
            margin-top: 4px;
        }}
        .chart-container {{
            margin: 16px 0;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10pt;
        }}
        .data-table.small {{
            width: 60%;
        }}
        .data-table th {{
            background: #f1f5f9;
            font-weight: 600;
            color: #334155;
            padding: 10px 12px;
            text-align: left;
            border-bottom: 2px solid #e2e8f0;
        }}
        .data-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid #f1f5f9;
        }}
        .data-table tr:nth-child(even) td {{
            background: #fafafa;
        }}
        .text-center {{
            text-align: center;
        }}
        .meta-stats {{
            margin-top: 16px;
            text-align: center;
        }}
        .meta-stats p {{
            font-size: 11pt;
            color: #1e293b;
            margin: 4px 0;
        }}
        .meta-note {{
            font-size: 10pt;
            color: #64748b;
        }}
        .insights-box {{
            background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
            border: 1px solid #99f6e4;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        .insight-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            font-size: 11pt;
            color: #134e4a;
        }}
        .insight-item:not(:last-child) {{
            border-bottom: 1px solid #99f6e4;
        }}
        .insight-icon {{
            font-size: 14pt;
        }}
        .map-container {{
            display: flex;
            justify-content: center;
        }}
        .page-break-before {{
            page-break-before: always;
        }}
        .unassigned-row td {{
            background: #fef3c7 !important;
            font-style: italic;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 9pt;
            color: #94a3b8;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{html.escape(org_name)} Analytics Report</h1>
        <div class="subtitle">Period: {html.escape(date_range)} | Generated: {generated_at}</div>
    </div>

    <div class="section">
        <h2>Key Metrics</h2>
        {metrics_html}
    </div>

    <div class="section">
        <h2>AI Insights</h2>
        {insights_html}
    </div>

    {status_section}
    {trend_section}
    {funnel_section}
    {team_section}
    {meta_section}
    {map_section}
    {performance_section}

    <div class="footer">
        This report was automatically generated by Surrogacy Force.
    </div>
</body>
</html>"""


async def export_analytics_pdf_async(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    date_range_str: str,
) -> bytes:
    """
    Export analytics report as PDF using Playwright (async version).

    Args:
        db: Database session
        organization_id: Organization ID
        start_dt: Optional start date filter
        end_dt: Optional end date filter
        date_range_str: Human-readable date range string

    Returns:
        PDF file content as bytes
    """
    from app.services import analytics_service

    # Get export data using existing service
    export_data = analytics_service.get_pdf_export_data(
        db=db,
        organization_id=organization_id,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    # Fetch meta spend data asynchronously
    meta_start = start_dt or datetime(1970, 1, 1, tzinfo=timezone.utc)
    meta_end = end_dt or datetime.now(timezone.utc)
    meta_spend = await analytics_service.get_meta_spend_summary(
        start=meta_start,
        end=meta_end,
    )

    # Generate HTML
    html_content = _generate_analytics_html(
        summary=export_data["summary"],
        surrogates_by_status=export_data["surrogates_by_status"],
        surrogates_by_assignee=export_data["surrogates_by_assignee"],
        trend_data=export_data["trend_data"],
        meta_performance=export_data["meta_performance"],
        org_name=export_data["org_name"],
        date_range=date_range_str,
        funnel_data=export_data.get("funnel_data"),
        state_data=export_data.get("state_data"),
        performance_data=export_data.get("performance_data"),
        meta_spend=meta_spend,
    )

    # Render to PDF (async)
    return await _render_html_to_pdf(html_content)


def export_analytics_pdf(
    db: Session,
    organization_id: uuid.UUID,
    start_dt: datetime | None,
    end_dt: datetime | None,
    date_range_str: str,
) -> bytes:
    """
    Export analytics report as PDF using Playwright (sync wrapper).

    Use export_analytics_pdf_async for async contexts.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            export_analytics_pdf_async(db, organization_id, start_dt, end_dt, date_range_str)
        )
    finally:
        loop.close()


# =============================================================================
# Journey Export
# =============================================================================


def _format_month_year(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).strftime("%B %Y")


def _format_iso_month_year(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.astimezone(timezone.utc).strftime("%B %Y")


def _find_repo_root() -> Path | None:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "apps").exists():
            return parent
    return None


def _get_default_image_data_url(slug: str) -> str | None:
    repo_root = _find_repo_root()
    if not repo_root:
        return None
    defaults_dir = repo_root / "apps" / "web" / "public" / "journey" / "defaults"
    for ext in ("jpg", "jpeg", "png", "webp"):
        image_path = defaults_dir / f"{slug}.{ext}"
        if image_path.exists():
            data = image_path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            return f"data:{mime};base64,{b64}"
    return None


def _build_attachment_data_url(attachment: Attachment) -> str | None:
    if not attachment.content_type.startswith("image/"):
        return None
    data, content_type = _load_file_bytes(attachment.storage_key)
    if not data:
        return None
    mime_type = content_type or attachment.content_type
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"


def _generate_journey_html(
    journey: journey_service.JourneyResponse,
    milestone_images: dict[str, str],
) -> str:
    surrogate_name = html.escape(journey.surrogate_name)
    generated_at = datetime.now(timezone.utc).strftime("%B %Y")

    terminal_html = ""
    if journey.is_terminal and journey.terminal_message:
        terminal_date = _format_iso_month_year(journey.terminal_date)
        date_suffix = f" - {terminal_date}" if terminal_date else ""
        terminal_html = f"""
        <div class="terminal-banner">
            <span>{html.escape(journey.terminal_message)}{html.escape(date_suffix)}</span>
        </div>
        """

    phases_html = ""
    for phase in journey.phases:
        phase_label = html.escape(phase.label.upper())
        milestones_html = ""
        for milestone in phase.milestones:
            status_label = ""
            if milestone.status == "completed" and milestone.completed_at and not milestone.is_soft:
                completed_at = _format_month_year(milestone.completed_at)
                status_label = f"Completed {completed_at}" if completed_at else ""

            status_html = (
                f'<div class="milestone-status">{html.escape(status_label)}</div>'
                if status_label
                else ""
            )

            image_src = milestone_images.get(milestone.slug, milestone.default_image_url)
            image_html = (
                f'<img class="milestone-image" src="{html.escape(image_src)}" alt="{html.escape(milestone.label)}" />'
                if image_src
                else ""
            )

            dot_class = f"dot-{milestone.status}"

            milestones_html += f"""
            <div class="milestone-row">
                <div class="dot {dot_class}"></div>
                <div class="milestone-card">
                    <div class="milestone-title">{html.escape(milestone.label)}</div>
                    <div class="milestone-desc">{html.escape(milestone.description)}</div>
                    {status_html}
                    {image_html}
                </div>
            </div>
            """

        phases_html += f"""
        <section class="phase">
            <div class="phase-header">
                <span class="phase-line"></span>
                <span class="phase-label">{phase_label}</span>
                <span class="phase-line"></span>
            </div>
            <div class="milestone-stack">
                {milestones_html}
            </div>
        </section>
        """

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>Surrogacy Journey</title>
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: "Helvetica Neue", Arial, sans-serif;
                color: #111827;
                background: #ffffff;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                padding: 6px 0 24px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 32px;
            }}
            .title {{
                font-size: 24px;
                font-weight: 600;
                margin: 0;
            }}
            .subtitle {{
                font-size: 14px;
                color: #6b7280;
                margin-top: 4px;
            }}
            .meta {{
                font-size: 11px;
                color: #9ca3af;
                margin-top: 10px;
            }}
            .terminal-banner {{
                border: 1px solid #e5e7eb;
                background: #f9fafb;
                border-radius: 10px;
                padding: 12px 16px;
                font-size: 12px;
                color: #6b7280;
                margin-bottom: 24px;
                text-align: center;
            }}
            .phase {{
                margin-top: 26px;
            }}
            .phase-header {{
                display: flex;
                align-items: center;
                gap: 14px;
                margin-bottom: 22px;
            }}
            .phase-line {{
                flex: 1;
                height: 1px;
                background: #e5e7eb;
            }}
            .phase-label {{
                font-size: 10px;
                letter-spacing: 0.25em;
                color: #9ca3af;
                white-space: nowrap;
            }}
            .milestone-stack {{
                display: flex;
                flex-direction: column;
                gap: 28px;
            }}
            .milestone-row {{
                display: grid;
                grid-template-columns: 18px 1fr;
                gap: 16px;
                align-items: flex-start;
            }}
            .dot {{
                width: 10px;
                height: 10px;
                border-radius: 999px;
                margin-top: 6px;
            }}
            .dot-completed {{
                background: #10b981;
            }}
            .dot-current {{
                background: #2563eb;
                box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
            }}
            .dot-upcoming {{
                border: 2px solid #d1d5db;
                background: transparent;
                width: 10px;
                height: 10px;
            }}
            .milestone-card {{
                break-inside: avoid;
            }}
            .milestone-title {{
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 6px;
            }}
            .milestone-desc {{
                font-size: 13px;
                color: #6b7280;
                margin-bottom: 6px;
            }}
            .milestone-status {{
                font-size: 11px;
                color: #6b7280;
                margin-bottom: 10px;
            }}
            .milestone-image {{
                width: 100%;
                border-radius: 12px;
                display: block;
                margin-top: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 class="title">Surrogacy Journey</h1>
                <div class="subtitle">{surrogate_name}</div>
                <div class="meta">Generated {html.escape(generated_at)}</div>
            </div>
            {terminal_html}
            {phases_html}
        </div>
    </body>
    </html>
    """


def export_journey_pdf(
    db: Session,
    org_id: uuid.UUID,
    surrogate_id: uuid.UUID,
) -> bytes:
    journey = journey_service.get_journey(db, org_id, surrogate_id)
    if not journey:
        raise ValueError("Surrogate not found")

    if not settings.FRONTEND_URL:
        raise ValueError("FRONTEND_URL is not configured")

    export_token = create_export_token(org_id, surrogate_id)
    token_param = quote(export_token)
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    print_url = (
        f"{frontend_base}/surrogates/{surrogate_id}/journey/print?export_token={token_param}"
    )

    loop = asyncio.new_event_loop()
    try:
        pdf_bytes = loop.run_until_complete(_render_url_to_pdf(print_url))
    except Exception as exc:
        raise ValueError("Failed to render journey export") from exc
    finally:
        loop.close()

    return pdf_bytes
