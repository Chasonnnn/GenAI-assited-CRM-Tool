# Production-copy rehearsal

Status: database preservation and isolated application compatibility checks passed; temporary resources removed. Production services and database have not been migrated or deployed.

- Project: `probable-dream-484923-n7`; region: `us-central1`.
- Production API source: `6b617131ba41979c0cf40c2aa4def91b8f76ce15`.
- Production API digest: `sha256:9e952d0c959a5a86214e873e438b0f767b28503790762337660413305047c692`.
- Production database: PostgreSQL 18, private IP only, daily backups and PITR enabled.
- Clone: `crm-match-rehearsal-0906`; clone operation completed at `2026-09-07T01:55:43.011Z`.
- Rehearsal identity: `crm-match-rehearsal`; no production secret access granted.
- Clone schema owner's password replaced with an independent credential. Production credentials were not read.
- First stage is a database-only job. No application server, worker, scheduler, or provider client starts.
- Job egress routes entirely through the VPC; no Cloud Routers/NAT entries were returned in the project inventory.
- Row comparison uses ephemeral keyed hashes over every existing column; output contains table counts and equality results only.
- Current worktree includes uncommitted preservation fixes; `source-manifest.json` records exact submitted file hashes. This is not a rehearsed release commit.
- Runtime overlay uses the immutable production image. Runtime dependencies and Dockerfiles are unchanged; this does not verify a complete release image build.

## Outstanding checks

Full service cutover, concurrent application workload, and authenticated staging workflows remain unverified. These isolated probes do not start the application lifespan, workers, or provider delivery. Cleanup completed.

## Database results

- Baseline revision: `20260830_0100`; 171 existing tables; 1,594,137 rows; database size 932,615,871 bytes.
- Existing records include 8,759 surrogates, 25 IPs, 27 matches, 2,469 Meta leads and 6 intake leads. No donor records exist in this snapshot.
- Commitment conflicts: zero.
- Held-table upgrade: SQLSTATE `55P03`; rollback preserved all 171 tables and all original row values.
- Upgrade: 0.604 seconds; all original columns and rows preserved.
- Downgrade: 0.398 seconds; all original columns and rows preserved.
- Re-upgrade: 0.453 seconds; all original columns and rows preserved.
- Final clone schema: `20260905_1600_record_integrations`.
- Durations measure migration calls on an idle clone. They do not measure production request interruption under concurrent load.
- Execution: `crm-match-rehearsal-0906-v4xhm`; image `sha256:df080700eb718b8b487e4f83590c06e89f51e2dd904ff811d3efadb221325b83`.
- Evidence: `database-results.json`.

## Application compatibility results

- Both actual production source and current worktree code selected existing Surrogate, IntendedParent, and Match rows on the expanded schema without missing-column errors. Raw driver rows were discarded without decryption or display.
- Both returned HTTP 200 for `/healthz`, `/health/live`, and `/readyz`. Old code used the planned temporary migration-check exception; new code checked the expanded migration head.
- A synthetic 1.25-second metrics-table lock delayed old `/health/live` to 1,259.90 ms. Current `/health/live` returned in 5.25 ms under the same lock. This confirms the old liveness dependency; it does not measure migration-related blocking or a Cloud Run traffic cutover.
- Probe metrics writes were rolled back. No SQL errors occurred.
- Execution: `crm-match-rehearsal-0906-mjsb7`, succeeded. Evidence: `availability-results.json`.
- Production API `crm-api-00236-n62`, worker `crm-worker-00281-x9h`, and frontend `crm-web-00216-g8w` retained 100% traffic throughout the final inventory check.

## Cleanup

- Cloud Run rehearsal job deleted. Both executions completed successfully before deletion.
- Clone backup `1788746041056` deleted. Clone deletion completed at `2026-09-07T02:14:57.822Z`, operation `e85b3fbd-a406-414d-a9ab-e3c600000032`; no final backup requested.
- Rehearsal Secret Manager secret and service account deleted.
- Both rehearsal image versions/tags and both uploaded source archives removed. Build and aggregate execution audit logs remain in Cloud Logging/Cloud Build.
- Local credential files and temporary image build directories removed. No local servers were started.
- Repository authmux binding remains local and ignored, as authorized.
- Production database, service revisions, and traffic were not changed by this rehearsal. No production release or feature activation occurred.
