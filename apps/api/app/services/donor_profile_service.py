"""Resolve donor profiles against submitted form snapshots without mutating submissions."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Donor, FormSubmission
from app.schemas.donor_profile import DonorChecklistItem, DonorProfileFields, DonorProfileRead
from app.schemas.surrogate import mask_ssn_last4
from app.services import form_submission_service

# The shared donor pre-screening questions. Submitted snapshots supply their own labels/options.
DEFAULT_QUESTIONS = [
    {
        "key": "education",
        "label": "Education level",
        "question": "Highest education level",
        "options": [
            {"label": "High school", "value": "High school"},
            {"label": "Some college", "value": "Some college"},
            {"label": "Associate degree", "value": "Associate degree"},
            {"label": "Bachelor’s degree", "value": "Bachelor’s degree"},
            {"label": "Master’s degree", "value": "Master’s degree"},
            {
                "label": "Doctorate / professional degree",
                "value": "Doctorate / professional degree",
            },
            {"label": "Other", "value": "Other"},
        ],
    },
    {
        "key": "college",
        "label": "University / college",
        "question": "University / college",
        "options": [],
    },
    {
        "key": "nicotine",
        "label": "Nicotine / tobacco use",
        "question": "Do you currently use nicotine or tobacco products?",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "cannabis",
        "label": "Cannabis use",
        "question": "Do you currently use cannabis?",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
    {
        "key": "infectious_disease",
        "label": "Infectious disease / STI history",
        "question": "Have you ever had an infectious disease such as HIV, hepatitis B/C, or an STI?",
        "options": [
            {"label": "Yes", "value": "Yes"},
            {"label": "No", "value": "No"},
            {
                "label": "Prefer to discuss with the team",
                "value": "Prefer to discuss with the team",
            },
        ],
    },
    {
        "key": "previous_donation",
        "label": "Previous donation",
        "question": "Have you been an egg or sperm donor before?",
        "options": [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}],
    },
]

# Only fields with an established donor questionnaire meaning can fall back to form answers.
FORM_PROFILE_KEYS = {
    "date_of_birth": ("date_of_birth",),
    "race": ("race",),
    "height_ft": ("height_ft", "height"),
    "weight_lb": ("weight_lb", "weight"),
    "address_city": ("address_city", "city"),
    "address_state": ("address_state", "state"),
    **{item["key"]: (item["key"],) for item in DEFAULT_QUESTIONS},
}


def read_profile(db: Session, donor: Donor) -> DonorProfileRead:
    submission = (
        db.query(FormSubmission)
        .filter(
            FormSubmission.organization_id == donor.organization_id,
            FormSubmission.donor_id == donor.id,
        )
        .order_by(FormSubmission.submitted_at.desc(), FormSubmission.id.desc())
        .first()
    )
    return resolve_profile(donor, submission)


def resolve_profile(donor: Donor, submission: FormSubmission | None) -> DonorProfileRead:
    values = DonorProfileFields.model_validate(donor).model_dump()
    overrides = set(donor.profile_updated_fields or [])
    fields = {}
    answers = {}
    mappings = {}
    if submission and submission.schema_snapshot:
        schema = form_submission_service.parse_schema(submission.schema_snapshot)
        fields = form_submission_service.flatten_fields(schema)
        answers = submission.answers_json or {}
        fields = {
            key: field
            for key, field in fields.items()
            if form_submission_service._is_field_visible(field, answers, fields)
        }
        mappings = {
            mapping["surrogate_field"]: mapping["field_key"]
            for mapping in submission.mapping_snapshot or []
            if mapping.get("field_key") in fields
            and mapping.get("surrogate_field") in FORM_PROFILE_KEYS
        }

    matching_fields = {}
    for target, aliases in FORM_PROFILE_KEYS.items():
        field = fields.get(mappings.get(target))
        if field is None:
            field = next((fields[key] for key in aliases if key in fields), None)
        if field is None:
            continue
        matching_fields[target] = field
        if target in overrides or values.get(target) is not None:
            continue
        raw = answers.get(field.key)
        if raw in (None, "", []):
            continue
        # Choice values are stored as labels in the profile; preserve custom option labels.
        option = next((option for option in field.options or [] if option.value == raw), None)
        if option:
            raw = option.label
        try:
            if target == "height_ft" and field.type != "height":
                raw = form_submission_service._coerce_surrogate_value("height_ft", raw)
            parsed = DonorProfileFields.model_validate({target: raw})
        except ValidationError, ValueError, TypeError:
            continue
        values[target] = getattr(parsed, target)

    checklist = []
    for spec in DEFAULT_QUESTIONS:
        key = spec["key"]
        field = matching_fields.get(key)
        # A submitted form defines which questions were actually asked.
        if submission and not field and values[key] is None and key not in overrides:
            continue
        options = spec["options"]
        if field and field.options:
            # Profile values use the human-readable answer, never a template's internal id.
            options = [{"value": option.label, "label": option.label} for option in field.options]
        checklist.append(
            DonorChecklistItem(
                key=key,
                label=spec["label"],
                question=field.label if field else spec["question"],
                value=values[key],
                options=options,
            )
        )

    return DonorProfileRead(
        **values,
        ssn_masked=mask_ssn_last4(donor.ssn_last4),
        partner_ssn_masked=mask_ssn_last4(donor.partner_ssn_last4),
        eligibility_checklist=checklist,
    )
