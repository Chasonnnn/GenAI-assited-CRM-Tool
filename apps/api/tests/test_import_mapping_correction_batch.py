from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import event

from app.db.models import Organization
from app.db.models.surrogates import ImportMappingCorrection
from app.services.import_service import ColumnMapping, store_mapping_corrections


@contextmanager
def correction_selects(db):
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("SELECT") and "FROM import_mapping_corrections" in statement:
            statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)


def mapping(column, field="full_name", action="map", transformation=None):
    return ColumnMapping(column, field, transformation, action)


def test_corrections_batch_normalized_duplicates_without_autoflush(db, test_org):
    assert db.autoflush is False
    with correction_selects(db) as statements:
        store_mapping_corrections(
            db, test_org.id, [], [mapping("Extra"), mapping("extra?"), mapping("Other")]
        )
    db.flush()
    corrections = db.query(ImportMappingCorrection).filter_by(organization_id=test_org.id).all()
    assert {row.column_name_normalized: row.times_used for row in corrections} == {
        "extra": 2,
        "other": 1,
    }
    assert len(statements) == 1


def test_corrections_update_only_selected_org_and_skip_unchanged_or_ignored(db, test_org):
    other_org = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    own = ImportMappingCorrection(
        organization_id=test_org.id,
        column_name_normalized="extra",
        corrected_field="email",
        corrected_action="map",
        times_used=4,
    )
    foreign = ImportMappingCorrection(
        organization_id=other_org.id,
        column_name_normalized="extra",
        corrected_field="email",
        corrected_action="map",
        times_used=7,
    )
    db.add_all([own, foreign])
    db.flush()
    with correction_selects(db) as statements:
        store_mapping_corrections(
            db,
            test_org.id,
            [{"csv_column": "Unchanged", "suggested_field": "full_name", "transformation": None}],
            [
                mapping("Extra"),
                mapping("extra?"),
                mapping("Ignored", action="ignore"),
                mapping("Unchanged"),
                mapping("?"),
                mapping("Invalid custom", action="custom"),
            ],
        )
    db.flush()
    assert (own.corrected_field, own.times_used) == ("full_name", 2)
    db.refresh(foreign)
    assert (foreign.corrected_field, foreign.times_used) == ("email", 7)
    assert db.query(ImportMappingCorrection).filter_by(organization_id=test_org.id).count() == 1
    assert len(statements) == 1
