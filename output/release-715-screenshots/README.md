# Release 0.91.66 candidate screenshots

These exact browser captures document current local QA with synthetic data. They do not represent a deployed release or production provider validation.

## Contents

- `raw/`: selected browser captures used by the manifest.
- `annotated/`: native-size captures with numbered callouts.
- `originals/`: byte-identical copies of the selected raw captures.
- `index.html`: local gallery with annotated and original downloads.
- `manifest.json`: titles, captions, and source-pixel callout coordinates.
- `QA.md`: verified results and remaining validation limits.
- `annotate.py`: deterministic renderer and packager.

## Rebuild

The package was rendered with Python 3.14 and Pillow 12.3.

```bash
python3 annotate.py --manifest manifest.json --validate-only
python3 annotate.py --manifest manifest.json --no-zip
python3 annotate.py --manifest manifest.json --zip-name release-0.91.66-screenshots.zip
```

`rawpath`, `rect`, `point`, and `marker_point` values use source-image pixels. Each callout requires `label`, `body`, and exactly one of `rect` or `point`. The optional `marker_point` places a rectangle callout's number in adjacent whitespace. The renderer keeps source screenshots at native size and adds the title header, callout gutter, caption, gallery, original copies, and deterministic ZIP.
