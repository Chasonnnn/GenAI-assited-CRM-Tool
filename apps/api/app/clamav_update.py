"""Scheduled ClamAV signature updater (Cloud Run job entrypoint)."""

from __future__ import annotations

import logging

from app.services import clamav_signature_service


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> None:
    clamav_signature_service.update_signatures()


if __name__ == "__main__":
    main()
