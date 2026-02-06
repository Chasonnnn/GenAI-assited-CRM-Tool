"""Template variable catalogs for email templates.

This is the single source of truth for which variables are supported in which
template surfaces (org templates, platform template studio, platform system templates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import re


VariableValueType = Literal["text", "url", "html"]

# Shared token extraction pattern: {{ variable_name }} (whitespace allowed)
VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


@dataclass(frozen=True)
class TemplateVariableDefinition:
    name: str
    description: str
    category: str
    required: bool = False
    value_type: VariableValueType = "text"
    html_safe: bool = False


def extract_template_variables(text: str) -> set[str]:
    if not text:
        return set()
    return {match.group(1) for match in VARIABLE_PATTERN.finditer(text)}


def list_org_email_template_variables() -> list[TemplateVariableDefinition]:
    """Variables available to org/personal email templates (main app)."""
    return [
        # Recipient
        TemplateVariableDefinition(
            name="first_name",
            description="Contact first name",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="full_name",
            description="Contact full name",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="email",
            description="Contact email",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="phone",
            description="Contact phone",
            category="Recipient",
        ),
        # Case
        TemplateVariableDefinition(
            name="surrogate_number",
            description="Surrogate number",
            category="Case",
        ),
        TemplateVariableDefinition(
            name="intended_parent_number",
            description="Intended parent number",
            category="Case",
        ),
        TemplateVariableDefinition(
            name="status_label",
            description="Current status",
            category="Case",
        ),
        TemplateVariableDefinition(
            name="state",
            description="State",
            category="Case",
        ),
        TemplateVariableDefinition(
            name="owner_name",
            description="Surrogate owner name",
            category="Case",
        ),
        # Organization
        TemplateVariableDefinition(
            name="org_name",
            description="Organization name",
            category="Organization",
        ),
        TemplateVariableDefinition(
            name="org_logo_url",
            description="Organization logo URL (use as image src)",
            category="Organization",
            value_type="url",
        ),
        # Appointment (only present in certain send contexts)
        TemplateVariableDefinition(
            name="appointment_date",
            description="Appointment date",
            category="Appointment",
        ),
        TemplateVariableDefinition(
            name="appointment_time",
            description="Appointment time",
            category="Appointment",
        ),
        TemplateVariableDefinition(
            name="appointment_location",
            description="Appointment location",
            category="Appointment",
        ),
        # Compliance
        TemplateVariableDefinition(
            name="unsubscribe_url",
            description="Unsubscribe link",
            category="Compliance",
            required=False,
            value_type="url",
        ),
    ]


def list_platform_email_template_variables() -> list[TemplateVariableDefinition]:
    """Variables available to Ops platform email templates (template studio)."""
    return list_org_email_template_variables()


def list_platform_system_template_variables(system_key: str) -> list[TemplateVariableDefinition]:
    """Variables available to a given platform system template key."""
    # Today all system templates share the same variable set. We intentionally do not
    # validate the key here so ops can create new system templates in the console
    # without shipping code changes for every system_key.

    return [
        TemplateVariableDefinition(
            name="org_name",
            description="Organization name",
            category="Organization",
        ),
        TemplateVariableDefinition(
            name="org_slug",
            description="Organization slug",
            category="Organization",
        ),
        TemplateVariableDefinition(
            name="first_name",
            description="Recipient first name",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="full_name",
            description="Recipient full name",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="email",
            description="Recipient email",
            category="Recipient",
        ),
        TemplateVariableDefinition(
            name="inviter_text",
            description="Inviter name (prefixed by 'by')",
            category="Invite",
        ),
        TemplateVariableDefinition(
            name="role_title",
            description="Invite role title",
            category="Invite",
        ),
        TemplateVariableDefinition(
            name="invite_url",
            description="Invite acceptance URL",
            category="Invite",
            value_type="url",
        ),
        TemplateVariableDefinition(
            name="expires_block",
            description="Expiry block (HTML)",
            category="Invite",
            value_type="html",
            html_safe=True,
        ),
        TemplateVariableDefinition(
            name="platform_logo_url",
            description="Platform logo URL",
            category="Branding",
            value_type="url",
        ),
        TemplateVariableDefinition(
            name="platform_logo_block",
            description="Platform logo HTML block",
            category="Branding",
            value_type="html",
            html_safe=True,
        ),
        TemplateVariableDefinition(
            name="unsubscribe_url",
            description="Unsubscribe link",
            category="Compliance",
            required=False,
            value_type="url",
        ),
    ]
