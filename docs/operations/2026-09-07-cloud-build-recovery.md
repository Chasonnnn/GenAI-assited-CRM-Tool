# Cloud Build recovery — September 7, 2026

## Failure

Project `probable-dream-484923-n7`, region `us-central1`, authentication context `crm`.

API build `c908569c-7001-4863-8b6c-17efc87c4abe` for source `3abe0c1a446308bd6d81dce2e1fde966dea42615` failed at `match-expansion-preflight`. API and worker image builds and pushes succeeded. The migration job reported `RuntimeError: This schema requires an explicit match expansion rollout` four times between 04:23:36 and 04:30:46 UTC. The bounded Cloud Logging query covered 04:17:37–04:32:00 UTC with a 25-entry cap and selected migration exception lines only.

The build used `_MATCH_EXPANSION_ROLLOUT=false` and an empty rehearsal SHA. It stopped before schema migration and API/worker service changes. Web build `68e1a6bd-faad-4f37-be46-d0eff3aeab65` succeeded independently.

## Recovery baseline

The user authorized exact-release rehearsal followed by production migration and deployment if checks pass. Feature activation is separate from the migration and remains disabled.

- API: `crm-api-00236-n62`, 100% traffic; image `sha256:9e952d0c959a5a86214e873e438b0f767b28503790762337660413305047c692`.
- Worker: `crm-worker-00281-x9h`, 100% traffic.
- Web: `crm-web-00217-vtb`, 100% traffic.
- Public API health returned HTTP 200, version `0.91.61`, schema `20260830_0100`, and healthy Redis.
- Production backup `1788750000000` completed successfully at 04:25:43 UTC. Daily backups and point-in-time recovery are enabled.

## Exact-release rehearsal

Status: passed. Clone `crm-release-rehearsal-0907` used an independent credential and a dedicated identity without production secret permissions. Provider clients and workers were not started. The clone and identity have been deleted.

Release API image: `sha256:6e5471eb0f328ffa316be7eaa56f21e9e534cec6a07b93c458befb60b56b5f0a`.

The migration runner used overlay build `66b858c2-47a1-40a1-a0f4-5a96a4648a3d`, digest `sha256:5a4e73c35931ef7e7a288f116c4d2a78828fd53a0086c97ec050e2aa983b422b`. The overlay added only rehearsal scripts; application source, dependencies, and migrations came from the release image.

The previous rehearsal did not certify this release. Seven existing application/migration files differ from its recorded source manifest.

Migration execution `crm-release-rehearsal-0907-p8bgz` passed against the fresh clone. It exercised `app.db.release_migration.run_migration` from the exact release image. The forced lock timeout produced SQLSTATE `55P03`; rollback, upgrade, downgrade, and re-upgrade each preserved all original values across 171 tables and 1,594,872 rows. Upgrade took 0.937 seconds, downgrade 0.580 seconds, and re-upgrade 0.748 seconds on the idle clone. The first runner attempt lacked `PYTHONPATH=/app`; correcting that rehearsal-only setting resolved the setup failure.

Application execution `crm-release-rehearsal-0907-7gcr6` succeeded. The adapted probe used overlay `sha256:e7b90404490bfda8a324feea7b9a6606c93bfcbe8139e318e170c59ebf6b77f7` from build `d528657e-4c27-4b9e-81a0-1601bf6a4947`. Surrogate, intended-parent, and match reads succeeded on the expanded schema. `/healthz`, `/health/live`, and `/readyz` returned 200. During a synthetic 1.25-second metrics-table lock, liveness took 4.77 ms. Probe writes were rolled back; no database errors occurred.

These checks cover database preservation and isolated application compatibility. They do not establish zero-interruption rollout or validate authenticated new-feature workflows. Expansion writes remain disabled pending separate activation checks.

## Production result

Build `3d2b5203-fb38-4bba-907c-1efabebd27d1` succeeded at 05:38:22 UTC. It used source `3abe0c1a446308bd6d81dce2e1fde966dea42615`, `_MATCH_EXPANSION_ROLLOUT=true`, and the matching `_MATCH_EXPANSION_REHEARSED_SHA`.

Production preflight, compatibility settings, migration, attachment-scan update, worker deployment, API deployment, and ClamAV update all succeeded. The retry rebuilt the release images; their digests differ from the rehearsed image, while the source SHA is the rehearsed commit.

- API `crm-api-00238-rdc`: 100% traffic, digest `sha256:214818f5b8428dc898a5ebb7e55986ac87415fbe2f601d0d809a1c24006876e7`.
- Worker `crm-worker-00283-8mh`: 100% traffic, digest `sha256:40bbee0e5fdf6260f3a1280e6c763c4e8d72cf37656207074db45b1529186b84`.
- Both services: `DB_MIGRATION_CHECK=true`, `DB_AUTO_MIGRATE=false`, `MATCH_CASE_EXPANSION_ENABLED=false`.
- Public API `/health`: HTTP 200, version `0.91.62`, schema `20260905_1600_record_integrations`, migration heads matched, Redis healthy.

## Cleanup

Deleted rehearsal job, clone credential secret, dedicated identity, all four rehearsal image versions, all four source uploads, and clone backup `1788757566124`. Clone deletion operation `19754b9f-dd8f-459c-9a44-afa900000032` completed; the final SQL instance inventory contained only `crm-db`. No production backup was deleted. Cloud Build and aggregate rehearsal audit logs remain available.

## Post-deployment verification

The corrected curl sampler collected 168 requests to `/health/live` and `/readyz` from 2026-09-07T05:32:31Z through 2026-09-07T05:40:05Z. Status counts: {"200": 168}. Sampling was approximately every five seconds per endpoint; it cannot exclude interruptions between samples. Initial urllib samples failed locally and were excluded before starting the corrected sampler.

Cloud Logging returned no error-level or HTTP 5xx entries for the new API/worker revisions in the bounded 05:38:22–05:39:30 UTC window, queried at 05:40 UTC with a 100-entry cap. This short window does not establish long-term health or validate new-feature workflows.

The task-owned health sampler exited. Local temporary runners, uploads, and sampled output were removed. No local service remains running for this task.
