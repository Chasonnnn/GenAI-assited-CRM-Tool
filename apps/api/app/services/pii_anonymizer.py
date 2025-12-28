"""PII Anonymization service for AI.

Strips and rehydrates PII (names, emails, phones) before/after AI calls.
Ensures sensitive data doesn't leave the system.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PIIMapping:
    """Stores mappings between placeholders and real values."""

    names: dict[str, str] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)
    phones: dict[str, str] = field(default_factory=dict)

    def add_name(self, real_value: str) -> str:
        """Add a name and return its placeholder."""
        if real_value in self.names:
            return self.names[real_value]
        placeholder = f"[PERSON_{len(self.names) + 1}]"
        self.names[real_value] = placeholder
        return placeholder

    def add_email(self, real_value: str) -> str:
        """Add an email and return its placeholder."""
        if real_value in self.emails:
            return self.emails[real_value]
        placeholder = f"[EMAIL_{len(self.emails) + 1}]"
        self.emails[real_value] = placeholder
        return placeholder

    def add_phone(self, real_value: str) -> str:
        """Add a phone and return its placeholder."""
        if real_value in self.phones:
            return self.phones[real_value]
        placeholder = f"[PHONE_{len(self.phones) + 1}]"
        self.phones[real_value] = placeholder
        return placeholder

    def get_reverse_mapping(self) -> dict[str, str]:
        """Get placeholder -> real value mapping for rehydration."""
        reverse = {}
        for real, placeholder in self.names.items():
            reverse[placeholder] = real
        for real, placeholder in self.emails.items():
            reverse[placeholder] = real
        for real, placeholder in self.phones.items():
            reverse[placeholder] = real
        return reverse


# Email regex pattern
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Phone patterns (various formats)
PHONE_PATTERNS = [
    re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # 123-456-7890
    re.compile(r"\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b"),  # (123) 456-7890
    re.compile(r"\b\+1\s*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),  # +1 123-456-7890
]


def anonymize_text(
    text: str, mapping: PIIMapping, known_names: list[str] | None = None
) -> str:
    """
    Anonymize PII in text.

    Args:
        text: The text to anonymize
        mapping: PIIMapping to store/retrieve mappings
        known_names: List of known names to look for (first, last, full)

    Returns:
        Anonymized text with placeholders
    """
    result = text

    # Replace known names first (case-insensitive)
    if known_names:
        for name in known_names:
            if name and len(name) > 1:  # Skip single chars
                pattern = re.compile(re.escape(name), re.IGNORECASE)
                if pattern.search(result):
                    placeholder = mapping.add_name(name)
                    result = pattern.sub(placeholder, result)

    # Replace emails
    for match in EMAIL_PATTERN.finditer(result):
        email = match.group()
        placeholder = mapping.add_email(email)
        result = result.replace(email, placeholder)

    # Replace phone numbers
    for phone_pattern in PHONE_PATTERNS:
        for match in phone_pattern.finditer(result):
            phone = match.group()
            placeholder = mapping.add_phone(phone)
            result = result.replace(phone, placeholder)

    return result


def rehydrate_text(text: str, mapping: PIIMapping) -> str:
    """
    Rehydrate anonymized text with real values.

    Args:
        text: Text with placeholders
        mapping: PIIMapping with the mappings

    Returns:
        Text with real values restored
    """
    result = text
    reverse = mapping.get_reverse_mapping()

    for placeholder, real_value in reverse.items():
        result = result.replace(placeholder, real_value)

    return result


def anonymize_case_context(
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    phone: str | None,
    notes_text: str | None,
    mapping: PIIMapping,
) -> dict[str, Any]:
    """
    Anonymize case context fields.

    Returns dict with anonymized values.
    """
    # Build list of names to search for
    known_names = []
    if first_name:
        known_names.append(first_name)
    if last_name:
        known_names.append(last_name)
    if first_name and last_name:
        known_names.append(f"{first_name} {last_name}")

    result = {}

    # Anonymize direct fields
    if first_name:
        result["first_name"] = mapping.add_name(first_name)
    else:
        result["first_name"] = None

    if last_name:
        result["last_name"] = mapping.add_name(last_name)
    else:
        result["last_name"] = None

    if email:
        result["email"] = mapping.add_email(email)
    else:
        result["email"] = None

    if phone:
        result["phone"] = mapping.add_phone(phone)
    else:
        result["phone"] = None

    # Anonymize notes
    if notes_text:
        result["notes_text"] = anonymize_text(notes_text, mapping, known_names)
    else:
        result["notes_text"] = None

    return result
