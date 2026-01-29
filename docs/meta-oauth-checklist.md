# Meta OAuth Rollout Checklist

Use this checklist to track implementation, validation, and cutover steps for the Meta OAuth integration.

## Phase 1 — Database + Models
- [x] Add `MetaOAuthConnection` model with multi-connection support (unique on org + meta_user_id).
- [x] Add `oauth_connection_id` to `MetaPageMapping`.
- [x] Add `oauth_connection_id` and `is_legacy` to `MetaAdAccount`.
- [x] Create migration for new table/columns.
- [x] Seed `is_legacy=True` for pre-OAuth assets.

## Phase 2 — OAuth Service + Token Resolution
- [x] Implement OAuth token exchange (code → short-lived → long-lived).
- [x] Fetch Meta user profile (`/me?fields=id,name`) and token scopes.
- [x] Validate required scopes (fail fast if missing).
- [x] Fetch pages/ad accounts for a specific connection.
- [x] Auto-subscribe pages to `leadgen` webhooks.
- [x] Implement centralized token resolution service.
- [x] Record connection health (`last_validated_at`, `last_error`).

## Phase 3 — API Endpoints
- [x] `GET /integrations/meta/connect` returns auth URL + state cookie.
- [x] `GET /integrations/meta/callback` validates state + scopes, saves connection.
- [x] `GET /integrations/meta/connections` lists org connections with health.
- [x] `GET /integrations/meta/connections/{id}/available-assets` (connection-scoped).
- [x] `POST /integrations/meta/connections/{id}/connect-assets` (overwrite support).
- [x] `DELETE /integrations/meta/connections/{id}` unlinks assets + deactivates connection.

## Phase 4 — Frontend UX
- [x] Connection list UI with health state + reauth prompt.
- [x] Connection-scoped asset selection (multi-select allowed).
- [x] Overwrite confirmation dialog for conflicting assets.
- [x] Asset table with "connected by" attribution.
- [x] Legacy asset warning banner.

## Phase 5 — Sync + CAPI
- [x] All Meta services use the centralized token resolver.
- [x] CAPI uses OAuth token (no system user).
- [x] Sync jobs gracefully skip assets without tokens.
- [x] Webhook handler remains verified + signed.

## Phase 6 — Tests
- [x] Backend: OAuth connect/callback tests.
- [x] Backend: scope validation + missing scopes path.
- [x] Backend: asset connect overwrite path.
- [x] Backend: disconnect unlinks assets.
- [ ] Frontend: connect flow + asset selection + overwrite dialog (manual testing required).

## Phase 7 — Cutover (No Backward Compatibility)
- [ ] Set `META_OAUTH_REQUIRED=True`.
- [ ] Disable legacy sync entirely.
- [ ] Remove manual token UI.
- [ ] Drop legacy token columns in cleanup migration.

## Phase 8 — Production Readiness
- [ ] Verify webhook subscription works end-to-end.
- [ ] Verify lead retrieval + mapping.
- [ ] Verify CAPI status events are sent and logged.
- [ ] Add monitoring alerts for connection errors.
