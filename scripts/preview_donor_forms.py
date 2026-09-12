"""Create EWI donor templates in the isolated local preview database only."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.schemas.forms import FormSchema  # noqa: E402
from app.services import platform_template_service  # noqa: E402


def main() -> None:
    url = make_url(settings.DATABASE_URL.get_secret_value())
    if not (
        settings.ENV == "dev"
        and url.host == "127.0.0.1"
        and url.port == 5549
        and url.database == "crm_donor_preview"
        and settings.API_BASE_URL == "http://127.0.0.1:8027"
    ):
        raise SystemExit("This script requires the isolated local donor preview environment.")

    schema = FormSchema.model_validate_json(
        (ROOT / "scripts/fixtures/ewi-donor-pre-screening.json").read_text()
    ).model_dump(mode="json", exclude_none=True)
    mappings = [
        {"field_key": key, "surrogate_field": key}
        for key in ("full_name", "email", "phone", "state", "education", "profile_photo")
    ]
    with httpx.Client(base_url=settings.API_BASE_URL, timeout=30) as client:
        dev_headers = {"X-Dev-Secret": settings.DEV_SECRET.get_secret_value()}
        response = client.post("/dev/seed", headers=dev_headers)
        response.raise_for_status()
        seeded = response.json()
        admin = next(user for user in seeded["users"] if user["email"] == "admin@test.com")
        response = client.post(f"/dev/login-as/{admin['user_id']}", headers=dev_headers)
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = client.cookies["crm_csrf"]

        def request(method: str, path: str, **kwargs):
            result = client.request(method, path, **kwargs)
            if not result.is_success:
                # These endpoints contain only this script's synthetic template data.
                raise RuntimeError(f"{method} {path}: {result.status_code} {result.text[:500]}")
            return result.json()

        forms = request("GET", "/forms")
        previews = {}
        for kind, label in (("egg_donor", "Egg donor"), ("sperm_donor", "Sperm donor")):
            name = f"EWI {label.lower()} pre-screening — local preview"
            donor_schema = {**deepcopy(schema), "public_title": f"{label} pre-questionnaire"}
            for page in donor_schema["pages"]:
                for field in page["fields"]:
                    if field["key"] == "previous_donation":
                        field["label"] = (
                            f"Have you been an {label.lower()} before?"
                            if kind == "egg_donor"
                            else "Have you been a sperm donor before?"
                        )
            template_settings = {
                "purpose": "other",
                "lead_kind": kind,
                "max_file_count": 1,
                "max_file_size_bytes": 10 * 1024 * 1024,
                "allowed_mime_types": ["image/png", "image/jpeg"],
                "mappings": mappings,
            }
            with SessionLocal() as db:
                template = next(
                    (
                        item
                        for item in platform_template_service.list_platform_form_templates(db)
                        if item.name == name
                    ),
                    None,
                )
                if template is None:
                    template = platform_template_service.create_platform_form_template(
                        db,
                        name=name,
                        description="EWI donor template for local review.",
                        schema_json=donor_schema,
                        settings_json=template_settings,
                    )
                else:
                    platform_template_service.update_platform_form_template(
                        db,
                        template,
                        name=name,
                        description=template.description,
                        schema_json=donor_schema,
                        settings_json=template_settings,
                        expected_version=template.current_version,
                    )
                platform_template_service.publish_platform_form_template(
                    db,
                    template,
                    publish_all=False,
                    org_ids=[UUID(seeded["org_id"])],
                )
                template_id = str(template.id)
            form = next((item for item in forms if item["name"] == name), None)
            if form is None:
                form = request("POST", f"/forms/templates/{template_id}/use", json={"name": name})
            else:
                request("PATCH", f"/forms/{form['id']}", json={"form_schema": donor_schema})
            request("POST", f"/forms/{form['id']}/publish")
            links = request("GET", f"/forms/{form['id']}/intake-links")
            link = links[0]
            link = request(
                "PATCH",
                f"/forms/intake-links/{link['id']}",
                json={
                    "embed_enabled": True,
                    "allowed_embed_origins": ["http://127.0.0.1:3027"],
                    "tracking_mode": "internal_only",
                    "privacy_policy_url": "http://127.0.0.1:3027/prototype/privacy/",
                },
            )
            previews[kind] = {
                "template_id": template_id,
                "form_id": form["id"],
                "slug": link["slug"],
                "builder_url": f"http://127.0.0.1:3037/forms/{form['id']}",
                "intake_url": f"http://127.0.0.1:3037/intake/{link['slug']}",
            }
        print(json.dumps(previews, indent=2))


if __name__ == "__main__":
    main()
