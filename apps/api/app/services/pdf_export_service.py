"""PDF export service using Playwright for headless rendering."""

import asyncio
import base64
import html
import os
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import FormSubmission
from app.services import profile_service, form_service


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


def _load_file_bytes(storage_key: str) -> tuple[bytes | None, str | None]:
    """Load file bytes from configured storage backend."""
    from app.services.attachment_service import _get_local_storage_path, _get_s3_client, _get_storage_backend

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
    case_name: str,
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
    <title>{html.escape(title)} - {html.escape(case_name)}</title>
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
        <h1>{html.escape(case_name)}</h1>
        <div class="subtitle">{html.escape(title)} • {datetime.now().strftime("%B %d, %Y")}{" • " + html.escape(org_name) if org_name else ""}</div>
    </div>
    
    {sections_html}

    {attachments_html}
    
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
    case_name: str,
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
        case_name=case_name,
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
    case_id: uuid.UUID,
    case_name: str,
    org_name: str = "",
) -> bytes:
    """
    Export a case profile as PDF.
    
    Args:
        db: Database session
        org_id: Organization ID
        case_id: Case ID
        case_name: Display name for the case
        org_name: Organization name for header
        
    Returns:
        PDF file content as bytes
    """
    # Get profile data
    profile_data = profile_service.get_profile_data(db, org_id, case_id)
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
        case_name=case_name,
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
