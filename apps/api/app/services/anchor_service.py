"""Anchor service for recalculating note positions after transcript changes."""

import difflib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import InterviewNote


# =============================================================================
# Anchor Recalculation
# =============================================================================


def recalculate_anchor_positions(
    note: "InterviewNote",
    original_text: str,
    current_text: str,
) -> tuple[int | None, int | None, str]:
    """
    Recalculate anchor position after transcript changes.

    Uses a multi-strategy approach:
    1. Exact match - text found at same or different position
    2. Diff mapping - trace position through edits
    3. Fuzzy match - find similar text nearby
    4. Lost - anchor text no longer exists

    Args:
        note: The interview note with anchor information
        original_text: The transcript text from the version the note was created on
        current_text: The current transcript text

    Returns:
        Tuple of (new_start, new_end, status)
        Status is one of: 'valid', 'approximate', 'lost'
    """
    if not note.anchor_text:
        return None, None, "valid"

    anchor_text = note.anchor_text

    # Strategy 1: Try exact match first
    idx = current_text.find(anchor_text)
    if idx != -1:
        return idx, idx + len(anchor_text), "valid"

    # Strategy 2: Use diff to trace position
    if note.anchor_start is not None and note.anchor_end is not None:
        mapped_position = _map_position_through_diff(
            original_text=original_text,
            current_text=current_text,
            original_start=note.anchor_start,
            original_end=note.anchor_end,
            anchor_text=anchor_text,
        )
        if mapped_position:
            return mapped_position[0], mapped_position[1], mapped_position[2]

    # Strategy 3: Fuzzy match nearby
    fuzzy_match = _find_fuzzy_match(
        current_text=current_text,
        anchor_text=anchor_text,
        original_position=note.anchor_start or 0,
        search_radius=500,
        similarity_threshold=0.6,
    )
    if fuzzy_match:
        return fuzzy_match[0], fuzzy_match[1], "approximate"

    # Strategy 4: Anchor text is gone
    return None, None, "lost"


def _map_position_through_diff(
    original_text: str,
    current_text: str,
    original_start: int,
    original_end: int,
    anchor_text: str,
) -> tuple[int, int, str] | None:
    """
    Map position from original to current text using diff opcodes.

    Returns (new_start, new_end, status) or None if mapping fails.
    """
    matcher = difflib.SequenceMatcher(None, original_text, current_text, autojunk=False)
    opcodes = matcher.get_opcodes()

    # Track cumulative offset
    offset = 0
    new_start = None
    new_end = None

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # Check if anchor falls within this equal block
            if original_start >= i1 and original_end <= i2:
                # Anchor is in an unchanged region
                block_offset = j1 - i1
                new_start = original_start + block_offset
                new_end = original_end + block_offset

                # Verify the text still matches
                if current_text[new_start:new_end] == anchor_text:
                    return new_start, new_end, "valid"
                else:
                    # Position mapped but text differs (shouldn't happen in equal block)
                    return None

        elif tag == "replace":
            # Check if anchor overlaps with replaced region
            if original_start >= i1 and original_start < i2:
                # Anchor starts in replaced region - try to find in new text
                return None

        elif tag == "delete":
            # Check if anchor overlaps with deleted region
            if original_start >= i1 and original_start < i2:
                # Anchor is in deleted text
                return None

        elif tag == "insert":
            # Insertions don't affect anchor positions directly
            pass

    return None


def _find_fuzzy_match(
    current_text: str,
    anchor_text: str,
    original_position: int,
    search_radius: int = 500,
    similarity_threshold: float = 0.6,
) -> tuple[int, int] | None:
    """
    Find similar text within a search radius of the original position.

    Uses SequenceMatcher ratio for similarity scoring.

    Args:
        current_text: The text to search in
        anchor_text: The original anchor text to find
        original_position: The original character position
        search_radius: How many characters to search in each direction
        similarity_threshold: Minimum similarity ratio (0-1)

    Returns:
        (start, end) tuple or None if no match found
    """
    if not anchor_text or not current_text:
        return None

    anchor_len = len(anchor_text)
    if anchor_len > len(current_text):
        return None

    # Define search window
    search_start = max(0, original_position - search_radius)
    search_end = min(len(current_text), original_position + len(anchor_text) + search_radius)

    best_ratio = 0.0
    best_match = None

    # Slide window through search area
    for i in range(search_start, min(search_end, len(current_text) - anchor_len + 1)):
        candidate = current_text[i : i + anchor_len]

        # Quick length check
        if len(candidate) != anchor_len:
            continue

        # Calculate similarity
        ratio = difflib.SequenceMatcher(None, anchor_text, candidate).ratio()

        if ratio > best_ratio and ratio >= similarity_threshold:
            best_ratio = ratio
            best_match = (i, i + anchor_len)

    return best_match


# =============================================================================
# Batch Operations
# =============================================================================


def recalculate_all_anchors_for_interview(
    notes: list["InterviewNote"],
    current_text: str,
    current_version: int,
    get_version_text: callable,
) -> list[tuple["InterviewNote", int | None, int | None, str | None]]:
    """
    Recalculate anchors for all notes on an interview.

    Args:
        notes: List of interview notes
        current_text: Current transcript text
        current_version: Current transcript version number
        get_version_text: Function to get text for a specific version

    Returns:
        List of (note, new_start, new_end, status) tuples
    """
    results = []

    for note in notes:
        if not note.anchor_text:
            results.append((note, None, None, None))
            continue

        if note.transcript_version == current_version:
            # Note created on current version
            results.append((
                note,
                note.anchor_start,
                note.anchor_end,
                "valid",
            ))
        else:
            # Need to map from original version
            original_text = get_version_text(note.transcript_version)
            if original_text is not None:
                new_start, new_end, status = recalculate_anchor_positions(
                    note=note,
                    original_text=original_text,
                    current_text=current_text,
                )
                results.append((note, new_start, new_end, status))
            else:
                results.append((note, None, None, "lost"))

    return results


# =============================================================================
# Anchor Validation
# =============================================================================


def validate_anchor_selection(
    transcript_text: str,
    anchor_start: int,
    anchor_end: int,
    anchor_text: str,
) -> tuple[bool, str | None]:
    """
    Validate that an anchor selection is valid.

    Returns (is_valid, error_message)
    """
    if anchor_start < 0:
        return False, "anchor_start must be non-negative"

    if anchor_end < anchor_start:
        return False, "anchor_end must be >= anchor_start"

    if anchor_end > len(transcript_text):
        return False, "anchor_end exceeds transcript length"

    # Verify the text matches
    actual_text = transcript_text[anchor_start:anchor_end]
    if actual_text != anchor_text:
        return False, "anchor_text does not match text at specified position"

    return True, None


def normalize_anchor_text(text: str, max_length: int = 500) -> str:
    """
    Normalize anchor text for storage.

    - Trims whitespace
    - Truncates to max length
    - Normalizes internal whitespace
    """
    import re

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Truncate
    if len(text) > max_length:
        text = text[:max_length - 3] + "..."

    return text
