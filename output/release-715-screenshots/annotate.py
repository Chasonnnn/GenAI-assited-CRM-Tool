"""Render native-size release screenshots with numbered callouts and an HTML gallery."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import sys
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "manifest.json"
ANNOTATED_DIRNAME = "annotated"
ORIGINALS_DIRNAME = "originals"

INK = "#172033"
MUTED = "#5f6b7a"
LINE = "#dce2ea"
PANEL = "#f6f8fb"
CARD = "#ffffff"
ACCENT = "#b84a2f"
ACCENT_SOFT = "#fff1ec"


@dataclass(frozen=True)
class Callout:
    label: str
    body: str
    rect: tuple[float, float, float, float] | None
    point: tuple[float, float] | None
    marker_point: tuple[float, float] | None


@dataclass(frozen=True)
class ScreenshotSpec:
    slug: str
    raw_path: Path
    title: str
    caption: str
    callouts: tuple[Callout, ...]


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{field} must be a non-empty string")
    return value.strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "screenshot"


def geometry(value: Any, length: int, field: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        fail(f"{field} must contain {length} numbers")
    if not all(isinstance(item, (int, float)) and math.isfinite(item) for item in value):
        fail(f"{field} must contain finite numbers")
    return tuple(float(item) for item in value)


def load_manifest(path: Path) -> tuple[dict[str, Any], tuple[ScreenshotSpec, ...]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Manifest not found: {path}")
    except json.JSONDecodeError as error:
        fail(f"Invalid JSON in {path}: {error}")

    if not isinstance(data, dict):
        fail("manifest root must be an object")
    require_text(data.get("version"), "version")
    require_text(data.get("demo_data_label"), "demo_data_label")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        fail("items must be a non-empty array")

    specs: list[ScreenshotSpec] = []
    seen_slugs: set[str] = set()
    for item_index, item in enumerate(items, start=1):
        prefix = f"items[{item_index - 1}]"
        if not isinstance(item, dict):
            fail(f"{prefix} must be an object")
        title = require_text(item.get("title"), f"{prefix}.title")
        caption = require_text(item.get("caption"), f"{prefix}.caption")
        raw_value = item.get("rawpath", item.get("raw_path"))
        raw_text = require_text(raw_value, f"{prefix}.rawpath")
        raw_path = Path(raw_text).expanduser()
        if not raw_path.is_absolute():
            raw_path = (path.parent / raw_path).resolve()
        if not raw_path.is_file():
            fail(f"{prefix}.rawpath does not exist: {raw_path}")

        slug = slugify(str(item.get("id") or raw_path.stem or title))
        if slug in seen_slugs:
            fail(f"duplicate screenshot id after normalization: {slug}")
        seen_slugs.add(slug)

        raw_callouts = item.get("callouts")
        if not isinstance(raw_callouts, list) or not raw_callouts:
            fail(f"{prefix}.callouts must be a non-empty array")
        callouts: list[Callout] = []
        for callout_index, raw_callout in enumerate(raw_callouts, start=1):
            callout_prefix = f"{prefix}.callouts[{callout_index - 1}]"
            if not isinstance(raw_callout, dict):
                fail(f"{callout_prefix} must be an object")
            has_rect = "rect" in raw_callout
            has_point = "point" in raw_callout
            if has_rect == has_point:
                fail(f"{callout_prefix} must define exactly one of rect or point")
            rect = geometry(raw_callout["rect"], 4, f"{callout_prefix}.rect") if has_rect else None
            point = geometry(raw_callout["point"], 2, f"{callout_prefix}.point") if has_point else None
            marker_point = (
                geometry(raw_callout["marker_point"], 2, f"{callout_prefix}.marker_point")
                if "marker_point" in raw_callout
                else None
            )
            if rect and (rect[2] <= 0 or rect[3] <= 0):
                fail(f"{callout_prefix}.rect width and height must be positive")
            callouts.append(
                Callout(
                    label=require_text(raw_callout.get("label"), f"{callout_prefix}.label"),
                    body=require_text(raw_callout.get("body"), f"{callout_prefix}.body"),
                    rect=rect,
                    point=point,
                    marker_point=marker_point,
                )
            )
        specs.append(
            ScreenshotSpec(
                slug=slug,
                raw_path=raw_path,
                title=title,
                caption=caption,
                callouts=tuple(callouts),
            )
        )
    return data, tuple(specs)


def font_candidates(bold: bool) -> Iterable[Path]:
    if bold:
        yield Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
        yield Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    else:
        yield Path("/System/Library/Fonts/Supplemental/Arial.ttf")
        yield Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in font_candidates(bold):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)


def split_long_word(draw: ImageDraw.ImageDraw, word: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for character in word:
        candidate = current + character
        if current and draw.textlength(candidate, font=font) > width:
            parts.append(current)
            current = character
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words: list[str] = []
        for word in paragraph.split():
            if draw.textlength(word, font=font) <= width:
                words.append(word)
            else:
                words.extend(split_long_word(draw, word, font, width))
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textlength(candidate, font=font) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def line_height(font: ImageFont.ImageFont, spacing: int = 4) -> int:
    box = font.getbbox("Ag")
    return box[3] - box[1] + spacing


def draw_lines(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    lines: list[str],
    font: ImageFont.ImageFont,
    fill: str,
    spacing: int = 4,
) -> int:
    x, y = position
    height = line_height(font, spacing)
    for index, line in enumerate(lines):
        draw.text((x, y + index * height), line, font=font, fill=fill)
    return len(lines) * height


def validate_geometry(spec: ScreenshotSpec, width: int, height: int) -> None:
    for index, callout in enumerate(spec.callouts, start=1):
        if callout.point:
            x, y = callout.point
            if not (0 <= x <= width and 0 <= y <= height):
                fail(f"{spec.slug} callout {index} point is outside {width}x{height}")
        if callout.marker_point:
            x, y = callout.marker_point
            if not (0 <= x <= width and 0 <= y <= height):
                fail(f"{spec.slug} callout {index} marker_point is outside {width}x{height}")
        if callout.rect:
            x, y, rect_width, rect_height = callout.rect
            if x < 0 or y < 0 or x + rect_width > width or y + rect_height > height:
                fail(f"{spec.slug} callout {index} rect is outside {width}x{height}")


def draw_pill(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    text_fill: str,
) -> int:
    width = math.ceil(draw.textlength(text, font=font)) + 22
    height = line_height(font, 0) + 10
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=fill)
    draw.text((x + 11, y + 5), text, font=font, fill=text_fill)
    return width


def render_screenshot(
    spec: ScreenshotSpec,
    *,
    version: str,
    demo_data_label: str,
    gutter_width: int,
    destination: Path,
) -> tuple[int, int]:
    raw = Image.open(spec.raw_path).convert("RGBA")
    raw_width, raw_height = raw.size
    validate_geometry(spec, raw_width, raw_height)

    title_font = load_font(27, bold=True)
    label_font = load_font(17, bold=True)
    body_font = load_font(15)
    small_font = load_font(13, bold=True)
    caption_font = load_font(16)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1), "white"))

    title_lines = wrap_text(measure, spec.title, title_font, max(120, raw_width - 64))
    title_height = len(title_lines) * line_height(title_font, 5)
    header_height = max(88, title_height + 34)
    card_width = gutter_width - 40
    text_width = card_width - 68
    card_layouts: list[tuple[list[str], list[str], int]] = []
    for callout in spec.callouts:
        label_lines = wrap_text(measure, callout.label, label_font, text_width)
        body_lines = wrap_text(measure, callout.body, body_font, text_width)
        content_height = len(label_lines) * line_height(label_font, 3)
        content_height += 6 + len(body_lines) * line_height(body_font, 4)
        card_layouts.append((label_lines, body_lines, max(68, content_height + 24)))

    side_start = header_height + 20
    side_height = sum(layout[2] for layout in card_layouts) + max(0, len(card_layouts) - 1) * 12
    main_bottom = header_height + raw_height
    side_bottom = side_start + side_height
    canvas_width = raw_width + gutter_width
    caption_lines = wrap_text(measure, spec.caption, caption_font, canvas_width - 64)
    caption_height = len(caption_lines) * line_height(caption_font, 5) + 36
    footer_top = max(main_bottom, side_bottom) + 20
    canvas_height = footer_top + caption_height

    canvas = Image.new("RGBA", (canvas_width, canvas_height), "white")
    canvas.paste(raw, (0, header_height))
    draw = ImageDraw.Draw(canvas, "RGBA")

    draw.rectangle((0, 0, canvas_width, header_height - 1), fill="#ffffff")
    draw.line((0, header_height - 1, canvas_width, header_height - 1), fill=LINE, width=1)
    draw_lines(draw, (32, 18), title_lines, title_font, INK, spacing=5)

    pill_x = raw_width + 20
    pill_y = 20
    version_width = draw_pill(draw, pill_x, pill_y, version, small_font, INK, "#ffffff")
    demo_width = math.ceil(draw.textlength(demo_data_label, font=small_font)) + 22
    if version_width + demo_width + 10 <= gutter_width - 40:
        draw_pill(draw, pill_x + version_width + 10, pill_y, demo_data_label, small_font, ACCENT_SOFT, ACCENT)
    else:
        draw_pill(draw, pill_x, pill_y + 34, demo_data_label, small_font, ACCENT_SOFT, ACCENT)

    draw.rectangle((raw_width, header_height, canvas_width, footer_top), fill=PANEL)
    draw.line((raw_width, header_height, raw_width, footer_top), fill=LINE, width=1)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    radius = 15
    for number, callout in enumerate(spec.callouts, start=1):
        if callout.rect:
            x, y, rect_width, rect_height = callout.rect
            box = (
                round(x),
                round(y + header_height),
                round(x + rect_width),
                round(y + rect_height + header_height),
            )
            overlay_draw.rounded_rectangle(box, radius=8, outline=(184, 74, 47, 235), width=3)
            if callout.marker_point:
                marker_x, marker_y = callout.marker_point
                pin_x = round(marker_x)
                pin_y = round(marker_y + header_height)
            elif y >= radius * 2:
                pin_x = round(x + min(16, rect_width / 2))
                pin_y = round(y + header_height - radius - 1)
            else:
                pin_x = round(x - radius - 1)
                pin_y = round(y + header_height + min(16, rect_height / 2))
            pin_x = min(max(pin_x, radius + 2), raw_width - radius - 2)
            pin_y = min(max(pin_y, header_height + radius + 2), main_bottom - radius - 2)
        else:
            point_x, point_y = callout.marker_point or callout.point or (0.0, 0.0)
            pin_x = min(max(round(point_x), radius + 2), raw_width - radius - 2)
            pin_y = min(max(round(point_y + header_height), header_height + radius + 2), main_bottom - radius - 2)
        overlay_draw.ellipse(
            (pin_x - radius, pin_y - radius, pin_x + radius, pin_y + radius),
            fill=(184, 74, 47, 255),
            outline=(255, 255, 255, 255),
            width=3,
        )
        number_text = str(number)
        number_box = overlay_draw.textbbox((0, 0), number_text, font=small_font)
        number_width = number_box[2] - number_box[0]
        number_height = number_box[3] - number_box[1]
        overlay_draw.text(
            (pin_x - number_width / 2, pin_y - number_height / 2 - number_box[1]),
            number_text,
            font=small_font,
            fill="#ffffff",
        )
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas, "RGBA")

    card_x = raw_width + 20
    card_y = side_start
    for number, (callout, layout) in enumerate(zip(spec.callouts, card_layouts), start=1):
        label_lines, body_lines, card_height = layout
        draw.rounded_rectangle(
            (card_x, card_y, card_x + card_width, card_y + card_height),
            radius=12,
            fill=CARD,
            outline=LINE,
            width=1,
        )
        circle_x = card_x + 24
        circle_y = card_y + 25
        draw.ellipse((circle_x - 14, circle_y - 14, circle_x + 14, circle_y + 14), fill=ACCENT)
        number_text = str(number)
        number_box = draw.textbbox((0, 0), number_text, font=small_font)
        draw.text(
            (
                circle_x - (number_box[2] - number_box[0]) / 2,
                circle_y - (number_box[3] - number_box[1]) / 2 - number_box[1],
            ),
            number_text,
            font=small_font,
            fill="#ffffff",
        )
        text_x = card_x + 48
        text_y = card_y + 12
        label_height = draw_lines(draw, (text_x, text_y), label_lines, label_font, INK, spacing=3)
        draw_lines(draw, (text_x, text_y + label_height + 6), body_lines, body_font, MUTED, spacing=4)
        card_y += card_height + 12

    draw.rectangle((0, footer_top, canvas_width, canvas_height), fill="#ffffff")
    draw.line((0, footer_top, canvas_width, footer_top), fill=LINE, width=1)
    draw_lines(draw, (32, footer_top + 18), caption_lines, caption_font, MUTED, spacing=5)

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(destination, format="PNG", optimize=True)
    return canvas.size


def gallery_html(
    *,
    version: str,
    demo_data_label: str,
    records: list[dict[str, str]],
) -> str:
    cards = []
    rows = []
    for record in records:
        title = html.escape(record["title"])
        caption = html.escape(record["caption"])
        annotated = html.escape(record["annotated"])
        original = html.escape(record["original"])
        cards.append(
            f"""
            <article class="card">
              <a href="{annotated}"><img src="{annotated}" alt="{title}"></a>
              <div class="copy">
                <h2>{title}</h2>
                <p>{caption}</p>
                <div class="links"><a download href="{annotated}">Download annotated PNG</a><a download href="{original}">Download original</a></div>
              </div>
            </article>"""
        )
        rows.append(
            f"<tr><td>{title}</td><td><a download href=\"{annotated}\">Annotated PNG</a></td><td><a download href=\"{original}\">Original</a></td></tr>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(version)} screenshots</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #eef1f5; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; }}
    header {{ position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 10px; padding: 16px 24px; background: rgba(255,255,255,.96); border-bottom: 1px solid #dce2ea; }}
    h1 {{ margin: 0 auto 0 0; font-size: 20px; }}
    .pill {{ padding: 6px 10px; border-radius: 999px; background: #172033; color: white; font-size: 12px; font-weight: 700; }}
    .pill.demo {{ background: #fff1ec; color: #b84a2f; }}
    main {{ width: min(1960px, 100%); margin: 0 auto; padding: 24px; }}
    .gallery {{ display: grid; gap: 24px; }}
    .card {{ overflow: hidden; background: white; border: 1px solid #dce2ea; border-radius: 14px; box-shadow: 0 8px 24px rgba(23,32,51,.07); }}
    .card img {{ display: block; width: 100%; height: auto; background: white; }}
    .copy {{ padding: 18px 20px 20px; border-top: 1px solid #dce2ea; }}
    h2 {{ margin: 0 0 8px; font-size: 18px; }}
    p {{ margin: 0; color: #5f6b7a; line-height: 1.5; }}
    .links {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 14px; }}
    a {{ color: #8f351f; font-weight: 700; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .index {{ margin-top: 28px; padding: 20px; background: white; border: 1px solid #dce2ea; border-radius: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 11px 10px; text-align: left; border-bottom: 1px solid #e8ecf1; }}
    th {{ color: #5f6b7a; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    @media (max-width: 700px) {{ header {{ position: static; flex-wrap: wrap; }} main {{ padding: 12px; }} .index {{ overflow-x: auto; }} }}
  </style>
</head>
<body>
  <header><h1>{html.escape(version)} screenshots</h1><span class="pill">{html.escape(version)}</span><span class="pill demo">{html.escape(demo_data_label)}</span></header>
  <main>
    <section class="gallery">{''.join(cards)}</section>
    <section class="index"><table><thead><tr><th>Screenshot</th><th>Annotated</th><th>Original</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
  </main>
</body>
</html>
"""


def add_zip_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def build_zip(path: Path, root: Path, relative_paths: list[Path]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for relative_path in sorted(relative_paths, key=lambda value: value.as_posix()):
            add_zip_bytes(archive, relative_path.as_posix(), (root / relative_path).read_bytes())


def render(manifest_path: Path, output_root: Path, zip_name: str | None) -> None:
    manifest, specs = load_manifest(manifest_path)
    version = require_text(manifest.get("version"), "version")
    demo_data_label = require_text(manifest.get("demo_data_label"), "demo_data_label")
    gutter_width = manifest.get("gutter_width", 320)
    if not isinstance(gutter_width, int) or not 280 <= gutter_width <= 600:
        fail("gutter_width must be an integer from 280 to 600")

    annotated_dir = output_root / ANNOTATED_DIRNAME
    originals_dir = output_root / ORIGINALS_DIRNAME
    annotated_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    package_paths: list[Path] = []
    for spec in specs:
        try:
            raw_relative = spec.raw_path.relative_to(output_root)
        except ValueError:
            fail(f"raw capture must be inside the output directory: {spec.raw_path}")
        original_suffix = spec.raw_path.suffix.lower() or ".png"
        original_relative = Path(ORIGINALS_DIRNAME) / f"{spec.slug}{original_suffix}"
        annotated_relative = Path(ANNOTATED_DIRNAME) / f"{spec.slug}.png"
        shutil.copy2(spec.raw_path, output_root / original_relative)
        width, height = render_screenshot(
            spec,
            version=version,
            demo_data_label=demo_data_label,
            gutter_width=gutter_width,
            destination=output_root / annotated_relative,
        )
        records.append(
            {
                "title": spec.title,
                "caption": spec.caption,
                "annotated": annotated_relative.as_posix(),
                "original": original_relative.as_posix(),
            }
        )
        package_paths.extend([raw_relative, annotated_relative, original_relative])
        print(f"rendered {spec.slug}: {width}x{height}")

    index_path = output_root / "index.html"
    index_path.write_text(
        gallery_html(version=version, demo_data_label=demo_data_label, records=records),
        encoding="utf-8",
    )
    support_paths = [Path("README.md"), Path("QA.md"), Path("annotate.py"), Path("manifest.json")]
    for support_path in support_paths:
        if not (output_root / support_path).is_file():
            fail(f"package support file is missing: {support_path}")
    package_paths.extend([Path("index.html"), *support_paths])
    print(f"gallery: {index_path}")
    if zip_name:
        zip_path = output_root / zip_name
        build_zip(zip_path, output_root, package_paths)
        print(f"zip: {zip_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--zip-name", default="release-0.91.66-screenshots.zip")
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest_path = args.manifest.expanduser().resolve()
        output_root = args.output_dir.expanduser().resolve()
        _manifest, specs = load_manifest(manifest_path)
        for spec in specs:
            with Image.open(spec.raw_path) as image:
                validate_geometry(spec, image.width, image.height)
        if args.validate_only:
            print(f"valid: {len(specs)} screenshot(s), {sum(len(spec.callouts) for spec in specs)} callout(s)")
            return 0
        zip_name = None if args.no_zip else Path(args.zip_name).name
        if zip_name and not zip_name.lower().endswith(".zip"):
            fail("zip name must end with .zip")
        output_root.mkdir(parents=True, exist_ok=True)
        render(manifest_path, output_root, zip_name)
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
