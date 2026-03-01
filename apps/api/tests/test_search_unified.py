from app.db.enums import Role
from app.services import search_service


def test_global_search_uses_single_unified_query(db, test_org, test_user, monkeypatch):
    execute_calls: list[object] = []
    original_execute = db.execute

    def counting_execute(*args, **kwargs):
        execute_calls.append(args[0] if args else None)
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(db, "execute", counting_execute)
    result = search_service.global_search(
        db=db,
        org_id=test_org.id,
        query="search text",
        user_id=test_user.id,
        role=Role.DEVELOPER.value,
        permissions={
            "view_surrogate_notes",
            "view_intended_parents",
            "view_post_approval_surrogates",
        },
        entity_types=["surrogate", "note", "attachment", "intended_parent"],
        limit=20,
        offset=0,
    )

    assert result["total"] == 0
    assert len(execute_calls) == 1


def test_global_search_builds_union_all_query(db, test_org, test_user, monkeypatch):
    captured_statements: list[object] = []
    original_execute = db.execute

    def capture_execute(*args, **kwargs):
        captured_statements.append(args[0] if args else None)
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(db, "execute", capture_execute)
    search_service.global_search(
        db=db,
        org_id=test_org.id,
        query="another search",
        user_id=test_user.id,
        role=Role.DEVELOPER.value,
        permissions={
            "view_surrogate_notes",
            "view_intended_parents",
            "view_post_approval_surrogates",
        },
        entity_types=["surrogate", "note", "attachment", "intended_parent"],
        limit=20,
        offset=0,
    )

    assert captured_statements
    sql = str(captured_statements[0]).upper()
    assert "UNION ALL" in sql
    assert sql.count("LIMIT") >= 2
