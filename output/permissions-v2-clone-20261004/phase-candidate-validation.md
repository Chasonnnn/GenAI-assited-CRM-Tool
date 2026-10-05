# Effective-stage query candidate

This records the initial local candidate check. The clone trial later passed, and the same executable function was committed as c9b0018a4.

Baseline source: a95db13ea. Candidate: phase_filter_candidate.py, SHA256 705fd172e8017fda30a8171c13afc630d1ac95cc7452f1e0e60997e490098601.

The candidate keeps the history and paused-origin resolution unchanged. The current stage joins only its pipeline. Effective-stage phase validation runs in an explicitly correlated EXISTS. Evidence review applies only when no row matches the effective stage ID. Existing inactive, foreign-pipeline, paused and terminal effective stages remain denied.

The candidate was applied only inside a disposable pytest process through phase_candidate_plugin.py. Production source remained unchanged. All 15 affected permission, scope and workflow suites passed: 256 tests and 19 subtests in 22.10 seconds. Ruff passed for the candidate; the temporary plugin import ordering was then normalized. The disposable database was verified absent, and the task wrapper scripts were removed. No services were started.

This is local contract preservation evidence. The clone query divergence is the failing case; the candidate later passed every agreement check for both affected clone records in query-trial-log.json. No claim that Memoize or JIT caused the divergence.

Test log: /private/tmp/crm-phase-candidate-affected.log.

Temporary test logs were removed after aggregate results were saved.
