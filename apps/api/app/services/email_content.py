"""Provider-neutral email content helpers."""

from __future__ import annotations

from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    """Collect visible text while excluding script and style content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._hidden_depth > 0:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth == 0 and data:
            self.parts.append(data)


def html_to_text(content: str) -> str:
    """Return a readable plaintext alternative for an HTML email."""

    parser = _ReadableTextParser()
    parser.feed(content)
    parser.close()
    return " ".join(" ".join(parser.parts).split())
