"""Temporary bounded reproduction of clone query-shape disagreement."""

from collections import Counter

from sqlalchemy import text

from app.db.models import Surrogate
from app.schemas.record_scope import RecordScopeRule
from app.services import pipeline_service
from app.services import record_scope_service as scopes
from tests.test_record_scopes_v2 import _record, _stage_history, context  # noqa: F401


def test_bulk_paused_phase_memoize(db, context):  # noqa: F811 - imported pytest fixture
    pipeline = pipeline_service.get_or_create_default_pipeline(db, context.org.id)
    stages = {stage.stage_key: stage for stage in pipeline.stages}
    expected = {}
    for index in range(1, 1201):
        key = "on_hold" if index > 1190 else "lost"
        record = _record(
            db, context.intake, "surrogate", key=key, paused="lost" if key == "on_hold" else None, suffix=index
        )
        phase = index % 3
        if phase != 2:
            origin = stages["contacted" if phase == 0 else "approved"]
            _stage_history(db, record, "surrogate", origin.id, stages["disqualified"].id)
            _stage_history(db, record, "surrogate", stages["disqualified"].id, stages["lost"].id)
            _stage_history(db, record, "surrogate", stages["lost"].id, stages["on_hold"].id)
        expected[record.id] = (phase == 1, phase == 0)
    db.execute(text("ANALYZE surrogates, surrogate_status_history, pipeline_stages, pipelines"))
    for setting in (
        "SET LOCAL jit = off",
        "SET LOCAL enable_hashjoin = off",
        "SET LOCAL enable_mergejoin = off",
        "SET LOCAL enable_material = off",
        "SET LOCAL enable_memoize = on",
    ):
        db.execute(text(setting))
    post = scopes._stage_filter(
        context.admin, "surrogate", Surrogate,
        RecordScopeRule(assignment="all", phase="post_approval"),
    )
    pre = scopes._stage_filter(
        context.admin, "surrogate", Surrogate,
        RecordScopeRule(assignment="all", phase="pre_approval"),
    )
    query = db.query(Surrogate.id, post, pre).filter(Surrogate.organization_id == context.org.id)
    sql = str(query.statement.compile(db.bind, compile_kwargs={"literal_binds": True}))
    plan = db.execute(text("EXPLAIN (FORMAT JSON) " + sql)).scalar_one()[0]["Plan"]
    counts = Counter()
    def count_nodes(node):
        counts[node["Node Type"]] += 1
        if node["Node Type"] == "Memoize":
            print({"cache_key": node.get("Cache Key")})
        for child in node.get("Plans", []):
            count_nodes(child)
    count_nodes(plan)
    actual = {record_id: (is_post, is_pre) for record_id, is_post, is_pre in query}
    print({"node_counts": dict(counts), "mismatches": sum(actual[key] != value for key, value in expected.items())})
    assert actual == expected
    candidates = scopes._handoff_candidates(db, context.org.id)
    assert {row["record_id"]: row["phase_requires_review"] for row in candidates} == {
        str(record_id): not is_post and not is_pre
        for record_id, (is_post, is_pre) in expected.items()
        if is_post or not is_pre
    }
