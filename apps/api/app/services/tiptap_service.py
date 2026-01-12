"""TipTap JSON processing utilities.

Handles sanitization, HTML generation, and plain text extraction for TipTap editor content.
Used for interview transcripts with anchored notes support.
"""

import re

from app.types import JsonObject, JsonValue


# Allowed TipTap node types (XSS prevention)
ALLOWED_NODES = {
    "doc",
    "paragraph",
    "text",
    "heading",
    "bulletList",
    "orderedList",
    "listItem",
    "hardBreak",
    "horizontalRule",
    "blockquote",
}

# Allowed mark types (including comment for anchored notes)
ALLOWED_MARKS = {
    "bold",
    "italic",
    "underline",
    "strike",
    "highlight",
    "link",
    "comment",  # For anchored notes
}

# Allowed mark attributes
ALLOWED_MARK_ATTRS = {
    "link": {"href", "target", "rel"},
    "highlight": {"color"},
    "comment": {"commentId"},
}

# Heading levels allowed
ALLOWED_HEADING_LEVELS = {1, 2, 3}


def sanitize_tiptap_json(doc: JsonObject | None) -> JsonObject | None:
    """
    Sanitize TipTap JSON document, removing disallowed nodes/marks.

    Args:
        doc: TipTap JSON document

    Returns:
        Sanitized document or None if input is None/invalid
    """
    if not doc or not isinstance(doc, dict):
        return None

    if doc.get("type") != "doc":
        return None

    return _sanitize_node(doc)


def _sanitize_node(node: JsonValue) -> JsonObject | None:
    """Recursively sanitize a TipTap node."""
    if not isinstance(node, dict):
        return None

    node_type = node.get("type")
    if not node_type:
        return None

    # Check if node type is allowed
    if node_type not in ALLOWED_NODES:
        return None

    result: JsonObject = {"type": node_type}

    # Handle text nodes
    if node_type == "text":
        text = node.get("text", "")
        if not isinstance(text, str):
            return None
        result["text"] = text

        # Sanitize marks on text nodes
        if "marks" in node and isinstance(node["marks"], list):
            sanitized_marks = []
            for mark in node["marks"]:
                sanitized_mark = _sanitize_mark(mark)
                if sanitized_mark:
                    sanitized_marks.append(sanitized_mark)
            if sanitized_marks:
                result["marks"] = sanitized_marks

        return result

    # Handle heading attributes
    if node_type == "heading":
        attrs = node.get("attrs", {})
        level = attrs.get("level", 1)
        if level not in ALLOWED_HEADING_LEVELS:
            level = 1
        result["attrs"] = {"level": level}

    # Recursively sanitize content
    if "content" in node and isinstance(node["content"], list):
        sanitized_content = []
        for child in node["content"]:
            sanitized_child = _sanitize_node(child)
            if sanitized_child:
                sanitized_content.append(sanitized_child)
        if sanitized_content:
            result["content"] = sanitized_content

    return result


def _sanitize_mark(mark: JsonValue) -> JsonObject | None:
    """Sanitize a TipTap mark."""
    if not isinstance(mark, dict):
        return None

    mark_type = mark.get("type")
    if not mark_type or mark_type not in ALLOWED_MARKS:
        return None

    result: JsonObject = {"type": mark_type}

    # Handle mark attributes
    if "attrs" in mark and isinstance(mark["attrs"], dict):
        allowed_attrs = ALLOWED_MARK_ATTRS.get(mark_type, set())
        if allowed_attrs:
            sanitized_attrs = {}
            for key, value in mark["attrs"].items():
                if key in allowed_attrs and isinstance(value, (str, int, bool)):
                    # Sanitize href to prevent javascript: URLs
                    if key == "href":
                        value = _sanitize_url(value)
                        if not value:
                            continue
                    sanitized_attrs[key] = value
            if sanitized_attrs:
                result["attrs"] = sanitized_attrs

    return result


def _sanitize_url(url: str) -> str | None:
    """Sanitize URL to prevent XSS."""
    if not isinstance(url, str):
        return None

    url = url.strip()

    # Block javascript: and data: URLs
    lower_url = url.lower()
    if lower_url.startswith(("javascript:", "data:", "vbscript:")):
        return None

    # Allow http, https, mailto, tel
    if not lower_url.startswith(("http://", "https://", "mailto:", "tel:", "/")):
        # Relative URL or missing protocol - add https
        if not lower_url.startswith("#"):
            url = "https://" + url

    return url


def tiptap_to_html(doc: JsonObject | None) -> str:
    """
    Convert TipTap JSON to sanitized HTML.

    Args:
        doc: TipTap JSON document (should be pre-sanitized)

    Returns:
        HTML string
    """
    if not doc or not isinstance(doc, dict):
        return ""

    if doc.get("type") != "doc":
        return ""

    return _node_to_html(doc)


def _node_to_html(node: JsonObject) -> str:
    """Convert a TipTap node to HTML."""
    node_type = node.get("type")

    if node_type == "doc":
        return _content_to_html(node.get("content", []))

    if node_type == "text":
        text = _escape_html(node.get("text", ""))
        marks = node.get("marks", [])
        for mark in marks:
            text = _apply_mark_html(text, mark)
        return text

    if node_type == "paragraph":
        content = _content_to_html(node.get("content", []))
        return f"<p>{content}</p>"

    if node_type == "heading":
        level = node.get("attrs", {}).get("level", 1)
        level = min(max(level, 1), 3)
        content = _content_to_html(node.get("content", []))
        return f"<h{level}>{content}</h{level}>"

    if node_type == "bulletList":
        content = _content_to_html(node.get("content", []))
        return f"<ul>{content}</ul>"

    if node_type == "orderedList":
        content = _content_to_html(node.get("content", []))
        return f"<ol>{content}</ol>"

    if node_type == "listItem":
        content = _content_to_html(node.get("content", []))
        return f"<li>{content}</li>"

    if node_type == "hardBreak":
        return "<br>"

    if node_type == "horizontalRule":
        return "<hr>"

    if node_type == "blockquote":
        content = _content_to_html(node.get("content", []))
        return f"<blockquote>{content}</blockquote>"

    return ""


def _content_to_html(content: list) -> str:
    """Convert content array to HTML."""
    return "".join(_node_to_html(child) for child in content if isinstance(child, dict))


def _apply_mark_html(text: str, mark: dict) -> str:
    """Apply a mark to text as HTML."""
    mark_type = mark.get("type")
    attrs = mark.get("attrs", {})

    if mark_type == "bold":
        return f"<strong>{text}</strong>"

    if mark_type == "italic":
        return f"<em>{text}</em>"

    if mark_type == "underline":
        return f"<u>{text}</u>"

    if mark_type == "strike":
        return f"<s>{text}</s>"

    if mark_type == "highlight":
        color = attrs.get("color", "yellow")
        return f'<mark style="background-color: {_escape_html(color)}">{text}</mark>'

    if mark_type == "link":
        href = attrs.get("href", "#")
        return f'<a href="{_escape_html(href)}" target="_blank" rel="noopener noreferrer">{text}</a>'

    if mark_type == "comment":
        comment_id = attrs.get("commentId", "")
        return f'<span class="comment-highlight" data-comment-id="{_escape_html(str(comment_id))}">{text}</span>'

    return text


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def tiptap_to_text(doc: JsonObject | None) -> str:
    """
    Extract plain text from TipTap JSON.

    Args:
        doc: TipTap JSON document

    Returns:
        Plain text string
    """
    if not doc or not isinstance(doc, dict):
        return ""

    if doc.get("type") != "doc":
        return ""

    return _node_to_text(doc).strip()


def _node_to_text(node: JsonObject) -> str:
    """Convert a TipTap node to plain text."""
    node_type = node.get("type")

    if node_type == "doc":
        return _content_to_text(node.get("content", []))

    if node_type == "text":
        return node.get("text", "")

    if node_type in ("paragraph", "heading", "blockquote"):
        content = _content_to_text(node.get("content", []))
        return content + "\n"

    if node_type in ("bulletList", "orderedList"):
        return _content_to_text(node.get("content", []))

    if node_type == "listItem":
        content = _content_to_text(node.get("content", []))
        return "• " + content

    if node_type == "hardBreak":
        return "\n"

    if node_type == "horizontalRule":
        return "\n---\n"

    return ""


def _content_to_text(content: list) -> str:
    """Convert content array to plain text."""
    return "".join(_node_to_text(child) for child in content if isinstance(child, dict))


def html_to_tiptap(html: str) -> dict | None:
    """
    Convert HTML to TipTap JSON (best effort).

    This is a simplified converter for basic HTML content.
    Complex HTML may not convert perfectly.

    Args:
        html: HTML string

    Returns:
        TipTap JSON document
    """
    if not html or not html.strip():
        return None

    # Simple HTML to TipTap conversion
    # For now, just wrap content in paragraphs
    paragraphs = []

    # Remove script/style tags
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Split by paragraph tags or double newlines
    parts = re.split(r"</p>|<br\s*/?>|<br>|\n\n", html, flags=re.IGNORECASE)

    for part in parts:
        # Strip HTML tags for text content
        text = re.sub(r"<[^>]+>", "", part).strip()
        if text:
            paragraphs.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": text}]
            })

    if not paragraphs:
        return None

    return {
        "type": "doc",
        "content": paragraphs
    }


def extract_comment_ids(doc: dict | None) -> set[str]:
    """
    Extract all comment IDs from a TipTap document.

    Args:
        doc: TipTap JSON document

    Returns:
        Set of comment IDs found in the document
    """
    if not doc:
        return set()

    comment_ids: set[str] = set()
    _extract_comment_ids_recursive(doc, comment_ids)
    return comment_ids


def _extract_comment_ids_recursive(node: dict, comment_ids: set[str]) -> None:
    """Recursively extract comment IDs from nodes."""
    if node.get("type") == "text":
        for mark in node.get("marks", []):
            if mark.get("type") == "comment":
                comment_id = mark.get("attrs", {}).get("commentId")
                if comment_id:
                    comment_ids.add(str(comment_id))

    for child in node.get("content", []):
        if isinstance(child, dict):
            _extract_comment_ids_recursive(child, comment_ids)
