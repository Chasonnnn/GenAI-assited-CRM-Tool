# Query-performance validation

This repository uses a local-first query-performance system. It does **not** provision or depend on a second Cloud SQL instance.

The system separates three questions that need different evidence:

| Question | Evidence | Merge blocking? |
| --- | --- | --- |
| Did the candidate make PostgreSQL do materially more work? | Local/CI base-versus-candidate deterministic gates | Yes |
| Did endpoint timing move on this laptop? | Local k6 base-versus-candidate report | No, always advisory |
| Does the release meet absolute latency and reliability targets on production infrastructure? | Query Insights, Cloud Monitoring SLOs, and a 10% Cloud Run canary | Release decision, not a laptop PR gate |

Production rows never leave GCP. Local and CI execution use deterministic synthetic profiles. The only production-derived database artifact permitted locally is a sanitized, encrypted PostgreSQL 18 planner-statistics artifact; it contains no table rows and is never committed.

## Deterministic PR gates

The hard gate compares the merge base and candidate against the same schema, seed profile, query corpus, PostgreSQL version, and planner settings. It records structured `EXPLAIN (FORMAT JSON)` documents rather than plan hashes.

The gate checks:

- query count and duplicate normalized fingerprints;
- required and forbidden node, join, relation, and index behavior;
- generic, custom, and automatic prepared-plan behavior;
- estimated cardinality and cost when sanitized production statistics are present;
- shared hit plus read blocks;
- rows produced or removed by each leaf scan, multiplied by loop count;
- temporary blocks and WAL work when relevant.

Default failure budgets are deliberately based on database work:

- any unexplained query-count increase;
- logical-buffer growth greater than both 15% and 32 blocks;
- scanned-row growth greater than both 15% and 100 rows;
- new temporary-block usage;
- a configured plan-invariant violation;
- estimated-cost growth greater than 20% when accompanied by an adverse structural change.

Sequential scans are not globally forbidden. Each query owns its expectation in [`apps/api/performance/plan-expectations.json`](../apps/api/performance/plan-expectations.json). For example, small stage-dimension scans are allowed, while the stage analytics query requires the organization/stage index and upcoming-task queries require indexed access. Every query in the capture manifest must have an explicit expectation.

Base-versus-base must pass before trusting a candidate comparison. The acceptance suite also proves that an intentional N+1, a removed required index, and scan amplification fail for the expected reason.

With a local PostgreSQL 18 admin connection available, run the full isolated
base-versus-candidate gate with:

```bash
cd apps/api
export PERFORMANCE_ADMIN_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/crm'
uv run python -m scripts.performance compare \
  --base origin/main --candidate HEAD --mode deterministic --seed-profile production
```

The orchestrator creates temporary databases and detached worktrees, migrates
both refs, seeds the exact same candidate profile into both schemas, captures
the checked-in manifest, evaluates the budgets, and removes all temporary
resources in a `finally` cleanup. `HEAD` must be committed so the detached
candidate worktree is the code being reviewed.

To compare previously captured deterministic reports:

```bash
cd apps/api
uv run python -m scripts.performance compare \
  --mode deterministic \
  --base-report performance/artifacts/base-plan-report.json \
  --candidate-report performance/artifacts/candidate-plan-report.json \
  --expectations performance/plan-expectations.json
```

The report must contain structural and work metrics only. It must never contain bind values, request cookies, authorization headers, tokens, or PII.

The executable capture contract is
[`apps/api/performance/capture-manifest.json`](../apps/api/performance/capture-manifest.json).
For an already-prepared synthetic database, capture all hot/cold and prepared
plan cases with:

```bash
uv run python -m scripts.performance capture \
  --manifest performance/capture-manifest.json \
  --output performance/artifacts/candidate-plan-report.json
```

## Synthetic seed profiles

Use the same named profile for both sides of a comparison:

- `smoke`: quick developer feedback over multiple organizations;
- `production`: production-shaped volume with a deliberately hot, warm, and cold organization;
- `growth10x`: the production distribution at 10 times the row volume.

The profiles are deterministic and are not derived from production rows. A hot/cold distribution is required so prepared statements exercise selective and unselective parameters. Do not replace the synthetic data with exported production rows, even if the rows appear anonymized.

## Prepared-plan scenarios

Every curated query should be captured in all three modes:

1. `plan_cache_mode = force_custom_plan`, with at least one hot and one cold parameter set;
2. `plan_cache_mode = force_generic_plan`, using the same normalized statement;
3. `plan_cache_mode = auto`, after enough representative executions for PostgreSQL to make its normal generic-versus-custom decision.

Keep the mode fixed for each capture. Automatic-mode warmup belongs inside the scenario and must not be shared between base and candidate. `auto_explain` is benchmark-only: parameter logging is disabled, plan node timing is disabled, and production application logs are never used as the local report.

## Weekly production query corpus

The checked-in critical seed is [`apps/api/performance/critical-query-corpus.json`](../apps/api/performance/critical-query-corpus.json). It guarantees coverage for important low-volume routes, but it does not replace observed production workload data.

Once per week, run the export from a trusted GCP environment with private Cloud SQL connectivity. Do not run it from a laptop and do not copy an unnormalized query dump out of GCP.

```bash
cd apps/api
export DATABASE_URL="$(gcloud secrets versions access latest --secret=crm-performance-readonly-database-url)"
uv run python -m scripts.performance export-corpus \
  --critical-queries performance/critical-query-corpus.json \
  --output performance/query-corpus.json \
  --limit 100
unset DATABASE_URL
```

The exporter reads up to 1,000 `pg_stat_statements` rows, normalizes comments and literal values, deduplicates fingerprints, and then selects at most 100 entries. Selection preserves:

- highest total database execution time;
- every query responsible for at least 1% of database time;
- every configured critical route, including low-volume routes.

Before committing the weekly normalized artifact:

1. Verify every query uses placeholders such as `$1`; reject string, numeric, UUID, or timestamp literals.
2. Verify route and release tags come from fixed allowlists. Never tag with an organization, user, case, query parameter, or other high-cardinality identifier.
3. Run the repository safety tests and review the diff. Only the normalized
   `performance/query-corpus.json` may leave GCP; it contains fingerprints and
   aggregate workload weights, never production rows or bind values.
4. Record the capture week, production PostgreSQL major version, and `pg_stat_statements` reset timestamp in the review metadata.
5. Publish only the normalized corpus. Delete the GCP temporary file and shell history entry if the environment records expanded secrets.

The production database role used for this export is read-only and only needs access to `pg_stat_statements`. Resetting production statistics is a separate operational decision; this workflow must not call `pg_stat_statements_reset()`.

## PostgreSQL 18 statistics-only artifact

Planner statistics are exported independently of the query corpus. PostgreSQL 18 statistics-only dumps can reproduce production cardinality, most-common-value, histogram, and correlation estimates without table rows. Some statistics can still contain actual column values, so the artifact is treated as sensitive until it has been allowlisted, scanned, and encrypted.

The allowlist is [`apps/api/performance/statistics-allowlist.json`](../apps/api/performance/statistics-allowlist.json). It intentionally excludes names, email addresses, phone numbers, street/city/postal data, free text, notes, message bodies, tokens, secrets, and search-normalization columns. Adding a relation or column requires privacy review and an accompanying sanitizer test.

### Export inside GCP

Use PostgreSQL 18 client tools. The exporter captures the raw `pg_dump --statistics-only` output in process memory, retains only allowlisted relation/attribute statistics, rejects PII-shaped values, encrypts the sanitized bytes with Fernet, and writes only the encrypted artifact.

```bash
cd apps/api
export DATABASE_URL="$(gcloud secrets versions access latest --secret=crm-performance-readonly-database-url)"
export PERFORMANCE_STATS_FERNET_KEY="$(gcloud secrets versions access latest --secret=crm-performance-stats-fernet-key)"
uv run python -m scripts.performance export-stats \
  --allowlist performance/statistics-allowlist.json \
  --output /tmp/crm-planner-stats.enc
unset DATABASE_URL PERFORMANCE_STATS_FERNET_KEY
```

Operational requirements:

- Run in a short-lived GCP job or trusted administration shell with no command tracing.
- Do not redirect `pg_dump` output to disk, logs, Cloud Build output, or an object store.
- Treat a sanitizer rejection as a hard failure; do not manually bypass or edit around it.
- Scan the encrypted artifact with the organization's normal artifact scanner, upload it to a restricted GCS bucket with retention/expiry, and record its capture date and SHA-256 digest in deployment metadata.
- Keep the encryption key in Secret Manager, separate from the artifact. Never place either in Git or an image layer.
- Delete `/tmp/crm-planner-stats.enc` after upload.

Raw statistics never leave GCP. Only the reviewed encrypted artifact may be downloaded to an authorized developer or CI runner.

### Restore locally or in CI

Create an ephemeral PostgreSQL 18 database at the candidate schema revision. Restore planner statistics before executing plain `EXPLAIN`:

```bash
cd apps/api
export DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:55432/crm_perf_plans'
export PERFORMANCE_STATS_FERNET_KEY="$(security find-generic-password -w -s crm-performance-stats-fernet-key)"
uv run -m alembic upgrade head
uv run python -m scripts.performance restore-stats \
  --allowlist performance/statistics-allowlist.json \
  --artifact /secure/path/crm-planner-stats.enc
unset DATABASE_URL PERFORMANCE_STATS_FERNET_KEY
```

After restore:

- Do **not** run `ANALYZE`, `VACUUM ANALYZE`, or a seed step in the statistics-only planner database; those operations overwrite the restored production estimates.
- Disable autovacuum/analyze for the lifetime of this ephemeral planner database and verify with `SHOW autovacuum`.
- Use plain `EXPLAIN (FORMAT JSON, GENERIC_PLAN ...)`, not `EXPLAIN ANALYZE`, because the statistics-only database has no production rows.
- Use a separate synthetic database for `EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)` work metrics.
- Destroy the database after the run. Interrupted runners must use a cleanup trap for databases, worktrees, API processes, and temporary files.

The capture CLI enforces the plain-EXPLAIN side of that split:

```bash
uv run python -m scripts.performance capture \
  --capture-mode estimated \
  --manifest performance/capture-manifest.json \
  --output performance/artifacts/production-stats-estimates.json
```

Refresh the encrypted artifact weekly. If its PostgreSQL major version, schema revision, or capture date is incompatible or stale, omit the estimate-based comparison and fail with an explicit provenance error; never silently run `ANALYZE` as a substitute.

## Advisory local k6 comparison

The supported base-versus-candidate command is:

```bash
cd apps/api && uv run python -m scripts.performance compare --base origin/main --candidate HEAD --mode load
```

It creates isolated base and candidate worktrees/databases, migrates and seeds them with the same deterministic profile, runs the current k6 suite, and cleans up on success, failure, or interruption. Results are written under `apps/api/performance/artifacts/` and are excluded from Git.

The report includes base/candidate p50, p95, p99, throughput, error rate, and available database-work deltas for surrogates, tasks, dashboard, analytics, workflows, search, intelligent suggestions, and representative mutations.

Wall-clock results are advisory by construction. Laptop Docker I/O, thermals, background processes, and virtualization can move percentiles materially. No p50/p95/p99 or throughput delta from this command may fail a PR or block a merge. Functional setup failures and request errors still exit nonzero because they mean the comparison did not run correctly.

## Production validation

Absolute latency belongs in production SLOs, not in a MacBook threshold.

Cloud SQL Query Insights should have normalized queries enabled, application tags enabled, client-address recording disabled, and a bounded query-text length. SQL/application tags must use low-cardinality values such as canonical route (`GET /surrogates`) and release/revision; they must not contain IDs, search text, emails, or other request values.

The API adds SQLCommenter tags from the matched FastAPI route template and the
SemVer release. The tag builder never receives query parameters, bind values,
cookies, organization IDs, or entity IDs.

Cloud Monitoring should define:

- API request-latency SLOs over Cloud Run request distributions;
- availability/error-rate SLOs;
- fast and slow error-budget burn alerts routed to the production notification channels;
- dashboards split by Cloud Run revision for latency, errors, instance CPU, and memory;
- correlated Cloud SQL CPU, disk/I/O, active connections, lock waits, and Query Insights database time.

### 10% Cloud Run canary

For a query-sensitive release:

1. Deploy the candidate as a no-traffic revision.
2. Confirm migrations are backward-safe for both revisions during the canary window.
3. Record the stable and candidate revision names and the release tag.
4. Route 10% to the candidate and 90% to stable. The checked-in helper verifies
   that the revision belongs to the service and discovers the current stable
   revision before changing traffic:

   ```bash
   PROJECT_ID="$PROJECT_ID" REGION="$REGION" \
   CANDIDATE_REVISION="$CANDIDATE_REVISION" \
   scripts/cloud-run-canary.sh start "$SERVICE"
   ```

5. Observe at least one representative traffic window. Compare candidate versus stable p50/p95/p99, request and database error rates, Cloud Run CPU/memory, Cloud SQL CPU/I/O, database time by normalized fingerprint, connection pressure, and lock waits.
6. Promote only if the latency SLO is healthy, no fast/slow burn alert fires, critical fingerprints show no unexplained database-work shift, and application errors remain within policy.
7. After promotion, continue the slow-burn observation window.

Rollback immediately when an SLO burn alert fires, errors increase materially, lock waits accumulate, or a critical fingerprint shows an unsafe plan/work shift:

```bash
PROJECT_ID="$PROJECT_ID" REGION="$REGION" STABLE_REVISION="$STABLE_REVISION" \
  scripts/cloud-run-canary.sh rollback "$SERVICE"
```

After the observation window, promote explicitly with
`CANDIDATE_REVISION="$CANDIDATE_REVISION" scripts/cloud-run-canary.sh promote "$SERVICE"`
and the same required `PROJECT_ID` and `REGION` environment variables.

Traffic rollback does not reverse a migration. Follow the migration runbook when schema state is implicated.

## Explicit non-goal: Cloud SQL clone

This implementation does not create a Cloud SQL clone or any second standing Cloud SQL instance. Reconsidering a clone/replay tier requires a separate architecture and privacy decision, and only if deterministic local gates plus production canaries prove insufficient.
