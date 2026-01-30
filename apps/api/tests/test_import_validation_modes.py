"""Tests for CSV import validation modes."""

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import import_service
from app.utils.normalization import normalize_email


def make_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines).encode("utf-8")


def test_import_lenient_drops_invalid_fields(db, test_org, test_user):
    rows = [
        {
            "full_name": "Lenient User",
            "email": "lenient@example.com",
            "phone": "p:123",  # invalid US phone
            "weight_lb": "160 lbs",
            "num_deliveries": "2 kids",
        }
    ]
    csv_data = make_csv(rows)

    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="lenient.csv",
        total_rows=1,
        file_content=csv_data,
    )

    mappings = [
        import_service.ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        import_service.ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
        import_service.ColumnMapping(
            csv_column="phone",
            surrogate_field="phone",
            transformation="phone_normalize",
            action="map",
        ),
        import_service.ColumnMapping(
            csv_column="weight_lb",
            surrogate_field="weight_lb",
            transformation="int_flexible",
            action="map",
        ),
        import_service.ColumnMapping(
            csv_column="num_deliveries",
            surrogate_field="num_deliveries",
            transformation="int_flexible",
            action="map",
        ),
    ]

    result = import_service.execute_import_with_mappings(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=csv_data,
        column_mappings=mappings,
        validation_mode="drop_invalid_fields",
    )

    assert result.imported == 1
    email_hash = hash_email(normalize_email("lenient@example.com"))
    surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.organization_id == test_org.id, Surrogate.email_hash == email_hash)
        .first()
    )
    assert surrogate is not None
    assert surrogate.phone is None
    assert surrogate.weight_lb == 160
    assert surrogate.num_deliveries == 2
