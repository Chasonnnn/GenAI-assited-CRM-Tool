"""Read-only PostgreSQL contention diagnostics without query text or customer rows."""

import json
import os

import psycopg
from sqlalchemy.engine import make_url

QUERIES = {
    "settings": """
        SELECT name, setting FROM pg_settings
        WHERE name IN ('max_connections', 'work_mem', 'jit', 'statement_timeout',
                      'lock_timeout', 'default_transaction_read_only',
                      'effective_cache_size', 'shared_buffers', 'random_page_cost')
        ORDER BY name
    """,
    "activity": """
        SELECT state, wait_event_type, wait_event, count(*) AS connections,
               max(extract(epoch FROM now() - query_start))::integer AS max_query_seconds,
               max(cardinality(pg_blocking_pids(pid))) AS max_blockers,
               bool_or(query LIKE '%surrogate_activity_log%'
                       AND query LIKE '%UNION ALL%') AS match_activity_query,
               bool_or(query LIKE '%audit_logs%') AS audit_query,
               bool_or(query LIKE '%tasks%') AS tasks_query
        FROM pg_stat_activity
        WHERE datname = current_database() AND pid <> pg_backend_pid()
        GROUP BY state, wait_event_type, wait_event
    """,
    "table_statistics": """
        SELECT relname, n_live_tup, n_dead_tup, last_analyze, last_autoanalyze,
               seq_scan, idx_scan
        FROM pg_stat_user_tables
        WHERE relname IN ('audit_logs', 'surrogate_activity_log', 'entity_activity_logs',
                          'tasks', 'entity_notes', 'attachments', 'matches', 'user_sessions')
        ORDER BY relname
    """,
    "statement_statistics_available": """
        SELECT extname FROM pg_extension WHERE extname = 'pg_stat_statements'
    """,
}


def main() -> int:
    url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql")
    try:
        with psycopg.connect(
            url.render_as_string(hide_password=False),
            connect_timeout=10,
            options=(
                "-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=1000"
            ),
            autocommit=True,
        ) as connection:
            failed = False
            for name, statement in QUERIES.items():
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(statement)
                        print(
                            json.dumps(
                                {
                                    "diagnostic": name,
                                    "columns": [column.name for column in cursor.description],
                                    "rows": cursor.fetchall(),
                                },
                                default=str,
                            ),
                            flush=True,
                        )
                except psycopg.Error as error:
                    failed = True
                    print(json.dumps({"diagnostic": name, "sqlstate": error.sqlstate}), flush=True)
            return int(failed)
    except psycopg.Error as error:
        print(json.dumps({"diagnostic": "connection", "sqlstate": error.sqlstate}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
