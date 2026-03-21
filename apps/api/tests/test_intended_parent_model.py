from app.db.models.intended_parents import IntendedParent


def test_intended_parent_stage_id_is_not_nullable() -> None:
    assert IntendedParent.__table__.c.stage_id.nullable is False
