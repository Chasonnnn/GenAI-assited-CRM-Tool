from __future__ import annotations

import json
import subprocess

import pytest
from cryptography.fernet import Fernet

from scripts.performance import __main__ as performance_main
from scripts.performance import orchestrator
from scripts.performance.corpus import QueryFingerprint, normalize_query, select_corpus
from scripts.performance.gates import compare_plan_reports
from scripts.performance.plans import (
    PlanInvariant,
    PreparedPlanMode,
    QueryWorkload,
    compare_plan_metrics,
    compare_query_workloads,
    extract_plan_metrics,
    plan_cache_settings,
)
from scripts.performance.profiles import get_seed_profile
from scripts.performance.reporting import compare_load_summaries, serialize_safe_report
from scripts.performance.statistics import (
    StatisticsAllowlist,
    StatisticsSafetyError,
    sanitize_statistics_dump,
)
from scripts.performance.statistics_artifacts import (
    export_encrypted_statistics,
    restore_encrypted_statistics,
)


def _plan(
    *,
    node_type: str = "Index Scan",
    index_name: str | None = "ix_surrogates_org_stage",
    total_cost: float = 100.0,
    shared_hit: int = 100,
    shared_read: int = 0,
    actual_rows: int = 100,
    rows_removed: int = 0,
    loops: int = 1,
    temp_written: int = 0,
) -> list[dict[str, object]]:
    node: dict[str, object] = {
        "Node Type": node_type,
        "Relation Name": "surrogates",
        "Total Cost": total_cost,
        "Plan Rows": actual_rows,
        "Actual Rows": actual_rows,
        "Actual Loops": loops,
        "Rows Removed by Filter": rows_removed,
        "Shared Hit Blocks": shared_hit,
        "Shared Read Blocks": shared_read,
        "Temp Read Blocks": 0,
        "Temp Written Blocks": temp_written,
        "WAL Records": 0,
        "WAL FPI": 0,
        "WAL Bytes": 0,
    }
    if index_name is not None:
        node["Index Name"] = index_name
    return [{"Plan": node}]


def test_k6_summary_parser_supports_current_flat_export_schema(tmp_path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "metrics": {
                    "http_req_duration": {
                        "med": 44.328,
                        "p(95)": 106.7264,
                        "p(99)": 242.73936,
                    },
                    "http_reqs": {"count": 2653, "rate": 21.938715},
                    "http_req_failed": {"value": 0.0018846588},
                }
            }
        )
    )

    assert performance_main._k6_summary(summary) == {
        "error_rate": pytest.approx(0.0018846588),
        "p50_ms": pytest.approx(44.328),
        "p95_ms": pytest.approx(106.7264),
        "p99_ms": pytest.approx(242.73936),
        "request_count": pytest.approx(2653),
        "throughput_rps": pytest.approx(21.938715),
    }


def test_database_work_is_normalized_per_http_request() -> None:
    assert performance_main._database_work_per_request(
        {
            "calls": 200,
            "logical_blocks": 1_000,
            "rows_returned_or_affected": 500,
            "temp_blocks": 0,
        },
        request_count=100,
    ) == {
        "calls": 2.0,
        "logical_blocks": 10.0,
        "rows_returned_or_affected": 5.0,
        "temp_blocks": 0.0,
    }


def test_load_report_uses_null_for_delta_from_zero_baseline() -> None:
    comparison = compare_load_summaries(
        base={"error_rate": 0.0},
        candidate={"error_rate": 0.01},
    )

    assert comparison.metrics["error_rate"]["delta_percent"] is None
    assert "Infinity" not in serialize_safe_report({"metrics": comparison.metrics})


def test_seed_profiles_are_deterministic_multi_tenant_and_growth_scaled() -> None:
    smoke = get_seed_profile("smoke")
    production = get_seed_profile("production")
    growth = get_seed_profile("growth10x")

    assert smoke.random_seed == production.random_seed == growth.random_seed
    assert smoke.organization_count >= 2
    assert production.organization_count >= 3
    assert production.total_surrogates > smoke.total_surrogates
    assert growth.total_surrogates == production.total_surrogates * 10
    assert growth.total_intended_parents == production.total_intended_parents * 10
    assert growth.total_matches == production.total_matches * 10
    assert growth.total_tasks == production.total_tasks * 10
    assert production.organization_weights[0] > production.organization_weights[-1]
    assert len({org.organization_id for org in production.organizations}) == 3


def test_query_normalization_removes_bind_values_and_comments() -> None:
    normalized = normalize_query(
        "SELECT * /* route: surrogate */ FROM surrogates "
        "WHERE email = 'alice@example.com' AND organization_id = 12345"
    )

    assert "alice@example.com" not in normalized
    assert "12345" not in normalized
    assert "route:" not in normalized
    assert normalized == normalized.lower()


def test_corpus_prioritizes_database_time_one_percent_and_critical_routes() -> None:
    samples = [
        QueryFingerprint(
            fingerprint=f"q-{index}",
            normalized_query=f"select * from table_{index} where id = $1",
            total_exec_time_ms=float(1_000 - index),
            calls=100,
            route=None,
        )
        for index in range(120)
    ]
    samples.extend(
        [
            QueryFingerprint(
                fingerprint="one-percent",
                normalized_query="select count(*) from surrogates",
                total_exec_time_ms=50_000,
                calls=2,
                route=None,
            ),
            QueryFingerprint(
                fingerprint="critical-low-volume",
                normalized_query="select summary from intelligent_suggestions where org_id = $1",
                total_exec_time_ms=1,
                calls=1,
                route="GET /surrogates/intelligent-suggestions/summary",
            ),
        ]
    )

    corpus = select_corpus(
        samples,
        critical_routes={"GET /surrogates/intelligent-suggestions/summary"},
        limit=100,
    )

    fingerprints = {sample.fingerprint for sample in corpus}
    assert len(corpus) == 100
    assert "one-percent" in fingerprints
    assert "critical-low-volume" in fingerprints
    assert corpus[0].fingerprint == "one-percent"


def test_statistics_sanitizer_keeps_only_allowlisted_non_pii_statistics() -> None:
    allowlist = StatisticsAllowlist.from_mapping(
        {
            "public.surrogates": {
                "columns": ["organization_id", "stage_id", "is_archived"],
            }
        }
    )
    dump = """
SELECT * FROM pg_catalog.pg_restore_relation_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'relpages', '42', 'reltuples', '1000');
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'attname', 'stage_id',
    'n_distinct', '12', 'most_common_vals', '{new,qualified,matched}');
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'attname', 'created_at',
    'n_distinct', '-0.8');
"""

    sanitized = sanitize_statistics_dump(dump, allowlist)

    assert "pg_restore_relation_stats" in sanitized
    assert "'stage_id'" in sanitized
    assert "'created_at'" not in sanitized


def test_statistics_sanitizer_accepts_pg18_dump_comments_containing_semicolons() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.surrogates": {"columns": ["stage_id"]}})
    dump = """
--
-- Statistics for Name: surrogates; Type: STATISTICS DATA; Schema: public; Owner: -
--

SELECT * FROM pg_catalog.pg_restore_relation_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'relpages', '42'::integer, 'reltuples', '1000'::real, 'relallvisible', '0'::integer);
"""

    sanitized = sanitize_statistics_dump(dump, allowlist)

    assert sanitized.count("pg_restore_relation_stats") == 1


def test_statistics_sanitizer_does_not_mistake_decimal_stats_for_phone_numbers() -> None:
    allowlist = StatisticsAllowlist.from_mapping(
        {"public.surrogate_activity_log": {"columns": ["activity_type"]}}
    )
    dump = """
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'version', '180001'::integer, 'schemaname', 'public',
    'relname', 'surrogate_activity_log', 'attname', 'activity_type',
    'stanumbers1', '{0.0063567436}'::real[]);
"""

    sanitized = sanitize_statistics_dump(dump, allowlist)

    assert "activity_type" in sanitized


def test_statistics_sanitizer_does_not_mistake_uuid_fragments_for_phone_numbers() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.matches": {"columns": ["surrogate_id"]}})
    dump = """
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'version', '180001'::integer, 'schemaname', 'public',
    'relname', 'matches', 'attname', 'surrogate_id',
    'stavalues1', '{9978913154-bf6f-4f0b-b8f2-6d727-9707874}'::text[]);
"""

    sanitized = sanitize_statistics_dump(dump, allowlist)

    assert "surrogate_id" in sanitized


def test_statistics_sanitizer_rejects_standalone_phone_values() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.surrogates": {"columns": ["source"]}})
    dump = """
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'attname', 'source',
    'most_common_vals', '{referral,+1 512-555-0100}');
"""

    with pytest.raises(StatisticsSafetyError, match="PII-like value"):
        sanitize_statistics_dump(dump, allowlist)


@pytest.mark.parametrize("column", ["email", "phone", "first_name", "last_name"])
def test_statistics_sanitizer_rejects_direct_pii_columns(column: str) -> None:
    with pytest.raises(StatisticsSafetyError, match="PII column"):
        StatisticsAllowlist.from_mapping(
            {"public.surrogates": {"columns": ["organization_id", column]}}
        )


def test_statistics_sanitizer_drops_non_allowlisted_pii_from_full_relation_dump() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.surrogates": {"columns": ["stage_id"]}})
    dump = """
SELECT * FROM pg_catalog.pg_restore_relation_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'relpages', '42'::integer, 'reltuples', '1000'::real, 'relallvisible', '0'::integer);
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'attname', 'stage_id', 'n_distinct', '12'::real);
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'attname', 'email', 'most_common_vals', '{alice@example.com}'::text);
"""

    sanitized = sanitize_statistics_dump(dump, allowlist)

    assert "stage_id" in sanitized
    assert "email" not in sanitized
    assert "alice@example.com" not in sanitized


def test_statistics_sanitizer_rejects_pii_values_even_on_allowlisted_columns() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.surrogates": {"columns": ["source"]}})
    dump = """
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'attname', 'source',
    'most_common_vals', '{referral,alice@example.com}');
"""

    with pytest.raises(StatisticsSafetyError, match="PII-like value"):
        sanitize_statistics_dump(dump, allowlist)


def test_statistics_sanitizer_rejects_non_restore_sql_in_a_retained_statement() -> None:
    allowlist = StatisticsAllowlist.from_mapping({"public.surrogates": {"columns": ["stage_id"]}})
    dump = """
SELECT dangerous_function(), pg_catalog.pg_restore_relation_stats(
    'schemaname', 'public', 'relname', 'surrogates', 'relpages', '42');
"""

    with pytest.raises(StatisticsSafetyError, match="Unexpected SQL"):
        sanitize_statistics_dump(dump, allowlist)


def test_statistics_artifact_is_encrypted_and_restored_without_plaintext_files(
    tmp_path, monkeypatch
) -> None:
    allowlist_path = tmp_path / "allowlist.json"
    allowlist_path.write_text(json.dumps({"public.surrogates": {"columns": ["stage_id"]}}))
    dump = """
SELECT * FROM pg_catalog.pg_restore_relation_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'relpages', '42'::integer, 'reltuples', '1000'::real, 'relallvisible', '0'::integer);
SELECT * FROM pg_catalog.pg_restore_attribute_stats(
    'version', '180001'::integer, 'schemaname', 'public', 'relname', 'surrogates',
    'attname', 'stage_id', 'n_distinct', '12'::real);
"""
    restored_sql: list[str] = []

    def fake_run(command, **kwargs):
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, stdout="pg_dump (PostgreSQL) 18.1\n")
        if command[0] == "pg_dump":
            return subprocess.CompletedProcess(command, 0, stdout=dump, stderr="")
        restored_sql.append(kwargs["input"])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("scripts.performance.statistics_artifacts.subprocess.run", fake_run)
    key = Fernet.generate_key()
    monkeypatch.setenv("PERFORMANCE_STATS_FERNET_KEY", key.decode("ascii"))
    artifact_path = tmp_path / "planner.stats.enc"

    export_encrypted_statistics(
        database_url="postgresql://example.invalid/database",
        allowlist_path=allowlist_path,
        output_path=artifact_path,
    )

    assert b"pg_restore_relation_stats" not in artifact_path.read_bytes()
    assert not list(tmp_path.glob("*.sql"))

    restore_encrypted_statistics(
        database_url="postgresql://example.invalid/database",
        allowlist_path=allowlist_path,
        artifact_path=artifact_path,
    )

    assert len(restored_sql) == 1
    assert "pg_restore_relation_stats" in restored_sql[0]
    assert "ANALYZE" not in restored_sql[0].upper()


def test_plan_metrics_use_root_buffers_and_relation_scan_work() -> None:
    document = _plan(shared_hit=180, shared_read=20, actual_rows=40, rows_removed=60, loops=2)

    metrics = extract_plan_metrics(document)

    assert metrics.logical_blocks == 200
    assert metrics.scanned_rows == 200
    assert metrics.loop_count == 2
    assert metrics.node_types == {"Index Scan"}
    assert metrics.indexes == {"ix_surrogates_org_stage"}
    assert metrics.relations == {"surrogates"}


def test_base_versus_base_has_no_deterministic_regressions() -> None:
    metrics = extract_plan_metrics(_plan())
    invariant = PlanInvariant(required_indexes={"ix_surrogates_org_stage"})

    assert compare_plan_metrics(metrics, metrics, invariant) == []


def test_buffer_and_scan_amplification_cross_dual_budgets() -> None:
    base = extract_plan_metrics(_plan(shared_hit=100, actual_rows=100))
    candidate = extract_plan_metrics(_plan(shared_hit=140, actual_rows=100, rows_removed=120))

    failures = compare_plan_metrics(base, candidate, PlanInvariant())

    assert {failure.metric for failure in failures} >= {"logical_blocks", "scanned_rows"}


def test_small_relative_changes_do_not_cross_absolute_budgets() -> None:
    base = extract_plan_metrics(_plan(shared_hit=10, actual_rows=10))
    candidate = extract_plan_metrics(_plan(shared_hit=20, actual_rows=20))

    failures = compare_plan_metrics(base, candidate, PlanInvariant())

    assert failures == []


def test_new_temporary_blocks_and_required_index_violation_fail() -> None:
    base = extract_plan_metrics(_plan())
    candidate = extract_plan_metrics(_plan(node_type="Seq Scan", index_name=None, temp_written=1))
    invariant = PlanInvariant(required_indexes={"ix_surrogates_org_stage"})

    failures = compare_plan_metrics(base, candidate, invariant)

    assert {failure.metric for failure in failures} >= {"temp_blocks", "required_index"}


def test_legitimate_sequential_scan_remains_accepted() -> None:
    metrics = extract_plan_metrics(_plan(node_type="Seq Scan", index_name=None))

    assert (
        compare_plan_metrics(
            metrics,
            metrics,
            PlanInvariant(allow_sequential_scan=True),
        )
        == []
    )


def test_cost_growth_only_fails_with_adverse_structure() -> None:
    base = extract_plan_metrics(_plan(total_cost=100))
    same_shape = extract_plan_metrics(_plan(total_cost=130))
    adverse = extract_plan_metrics(_plan(node_type="Seq Scan", index_name=None, total_cost=130))

    assert compare_plan_metrics(base, same_shape, PlanInvariant()) == []
    failures = compare_plan_metrics(
        base,
        adverse,
        PlanInvariant(allow_sequential_scan=False),
    )
    assert "estimated_cost" in {failure.metric for failure in failures}


def test_intentional_n_plus_one_fails_query_count_and_duplicate_validation() -> None:
    base = QueryWorkload(query_count=3, fingerprint_counts={"surrogate": 1, "owner": 1})
    candidate = QueryWorkload(query_count=12, fingerprint_counts={"surrogate": 1, "owner": 10})

    failures = compare_query_workloads(base, candidate)

    assert {failure.metric for failure in failures} == {"query_count", "duplicate_fingerprint"}


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (PreparedPlanMode.GENERIC, "force_generic_plan"),
        (PreparedPlanMode.CUSTOM, "force_custom_plan"),
        (PreparedPlanMode.AUTOMATIC, "auto"),
    ],
)
def test_prepared_plan_modes_are_explicit(mode: PreparedPlanMode, expected: str) -> None:
    settings = plan_cache_settings(mode)

    assert settings == ("SET LOCAL plan_cache_mode = %s", (expected,))


def test_wall_clock_load_comparison_is_always_advisory() -> None:
    comparison = compare_load_summaries(
        base={"p50_ms": 100, "p95_ms": 200, "p99_ms": 300, "throughput_rps": 20},
        candidate={"p50_ms": 300, "p95_ms": 900, "p99_ms": 2_000, "throughput_rps": 5},
    )

    assert comparison.advisory is True
    assert comparison.gate_failures == ()
    assert comparison.metrics["p95_ms"]["delta_percent"] == 350.0


def test_safe_report_rejects_sensitive_keys_and_values() -> None:
    assert json.loads(
        serialize_safe_report({"fingerprint": "abc", "logical_blocks": 20, "parameter_count": 2})
    )

    with pytest.raises(ValueError, match="sensitive report key"):
        serialize_safe_report({"cookie": "session=secret"})
    with pytest.raises(ValueError, match="sensitive report value"):
        serialize_safe_report({"route": "alice@example.com"})


def test_gate_consumes_privacy_safe_capture_reports(tmp_path) -> None:
    capture = {
        "schema_version": 1,
        "captures": [
            {
                "query_id": "surrogates_list",
                "scenario": "hot",
                "prepared_plan_mode": "custom",
                "capture_mode": "analyze",
                "parameter_count": 1,
                "automatic_warmup_count": 0,
                "plan": _plan(),
            }
        ],
    }
    base_path = tmp_path / "base.json"
    candidate_path = tmp_path / "candidate.json"
    expectations_path = tmp_path / "expectations.json"
    base_path.write_text(json.dumps(capture))
    candidate_path.write_text(json.dumps(capture))
    expectations_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "queries": {
                    "surrogates_list": {
                        "required_indexes": ["ix_surrogates_org_stage"],
                    }
                },
            }
        )
    )

    report, failed = compare_plan_reports(
        base_report_path=base_path,
        candidate_report_path=candidate_path,
        expectations_path=expectations_path,
    )

    assert failed is False
    assert report["gate"] == "passed"
    assert report["results"][0]["scenario"] == "hot:custom:analyze"


def test_deterministic_orchestrator_cleans_up_after_interrupt(tmp_path, monkeypatch) -> None:
    dropped: list[str] = []
    removed = []

    def fake_worktree(_repository_root, destination, _git_ref):
        destination.mkdir(parents=True)

    monkeypatch.setattr(orchestrator, "_worktree", fake_worktree)
    monkeypatch.setattr(orchestrator, "_create_database", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_prepare_database", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_disable_autovacuum", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_seed_database", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_normalize_database", lambda *_args: None)
    monkeypatch.setattr(
        orchestrator,
        "_capture_database",
        lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        orchestrator,
        "_drop_database",
        lambda _database_url, database_name: dropped.append(database_name),
    )
    monkeypatch.setattr(
        orchestrator,
        "_remove_worktree",
        lambda _repository_root, destination: removed.append(destination),
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run_deterministic_comparison(
            repository_root=tmp_path,
            base_ref="base",
            candidate_ref="candidate",
            admin_database_url="postgresql+psycopg://postgres:postgres@localhost/crm",
            results_dir=tmp_path / "results",
        )

    assert len(dropped) == 2
    assert len(removed) == 2
    assert all(not destination.exists() for destination in removed)


def test_deterministic_orchestrator_disables_autovacuum_before_seeding_and_normalizes_before_capture(
    tmp_path, monkeypatch
) -> None:
    events = []

    def fake_worktree(_repository_root, destination, _git_ref):
        destination.mkdir(parents=True)

    def fake_capture(_checkout, database_url, output_path):
        events.append(("capture", database_url))
        output_path.write_text("{}")

    monkeypatch.setattr(orchestrator, "_worktree", fake_worktree)
    monkeypatch.setattr(orchestrator, "_create_database", lambda *_args: None)
    monkeypatch.setattr(
        orchestrator,
        "_prepare_database",
        lambda _checkout, database_url: events.append(("prepare", database_url)),
    )
    monkeypatch.setattr(
        orchestrator,
        "_disable_autovacuum",
        lambda database_url: events.append(("disable_autovacuum", database_url)),
    )
    monkeypatch.setattr(
        orchestrator,
        "_seed_database",
        lambda _checkout, database_url, _profile: events.append(("seed", database_url)),
    )
    monkeypatch.setattr(
        orchestrator,
        "_normalize_database",
        lambda database_url: events.append(("normalize", database_url)),
    )
    monkeypatch.setattr(orchestrator, "_capture_database", fake_capture)
    monkeypatch.setattr(orchestrator, "_drop_database", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "_remove_worktree", lambda *_args: None)

    orchestrator.run_deterministic_comparison(
        repository_root=tmp_path,
        base_ref="base",
        candidate_ref="candidate",
        admin_database_url="postgresql+psycopg://postgres:postgres@localhost/crm",
        results_dir=tmp_path / "results",
    )

    assert [event for event, _database_url in events] == [
        "prepare",
        "prepare",
        "disable_autovacuum",
        "disable_autovacuum",
        "seed",
        "seed",
        "normalize",
        "normalize",
        "capture",
        "capture",
    ]


def test_database_normalization_uses_safe_table_identifiers_and_controlled_vacuum(
    monkeypatch,
) -> None:
    statements: list[str] = []
    connection_options: list[dict[str, object]] = []

    class Result:
        def fetchall(self):
            return [("public", "surrogates"), ("public", 'odd"table')]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement):
            rendered = statement.as_string() if hasattr(statement, "as_string") else statement
            statements.append(rendered)
            return Result()

    def fake_connect(_database_url, **options):
        connection_options.append(options)
        return Connection()

    monkeypatch.setattr(orchestrator.psycopg, "connect", fake_connect)

    database_url = "postgresql+psycopg://postgres:postgres@localhost/performance"
    orchestrator._disable_autovacuum(database_url)
    orchestrator._normalize_database(database_url)

    assert connection_options == [{"autocommit": True}, {"autocommit": True}]
    assert "c.relkind = 'r'" in statements[0]
    assert "n.nspname = 'public'" in statements[0]
    assert statements[1] == (
        'ALTER TABLE "public"."surrogates" SET '
        "(autovacuum_enabled = false, toast.autovacuum_enabled = false)"
    )
    assert statements[2] == (
        'ALTER TABLE "public"."odd""table" SET '
        "(autovacuum_enabled = false, toast.autovacuum_enabled = false)"
    )
    assert statements[3] == "VACUUM (ANALYZE)"


def test_deterministic_orchestrator_seeding_sets_isolated_encryption_key(
    tmp_path, monkeypatch
) -> None:
    captured_environment = {}
    for key in (
        "VERSION_ENCRYPTION_KEY",
        "META_ENCRYPTION_KEY",
        "DATA_ENCRYPTION_KEY",
        "FERNET_KEY",
        "PII_HASH_KEY",
        "JWT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    def fake_run(_command, *, cwd, env=None):
        assert cwd == tmp_path / "apps" / "api"
        captured_environment.update(env or {})

    monkeypatch.setattr(orchestrator, "_run", fake_run)

    orchestrator._seed_database(
        tmp_path,
        "postgresql+psycopg://postgres:postgres@localhost/performance",
        "production",
    )

    assert captured_environment["ENV"] == "test"
    assert captured_environment["SEED_PROFILE"] == "production"
    assert captured_environment["SEED_REDACT_SUMMARY"] == "1"
    for key in (
        "VERSION_ENCRYPTION_KEY",
        "META_ENCRYPTION_KEY",
        "DATA_ENCRYPTION_KEY",
        "FERNET_KEY",
    ):
        Fernet(captured_environment[key].encode("ascii"))
    assert captured_environment["PII_HASH_KEY"].startswith("local-performance-")
    assert captured_environment["JWT_SECRET"].startswith("local-performance-")
