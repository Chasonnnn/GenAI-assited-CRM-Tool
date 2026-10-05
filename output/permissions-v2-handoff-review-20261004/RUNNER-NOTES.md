Frozen source: 91da87428dc6d90ac051f96a25ae2decf0f6de43. Schema gate: 20261004_1300_organization_logo.

Build context: /private/tmp/crm-handoff-review-20261004/build
Private key: /private/tmp/crm-handoff-review-20261004/ledger-private-key.pem (0600, outside build)
Runner: build/source/apps/api/_handoff/runner.py
Public key and clone binding: build/source/apps/api/_handoff/
Source/hash manifest: source-manifest.json and packaged _handoff/source-manifest.json
Job specification: job-config.json

Build command (root owns cloud execution):

gcloud builds submit /private/tmp/crm-handoff-review-20261004/build --project probable-dream-484923-n7 --region us-central1 --config /private/tmp/crm-handoff-review-20261004/build/cloudbuild.yaml

Use the built image digest for the Cloud Run job. Bind DATABASE_URL to crm-handoff-db-1004:2, the clone-only crm_user secret version. No production keys/provider env. Entrypoint is python /app/_handoff/runner.py; no API or worker process.

The Dockerfile verifies the pinned production base image's pyproject.toml and uv.lock SHA256 before replacing /app with frozen source. A mismatch stops the build; do not bypass the check. Use a full build from the frozen production Dockerfile if dependencies differ.

The initial transaction may create/initialize only public.permission_handoff_review_guard_app on the bound clone. Business collection uses one repeatable-read/read-only/UTC transaction across every guarded organization. It requires the expected schema head and does not run migrations, resolutions, or activation. Source files, clone/run binding, network destination, encryption absence, and aggregate privacy are checked. Database errors/logging are suppressed.

Download one execution's complete Cloud Logging JSON entries into a private file outside build. Decrypt locally with repository-pinned Python/dependencies:

mise exec -- uv run --project /Users/chason/GenAI-assited-CRM-Tool/apps/api python /private/tmp/crm-handoff-review-20261004/decrypt_ledger.py /private/tmp/crm-handoff-review-20261004/execution-logs.json /private/tmp/crm-handoff-review-20261004/private-ledger.json

The helper emits only status/byte count, writes plaintext mode0600, and rejects output inside build. Never upload credentials/, private-key PEM, decrypted ledger, or the staging root. Upload build/ only. Preserve the private key until evidence review is complete; deleting it makes the ciphertext unrecoverable.

The evidence runner requires the clone-only DATABASE_URL username crm_user; a different username fails before connecting. The app-owned sentinel is separate from the earlier postgres-owned sentinel.

Historical executed runner bytes are preserved in runner-initial.py.txt and runner-diag.py.txt with their matching source-manifest-initial.json and source-manifest-diag.json.
