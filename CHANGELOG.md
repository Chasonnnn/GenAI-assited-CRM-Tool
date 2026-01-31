# Changelog

All notable changes to this project will be documented in this file.

## [0.54.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.53.3...surrogacy-crm-platform-v0.54.0) (2026-01-31)


### Features

* **api:** add backend support for repeatable tables and conditional field rendering ([4a9c4e9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4a9c4e9fd6b5f3491b2faac562e11c1da645cd90))
* **forms:** add repeatable tables, conditional logic, and Jotform templates ([f66bd99](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f66bd99fa389b5dc3bf7bdab6725fcda20885f3f))
* **integrations:** support multiple Zapier inbound webhooks ([1477b3d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1477b3db4a4767a3c82db21e806dffd4aecdb31d))
* **web:** implement repeatable table fields and conditional visibility in intake forms ([ff5dc9f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ff5dc9f25de65d8b54479e1d2d07559feb61eafd))


### Bug Fixes

* **forms:** map conditional logic and table columns in form builder ([e81ab65](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e81ab657bf4237a77c678af0cb605f5d67a3c535))
* **web/api:** reliability improvements for dashboard and imports ([9969c5a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9969c5a436869369697be38c4e40d67a15cb0b9c))


### Maintenance

* **ai:** cleanup AI streaming and remove debug overlay ([c9a2f5a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c9a2f5ad0c8a7af42e78be6953ffb2d7a6dd763b))
* **infra:** security cleanup and infrastructure refinements ([003b727](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/003b72777721e56c9267f6dd550456790f41cc82))

## [0.53.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.53.2...surrogacy-crm-platform-v0.53.3) (2026-01-31)


### Bug Fixes

* **web:** abort AI streaming on entity context change in AIChatPanel ([72b9038](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/72b9038885ea5cad6e9717dba6ff685949a6ab15))
* **web:** explicitly handle null/undefined in entity context tracking for AIChatPanel ([9ed2c64](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ed2c64e40e6a2685987b9074571cc798d018b45))

## [0.53.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.53.1...surrogacy-crm-platform-v0.53.2) (2026-01-31)


### Bug Fixes

* **api:** implement heartbeat mechanism for AI chat streaming ([ef97203](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ef97203e20bcb0f5076044d1d27d5580543e6ef6))
* **web:** improve error handling and debug tracking in stream client ([9bfe8bb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9bfe8bb4f080cb6d73e4d3c5c36a0f99f7c1ceec))

## [0.53.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.53.0...surrogacy-crm-platform-v0.53.1) (2026-01-31)


### Bug Fixes

* **api/web:** enhance AI stream reliability and add debug overlay ([d1b80a4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d1b80a4579dc16da3e8750a7cd2b0cb0aff66aa3))
* **api:** implement dedicated database session handling for AI streaming ([0651c21](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0651c21478f60fe6de8014b07e74f5060083224b))
* **api:** optimize SSE headers and CORS for reliable cross-origin streaming ([30b079d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/30b079d7117a18be895a71f059d2a6f0435e01b2))
* **web/auth:** prevent duplicate Duo MFA verify attempts in callback ([8be2662](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8be2662e393f78ed97a87102ef3de329e9950e26))
* **web:** resolve multi-line data parsing in SSE client ([954964e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/954964e10ebd351bb6efd63ffa942d1d063e67f1))

## [0.53.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.52.0...surrogacy-crm-platform-v0.53.0) (2026-01-31)


### Features

* **api:** improve SSE streaming reliability with preambles ([00b7ac6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/00b7ac6cacf89e7ae74b0c945500f6d4530a7bab))


### Bug Fixes

* add clamav user in worker image ([719ecad](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/719ecadd90c73599b55f8f6d950ef933804299c0))

## [0.52.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.51.0...surrogacy-crm-platform-v0.52.0) (2026-01-31)


### Features

* **web:** add intelligent mapping alerts for detected Zapier forms ([62f5995](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/62f599540301943e7a4bb43e50b58b32a5a3aa9f))


### Bug Fixes

* **api:** ensure stable form identifier in Zapier webhooks for consistent lead mapping ([139efb7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/139efb77612329cc709c4f5096787658c5435fee))
* Fixed the typecheck errors ([c2306f5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c2306f55f780f7dd31e64fd94f8111f2826a6155))

## [0.51.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.50.0...surrogacy-crm-platform-v0.51.0) (2026-01-31)


### Features

* **ai:** optimize chat scrolling and enhance SSE stream parsing robustness ([50f11b9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/50f11b9e36d7d9b69d6a3f03a62e92ca0019607b))
* **api:** improve global search with fallback partial matching for surrogates ([300a387](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/300a38739b94b0c880486cc73098a0f27a6e244f))
* **import:** enhance deduplication and add flexible source channel detection ([f9c7796](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f9c77965f80f70e3fe94b8a59c975f38c9d85004))
* **surrogates:** expand lead sources and refine dashboard rendering ([a7679b9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a7679b911ce05d296ffda5e74aaf746c79fa293d))
* **zapier:** implement detailed status messages for webhook lead processing ([5a7943f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5a7943f6524a2b33db17084ea76cbfa673cc0843))


### Bug Fixes

* narrow surrogate source filter type ([7c84306](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7c843069865c08c4e998fa265f02383a04cc3ba2))

## [0.50.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.49.1...surrogacy-crm-platform-v0.50.0) (2026-01-31)


### Features

* **api/interviews:** refactor interview summarization to use services ([3fa71fd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3fa71fd6aa3174eed28c541eb8d43bd2c5b6c789))
* **api:** implement AI streaming with Server-Sent Events (SSE) ([c29448e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c29448e403c336c411abbba44dc93b43f1a3df09))
* **campaigns:** enhance campaign wizard with state filtering and quick-send ([1a94848](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1a948486e079ac6aa2ad9cf6ff2521fbc49fdb6b))
* **web/api:** improve CSV import with AI streaming suggestions ([159aa1f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/159aa1f96890a38a8c2f003a1a1e44cb15266364))
* **web:** add global session expiration detection and dialog ([1649fd9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1649fd9ac06702672906484cb80fe196c2f100a0))
* **web:** add support for AI streaming and real-time UI updates ([7ac6c03](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7ac6c03fa94841df034201fddffd1934cb9ae571))


### Bug Fixes

* **api:** fix quote formatting in interview streaming route ([ab97501](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ab97501ad5ca55397e64d5acd2ac31b8f6c93285))


### Maintenance

* **api/services:** clean up imports and typing in domain services ([cbe3fd6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cbe3fd68c4dfaa670b042b50fc6995841338e943))
* **main:** release surrogacy-crm-platform 0.49.1 ([d27e420](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d27e4205e4404cdd9f58f02bf31a0018fd826def))
* **main:** release surrogacy-crm-platform 0.49.1 ([61ea3fd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/61ea3fd33463a5c23e64e879a6533f38bcf9f7a3))

## [0.49.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.49.0...surrogacy-crm-platform-v0.49.1) (2026-01-31)


### Bug Fixes

* Fixed the Bandit B104 ([ebc9247](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ebc9247499e256daed2ce1d2d626b5cbdc7f29eb))
* Fixed the campaign detail test mocks ([62ea76b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/62ea76b4382bafd58cfd7766a1ca79538c77a2dc))

## [0.49.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.48.0...surrogacy-crm-platform-v0.49.0) (2026-01-31)


### Features

* **ai:** normalize model defaults and improve Gemini provider support ([396fee1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/396fee1088a5e2603e8444115414a711c69740a1))
* **campaigns:** add stop functionality and edit support for scheduled campaigns ([1ae812a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1ae812a705b3b34a0ec4a2c6e2a271cfd8789caf))
* implement consistent race data normalization and display ([b918ec1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b918ec1af9646988084e77b20caf3e65bcf1078e))


### Maintenance

* migrate worker from Cloud Run Job to Service with auto-scaling ([13256f5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/13256f5e29b7b75060fa3d8482ea1d5ff98809d0))

## [0.48.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.47.0...surrogacy-crm-platform-v0.48.0) (2026-01-31)


### Features

* **ai:** improve chat history loading and add HTML sanitization to previews ([9c0e0ba](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9c0e0ba5e1540bdcde9615d95cff4fcb6b2e6fd4))
* **compliance:** add pagination to legal holds and improve management UI ([728641f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/728641f2953e5ae1a2192ec23af82d66d7825770))
* **security:** add download-only mode for ClamAV signatures and improve update reliability ([c070a29](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c070a2981b2e324f1e7f16b3994fb5e7b5e49ef7))
* **settings:** use qrcode.react for TOTP and add sanitization to signature previews ([6d8e0d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6d8e0d53ced35caf87f3f16fa445fdd71e6bef4d))


### Bug Fixes

* more fixes ([19e4eb7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/19e4eb7a1651c2a4cf21266597a3477c90222944))
* updated dependencies version ([0422947](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0422947edd53e7e3ade06f326bd8292ef4d3d3a3))

## [0.47.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.46.0...surrogacy-crm-platform-v0.47.0) (2026-01-31)


### Features

* **api:** add ClamAV for virus scanning of uploaded attachments ([04bcf17](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/04bcf17d8e8cfe4ac136ab85c048466388e611ba))
* enforce virus scanning for form submission file uploads ([3bbf6dd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3bbf6dd0175257dc9d5a7acc05ef00e231dd1b81))
* integrate ClamAV scanning for attachments and worker signatures ([43297d1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/43297d15807e9f2e9099c1dc984c1aa4ecde2b90))


### Maintenance

* maintenance cleanup and sync contract tests across AI services ([6d0a667](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6d0a6674f545eab6f0a4ea37005ec1813089c27f))

## [0.46.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.45.0...surrogacy-crm-platform-v0.46.0) (2026-01-30)


### Features

* **api:** refactor AI provider and transcription architecture ([bee397f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bee397f34491c60c132f327ab11b9c64dc4f1808))
* enhance import system with validation modes and flexible transformers ([8da37f7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8da37f70bda9da78345204673967bd975ab44495))


### Maintenance

* **api:** update dependencies in pyproject.toml and uv.lock ([d4ad435](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d4ad4357f2be04b5aefe9f7081150a5d73e7a71c))
* update .gitignore to include .pnpm-store ([eda0cf6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/eda0cf6468257e030441d772dc66e300bf7c7fba))
* update api dependencies and cleanup documentation ([fb2d72b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fb2d72b7cabdf8acef2c93917c806c6c174d3264))
* **web:** update dependencies and pnpm peer dependency rules ([475d1d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/475d1d52b64b97d0bf53827f3a111911bb664f88))

## [0.45.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.44.0...surrogacy-crm-platform-v0.45.0) (2026-01-30)


### Features

* add personal vs organization scope for email templates ([ab221c5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ab221c5996758b61936ce9ce8ef4f04b5ddfb75e))
* add template_name_exists utility for scoped validation ([0fb10f7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0fb10f701078ef425ccd59716191fd49b2940501))
* AI assistant and workflow builder enhancements ([dd2d923](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd2d92350ef7b678b437eec099aed8661f894225))
* appointment system enhancements and auto-approval logic ([75677f4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/75677f4da4e6083d47993629b406c00d1467142b))
* automated signature injection for workflow emails ([195c741](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/195c741c98486cbc47894518fbea153cf22737da))
* enhance automation UI for scoped templates and workflows ([d3f7d8b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d3f7d8b276cf859ed0782176e6d20c058fa19d3b))
* enhance email template models and UI logic ([8fb0af1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8fb0af1ae8ac13cb1d5a280006e1122a03230c03))
* enhance signature preview with org-only mode support ([38227ad](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/38227ad8917de266192586450ea8ec9ca28dbbba))
* form system enhancements with file uploads and mapping snapshots ([4f3d30e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4f3d30ef239f8e2f57c167e41247ebc73e698b31))
* implement scope-aware validation for workflow email templates ([355351b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/355351b3c0c2052c1bd34bd7d775affcbdcced5d))
* switch from OpenAI to Gemini/Vertex AI for all AI features ([f6d8fb7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f6d8fb78181ae4250d11dd5cf2937b9c4dd5b018))
* update dashboard KPIs to track 24h lead conversion ([053ed89](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/053ed89bb251ceb2f38c7e6ecc1c85818316c760))


### Bug Fixes

* **web:** improve form builder stability and application tab safety ([5c3df61](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5c3df6183f87e861898f623c402f43f1a6088f36))
* **web:** refine workflow types and automation UI state ([07f1ea2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/07f1ea29c242dec43bf8ef5000f5549adf5e2eae))


### Maintenance

* cleanup and final test refinements for automation and forms ([344e456](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/344e45615315e788d37d60eaad2ff9f5eaebf98e))
* update CHANGELOG.md and minor UI/dependency cleanup ([44672a2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/44672a255fc70622ea335edf26fbe1dc2eb1be24))

## [0.44.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.43.0...surrogacy-crm-platform-v0.44.0) (2026-01-30)

### Features

- Baby gender and weight tracking for surrogate delivery outcome
- Client-safe redacted journey export
- Delivery tracking and future-only scheduling for campaigns
- Enhanced Duo MFA security with state cookies and UA hashing
- Enhanced surrogate import workflow and error reporting
- Workflow engine multi-entity testing support
- Zapier lead ingestion with batch support and auto-mapping
- Modernized Meta integration and OAuth handlers
- Overhauled tasks page with modular components
- Organization AI status sync and improved integration settings UI

### Bug Fixes

- Accessibility and consistency improvements across settings and automation pages
- Preserved handler signature in FailOpenLimiter decorator
- Refined automation page error handling and UI helpers

---

## [0.43.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.42.0...surrogacy-crm-platform-v0.43.0) (2026-01-29)

Consolidated release including changes from 0.19.2 through 0.42.0.

### Major Features

**Multi-Tenant Platform**
- Multi-tenant subdomain routing with org resolution and slug management
- Ops console for platform administration with dedicated subdomain
- Session host validation and wildcard tenant routing
- Organization soft delete with scheduled purge via worker job

**Authentication & Security**
- Duo MFA integration with TOTP fallback
- Double-submit CSRF token pattern
- Platform admin MFA reset capability
- Rate limiter with fail-open behavior and Redis fallback

**Email & Campaigns**
- Resend platform email service with webhook handling
- Email unsubscribe and suppression management
- Email engagement tracking for invites
- Failed recipients tab with retry-failed endpoint

**Meta Integration**
- Meta OAuth infrastructure for Facebook Login for Business
- Meta form mapping and lead conversion UI
- Meta performance analytics with automated reporting
- Ad-level platform breakdown for attribution

**Import & Data Management**
- Import templates with custom field mapping
- AI-assisted CSV import with auto-match and mapping correction
- CSV content storage in DB with backdate flag support
- Cursor-based pagination for high-volume lists

**Workflow & Automation**
- Personal workflow scope with permission-based access control
- Workflow email provider resolution based on scope
- Zapier integration for inbound leads and outbound events
- Cancel match request workflow

**Appointments & Calendar**
- Zoom and Google Meet integration
- Webhook registry for appointment integrations

**AI & Analytics**
- Vertex AI WIF support
- Centralized AI prompts with output validation
- Normalized identity fields for search
- Monitoring endpoints and analytics improvements

**Observability & Infrastructure**
- Health probes and monitoring webhook infrastructure
- GCP Cloud Run deployment with Cloud Build 2nd gen triggers
- Redis pub/sub backplane for WebSocket
- Monitoring alerts, billing budgets, and weekly cost reports

### Bug Fixes

- Stabilized import routing and hardened preview/approval responses
- Fixed org-scoped status change lookup and storage rollback
- Resolved sidebar navigation and org context issues
- TypeScript compatibility for Next.js 15+ params/searchParams
- MFA flow refinements and session persistence fixes

---

## [0.41.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.40.0...surrogacy-crm-platform-v0.41.0) (2026-01-28)

### Breaking Changes

- Full rename of Cases entity to Surrogates across the stack

### Features

- Multi-tenant subdomain routing with org resolution
- Duo MFA integration with TOTP fallback and platform admin reset
- Resend platform email service with webhook handling
- Import templates with custom field mapping
- Health probes and GCP Cloud Run deployment
- Surrogate journey timeline with featured images and PDF export
- Zoom and Google Meet integration for appointments

---

## [0.40.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.39.0...surrogacy-crm-platform-v0.40.0) (2026-01-28)

- Health probes and monitoring webhook infrastructure

---

## [0.38.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.37.0...surrogacy-crm-platform-v0.38.0) (2026-01-27)

- Webhook registry appointment integrations
- Next.js 15+ compatibility updates

---

## [0.37.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.36.0...surrogacy-crm-platform-v0.37.0) (2026-01-26)

- Personal workflow scope with permission-based access control
- Workflow email provider resolution based on scope

---

## [0.36.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.35.0...surrogacy-crm-platform-v0.36.0) (2026-01-26)

- Import templates and custom fields support
- Attachment scanning service (ClamAV)

---

## [0.35.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.34.0...surrogacy-crm-platform-v0.35.0) (2026-01-26)

- Resend configuration API and webhooks
- System email template management UI

---

## [0.34.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.33.0...surrogacy-crm-platform-v0.34.0) (2026-01-25)

- Organization deletion with restore capability
- Platform admin email service

---

## [0.33.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.32.0...surrogacy-crm-platform-v0.33.0) (2026-01-24)

- Duo MFA initiation and platform MFA management
- Org context in invite acceptance flow

---

## [0.32.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.31.0...surrogacy-crm-platform-v0.32.0) (2026-01-24)

- Multi-tenant subdomain infrastructure
- Public org resolution and slug management APIs

---

## [0.31.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.30.0...surrogacy-crm-platform-v0.31.0) (2026-01-22)

- Ops subdomain support with dedicated routing
- Database migration checks in readiness probes

---

## [0.30.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.29.0...surrogacy-crm-platform-v0.30.0) (2026-01-21)

- GCP Cloud Run deployment infrastructure
- Configurable DB connection pooling and Redis client

---

## [0.29.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.28.0...surrogacy-crm-platform-v0.29.0) (2026-01-20)

- Security hardening and ops readiness for launch
- Double-submit CSRF token pattern

---

## [0.28.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.27.0...surrogacy-crm-platform-v0.28.0) (2026-01-18)

- Redis pub/sub backplane for WebSocket
- Monitoring alerts, billing budgets, and weekly cost reports

---

## [0.27.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.26.0...surrogacy-crm-platform-v0.27.0) (2026-01-17)

- Enhanced surrogate import with AI mapping and file hashing
- CSV import backdating support

---

## [0.26.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.25.0...surrogacy-crm-platform-v0.26.0) (2026-01-16)

- Zapier integration for inbound leads and outbound events
- Cancel match request workflow

---

## [0.25.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.24.0...surrogacy-crm-platform-v0.25.0) (2026-01-15)

- Zoom and Google Meet integration for appointments
- Journey timeline with featured images and PDF export

---

## [0.24.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.23.0...surrogacy-crm-platform-v0.24.0) (2026-01-14)

- AI assistant privacy and access controls
- Compliance service with activity tracking

---

## [0.23.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.22.0...surrogacy-crm-platform-v0.23.0) (2026-01-12)

- Surrogate journey timeline
- Tab navigation and activity timeline

---

## [0.22.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.21.0...surrogacy-crm-platform-v0.22.0) (2026-01-11)

- 'Run Now' support for surrogate imports
- Welcome page for new users

---

## [0.21.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.20.0...surrogacy-crm-platform-v0.21.0) (2026-01-10)

- Portal domain support
- Session management page

---

## [0.20.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.19.2...surrogacy-crm-platform-v0.20.0) (2026-01-09)

- Error boundaries and not-found pages
- Rate limit handling in API client

---

## Pre-Release History (2025-12 - 2026-01)

### [2026-01-05] Workflow Approval System
- Human-in-the-loop approvals with 48 business hours timeout
- Business hours calculator with timezone support
- Email signature enhancement with 5 templates
- Team performance report with per-user conversion funnel analytics
- AI assistant analytics tools with dynamic function calling

### [2026-01-04] Interview Tab
- Interview recording and transcription support
- AI-powered interview summaries

### [2026-01-03] Contact Attempts & Security
- Contact attempts tracking with automated reminders
- Security headers middleware

### [2025-12-31] Profile & Access
- Profile card enhancement with inline editing, sync, hidden fields, and PDF export
- Intake specialist view access for post-approval cases (read-only)

### [2025-12-29] Form Builder & Search
- Complete form builder backend with JSON schema structure
- Token-based secure public form submissions
- Global search command (Cmd+K / Ctrl+K)
- GCP Cloud Monitoring integration

### [2025-12-27] RBAC & Calendar
- Calendar push (two-way sync with Google Calendar)
- Advanced full-text search with PostgreSQL tsvector
- RBAC standardization with centralized ResourcePolicy definitions

### [2025-12-26] MFA & Calendar Tasks
- Multi-factor authentication with TOTP and Duo Web SDK
- Calendar tasks integration
