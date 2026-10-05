# Local phase query reproduction

Source: a95db13ea. PostgreSQL 18.1 in the existing local crm_db container. Four unique disposable databases through apps/api/run_tests.sh. Production code unchanged.

| Fixture | Transaction-local settings | Plan | Result |
| --- | --- | --- | --- |
| 300 On-Hold records, paused from Lost; 100 pre-approval, 100 post-approval, 100 missing history | jit off; hashjoin, mergejoin, seqscan off; memoize on | 6 Memoize nodes, 16 nested loops | Correct phase and handoff results |
| 1,200 records; 1,190 terminal Lost and 10 On-Hold paused from Lost; 400 each pre/post/unknown | jit off; memoize on; default joins | 14 hash joins, no Memoize | Correct phase and handoff results |
| Same mixed fixture | jit off; hashjoin, mergejoin, seqscan, material off; memoize on | 6 Memoize nodes, 16 nested loops | Correct phase and handoff results |
| Same mixed fixture | jit off; hashjoin, mergejoin, material off; memoize on; seqscan enabled | 16 nested loops, no Memoize | Correct phase and handoff results |

Each fixture analyzed the synthetic record, history, pipeline and stage tables. Known histories traversed Contacted or Approved, then Disqualified, Lost and On-Hold. Assertions compared all record phases and migration handoff membership/review flags with fixture expectations.

Observed Memoize keys were plain history from_stage_id values. The clone computed-key failure was not reproduced. These passes do not disprove the PostgreSQL planner hypothesis or validate the contradictory clone result.

Exploration stopped after four bounded runs. The temporary pytest file was removed from tests; its final probe remains in local_app_phase_probe.py. No permanent test or production changes were made. Logs: /private/tmp/crm-phase-memoize-{baseline,mixed,forced,scan}.log.

Temporary test logs were removed after aggregate results were saved.
