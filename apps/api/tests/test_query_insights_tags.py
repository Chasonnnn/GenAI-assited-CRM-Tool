from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.query_insights import (
    add_query_insights_comment,
    query_insights_request_context,
    set_query_insights_context,
)


def test_query_insights_comment_contains_only_low_cardinality_route_and_release() -> None:
    raw_identifier = "94af34d3-d8c1-4aac-b942-e3767f515b6a"
    with set_query_insights_context(
        method="GET",
        route_template="/surrogates/{surrogate_id}",
        release="0.91.33",
    ):
        statement = add_query_insights_comment(
            "SELECT * FROM surrogates WHERE id = %(surrogate_id)s",
        )

    assert "route='GET%%20%%2Fsurrogates%%2F%%7Bsurrogate_id%%7D'" in statement
    assert "release='0.91.33'" in statement
    assert raw_identifier not in statement
    assert "%(surrogate_id)s" in statement


def test_query_insights_comment_is_absent_without_request_context() -> None:
    query = "SELECT 1"

    assert add_query_insights_comment(query) == query


@pytest.mark.asyncio
async def test_fastapi_dependency_uses_matched_route_template(monkeypatch) -> None:
    monkeypatch.setattr("app.core.query_insights.settings.VERSION", "0.91.33")
    request = SimpleNamespace(
        method="GET",
        scope={"route": SimpleNamespace(path="/tasks/{task_id}")},
    )

    dependency = query_insights_request_context(request)
    await anext(dependency)
    try:
        tagged = add_query_insights_comment("SELECT * FROM tasks WHERE id = $1")
        assert "route='GET%%20%%2Ftasks%%2F%%7Btask_id%%7D'" in tagged
    finally:
        with pytest.raises(StopAsyncIteration):
            await anext(dependency)
