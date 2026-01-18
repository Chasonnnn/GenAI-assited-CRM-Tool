# Backup and Restore Runbook

This runbook covers database and file storage backups for the Surrogacy Force stack.

## Scope
- Postgres data (all application data and metadata)
- Attachment storage (`.attachments` for local, S3 for production)
- Export artifacts (`.exports` for local, S3 for production)
- Encryption keys (required to decrypt stored tokens/PII)

## Preconditions
- Docker container `crm_db` is running.
- You have the same encryption keys used in production:
  - `FERNET_KEY`
  - `DATA_ENCRYPTION_KEY`
  - `PII_HASH_KEY`
  - `META_ENCRYPTION_KEY`
  - `VERSION_ENCRYPTION_KEY` (if used)

## Backup (Postgres)
Create a compressed, consistent snapshot of the database:

```bash
mkdir -p backups
docker exec -t crm_db pg_dump -U postgres -Fc crm > backups/crm_$(date +%Y%m%d_%H%M).dump
```

Optional: capture schema-only for quick diffing:

```bash
docker exec -t crm_db pg_dump -U postgres -s crm > backups/crm_schema_$(date +%Y%m%d_%H%M).sql
```

## Restore (Postgres)
Restore into an empty database. This will overwrite existing data.

```bash
docker exec -t crm_db dropdb -U postgres --if-exists crm
docker exec -t crm_db createdb -U postgres crm
docker exec -i crm_db pg_restore -U postgres -d crm --clean --if-exists < backups/crm_YYYYMMDD_HHMM.dump
```

## Verify
```bash
docker exec -it crm_db psql -U postgres -d crm -c "select count(*) from organizations;"
```

## Attachment Storage
### Local storage
Backup the attachment directory:

```bash
tar -czf backups/attachments_$(date +%Y%m%d_%H%M).tgz .attachments
```

Restore:

```bash
tar -xzf backups/attachments_YYYYMMDD_HHMM.tgz
```

### S3 storage
- Enable bucket versioning.
- Enable lifecycle retention matching `DEFAULT_RETENTION_DAYS`.
- Use S3 batch restore or cross-region replication for DR.

## Export Artifacts
If using local exports:

```bash
tar -czf backups/exports_$(date +%Y%m%d_%H%M).tgz .exports
```

If using S3 exports, include the export bucket in your S3 DR plan.

## Notes
- Restores require the original encryption keys to read encrypted fields.
- For production, schedule automated backups (daily) and test restores monthly.

## Quarterly Restore Test (Required)
Run a full restore test quarterly and record the outcome.

### Procedure
1. Select the most recent production backup artifact.
2. Restore into an isolated environment (staging or a dedicated restore sandbox).
3. Verify encryption keys are loaded (`FERNET_KEY`, `DATA_ENCRYPTION_KEY`, `PII_HASH_KEY`, `META_ENCRYPTION_KEY`, `VERSION_ENCRYPTION_KEY`).
4. Run basic data checks:
   - `select count(*) from organizations;`
   - Spot-check a surrogate + intended parent record.
5. Record results below.

### Restore Test Log
| Date (UTC) | Environment | Backup Artifact | Result | Verified By | Notes |
|---|---|---|---|---|---|
| | | | | | |
