## 2025-05-15 - Image Processing Fail-Closed
**Vulnerability:** A "fail-open" vulnerability was found in the image sanitization function (`strip_exif_data`), where invalid or malicious files masquerading as images were returned as-is when processing failed.
**Learning:** Security sanitization functions must always fail closed (reject input) on error. Assuming "if it fails, it's fine" is a dangerous pattern.
**Prevention:** Catch specific exceptions from processing libraries (e.g., `UnidentifiedImageError` from Pillow) and raise a validation error instead of returning the original input.

## 2025-05-15 - Image Processing Memory Exhaustion (DoS)
**Vulnerability:** The image processing function used `list(img.getdata())` to copy pixel data, which loads the entire uncompressed image into memory as Python objects, leading to potential Memory Exhaustion (DoS).
**Learning:** Avoid loading large binary datasets into memory structures like lists.
**Prevention:** Use streaming methods or efficient library functions (e.g., `image.save()` to a buffer) that handle data processing without full memory expansion.
