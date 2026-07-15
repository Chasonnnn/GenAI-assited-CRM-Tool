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

The root `queryproof.toml` is deliberately not introduced by this asset-only
change. Wiring remains blocked until the QueryProof engine accepts invariants
scoped by both prepared-plan mode and capture mode. Collapsing the historical
matrix to case-only invariants would discard proven hot/cold planner behavior.
Runtime lifecycle, authentication, database-role, seed, load, and CI wiring are
separate adoption changes.
