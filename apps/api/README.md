# Surrogacy Force API

This README covers local usage and the recommended org bootstrap flow.

## Quick Start

```bash
# Start dev server
cd apps/api && uv sync --extra test
cd apps/api && uv run -- uvicorn app.main:app --reload

# Run tests
cd apps/api && uv run -m pytest -v

# Format and lint
ruff check . --fix && ruff format .
```

## Org Bootstrap (New Tenant)

Surrogacy Force is invite-only and enforces one active org per user.

### 1) Create the org and invites (CLI)

```bash
cd apps/api
uv run -m app.cli create-org \
  --name "Acme Agency" \
  --slug "acme" \
  --admin-email "admin@acme.com" \
  --developer-email "dev@acme.com"
```

Notes:
- Invites created by the CLI never expire and do not send email.
- If admin and developer emails match, a single developer invite is created.
- If a user already belongs to an org, the CLI will fail to protect the 1-org rule.

### 2) Accept the invite (SSO)

The invitee signs in with Google SSO using the invited email. On first login the invite is accepted and a membership is created.

### 3) Configure org settings in the UI

Suggested first settings:
- Organization name (internal name)
- Signature company name (external display name)
- Timezone
- Portal domain (if you use branded booking links)

### 4) Invite additional users

In the app, go to Settings -> Team to invite members.

Requirements:
- The inviter must connect Gmail (Settings -> Integrations) to send invite emails.
- If `ALLOWED_EMAIL_DOMAINS` is configured, the invite email must match allowed domains.
- Invite roles are `intake_specialist`, `case_manager`, or `admin`; only a Developer can promote a user to `developer`.

## Promote to Developer (No Manual DB Update)

If you need to elevate an existing member:

```bash
cd apps/api
uv run -m app.cli promote-to-developer \
  --email "dev@acme.com" \
  --org-slug "acme"
```

The `--org-slug` check is optional but recommended in multi-tenant environments.

## Common Troubleshooting

- "not_invited": the email has no pending invite.
- "invite_expired": the invite expired (CLI invites do not expire).
- "User already belongs to an organization": the user has an active membership; use another email.
