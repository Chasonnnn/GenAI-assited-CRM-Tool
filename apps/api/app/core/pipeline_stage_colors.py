"""Pipeline stage color helpers."""

from __future__ import annotations

import re

DEFAULT_CUSTOM_STAGE_COLOR = "#6b7280"
FALLBACK_GRAY_STAGE_COLORS = {DEFAULT_CUSTOM_STAGE_COLOR}

CUSTOM_STAGE_COLOR_PRESETS: dict[str, list[str]] = {
    "intake": ["#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#8b5cf6", "#f59e0b"],
    "post_approval": ["#0f766e", "#0891b2", "#4f46e5", "#8b5cf6", "#db2777", "#ea580c"],
    "paused": ["#b4536a"],
    "terminal": ["#ef4444", "#dc2626"],
}

KEYWORD_STAGE_COLOR_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("docusign", "docu", "signature", "consent"), "#f59e0b"),
    (("insurance",), "#0891b2"),
    (("medical", "medically", "clinic"), "#14b8a6"),
    (("legal", "contract"), "#6366f1"),
    (("transfer", "cycle"), "#0d9488"),
    (("pbo",), "#db2777"),
    (("anatomy", "heartbeat", "hcg", "pregnancy", "pregnant", "ob"), "#16a34a"),
    (("interview", "consult", "screen"), "#a855f7"),
    (("application", "packet", "submit", "submitted"), "#8b5cf6"),
    (("review",), "#f59e0b"),
    (("qualif",), "#10b981"),
    (("contact", "outreach"), "#0ea5e9"),
)


def _normalize_hex_color(color: str | None) -> str | None:
    if not color:
        return None
    normalized = color.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", normalized):
        return normalized
    return None


def _normalize_stage_text(*parts: str | None) -> str:
    joined = " ".join(part for part in parts if part)
    return re.sub(r"[^a-z0-9]+", " ", joined.lower()).strip()


def _fallback_palette_index(stage_type: str | None, stage_key: str | None, order: int | None) -> int:
    palette = CUSTOM_STAGE_COLOR_PRESETS.get(stage_type or "", [DEFAULT_CUSTOM_STAGE_COLOR])
    if order and order > 0:
        return (order - 1) % len(palette)
    seed = _normalize_stage_text(stage_key, stage_type)
    return sum((index + 1) * ord(char) for index, char in enumerate(seed)) % len(palette)


def suggest_stage_color(
    *,
    label: str | None,
    slug: str | None,
    stage_key: str | None,
    stage_type: str | None,
    order: int | None = None,
) -> str:
    normalized_text = _normalize_stage_text(label, slug, stage_key)
    for keywords, color in KEYWORD_STAGE_COLOR_RULES:
        if any(keyword in normalized_text for keyword in keywords):
            return color

    palette = CUSTOM_STAGE_COLOR_PRESETS.get(stage_type or "", [DEFAULT_CUSTOM_STAGE_COLOR])
    return palette[_fallback_palette_index(stage_type, stage_key or slug, order)]


def resolve_stage_color(
    *,
    color: str | None,
    label: str | None,
    slug: str | None,
    stage_key: str | None,
    stage_type: str | None,
    order: int | None = None,
    is_locked: bool = False,
) -> str:
    normalized_color = _normalize_hex_color(color)
    if normalized_color and normalized_color.lower() not in FALLBACK_GRAY_STAGE_COLORS:
        return normalized_color
    if is_locked:
        return normalized_color or DEFAULT_CUSTOM_STAGE_COLOR
    return suggest_stage_color(
        label=label,
        slug=slug,
        stage_key=stage_key,
        stage_type=stage_type,
        order=order,
    )
