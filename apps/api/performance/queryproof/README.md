# QueryProof CRM assets

This directory is the reviewed, consumer-owned bridge from the CRM performance
harness to QueryProof.

- `capture-corpus.json` preserves the ten-query hot/cold corpus, explicit
  parameter kinds, automatic/generic/custom prepared-plan modes, and
  estimated/analyze capture modes. Their Cartesian product is 120 captures.
- `plan-expectations.json` expands every historical capture into an explicit
  scenario invariant. Relation and index identifiers are schema-qualified for
  QueryProof; no legacy invariant is weakened to fit a less-specific schema.
- `critical-routes.json` preserves all twelve critical routes and reasons.
- `statistics-allowlist.json` is an exact copy of the reviewed non-PII
  statistics allowlist.
- SQL is stored only in the reviewed `.sql` files referenced by these JSON
  assets. JSON metadata must never embed SQL or production values captured at
  runtime. The corpus JSON does contain reviewed, deterministic synthetic
  parameters required to reproduce hot/cold fixture cases.

The root `queryproof.toml` is the nonblocking query-only compatibility pilot.
It configures the full 120-capture matrix, per-revision Alembic migrations,
candidate-owned role/extension and seed hooks, and a reviewed NOLOGIN
application role. The candidate hook creates the role and
`pg_stat_statements` before either revision migrates, then applies relation ACLs
after each revision has created its own schema. QueryProof creates an ephemeral
LOGIN and may only `SET ROLE` to that role. The role has `USAGE` on `public` and
`SELECT` on the seven exact relations referenced by this corpus; it has no write
or sequence privileges.

Under `QUERYPROOF_MODE=deterministic`, the production-shaped seed freezes its
reference clock and derives the surrogate and intended-parent UUIDs used by the
captured corpus from stable organization/entity keys; the configured PRNG seed
controls the remaining synthetic choices it owns. The required 120-capture
selftest—not this helper-level claim—is the proof of complete seeded database
determinism. Ordinary development seeding retains wall-clock timestamps and
random UUIDs.

Both the `smoke` and `production` QueryProof profiles currently use the same
production-shaped seed distribution because QueryProof seed phases are not
profile-specific. The names select deterministic database settings, not two
different fixture sizes. No service, HTTP probe, authentication hook, k6
adapter, CI gate, or retirement of the established harness is part of this
pilot.

From a reviewed QueryProof checkout, use an isolated PostgreSQL 18.4
administrator URL and run:

```bash
QUERYPROOF_ADMIN_DATABASE_URL=postgresql://... \
  /path/to/queryproof selftest --ref HEAD --profile smoke

QUERYPROOF_ADMIN_DATABASE_URL=postgresql://... \
  /path/to/queryproof compare --base origin/main --candidate HEAD --profile production
```

Promotion remains blocked until exact base-versus-base runs and intentional
N+1/index/scan regressions pass the adoption criteria. The established local
performance harness and its CI policy remain authoritative until then.
