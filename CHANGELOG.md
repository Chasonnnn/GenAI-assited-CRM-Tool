# Changelog

All notable changes to this project will be documented in this file.

## [0.18.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.17.0...surrogacy-crm-platform-v0.18.0) (2026-01-13)


### Features

* improve dev experience and code quality ([0aeca2d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0aeca2d4a9c72fc94e2bedfcddf709b63715a88b))
* membership soft-delete + dependency upgrades + lifespan ([29f403b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/29f403bf82582842bc11a2c23d69d50c9497eddd))
* scope org-sensitive paths for security ([e990150](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e9901503b57d188e1f3aff9a0e3ef8d0da78aed1))
* **ui:** comprehensive UI/UX audit Phase 1 & 2 ([7661078](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7661078aa5450cb212db3d4c1eae2f92e528adcc))


### Bug Fixes

* baseline migration FK ordering + protobuf CVE ([c37d027](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c37d027260b89ea54ceb97a4a89693830e9015a9))


### Performance Improvements

* eliminate N+1 queries and harden config ([a690226](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a690226396e81508b7a34f50f62147bf4ba1954c))

## [0.17.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.16.0...surrogacy-crm-platform-v0.17.0) (2026-01-08)


### Features

* **activity:** log note and attachment previews ([e13bf1a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e13bf1abca3bec67dd241fa219258dcc449c1e01))
* Add 'Add Task' button to match calendar header ([2677eb7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2677eb7783960d6879eb14544d7890248411759e))
* Add 'Share Booking Link' button to appointments page header ([28b167e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/28b167e3941b8c9bfa4aabbe80f042e388a7dc47))
* Add /cases/{id}/send-email endpoint for Phase 3A ([fffb151](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fffb1516aec6cf9dea2f1c74268590dc41d53078))
* Add AI API contract tests, CI migration check, and encryption keys for tests. ([d68212f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d68212f46f9357f924685f8755173049942cecfe))
* Add AI config to integrations, fix assign button, improve workflow wizard ([f73aa4f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f73aa4fd75fe64667df38172b4bcce39f8c0f7eb))
* Add AI Summary option to interview dropdown menu ([ecf4baa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ecf4baa20a9eac3cd6a38e25da6acc8e5a97ac90))
* Add AI Summary to interview menu and create standalone Notification settings page ([478520d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/478520d0437e577178c3f08336f122a45423486a))
* add ai_enabled column to organizations ([471185b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/471185b4ce42316fb9d5739a4261b8a2c12d00ef))
* Add appointment scheduling system and consolidate Tasks/Calendar views ([cbb2fcc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cbb2fcc3a89209aa30ff7fdce4cd3b100f977986))
* Add browser push notifications ([7504b61](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7504b61d5abd1754ad3b5e7004db02be714229ce))
* Add bulk task completion endpoint and hook ([24e4c62](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/24e4c62ccee55df0046f69a16c078c8ebd1f2e18))
* Add Campaigns and AI Builder to main sidebar ([eb858c2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/eb858c235cef01593cf55d273ce06b8e315d3ae7))
* Add Campaigns tab to automation page + document future features ([1112cef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1112cef65db995c0c93f0c47fa52ced8f6f0f986))
* Add case activity types and refactor queue service logging to use a dedicated service, and fix integration test cookie parsing. ([8ca9077](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8ca9077718b45ecc28334d5b99095c82dcd6984f))
* Add case-level access checks to AI endpoints ([be2487c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/be2487ca0497d81d470a5782f9ba40795ecbcf88))
* add comprehensive RBAC permission management system ([dd5f2f5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd5f2f545b648df0f4b0ff7a0488fe5b02618732))
* Add contact attempts tracking with automated reminders ([ee343c2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ee343c27f4a608ee77f00c18037e839a5b71d5d5))
* Add context-aware chatbot with task context and schedule parsing ([7ffaa6a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7ffaa6a900b3619e03f59ebfb071bf546aebe6e1))
* Add CSV import with dedupe (Feature B) ([5973c4b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5973c4b8d77892c38db18038d6c63da025fc1dd0))
* Add download error toast notification ([bb69253](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bb6925315308b815f4cf1362e868ee9c9caa82d9))
* Add Edit Workflow functionality ([d237490](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d2374907e35292d871cc865681eb4e6059e38f78))
* Add email templates page with per-user signature editor ([e69da86](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e69da8625b7e18c036670b1c25b70f5cd7099b33))
* Add file download button and validate Match Accept flow ([8484afc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8484afc889f65f621e14e7d69e052866c76cf275))
* Add filter persistence for Match detail page ([da4150d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/da4150d471d0b00501392effdfe699a9d4d2318c))
* Add filter persistence to Cases, IPs, and Tasks pages ([ac7c3fb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ac7c3fb5dfb1f32ad468204e759449f34dae98f2))
* add form builder backend flow ([b7a8905](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b7a890506a3cfb33111301fce44594242051b403))
* add form draft insights and normalize terminology ([ea442ce](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ea442ce01a39a7c825a2c48cc1173cdfabc27cba))
* Add funnel, state, and performance data to analytics, refactor signature preview with template override, and migrate analytics PDF export to an async service. ([b53d31d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b53d31de3c7196697dbc9055ea53a857eaafb829))
* add gcp monitoring and health probes ([ed83c1c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ed83c1ce22dda99d33c8520f210adb9f50a4be34))
* Add global audit trail (Feature A) ([a13a34a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a13a34a173d60ba656c7228ba27fa996a02cc992))
* Add Gmail status endpoint for Phase 3A ([59d7236](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/59d7236eee0b95b8acdfb81625755a78e613e5f1))
* Add Google Calendar event display to unified calendar ([5353532](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/53535329fa12e05c5026bd627111f6f4c9a4b29d))
* Add match support to schedule parser ([41bd9ff](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/41bd9ff13d9d7b2a6b5956d0c9d39c0731022e05))
* Add Meta Lead Ads integration for webhook processing, secure lead fetching, and auto-conversion to cases. ([04c30e5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/04c30e5b2a0bdaba7a18fa69f155c5ac229084f3))
* Add Meta Leads Admin and CSV Import backend APIs ([de7a37d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/de7a37de4ab0cef196cd8f65b43af8ab96704de9))
* Add Next.js Bundle Analyzer support ([5b0caa7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5b0caa7ea4eb210fd4e16d40d162c3967f03daaa))
* Add notification triggers and scheduled job ([d17e2ba](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d17e2ba046eef89e2273cea7f5aaccfe3cf38c2c))
* Add org-configurable pipelines (Feature C) ([98443dd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/98443dd19cc881ed118548f0b8459f29529b860c))
* Add org-wide activity feed for Phase 3C ([f95206c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f95206caf8cd34ff3f26f772775ab0419f624c29))
* Add Parse Schedule button to match detail page ([c57c202](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c57c202baf4ffcbd91d0abfb9a56096baf24bcaa))
* add PDF export for analytics reports ([7fd5f4d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7fd5f4dfc875375e925b371bd79b27639c0f9b92))
* add priority field and show phone/email in cases list ([619b473](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/619b473e9308ca2a22fcba3feccc93d0df0f5e73))
* Add production-quality Meta Admin and CSV Import UIs ([00c47ee](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/00c47ee1bba027a57dfb2966c8faa32c69d4f9e8))
* Add Profile Card with inline editing, sync, hidden fields, and PDF export ([ffc7999](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ffc7999391fb94dd863db4d0fb150d55a47d778d))
* Add qualified/applied statuses + fix CAPI implementation ([abe4f44](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/abe4f4414ad0e1b3a82c870b9f60dfc434c1c25e))
* Add Send Email feature to case detail page ([d13cbc2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d13cbc25c471ae79dd03f045c65431bd2c476582))
* Add Smart Task Creation from AI with schedule parsing ([5afbdd3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5afbdd3d4c77095531c91486231821216f02930a))
* Add sortable columns and search to list pages ([918bfb0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/918bfb001c61ff9c06b6c899cbeff924f0fa4f48))
* add task reassignment notification + TODO for due/overdue ([0adf554](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0adf554cb01a794c1c924bc67bb0eef646713077))
* Add task reminders and appointments to notification settings ([29898d3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/29898d3cfee1353254c3f4a0526c96a6687b7363))
* Add Test Workflow feature ([69d5544](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/69d554419f9cd14f3ba0a126e66a26c154a6fffd))
* Add toast notifications and delete attachments ([1bd0432](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1bd0432a504db9c813bb48a9785590faea894ce9))
* Add Zoom meeting integration, including a new date-time picker component and refined timezone handling for meeting creation. ([dbf5bcb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dbf5bcb492b2301ab72bdcd73be299f8b1a2f22b))
* Admin data management UI for export/import ([e2f06af](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e2f06af0a7807946e084da4c0479dd43c38cd3b0))
* Admin export/import improvements + concurrency fixes ([fc0a541](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fc0a5411da486d21a6de64763e2fa384d67e53f1))
* AI Assistant improvements ([ce0bbc4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ce0bbc4a8e74f55419a67866794bf2552066b72a))
* AI Assistant tab, Meta Ads spend integration, UI refinements ([6a86566](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6a865660ae46e1259ddc5a16abd0af612f941db4))
* AI Assistant v1 - Focused endpoints and case detail panel ([447db95](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/447db95930232839df724448a95f8bcd7386e115))
* AI audit time window selector, click-through, and token usage card ([41d760b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/41d760bd06ef5185bc7f0da23cb4eb2a0a7b0adc))
* AI settings versioning (Phase 3b) ([14a4589](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/14a4589f3759384fe8a75dea9757250cd2abaed3))
* **alerts:** wire system alerts for service failures ([994d043](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/994d0438f903601474890f2f0a029eb0b997f515))
* Allow intake specialists to view post-approval cases ([c7eda3a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c7eda3afdcaa8e6062a0597ac83b9e1335b705dd))
* **api:** add /cases/stats endpoint for dashboard aggregations ([1a69f8e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1a69f8e8ad06818b437e2d296c2cd490412faba7))
* **api:** add background jobs and email foundation (Week 5b) ([6d72b2a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6d72b2adca8f71c0338d59d817ffdbc74bf6e052))
* **api:** add Intended Parents module (Week 6 Phases 1-3) ([b4579b1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b4579b1e961994ddc04607bfffb28f27e41306e7))
* **application:** manage submission attachments ([b435e39](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b435e39016941e1c4755a103624725720237f670))
* Audit Log Viewer UI ([1d0b8d3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1d0b8d377578ac18af0b4c50c1b675859a874389))
* **auth:** implement authentication and tenant isolation ([2121126](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/212112608cb59e02d1dddbe218c724582834bfd3))
* Automation System Enhancement - Campaigns, Workflows, AI Builder ([1b57cd8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1b57cd80da3338c497edaf2a4c2172c130f95cb1))
* booking preview, lost stage, and automation seeds ([5ca24dc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5ca24dcc411e0b365ffb0f0671f2429082caf831))
* Calendar Push + Advanced Search + HIPAA Audit ([ac7fa65](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ac7fa65b6a09d57d46f0ee594f57b7341a7d31d2))
* Case inline editing (hybrid approach) ([03d300e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/03d300e7fea708d214c9c9d87b69ddda09df80d4))
* CI/CD Pipeline and Frontend Testing Setup ([aecf994](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aecf994a3b1b61fdfab6d4ae7e4130854d7cb9d0))
* Collapsible sidebar sub-menu for Settings ([0f0cf71](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0f0cf71e3dfdb8e7bade4cab1debf2150bc71ca2))
* complete AI chatbot permissions and page integrations ([532af80](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/532af80e4cf79cfc56a17c2aceede63b6b9a4a02))
* Complete All Tasks (v0.06.09) ([2d87a98](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2d87a9859fcdb7bd2920330a1d2ef0d857bebd36))
* Complete Enterprise Audit + Versioning System ([0cf9c50](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0cf9c509f2f89bd828b0e6c10d10b5a780f7081f))
* Complete Queue/Ownership UI ([1d3d77a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1d3d77ad50c2a83499506ed869a117dfd8ef4ae5))
* **compliance:** Add edge case tests and UI warning ([1a61cd6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1a61cd6886098e3ae9e475c022b182af5f9eb310))
* comprehensive case activity logging and bulk-assign endpoint ([816737a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/816737ae1e7036611b2cb0cd8d824aaa0aa608d7))
* context-aware AI chatbot with security hardening ([8b2ed5a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8b2ed5a0ac87a8b6a2b1d4f3d0765397255ad434))
* Dashboard charts with v0 styling ([a349cf6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a349cf6296c427e8945237a33e2f88eae8f06cb2))
* Dashboard real-time improvements with WebSocket ([bffad41](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bffad41448fb5a559dc4c2886ad581da5fe4e530))
* Dashboard UI redesign with v0-style cards and charts ([79e24b2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/79e24b28ae948cf924ae958408863b40faf515ff))
* **dashboard:** Add upcoming tasks/meetings widget ([d7444ef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d7444ef2255202b34a7d838f7d30ad7b944d1813))
* Email Template Version History UI ([af648ac](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/af648acdb4a92e3d47a64a149c96d3b59df4c568))
* Email templates versioning (Phase 3a) ([f73fab2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f73fab2f3d7b20d870f6d6d068c7b847095cecd5))
* Enforce authentication for `/auth/me`, update pipeline stage statuses, add encryption keys for versioning, and enhance test database isolation. ([936f75d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/936f75d8c5dfed3fcb5f6d613f1334ed5425be20))
* enforce MFA challenge flow ([1da33fd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1da33fd833581517e8829521f58df3603cef3a82))
* Enforce NOT NULL on case ownership + cleanup + tests ([e2b1b70](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e2b1b70ca027f0053a502789cc716ff69884cdc9))
* Enhanced notifications page with overdue tasks section ([cf7ec17](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cf7ec170382bfbe2920f615747a417c607fbc5e1))
* Enterprise Audit + Versioning System (Phase 1) ([f8a788e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f8a788e8f04504df30df0745ebb0ea4666fcd2c9))
* Expand ALLOWED_CONDITION_FIELDS for workflows ([ce778bb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ce778bb2a19803c9afd45626077ef2f98c26e415))
* **forms:** integrate Form Builder UI with navigation ([dae0930](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dae0930775ab8a04dca561a4ba94bb90f07f7033))
* frontend multi-select cases with floating action bar ([b1d982a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b1d982ad36e7ca9e04983109b18dedab8ce1a216))
* Frontend queue hooks (use-queues.ts) ([cb173f9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cb173f94457b1cd6a52f2eb5e6dc26ea1082cea4))
* Full Integration Test Suite (13 passed, 1 xfail) ([2eef977](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2eef977fafbd666664c320a8eb7721b23a3bdf53))
* gold row styling for priority cases and toggle priority option ([f4fa67e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f4fa67eeeb6ba5c7a3cf62b14229f84588d7f050))
* Implement 3 sprint features - File Attachments, Invitations, Calendar ([cc12d33](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cc12d339f3e5f0d03cf74ecac887c88345504134))
* Implement async CSV import with job queue ([97f2588](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/97f2588df7ee86804b3cfafaf72b05b2b199929b))
* Implement attachment virus scanning, enhance attachment API security and access control, and add invite email service and task editing UI. ([7b04a3c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7b04a3c5d53a0fe506ec4e66b599c39fd4e7e18a))
* implement case edit dialog for all roles ([62ee0d0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/62ee0d0122339d5a97f41cffbeb17762296ddaa7))
* implement case handoff workflow ([3644ace](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3644ace3ababc1fdb302813906e6d1210e69bfff))
* Implement MFA with TOTP, Duo, and login enforcement ([1d64e6b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1d64e6b914733f1f22411f5b0267d8d487f22705))
* implement Settings Save functionality ([704973d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/704973d1d91dc73b5ff8417819ff68b7b1c56b49))
* Integrate appointments into MatchTasksCalendar ([7c490b9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7c490b9057ae6d1c3b3bf51fbff18872419c70bd))
* Integrate schedule parser with AI Assistant ([fde73cb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fde73cb9f33af51df604a17ca4b99a4cca7069c2))
* Interview notes with Google Docs-style anchoring and connecting lines ([93ca566](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/93ca56641a7b35adce3830b7925056dbff4af0b8))
* **interviews:** store transcripts as tiptap ([bdc5340](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bdc5340551ceb0cc1a0b9f74f347268b45ac08d6))
* Introduce AI assistant features, new OAuth integrations, and enhanced analytics with new chart components. ([38f4c3d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/38f4c3d536a8a22022feaa2b9a60afbd5dc56f1f))
* Introduce OAuth setup guide, add search command component, and enhance team settings with developer role and UI adjustments. ([3b4d204](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3b4d204086a54aa47eabbbe02f3db1197542c3ac))
* **ip-history:** add changed_by_name to status history API ([615faae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/615faae7aa5a9570214a4268335684a9826bdc2a))
* **ip:** add intended_parent_id support to tasks and attachments ([89f232e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/89f232e9dbd9696f57a3f4318e495fa00aa68825))
* Major settings refactor with sessions, signatures, and user profile ([8133c8e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8133c8e9bf7709c19de8b904befea9250dd366e3))
* Match detail enhancements - dialogs, calendar, filter fixes ([aced920](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aced920d7c3a9961a877ae58771a083cb0329ee0))
* **matches:** Add Matches module with 3-column detail view and tasks calendar ([263a896](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/263a89609660188d1651043fcd1275128260e03f))
* **matches:** add RejectMatchDialog and AddNoteDialog components ([611e451](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/611e4515f55f2f358c67f1792c9161f87240345d))
* **matches:** Complete matching system frontend ([7d1c70d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7d1c70de26b680dc4212f1481bcfaf8fae805dea))
* **matches:** enhance Match detail with source filter, activity tab, and UI refresh ([1824c9e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1824c9e32b433dd81b5ae6ed9bb91ccb60c8c2dc))
* **matches:** Wire ProposeMatchDialog to case detail page ([9ed2ce5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ed2ce5af37bab5020e0fbbd6e5489e88b1e1de1))
* Meta Performance as pie chart with days to convert insight ([921c787](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/921c7874453a52661128486c9f232c0ce66e9d13))
* **meta:** Add Conversions API for lead quality signals ([5054391](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/50543918d78be2e3015a5db0102f4530ff186e7c))
* Metadata API for picklist values ([d183c27](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d183c277f79223a5b2877caee8ae447e86627aa1))
* **meta:** Week 9 Meta Lead Ads integration ([a155408](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a155408204814ce1cb0d36a04287934651f0d3cc))
* Migrate IntendedParent to owner_type/owner_id pattern ([e5ff027](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e5ff0271e9381a1ee2f4a8a21b5bfd7591cdc50a))
* **notifications:** Add workflow approval notification preference ([f6cc1f6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f6cc1f6d1e4b2e96d4bc25c79a1a270452ebf2c4))
* Org Settings Versioning (v0.06.07) ([8c6a070](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8c6a070b65e5d43928e8ccf184bf0ad616cbe3f8))
* Pipeline versioning integration (Phase 2) ([f1b91ca](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f1b91ca5c9c69ff99b62860d5b012989b5bb13ad))
* **pipeline:** Phase 2 backend services and API endpoints ([b4123f1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b4123f18f0a53727e939d16738e1b7c388183538))
* **pipeline:** Phase 2 database layer - stage CRUD ([602377b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/602377bed8418cfa3080fa63ca7e03b4c9dd9010))
* **pipelines:** Add pipeline settings UI ([599e14e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/599e14e1f3b5a11dd30b8b1c1bb58cd4ec335a2a))
* Polish booking confirmation page ([63d5a06](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/63d5a0673318f96cfb1f97158603fffbdeb6fe01))
* PostgreSQL atomic counter for case numbers ([91b92d6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/91b92d6dc25f71a6e5217dd08c69b20e820989fe))
* Production deployment preparation ([6e3db17](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6e3db171a89b390e6bc0b98174e7acbcea04ce14))
* proper PDF export with native reportlab charts ([61de60d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/61de60de22a9cad4c70e857f9c61351a07f32247))
* Queue filter on cases list page ([a915965](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a9159658ea491917a8b7ce9be236eefdc3120b5e))
* Queue member management + campaign recipient preview ([69afeac](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/69afeac44d27d1bea1081d85e3497b1851ff0810))
* Queue/Ownership System (Salesforce-style) ([3c38a7e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3c38a7ef724b797c55902b11e2ed5fd93b15fdd8))
* Rate limiting + Workflow Template Marketplace ([1f8c08d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1f8c08d9b96b240761e70d6728e36370ff3c9a77))
* **rbac:** add backfill-permissions CLI command ([a9f26be](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a9f26be93e347a2c114a28cde666c9c76a3181fd))
* **rbac:** add bulk role assignment UI and developer_only guard ([02dd00f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/02dd00f451926a3b522938bce351bf98f2f51291))
* **rbac:** add view_post_approval_cases permission filter ([f50d299](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f50d299f573dbb7e1754acc5b4202d6a510cb982))
* **rbac:** add view_roles permission for managers ([5e67e07](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5e67e07f92bfaabc196428670cb152ff4bd4c8db))
* **rbac:** complete route migration to permission-based auth ([06587ac](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/06587ac326f8715d8a149f0c3f13d42833c9ef75))
* **rbac:** migrate permissions and invites routers ([6d7d5fb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6d7d5fb84ac187e3b45471a7acad2b965a741c96))
* **rbac:** migrate pipelines.py to permission-based auth ([d9218c4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d9218c4dc7ddcef7a3e2745856386e17a62c262c))
* **rbac:** migrate read-only routes to permission-based auth ([a8e86b2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a8e86b2918d2b4883e74338f1768573b833793c0))
* **rbac:** migrate workflows.py to permission-based auth ([d276235](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d27623514ff22013109392ffec74463e458f40a6))
* rename 'manager' role to 'admin' ([6f852a3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6f852a3e199d29b86bbba6bfaa672ec70fe65dcc))
* Reports charts with computed insights CardFooters ([75da2d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/75da2d51b698ecaface893a957a69a7ffa648c45))
* **reports:** Add Team Performance Report and AI Analytics Tools ([ff58372](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ff58372b3bbbf79ea1c3ae4fa4537d431d3dc6b8))
* **reports:** update performance table ([7a57121](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7a57121fd6c1ed274b6f92456b40753fcfd1e63a))
* restrict pipeline settings to Developer role only ([173287e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/173287e2fa232a3ae7479845a58f1cd124bea512))
* schema hardening + appointment buffers + campaign idempotency ([e7e6471](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e7e647191b0faea280620a156ab4c64c1e479b47))
* Scope appointments in Match calendar to match's case/IP ([4068773](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4068773eea6f0386c6779599ff732b59ce79ee8e))
* show both Qualified and Converted rates for Meta leads ([22912b7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/22912b74d85fb3ec2087514f68fa3ee989682500))
* **signature:** Enhanced email signature with org branding, social links, and templates ([c15807a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c15807afd454b56066be3ec4408ed4cd0bc30228))
* Standardize datetime fields to timezone-aware, add multiple database indexes, and rename an auth identity constraint. ([76dffad](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/76dffad5db255854bea30ca9fb5ff3d34b5e5fe4))
* Task search with q param and date filters ([7d799ef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7d799efc54e78d5e46e1861dfb69b4f7c6577781))
* **tasks:** add calendar, recurrence, and delete ([e9c4e39](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e9c4e398184c68686a074d1c0cf7ad66240292ec))
* Testing Infrastructure (v0.06.08) ([f2308ec](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f2308ec0b8b67a623c01c178b6d825d3badc1e2b))
* **testing:** add MSW integration testing infrastructure ([8ed8a87](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8ed8a87e4e9d2c574a0c8ea2b23cb70fd5bbfee6))
* Update CI workflow with newer Postgres, pnpm, and Node versions, remove CITEXT extension, and refactor dev authentication bypass to use a configurable setting. ([f507811](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f5078110a4f5f00877a8145e828d5b9e9aabe42a))
* update history tab to display comprehensive activity log ([511b265](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/511b265953318621082f13e94c7718ff044d5d4b))
* Update README for v0.13.00 with appointment scheduling and tasks calendar, and resolve several high/medium priority feature gaps including CSRF, WebSocket auth, and CORS. ([978d878](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/978d878e6e87dfdc5bb8f8c98ed67ae42632b295))
* V2 audit hash with full column coverage ([a518f93](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a518f933da355d7ae0aa3c3861347ff6e3eb4eed))
* Version History UI for Pipelines (v0.06.06) ([011975b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/011975b7dd470eaf758cd80aa77f2ed431a29dd3))
* **web:** add API client layer and React Query hooks ([ab99a0b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ab99a0b218bfd667448640d9dc7d3aa912a61586))
* **web:** add Automation page with v0 design ([cefd1bf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cefd1bf310e657592b1e25929556f27029856708))
* **web:** add case detail page with Overview, Notes, Tasks, History tabs ([6c0543c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6c0543cd349d2a43612fbaee31eb76762acb37a8))
* **web:** add Cases list page with React Query + shadcn ([ca1eb98](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ca1eb98b4c98a1a1e21924b8432bcc523fb11c88))
* **web:** add dashboard page with stats, tasks, and activity ([94da128](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/94da1282d84e1aa670c43225a07e9900514d0514))
* **web:** add Duo SSO login page with v0 design ([46e361c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/46e361c6bcf06f5941d04a3f0f251e0ac722614a))
* **web:** add email templates UI in Settings (Week 5b Phase 5) ([250b53b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/250b53be13c2d22354508f3d7254a7e60d9a0109))
* **web:** add Intended Parents frontend (Week 6 Phase 4) ([9a98483](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9a98483d2495cb377b8f2479887e1212c15de2d2))
* **web:** add Intended Parents page with v0 design ([a73deec](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a73deecaf91710953ee745664340a8dd3ad4f19d))
* **web:** add login page with Google OAuth button ([268c1f3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/268c1f370ffc56214ac3afb199ccbd49c476975e))
* **web:** add Reports page with charts from v0 design ([03c6552](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/03c655267475b935b6308b2cdeb60fa7cd9ff269))
* **web:** add Settings page with v0 design ([dd7bd3b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd7bd3b161c58789ac8a9285f377dbb324b85c94))
* **web:** add Tasks page with v0 design ([4a4d1e5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4a4d1e516306398d2856439240c8d438b35c4cb5))
* **web:** complete Week 5 frontend-backend integration ([d3bd53f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d3bd53f8044566d16ced579698ba1195c8c80035))
* **web:** implement v0 sidebar with CRM navigation ([c7b3f27](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c7b3f2766d290fcffeb9c74e4176dd9b9765dd69))
* WebSocket Real-Time Notifications ([87b5d8f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/87b5d8f55ea7090309e66091e6afdf54e23c824e))
* **web:** update Cases list page with v0 design ([16b91e6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/16b91e660806347fa511e8ea731036cfe9165293))
* **web:** update to latest dependencies ([41d502c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/41d502c22d6d84179dbb0a9762f8ba4014f45f1a))
* **web:** upgrade recharts to v3 ([2ec5242](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2ec52428e9db4e512dcc979950f5e813a3b3e675))
* **web:** wire case detail page to API with notes and tasks ([aa07890](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aa07890071b05eac3b70fd239d701e58d401cf59))
* **web:** wire cases page to API with filters and pagination ([4d63f5f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4d63f5f1f7941d5fb118fa23ef2dbfe984ce4d44))
* **Week 8:** implement in-app notifications backend ([10dcc5f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/10dcc5fda6349550d034f7fe9ff16ac267fc886d))
* **Week 8:** implement notifications frontend + dark mode ([d4db4b9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d4db4b9f2dbb5e7d321a6d88fc271e6340cfe5e2))
* **week10:** Add analytics endpoints for manager dashboards ([d4c3da5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d4c3da5d58228f5b3def965e9cd8875a2208c421))
* **week10:** Add frontend for analytics, alerts, and integrations ([8e0ffc0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8e0ffc028f7dafa3a304f5558c979678be7e1a9c))
* **week10:** Add integration health + alerts + metrics tables ([daef8e2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/daef8e20777697d65970bf52824c18cfcc9749b8))
* **week10:** Add ops router for integration health and alerts ([39ef38e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/39ef38e8596bbd0f6b6a69c65dea882db59441dd))
* **week10:** Add ops/alert/metrics services + worker integration ([dd6bebd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd6bebda848cc47b3cf6cd3a4e288c5f816413c9))
* **week10:** Add scheduled token-check endpoint ([355ebd5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/355ebd525f39b572e40acab4e3a250ef1582442d))
* **week3:** implement cases module with full CRUD ([24b3a92](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/24b3a92478453196be43f7132acfcffd6b05d010))
* Wire AI Assistant page to backend API ([0b23e09](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0b23e09a9439e84976115db179ebf8a10b65ae52))
* Wire appointment notifications to service layer ([13c366d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/13c366da462bba3baa0b8fa154321010cd2285d5))
* Workflow editor validation, reports improvements, match fixes ([54512a1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/54512a18d6adea1f8f2045e7ab69eb5fae1d025d))
* Workflow Execution Dashboard for monitoring automation runs ([b12e805](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b12e8059d62ea7d6d2c850ca343cf20af5d5c10c))
* **workflow:** Add workflow approval system with business hours ([a9400f5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a9400f526b3d96af9011b3f63f09c27e1187e43b))
* Zoom email invite with auto-created template ([f406f5b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f406f5be4c9ae0bb53ec49d59e4dada9b3f01414))
* Zoom integration - meeting creation with notes and tasks ([7e8f2bb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7e8f2bbbd2891dd1aba65fe3530896057cc917bf))
* **zoom:** Add Zoom settings page with meeting history ([f597470](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f59747001ecffe290b76f677c5be681a695de917))


### Bug Fixes

* 🎉 100% TEST COVERAGE! 85/85 tests passing! 🎉 ([7b382bd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7b382bdfda92c6e3647763d3d18feb23d31c7076))
* ACHIEVED 100% TEST COVERAGE! 🎉 (85/85 tests passing) ([c85aa23](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c85aa23850e90c6ceaad489174fd0d31b27c071a))
* Add ai_enabled check to Parse Schedule buttons ([07b4734](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/07b47343f15e890659a85432a8045a81aace49c7))
* Add comprehensive tests + fixes for Phase 2B ([b9a89de](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b9a89dee03e2c501076ac3e6c00b491698250d9e))
* Add EmailComposeDialog to case detail page and fix TypeScript errors ([777acb9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/777acb99f192745ce1ef429facaf42bfc80dbfc8))
* Add idx_cases_reminder_check index to Case model ([0bfb2ac](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0bfb2acb72b2f3ee6a76f8b1e34e00105d2debb3))
* Add missing closing brace to reports page component. ([fb7f4e5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fb7f4e5785e3ba678d492e5e00bd27bc41ae14a8))
* Add missing test mocks for automation-page and case-detail ([8af6ebc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8af6ebc6c7c40693080d7bbd8b5edf4f1362a68c))
* add nh3 to requirements.txt and remove invalid task search ([533ea9f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/533ea9f87ea0ca33deb55651eb9b7653af2f1891))
* Add null checks and explicit nulling for WebSocket timer refs during cleanup. ([3992ea1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3992ea177b4b3bbee8cbdcaaa97bcdd06497ffca))
* Add Parse Schedule button and AI context to match detail page ([63cf5e5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/63cf5e50b087590059869e8fe436efcecbf7beeb))
* add phone_hash indexes, MFA timestamp types, and address bandit security findings (B108/B608) ([40f59de](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/40f59de8cdda68f0335c3064dd39e3d38733c507))
* Add PUT method to API client ([3af5c7b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3af5c7b655c931e79826946fb2582924c3eb3304))
* Add render functions to all dropdown SelectValue components ([da7f953](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/da7f9535973a3191dcea7a59b4ce5a291f4af46a))
* add search_vector columns to models and fix search page import ([33d8382](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/33d8382814613c3b58771e1059a8a31558b071a1))
* add Suspense boundary for Duo callback and fix MFA timestamp types ([2a281b3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2a281b3d0a809cfb03df98a2d49b814821e2e58c))
* Add tracking_token unique index to CampaignRecipient model ([967ac8a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/967ac8a69f5573ebed17bdc0ed06e5adf93e6a0e))
* Add useCreateContactAttempt mock to case-detail tests ([6e42023](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6e420231f221f800b2c629155c58406185511f0a))
* address 13 code review findings ([cbc0d1d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cbc0d1d15b1766db7ada8f4863f2f05c433f422f))
* address 6 bugs in case handoff implementation ([711ab54](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/711ab540984fcbe08b233da1a95c3e1000a14bac))
* address 6 bugs in Week 3 Cases module ([bbd1de9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bbd1de9fd67ea873428d645fbd527abc0b2e968f))
* Address all code review issues from today's commits ([e5958d3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e5958d3f9c656b4137c6d3bdde595c26d0a4d9d3))
* address all implementation gaps for multi-select and activity logging ([cc248f0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cc248f0128c192c055cc7581e5464162536d107f))
* Address audit/versioning blockers ([37183f1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/37183f162e2fd238cf95f90369334f1f1eb3f187))
* Address automation system feedback ([a34b85a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a34b85a2841a85674f4d0ad0328365deb10e5ed1))
* Address identified bugs and UX improvements ([a3f833f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a3f833f2e00654f7eafe507b7894b61000de72ab))
* Address review issues for Google Calendar and AI chatbot ([3df16cb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3df16cb69dd62e92cd3f8ab39462c456fd7c42bd))
* AI chatbot critical issues and add global mode ([eb62308](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/eb62308500f09bed80ad49f59a1960c39bb94e38))
* AI permission + match event validation + date filtering ([0369e26](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0369e264359bfe3f9a5198aa59343057f6cba90e))
* AI workflow validation, notification routing, campaign lifecycle ([bd04fd7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bd04fd71848744cc5f7257b996d9ceec919f5618))
* align frontend enums with backend schema ([a6441d8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a6441d882abf41eb891f564a43e185939ad01f6c))
* Always create task for Zoom meetings (remove checkbox) ([25a3b4c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/25a3b4c11286904adf44e2033f35fb810f5d5fe7))
* Analytics service and websocket improvements ([28798d7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/28798d7e5845025e23b6249e6639bb9219c8175d))
* **api:** add CSRF protection to all IP mutation endpoints ([a1ae06b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a1ae06b0144a4a9fa81292fe2f63d029bdb6a3b1))
* **api:** address IP module issues ([ce72453](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ce724538eb6a219aaf5230501e145cb13d7f76f0))
* **api:** require manager role on /email-templates/send for CSRF protection ([7cf426f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7cf426f84a08c8a562689b14883db46115f61625))
* **api:** update routers to use require_roles and attribute access ([fc2da86](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fc2da868f88c5e68b3c3ad95d57ce5dcb7495438))
* apply suppressHydrationWarning to root HTML and body elements ([60a3c4d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/60a3c4df43aba973043efcda97127146b4dc4017))
* archive permission and note_deleted rendering issues ([6a136ae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6a136ae834fc045909d41212a3d631bbf69f3041))
* **automation:** Apply SelectValue render function pattern for proper label display ([5be3354](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5be3354df534e7c591ca29b5521e8bf3a33af0ae))
* **automation:** UI/UX improvements for workflows and templates ([31e1895](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/31e18953c86e067b259afd5a51ea35234e66257e))
* Backend tests 91% passing (50/55) - major progress! ([bb93892](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bb938927dc38325a98594f66877f661384812b38))
* Backend tests 93% passing (51/55) - Meta encryption test fixed! ([f805f8e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f805f8e6eda86e81ccaf12c58a7a8a462497595e))
* Calendar component for date range picker ([3d95542](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3d9554298ad87a81f57192a50d7eb7df3cf102b7))
* Campaign status filter + templates API ([26f241d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/26f241df7cad87d2380eb716f7d396eb57d621a8))
* CAPI via job queue + idempotent MetaLead storage (team review) ([57de4ea](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/57de4ea0cef67e9e5c8a2933c8768b63b4d4e273))
* case detail params, notes XSS, and wire tasks page ([1033156](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/10331566fe590a38e90855f5b95831fa9b619136))
* Change Case owner relationships to use selectin loading ([e79787d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e79787def2441ee83890c662acb2c7d759925fa0))
* CI backend tests - lazy imports in conftest.py, add CITEXT extension step ([3bc5f25](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3bc5f2513da4eda5d07d0d4126615eb335a88ba4))
* CI uses pnpm (project has pnpm-lock.yaml), upgraded @testing-library/react to v16 for React 19 ([3459a58](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3459a5874565a7a8b6e25a55b95933c3cfffa339))
* CI workflow - remove npm cache, add continue-on-error ([65a9a68](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/65a9a6804ca5dae70814f3b719a4268416511f97))
* Clean up test file - remove debug prints, fix duplicate assertion ([f2fc73c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f2fc73c900ccad3b43d900aa946de1a2b81c6080))
* clean up unused imports with eslint-plugin-unused-imports ([9b671f6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9b671f6a2b9ff1d37a75510b479fb47dc4abd719))
* close remaining access control gaps in tasks and notes ([d848ee5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d848ee5b4ac03f0cf198153306053a0382a9ebb8))
* Complete alembic schema sync for Pipeline Phase 2 ([2d6c14e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2d6c14eb3dbf8a815ff3a0b4d269ad318f56a80b))
* convert remaining asChild to render props for Base UI components ([6c77802](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6c7780211f07474b9285ece022333ce718fc22fe))
* correct analytics metrics for qualification and contact rates ([6c12e75](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6c12e75c8592d9d46e9914ece17a290397ca34d8))
* correct field names and improve task-to-case workflow mapping ([0b3d61c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0b3d61ca534ac275bbe4df63086eac26be9193c4))
* Correct import path in queues.py (app.core.deps) ([cc76246](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cc76246e523b32115dd54615059f4a24d9e9c32c))
* correct table names in migration (memberships, not membership) ([7c771c9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7c771c9f4d433ef759e5443848e28b30ab4ecfb8))
* Critical bug fixes and improvements ([d42ec7f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d42ec7fd0fb57c269da376221c596cb16f4d9f3b))
* Critical bug fixes from code review ([d256d45](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d256d45690f809a47a37eda30a786d76b80bdb01))
* critical bug fixes round 3 + template marketplace improvements ([80a247b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/80a247bf2a64b58ed838ee20e51accd26c3fd699))
* Critical campaign + appointment bugs ([cdb092a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cdb092aefdc6db8dae794f2a59cbfd2e75b9ba25))
* Critical workflow engine bugs ([674f491](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/674f49171d83d07b5d57c7525c9641990a5f7511))
* Date range picker closes prematurely on first click ([6a0b99a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6a0b99a492d1826f51e23905350d60cedc717eb2))
* **db:** add explicit TIMESTAMP() types to datetime columns ([ba770fa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ba770faeb1d6f39d3f170e26d5669006d7ce5f54))
* Default timezone to Pacific (America/Los_Angeles) for calendar events ([718f97a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/718f97a0c812edf45ebae855fbf21ad894e5311a))
* Deprecation warnings (regex→pattern, class Config→model_config) ([e86491e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e86491ee1cc3c158d171d9e2e42f7a8082475933))
* ensure audit log event type filter defaults to 'all' and update API dependencies. ([9b5ffa6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9b5ffa6901032ab5c94ca4bec30918673d98b2be))
* exec review - security & correctness fixes ([303edef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/303edef097eed1f254349838e943fc7ab56414db))
* Frontend tests 100% + major backend test progress ([bcccae9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bcccae94a4bf1cd0e55bd59d570b6651f8d575b9))
* Frontend tests 100% passing (30/30) ✅ ([6c67ebf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6c67ebf211ac59ff762b65b8dac1f11b28a3b8c1))
* Generate alembic migration for automation workflows schema updates ([2a53628](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2a536285cc3f1f7351f26d074bdb0e86df41c8bb))
* global chat UUID issue, audit trail, and permission gating ([d01bf15](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d01bf151167bcabaf2c24f4e121f293b2615ce9a))
* Handle null state value in EmailComposeDialog ([7d6e8dc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7d6e8dca238b2a04ed449dd5aae266778c0565ef))
* harden audit logging and time handling ([165edae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/165edaeeb44d9a59834902fed6647ae821f4e302))
* High-priority bug fixes ([3248f04](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3248f04f79c7d76cecd55f85cbbdab569f61fc15))
* Hydration mismatch with stable IDs for sidebar tooltips ([f609ba3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f609ba365f603e8d5a231f0120367e77ee35db92))
* Implement remaining TODOs per zero-tolerance rule ([7177715](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/717771549c1aedf2934b960ec52c038f99ce80be))
* improve PDF export with light theme and better chart rendering ([ed082a7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ed082a75820a2c4b799c67c6274afc75ee364501))
* increase warmth in dark mode Stone colors, add teal-tinted buttons ([2f1dad9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2f1dad945e0f4f536823e0135491b11ff98ca802))
* invalidate dashboard stats when tasks complete/uncomplete ([f708136](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f708136995084623f9f9b851a8d25be3514aba68))
* Label component to use native label element ([53da609](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/53da6092b84ffffd3672684aeb57e38c2023456a))
* make cases table scroll independently from header/filters ([95d1e3f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/95d1e3f6b9acecc391cdecda7dd2e45336117787))
* **matches:** add actor_name display and remove duplicate activity events ([e4addc2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e4addc273092d8e03c9495971ce704a093aba315))
* **matches:** Address code review gaps ([b2faf0c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b2faf0c61c5596f16bbbdce8132f97d21fb06b3d))
* **matches:** Complete remaining code review gaps ([5feb6ba](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5feb6ba0112ba3a1eecdd5e22ca59da2000152ca))
* Meta Ads Spend integration improvements ([e18d957](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e18d9577b8dabe30078987b52aa5bb085cd2c0e2))
* Migrate react-resizable-panels to v4 API + IP date format fix ([51bf990](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/51bf9908520e6518449975cd41d3312a7c51981a))
* multiple bug fixes and add Age/BMI columns ([16cc5c0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/16cc5c0390680eb3ac0c6e84d7bab9b8216bc801))
* notification multi-tenancy issues ([2ef7ea7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2ef7ea7251344b3a3d0fe6772a5b3f45a057cc20))
* Override d3-color to &gt;=3.1.0 to fix ReDoS vulnerability ([878097f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/878097f3ec7c0a5651935f050dd9c04ebe6e61db))
* Pipeline Phase 2 validation and test fixes ([eaa9766](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/eaa976606a2ea978b6893e966e257f3a5b28c2e8))
* **pipelines:** Fix navigation and order field issues ([cac2f78](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cac2f78075ab41b1c76879d8fe3201784f2f7681))
* **pipelines:** Implement rename/reorder-only mode ([8da32e8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8da32e8f4a538b6a7803e10904aa091ad35fe29a))
* RBAC permissions data flow and safeguards ([9012c88](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9012c882cec8c92a1630636620fd8a211c0fd511))
* **rbac:** enforce developer_only permissions for non-developers ([039abe4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/039abe42637feea3690e1b14db4a28ef06340093))
* Reduce appointments page spacing for tighter layout ([a130e76](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a130e76daa2d0ce5334ba6bd13c710f2dfdf6d93))
* remove all asChild usages from app directory ([2bf6b20](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2bf6b2088a1cc91a963b3d485034bc8db2cb7c18))
* Remove auto-transition approved → pending_handoff ([e8b7f03](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e8b7f03da38749a63cdfe1dd9f643f3def64ecd1))
* Remove Card wrapper from AppointmentsList to eliminate empty space ([e3f3c04](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e3f3c04a38bd6d0b94821601ce20953deb633a6b))
* Remove conflicting Config classes in import router ([699a45e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/699a45eabec0a29c94952c0b6aaee70dc86e3252))
* remove custom ID generation causing hydration mismatch ([a04a297](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a04a297d0ae3e8786f3c034aa5a11642b996f56d))
* Remove empty space above tables and tabs ([7d7b950](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7d7b950b6e7e1181e9912a9ffcd784eeaf36c699))
* Remove index=True from tracking_token (migration handles index) ([3341309](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/33413094a2173e508868d64d04b5155891ea715f))
* Remove outdated auto-transition reference from docstring ([59aabb5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/59aabb5d1ab99c10e50fa8a26fd95760cf5a1b67))
* replace DropdownMenuLabel with div to fix Menu.Group error ([97d31d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/97d31d5782fc4f4f16ecd7edbde6df559c2ce13e))
* Resolve circular FK dependency between cases and meta_leads ([295c049](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/295c04945d9fb42a797ce07aaa21adc276399815))
* resolve workflow, campaign, appointment, and documentation bugs ([c769fb3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c769fb3152c2184385152271d7e8a989a70485ab))
* restore layout.tsx and page.tsx after v0 install ([6bb166f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6bb166f481e39279965d3d7def018d7686670e84))
* Rich Text Editor Scrolling and Preview Match ([ebcc6fa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ebcc6fabaece3a2c22053b4e6d3c10205a65f3df))
* Schema drift - MFA timestamps and tracking_token index ([d039ce0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d039ce0a4b26dcb49cb0d160e3d5370fe573ef2f))
* Security hardening for audit system ([01f61ca](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/01f61caf0aa6998577b4ee35e58a5ce7ae1a392f))
* security issues from FEATURE_GAPS audit ([81628be](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/81628be6f63253d6027c207de3f6f434cd05e17a))
* set case.status on archive/restore ([3bec88b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3bec88bff31474b7e1437504d57fc964f31def2d))
* Sidebar nesting errors (button-in-button, anchor-in-anchor) ([6a268ee](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6a268ee860e53942297af2c97035998313ceb461))
* Simplify test suite to unit tests only ([9ec05ee](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ec05ee24c6431f6a87aa32fa847587db5246b4f))
* Sprint 1 improvements + feat(matches): Add matching system backend ([00577a4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/00577a4f7ed447d49a934fa956f8c540766fad8f))
* stabilize zap baseline scan ([219913c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/219913c8d0bab93722ba7518813620a5c215430e))
* Test fixture handles nested transaction context managers ([4bc154e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4bc154e6b857bfd6971ad43b7f4860c31e22d27c))
* **tests:** Fix compliance test ordering issue ([86ca1ae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/86ca1aefc3a0db807547d7e72d263cd36402ca19))
* TypeScript CI errors - dompurify and implicit any ([3f01cfd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3f01cfdb4123b38c6806285910d53652bc13a786))
* TypeScript error in ai-assistant page for null approval_id ([0218b2f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0218b2fa6190cc69e3f0ded795ff92970b636e93))
* TypeScript errors for build ([163eb05](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/163eb05918d5943e21865b09842cc614700c88ce))
* TypeScript type assertion and migration index drop ([33efd4c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/33efd4cebaa37ded1f2c8c05c8fa9f8318c7679f))
* UI consistency audit + campaign preview bug ([2c84ee8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2c84ee805484d9148ce25f4a615c4d35c4afe50c))
* **ui:** filter override permissions by type and effective perms ([6bd5968](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6bd5968efa0e6a5f4f6636ebc20b77ab9a692ca0))
* **ui:** improve permission dropdown positioning and width ([8e54a2e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8e54a2e20af831bbee7a5e64b966b0da6abc429a))
* Update bundle analyzer to use Turbopack-compatible command ([2fb9846](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2fb98465ae433023d89f330ca594088465a953b4))
* update dark mode theme to Stone base + Teal accent colors ([6ed337a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6ed337a50ffdef67f10d77de76944c566d9e35cf))
* Update test mocks and migration for Pipeline Phase 2 ([763accb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/763accb545e3002a84a035597da748aa193e01e6))
* Update tests to provide stage_id for Case creation (NOT NULL) ([d0bec89](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d0bec894dc849c95774ca83818b52b5d710657d8))
* use defaultOpen for Collapsible to fix controlled/uncontrolled warning ([838e526](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/838e526f2e55442075558291316de6a02b29e6c9))
* use dynamic import for AppSidebar to prevent hydration mismatch ([257143e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/257143e1085a0d38882565850567af86ce058948))
* Use in-memory rate limiter storage in tests to fix CI ([e24ec39](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e24ec39af7ef9c903638a82a5616bc546353218c))
* use render prop instead of asChild for Base UI DialogTrigger ([382a206](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/382a206601d3f9e386fc96e297b214b6bf688c19))
* use sonner toast instead of shadcn use-toast ([7b6ccb7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7b6ccb7a81de38d423cfc18b8e922f494916df85))
* **web:** add auth protection and fix logout POST ([b7da1f0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b7da1f09a0884ae8460b6c64d9a53ba7122f57fa))
* **web:** add min-width to tables for mobile horizontal scroll ([f21d76d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f21d76d0b5eb5f151363e5e53b1754e34c9e16d1))
* **web:** address compatibility issues and type errors ([cab8fc4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cab8fc4e744ecb381c55a3df7aab3565e0c8d8ea))
* WebSocket URL construction for dev environment ([01c8388](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/01c83882718afda8c368417519d9a431707e51d7))
* **web:** update components to use base-ui API patterns ([3a371b0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3a371b03a44b6082c720bafab8e5a205489b90b1))
* **web:** update login page to match soft watercolor design ([61ec57c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/61ec57c6e689df2ca3838e2c6c450c3a7ef3fb61))
* **web:** use Google Inter font instead of missing local Geist fonts ([7ee550c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7ee550c23dbb6f27aeeff5941174bb41a256cc9a))
* **web:** use render prop instead of asChild for base-ui dropdown ([ac9b906](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ac9b906a780ccff69d4cb566efbb51c42f73de30))
* **week10:** Address code review feedback ([a6bb16d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a6bb16db4b5457f8419a9600f284151372da8fbb))
* wire notification settings UI to real API, add org_id to mark_read ([faf6305](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/faf63054bb76b303b17b4e7945c7738c101ab532))
* wire realtime stats and align auth UI ([49d2b41](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/49d2b416f50950578a6d19dc12ff95c4e1830dc7))

## [2026-01-05]

### Added
- **Workflow Approval System** — Human-in-the-loop approvals for workflow actions
  - Approval tasks with 48 business hours timeout (respects US federal holidays)
  - Business hours calculator with timezone support (8am-6pm Mon-Fri)
  - Action preview with sanitized display (no PII exposure)
  - Owner change invalidates pending approvals
  - Approval expiry sweep job for timed-out tasks
  - ApprovalStatusBadge and ApprovalTaskActions frontend components
  - Migration: `h1b2c3d4e5f6_add_workflow_approval_columns.py`
  - 23 new tests in `test_workflow_approvals.py`

- **Email Signature Enhancement** — Organization branding and templates
  - 5 email-safe templates (classic, modern, minimal, professional, creative)
  - Organization-level branding (logo, primary color, company info)
  - User-editable social media links (LinkedIn, Twitter, Instagram)
  - Logo upload with processing (max 200x80px, <50KB)
  - Backend-rendered signature preview
  - Copy-to-clipboard functionality
  - Admin settings UI for signature branding
  - Migration: `0afc5c98c589_signature_enhancement_org_branding_and_.py`

- **Team Performance Report** — Per-user conversion funnel analytics
  - `/analytics/performance-by-user` endpoint with assignment/conversion metrics
  - Tracks assigned, applied, matched, and lost cases per owner
  - Conversion rate calculation with date range filtering
  - Activity mode for alternative metrics view
  - New frontend components: PerformanceByUserChart, TeamPerformanceCard
  - 9 new tests in `test_analytics.py`

- **AI Assistant Analytics Tools** — Dynamic function calling for analytics queries
  - AI can query team performance data on demand
  - Natural language questions about conversion rates and team performance
  - Context injection for global mode analytics

- **Workflow Approval Notification Preference** — Dedicated notification settings
  - `workflow_approvals` toggle in user notification settings
  - `WORKFLOW_APPROVAL_REQUESTED` notification type
  - Migration: `c5f4e3d2b1a0_add_workflow_approval_notification_pref.py`

### Changed
- Dashboard, analytics, and calendar components now exclude workflow approval tasks from regular counts
- Removed jspdf dependency from frontend

---

## [2026-01-04]

### Added
- **Interview Tab** — Interview transcription and AI analysis workflow
  - Interview recording and transcription support
  - AI-powered interview summaries
  - Performance optimizations for interview loading

---

## [2026-01-03]

### Added
- **Contact Attempts Tracking** — Log and track contact attempts with automated reminders
  - Contact attempt logging with method, outcome, and notes
  - Automated contact reminder check job
  - Case reminder index for efficient queries

### Security
- **Security Headers Middleware** — Added X-Content-Type-Options, X-Frame-Options, COOP, CORP headers

### Changed
- Replaced `manager` role with `admin` throughout the codebase

---

## [2025-12-31]

### Added
- **Profile Card Enhancement** — Inline editing, sync, hidden fields, and PDF export
  - Editable profile fields with inline save
  - Profile visibility toggle (hidden fields)
  - PDF export functionality

- **Intake Specialist View Access** — Intake specialists can now view post-approval cases (read-only)

### Fixed
- Added `idx_cases_reminder_check` index to Case model
- Added `useCreateContactAttempt` mock to case-detail tests
- Override d3-color to >=3.1.0 to fix ReDoS vulnerability

---

## [2025-12-29]

### Added
- **Form Builder Backend** — Complete backend flow for dynamic form creation
  - New database models: `Form`, `FormSubmission`, `FormSubmissionToken`, `FormFieldMapping`
  - JSON schema-based form structure with pages and fields
  - Supported field types: text, email, phone, date, number, select, multiselect, radio, checkbox, file, address
  - Field mapping to automatically update Case data upon approval
  - Token-based secure public form submissions linked to cases
  - File upload with size/count/MIME validation, EXIF stripping, virus scan integration
  - Review workflow: Pending Review → Approved/Rejected
  - Audit logging for form submission events
  - New files: `routers/forms.py`, `routers/forms_public.py`, `schemas/forms.py`, `services/form_service.py`
  - Migration: `a9f1c2d3e4b5_add_form_builder_tables.py`
  - 170 new tests in `test_forms.py`

- **Global Search Command** (⌘K / Ctrl+K)
  - New `SearchCommand` component with keyboard shortcut
  - Searches across cases, intended parents, notes
  - Real-time results as you type
  - Navigation to search results on selection
  
- **GCP Cloud Monitoring Integration**
  - Health probes for Kubernetes readiness/liveness
  - Monitoring configuration for GCP deployment

- **OAuth Setup Guide** — Comprehensive documentation for OAuth integrations
  - Google Calendar, Zoom, Meta Lead Ads setup instructions
  - Environment variable configuration
  - Troubleshooting steps

### Changed
- **Team Settings Enhancement**
  - Added Developer role visibility in team member list
  - Improved UI layout for role badges
  
- **Dashboard Simplification**
  - Streamlined dashboard layout (126 lines reduced)
  
### Fixed
- **Rich Text Editor Scrolling** — Fixed scroll behavior in editor component
  - Added proper overflow handling
  - 62 lines of improvements
  
- **Recipient Preview Card** — Fixed overflow issues in campaign preview
  - Better text truncation and layout handling

- **Search Vector Columns** — Added missing GIN indexes to models
  - Case, IntendedParent, EntityNote, Attachment now have proper search_vector columns
  - Fixed search page import path

---

## [2025-12-27] (Evening)

### Added
- **Calendar Push (Two-way Sync Complete)** — Push appointments to Google Calendar
  - Appointments are now created in Google Calendar when approved
  - Reschedules update the Google Calendar event
  - Cancellations delete the Google Calendar event
  - Two-phase commit: appointment saved first, then best-effort sync
  - Uses client timezone for event times (falls back to org/UTC)
  - Handles missing/expired tokens gracefully (logs warning, continues)
  - `calendar_service.py`: Added `timezone_name` parameter
  - `appointment_service.py`: Added `_run_async()` helper, `_sync_to_google_calendar()` helper

- **Advanced Search** — Full-text search across cases, notes, attachments, intended parents
  - PostgreSQL tsvector columns with GIN indexes
  - Auto-update triggers for insert/update
  - HTML tag stripping for notes (via `regexp_replace`)
  - Uses `simple` dictionary (no stemming) for names/emails
  - Backfill for existing rows
  - New files:
    - `alembic/versions/5764ba19b573_add_fulltext_search.py`
    - `services/search_service.py` — `global_search()` function
    - `routers/search.py` — `GET /search` endpoint
  - Features:
    - Org-scoped results
    - Permission-gated (notes require `view_case_notes`, IPs require `view_intended_parents`)
    - Ranked by relevance
    - Snippets via `ts_headline()` with highlights
    - `websearch_to_tsquery()` with `plainto_tsquery()` fallback

## [2025-12-27] (Afternoon)

### Added
- **RBAC Standardization** — Complete refactoring of permission system
  - New `policies.py` with centralized `ResourcePolicy` definitions
  - `PermissionKey` enum for type-safe permission references
  - `require_any_permissions()` and `require_all_permissions()` helpers
  - All 20 routers now use policy-driven dependencies
  - RBAC regression matrix tests (`test_rbac_policies.py`)
  
- **MSW Integration Testing Infrastructure**
  - Mock Service Worker (MSW) for intercepting API calls in tests
  - `tests/mocks/handlers.ts` with data factories
  - `tests/utils/integration-wrapper.tsx` with real QueryClientProvider
  - Separate `vitest.integration.config.ts` for integration tests
  - Example integration test for permissions page
  - New npm scripts: `test:integration`, `test:all`

### Refactored
- **SQL Consolidation** — All router-level SQL moved to service layer
  - New services: `ai_service.py`, `match_service.py`, `queue_service.py`, `membership_service.py`, `meta_page_service.py`
  - Updated services: `analytics_service.py`, `audit_service.py`, `note_service.py`, `task_service.py`, `invite_service.py`, `alert_service.py`, `org_service.py`, `user_service.py`
  - **AI router**: Entity lookups, approvals, conversations, notes/tasks, dashboard counts → `ai_service`
  - **Matches router**: Match queries, events, batch loading → `match_service`
  - **Queues router**: CRUD, claim/release, member management → `queue_service`
  - **All other routers**: Thin HTTP handlers delegating to services
  - Pattern: Routers handle HTTP concerns only; services own all SQL/ORM queries

- **Analytics Service Centralization**
  - Unified `analytics_service.py` now provides shared computation for:
    - `parse_date_range()` — consistent date parsing across endpoints
    - `get_analytics_summary()` — high-level KPIs
    - `get_cases_by_status()` / `get_cases_by_assignee()` — breakdown stats
    - `get_cases_trend()` — time-series data
    - `get_meta_performance()` / `get_meta_spend_summary()` — Meta Lead Ads metrics
  - `analytics.py` router now calls service functions instead of inline queries
  - `admin_export_service.py` uses analytics_service for all analytics data
  - `admin_exports.py` uses analytics_service for date parsing and Meta spend
  - PDF export now uses same computation path as API endpoints

### Changed
- Permission checks shifted from role-based to permission-based approach
- Test expectations updated: unauthenticated requests now return 401

### Test Coverage
- **Frontend Unit**: 80 tests passing
- **Frontend Integration**: 3 tests passing (new)
- **Backend**: 267 tests passing
- **Total**: 350 tests

---

## [2025-12-26] (Evening)

### Added
- **Multi-Factor Authentication (MFA)**
  - TOTP-based 2FA with QR code enrollment
  - 8 single-use recovery codes (hashed storage)
  - Duo Web SDK v4 integration
  - MFA enforcement during login flow
  - `/mfa/complete` endpoint upgrades session after verification
  - Security settings page at `/settings/security`
  
- **Calendar Tasks Integration**
  - UnifiedCalendar now displays tasks with due dates
  - Month/Week/Day views show tasks alongside appointments
  - Task filter support (My Tasks toggle)
  - Color-coded legend for appointments vs tasks
  
- **Intended Parents Date Filtering**
  - `created_after`/`created_before` API parameters
  - Frontend date range picker on IP list page

### Fixed
- **Schema Drift Issues**
  - MFA timestamps now use `DateTime(timezone=True)`
  - `tracking_token` unique index properly defined in model
  - Migration `d70f9ed6bfe6` uses `DROP INDEX IF EXISTS`
  
- **Base UI Button Warnings**
  - Standardized dropdown triggers to use native buttons
  - Replaced Button components with buttonVariants + spans
  - No more "not rendered as native button" warnings
  
- **Match Detail Page**
  - No longer fetches unfiltered tasks while loading
  - Rejection now invalidates match queries
  
- **Task Date Bucketing**
  - Uses local date parsing to avoid timezone skew
  
- **Cases Page**
  - Reset button clears date range filters
  - Shows Reset when date filter is active
  
- **Settings Page**
  - Hydrates org settings + user/org names on load
  - Removed unsupported profile phone field

### Security
- **Server-side HTML Sanitization**
  - Notes sanitized via `note_service.sanitize_html()` (uses nh3)
  - Match notes explicitly sanitized in create/accept/reject/update

### Test Coverage
- **Frontend**: 80 tests passing
- **Backend**: 241 tests passing (0 warnings)

---

## [2025-12-27] (Late Night)

### Added
- **Workflow Editor Validation**
  - Validates required fields before wizard step advancement
  - Checks trigger type, action types, email templates, task titles
  - Resets/hydrates state per edit session
  
- **Reports/Analytics Improvements**
  - Local date formatting for filters
  - Error states for funnel chart, map chart, and PDF export
  - Tooltip now renders zero values correctly
  - Campaign filter shows clearer labeling

### Fixed
- **Match Detail Improvements**
  - Notes use `updated_at` for accurate timestamp ordering
  - Files tab has "Upload File" action button
  - Add Note / Reject Match dialogs reset state on close (overlay/ESC)
  - Prevent IP task queries when ipId is missing
  - Local date parsing for DOB/due dates
  
- **Execution History**
  - Button now routes to `/automation/executions` global page
  - Pagination resets on filter changes
  
- **Email Templates**
  - DOMPurify sanitization for template/signature previews
  
- **Legacy Route Cleanup**
  - Removed `/matches/[id]` in favor of `/intended-parents/matches/[id]`
  
- **Intended Parents List**
  - Added `isError` handling with proper error UI
  
- **SQLAlchemy Test Warning**
  - Fixed "transaction already deassociated" warning in conftest.py

## [2025-12-26]

### Fixed
- **AI Bulk Tasks Permission**: Changed `require_permission("manage_tasks")` → `create_tasks`
  - `manage_tasks` didn't exist in PERMISSION_REGISTRY, causing 403 errors
  
- **Match Event Validation**: Added proper validation for all-day vs timed events
  - `all_day=True` now requires `start_date`
  - `end_date` must be >= `start_date`
  - Timed events require `starts_at`
  - `ends_at` must be >= `starts_at`
  
- **Match Event Date Filtering**: Multi-day all-day events now appear in date range queries
  - Uses overlap logic instead of start_date only
  
- **Campaign Wizard**: Restructured from 4 to 5 steps
  - Step 4: Preview Recipients (summary + RecipientPreviewCard)
  - Step 5: Schedule & Send (schedule options + confirm button)
  
- **Page Height Consistency**: Fixed IP list + Matches page scroll issues
  - Changed `min-h-screen` → `h-full overflow-hidden`
  
- **Campaign Recipient Preview**: Fixed `stage.name` → `stage.label` bug
  - PipelineStage uses `label` attribute, not `name`

### Added
- `test_match_events.py` - Event validation and range overlap tests
- `test_ai_bulk_tasks.py` - Case manager permission check tests
- Frontend templates page tests (4 new tests)

### Test Coverage
- **Frontend**: 78 tests passing
- **Backend**: 147 tests passing
- **Total**: 225 tests

---

## [2025-12-24]

### Added
- Template Marketplace with workflow templates
- Frontend template configuration modal for email action setup
- Campaign wizard improvements

### Fixed
- `send_notification` action kwargs mismatch
- Google Calendar integration field name (`provider` → `integration_type`)
- Cancelled campaigns still executing
- Campaign scheduling for "later" option
- Booking links org_id scoping
- Document upload trigger for intended-parent attachments
- `useDashboardSocket` re-render issue
