"""Email layouts: the frame that sends draw around a template body.

Templates store the chosen layout in a nullable ``layout`` JSON column. NULL
means the default for the template scope: org templates send in a card,
personal templates read like the sender's own mail.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

EmailLayoutKind = Literal["plain", "card", "letterhead"]
HEX_COLOR = r"^#[0-9a-fA-F]{6}$"

DEFAULT_PAGE_BACKGROUND = "#f4f4f5"


class InvalidEmailLayoutError(ValueError):
    """The value is not a stored email layout."""


class EmailLayout(BaseModel):
    """Layout settings; ``accent_color`` None follows the org signature color."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: EmailLayoutKind
    show_logo: bool = True
    logo_position: Literal["left", "center"] = "center"
    accent_color: str | None = Field(default=None, pattern=HEX_COLOR)
    page_background: str = Field(default=DEFAULT_PAGE_BACKGROUND, pattern=HEX_COLOR)


def default_layout(scope: str) -> EmailLayout:
    return EmailLayout(kind="card" if scope == "org" else "plain")


def parse_layout(value: object) -> EmailLayout | None:
    """Parse a stored layout; None stays None so callers apply the scope default."""
    if value is None:
        return None
    if isinstance(value, EmailLayout):
        return value
    try:
        return EmailLayout.model_validate(value)
    except ValidationError as exc:
        raise InvalidEmailLayoutError("layout is not a valid email layout") from exc


def resolve_layout(value: object, scope: str) -> EmailLayout:
    return parse_layout(value) or default_layout(scope)


def dump_layout(layout: EmailLayout | None) -> dict[str, Any] | None:
    return layout.model_dump() if layout is not None else None
