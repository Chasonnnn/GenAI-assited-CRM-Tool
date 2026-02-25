# Changelog

All notable changes to this project will be documented in this file.

## [0.90.5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.90.4...surrogacy-crm-platform-v0.90.5) (2026-02-25)


### Features

* add important in-app notification settings and routing ([02e83a5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/02e83a58b5ce81205eb058dde2f11563151e9c6c))
* add important notification controls and workflow types ([01a4466](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/01a4466f8932e584820acded81a6410b67c3f261))
* add self effective permissions endpoint for audit visibility ([4e260f8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4e260f86ab2cd7594038b3c419e992011cf495a6))
* add self-service URL samples in email template previews ([a0e0ac9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a0e0ac9a1b4b4e8753194a401b91535bec43b800))
* add semantic audit events for core crm write flows ([40dbd57](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/40dbd57aa5c87694ac1ade10109b3693a56cfdde))
* add unified recipient manage appointment page ([29c021f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/29c021fc66caf0d8bc11c56e6f2db2f6985edc29))
* add unified self-service manage appointment flow ([ac9e716](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ac9e716d2acd4cfcb520c9482c9843c3511e8306))
* **api:** add interview outcomes logging and intake follow access ([886272b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/886272b70e54ba62015f23811706b74e18a3a127))
* expand mock data seeding scenarios and summary output ([b1943dc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b1943dca07b227bf5590a59892cc5491713cf0e3))
* expose appointment self-service template variables ([65a1072](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/65a1072a762cf2af933fee7d8172d2287fce8b05))
* improve workflow execution entity readability ([06d5a2f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/06d5a2f71167c78e5f008a00dca7b0610ff1aab8))
* show bounced email details in surrogate activity ([5a37d45](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5a37d45559945026e4e1d218001e78a02e61f6fb))
* **web:** add interview outcome dialog and activity timeline support ([2365ee9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2365ee922736a4fe971bbf03fcf3b04f07b0e3ef))


### Bug Fixes

* add mutation fallback logging and audit enum consistency ([6b4c5ba](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6b4c5ba161ffe20c1e4aea4109b44ce527b38c7a))
* align platform alert filters with supported enums ([e7a4373](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e7a43735169177ceb92625da4410862203b3cc7a))
* align queued reminder handlers and contact reminder scheduling ([f881c1f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f881c1f63da68ca8bad58c5e0c8b40da359c5c83))
* **api:** drop match compatibility score field ([ba66b56](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ba66b564277dd42b7edbd360ab8c51f95f545fa8))
* enforce fail-closed image sanitization ([42a50e3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/42a50e3a0bb992a7bcc86fdfb8facc182425417e))
* fail closed on malformed resend webhook secrets ([28c76e8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/28c76e83747556240fa3e3791cfaec59191b6727))
* gate surrogate header actions by stage progression ([37afbcb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/37afbcbc9f2a6cf1375cfb74afa1ba0f35d9d01a))
* harden notification websocket polling fallback ([7a290f8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7a290f886e77e662b0f09a19f6f786069f09f786))
* improve inline and upload accessibility behavior ([0cfd01d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0cfd01dc1aee1b0511344912c99fbde141a6a055))
* improve ops error message handling ([21b8aca](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/21b8aca529531461f5034de293ed00153e74a223))
* isolate and harden system alert persistence ([c3ac17c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c3ac17cda8a4d46c5b81b35c39e8ca2abbed1f4d))
* make dev seed idempotent with role-complete users ([031c561](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/031c56110ff97a653e35dc6e103e057eead97b40))
* make reschedule integration tests date-stable ([1926da9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1926da9b07731fb44367de861e7b0c94528642a9))
* pass db to interview modification guard ([20273d8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/20273d870f1e22da0fcaa84a12af32496b6be506))
* persist audit logs in compliance and integration flows ([8e8f5ae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8e8f5aefa2aaae37a9fd3f9ec7d4fa8fa2aaf251))
* reconcile workflow status with resend delivery failures ([4ea78d7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4ea78d74b801a5d0f8f7812cb2249ce1b2fb0826))
* remove extra surrogate last-activity query ([e6789f9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e6789f914ef87c40866f2d8ff0b5487a6eb5c075))
* stabilize search results while typing ([fe91370](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fe913709de1a876ef9b65e9655d5020491d1b855))
* switch compose attachments to drag-and-drop only ([9569ae9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9569ae94ce63f1090a903c8741f327a1a2d6fb68))
* **web:** remove match compatibility UI and client fields ([b35820b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b35820b14b376dad78f0163ac8b13923b97f5613))

## [0.90.4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.90.3...surrogacy-crm-platform-v0.90.4) (2026-02-23)


### Bug Fixes

* add form submission correction actions and manual relink UI ([61b9a7f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/61b9a7fce3e6c36fffda69e1279a77dbade1266e))
* add per-form submission history and approvals shortcut ([d4c6c62](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d4c6c62c83b6554b44baf14092888c69d56cb2ab))
* add submission match retry flow with duplicate-safe lead reuse ([8511d43](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8511d4364b52871a5bef356ea3db394acc3f30b1))
* improve form delivery card layout and add quick share actions ([4196144](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4196144d470c92020f0579aba59ccaf14b6f8b05))
* resolve form-scoped workflow templates by published form name ([af672d6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/af672d645f58e8bef374656816761464449d4b62))
* route form builder back navigation to forms list ([2980c58](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2980c58e1018f96e03659c5573c215d72b8dc3d3))
* seed approval-gated intake auto-match workflow template ([fd9484c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fd9484c2fd4c5566fade4dbc6cedfea9e58b910c))
* seed separate approval-gated intake workflow templates ([e216397](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e216397ad43d3bdf656d56b0ba1a363c77a0ee5a))
* seed surrogate pre-screening questionnaire ops template ([98f0d97](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/98f0d97f192bcd14035bcd427726bb56b79c777b))
* stabilize mobile public form input rendering ([55f520d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/55f520d1a3c79756a76af7ffac2369b0100f0e19))


### Maintenance

* harden terraform storage IAM handling ([e585e1a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e585e1a5340eb4f0c8e015abc08c8d177aa81a90))

## [0.90.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.90.2...surrogacy-crm-platform-v0.90.3) (2026-02-23)


### Features

* open slot picker when drag-rescheduling appointments ([cf9513b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cf9513b0c50aaae4365e99f15fe461a3a77cb8e9))


### Bug Fixes

* return 503 for storage outages and refresh README ([830792b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/830792b7ac267d027fed2f8241f40d9ac6ce37d6))

## [0.90.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.90.1...surrogacy-crm-platform-v0.90.2) (2026-02-23)


### Bug Fixes

* add intake routing actions to workflow builders ([bbd4559](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bbd455998007354a709995456a6c12d08e168093))
* align pre-1.0 release versioning with patch policy ([e868c59](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e868c59ca81a6510314b2e849405e9415b3f06d3))
* break org-form-email template fk cycle in metadata ([d088fd1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d088fd135ace85c025e809ed542941d8002da6e1))
* declare default surrogate application index in org model ([21697a7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/21697a7f1ba8ca6a2901f4d5ae0a0a30795716ce))
* enforce default surrogate application form guardrails ([766ff0e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/766ff0e08332ce073d988816e6e9b1fbb05dcc69))
* include owner context in google meet reschedule failures ([c5eaf41](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c5eaf4131e481fd6b3e96e7e7de30e0cedb286f9))
* prevent stale autosave during form template hydration ([9c084fd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9c084fd1c601fe5b275f0f56f00ac43eede6e086))
* route intake submissions through workflow-driven matching ([6b14f8b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6b14f8b64206fe024a9f3f3f5eb829611dd56543))
* streamline application sharing with auto QR and default sends ([f60e574](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f60e574f994165d1838a1fedc84ab2bc0bec8f1e))

## [0.90.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.90.0...surrogacy-crm-platform-v0.90.1) (2026-02-23)


### Bug Fixes

* gate ticketing UI to developers and harden intake migration ([6a549ef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6a549ef7644fede4d342912d75a42e4dcb3dc2fb))

## [0.90.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.89.0...surrogacy-crm-platform-v0.90.0) (2026-02-23)


### Features

* gmail journal ticketing ([b34d7af](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b34d7afef26216f1425b421e472874a636522c0a))


### Bug Fixes

* enforce surrogate ACL on email contact routes ([8633663](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8633663b8e5d6af6831650643500ec1f7bc0b9d3))
* make mailbox sync idempotency run-scoped ([f700bb8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f700bb8f46650e03f03ddc6bf04550d23444629f))
* resolve duplicate alembic revision 20260222_1700 ([d2693c0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d2693c06a05a69aee9b23c71f282845157508d4a))


### Maintenance

* merge main and resolve db model export conflict ([d65fcb3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d65fcb3a9ce02f6e1b0c02675d8d76d93f1fa74d))

## [0.89.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.88.0...surrogacy-crm-platform-v0.89.0) (2026-02-22)


### Features

* add dual-mode intake schema and migrations ([673a926](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/673a9263cd28e2d66ebd99b8b5f985e9c09b71ff))
* add forms submissions workspace and shared intake page ([ec61dc5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ec61dc5a5a56478dcd65c29f121150152c4a23ce))
* extend forms frontend API for intake links and queues ([263a26b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/263a26bdd7a75d995ea9aac0f9370938bce6ec7a))
* implement dual-mode intake endpoints and matching services ([dd640f3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd640f3ad9de176acd01e19eaeee2cc919fefd29))
* improve dedicated surrogate application send workflow ([bb6ed16](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bb6ed168dff0d16dc00ba0fd3ce98f9d177b1b04))


### Bug Fixes

* Update pypdf to version 6.7.1 to address a CVE and add a test to enforce the minimum security-compliant version. ([b6d41ab](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b6d41ab0c7c9d47baf7d1eb712bc4780bc88d48c))

## [0.88.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.87.0...surrogacy-crm-platform-v0.88.0) (2026-02-21)


### Features

* improve appointment rescheduling workflow and tab defaults ([952b561](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/952b56172f9548e8eba2e739a0e6b9bbb61be9ff))


### Bug Fixes

* add manual google calendar sync with integration diagnostics ([a0088be](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a0088be10da72689ad6e8d798a1854399789cbb2))
* align app and browser notification icons ([4504e41](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4504e412e0a5f6828a60245af71e746bf7c39045))
* coerce unknown task types to safe fallback ([857bba0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/857bba0b83273d04ebeab507d6df0a58fbfa2588))

## [0.87.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.86.1...surrogacy-crm-platform-v0.87.0) (2026-02-21)


### Features

* add combined surrogate export UI and print view ([5cabd3d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5cabd3d37abc88f8671953d0e04a0b0f95691794))
* add combined surrogate packet export backend ([8f6eb6d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8f6eb6d0551b1799fa6ef047507fe75ce1d6439b))


### Bug Fixes

* **api:** allow priority-only surrogate updates without edit permission ([9f75198](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9f751984781166efb38206c1bf53a533d0b89889))
* **api:** normalize bmi calculations and expose contact note previews ([8fbcac0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8fbcac01efa0edf2bd9137225af123e3ab7c05fe))
* **api:** sync outbound surrogate email activity and audit logging ([f8bc247](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f8bc24763d74a2d866bb5d55032f60a8ea1f5a1e))
* restore immediate Google sync in async workers ([9e71228](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9e712289fd8845c18a50ae51c12cf4614ba5e74e))
* upgrade pypdf to 6.6.2 for security vulnerabilities ([f4a789d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f4a789dd71391a89d4f89b002ef65f1740a55e85))
* **web:** resolve sidebar, template editor, and activity preview regressions ([0e2b47e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0e2b47e84e53ec656247d8ec67634316b27a5cc2))


### Maintenance

* **api:** apply ruff formatting drift fixes ([fdb34a6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fdb34a6bf94e63354bcd60d0867275274192c584))

## [0.86.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.86.0...surrogacy-crm-platform-v0.86.1) (2026-02-20)


### Bug Fixes

* add google tasks access diagnostics and assigned task sync ([39bb57f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/39bb57fa79d79416d3edbd51e2db0e8d3a90cde9))

## [0.86.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.85.3...surrogacy-crm-platform-v0.86.0) (2026-02-20)


### Features

* **api:** add surrogate send attachment validation and provider routing ([a97862d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a97862d80327ed1dae619e04f24ab48b80d780d6))
* **api:** persist and deliver email attachments across providers ([4430a67](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4430a67165063036af0b09640655e9d67ef8c627))
* **web:** add drag-drop compose attachments with send gating ([539cd59](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/539cd592a64c02a648b6af816a5d404b925e1efe))


### Bug Fixes

* add source-level regression guards for hook fixes ([c37df08](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c37df08e948b2ce2fd8cc984e8136234087e804e))
* always use personal signature in surrogate email send and preview ([85d3dd5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/85d3dd57a4536254c698a6c1edcc804e0afa3f9e))
* auto-refresh Google calendar events in tasks view ([1c89ba8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1c89ba8c0f5f3ca1b5a444f3a5ddd1206578996e))
* default blank Google event titles to no-title fallback ([dffa333](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dffa333181df0035505f485901a4c99bb7572cdb))
* enforce strict provider policy for surrogate and campaign sends ([9969f99](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9969f99c807af0f00c66cbca09f4eaab465d4410))
* enforce strict provider rules for surrogate and org email flows ([bcbe4be](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bcbe4beef85df0524c5176b320d70e528f77df0c))
* guard ops agencies effects against stale async updates ([f10ab2f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f10ab2f36e30e6a075cd0730a2be1d03b5f471d2))
* harden keyboard interactions for clickable surfaces ([ccd3a32](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ccd3a32dfc2a7c392708a42eece33fa72eaddbb5))
* harden mass-edit defaults and import state handling ([70f78ae](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/70f78aeaf0f75a410dcee92e32a0fb278add4d1e))
* hide terminal pregnancy tracker and show real status transition ([a655a50](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a655a50423b26f5d802f79cb54bc620bb5a3bf4e))
* hoist team report sort icon component ([304ca64](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/304ca643d7e48b3ea59ad4eafd327af36c366b70))
* implement google tasks two-way task sync ([dbd1a1e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dbd1a1e380e84429287161bbe554eb8f41f477bd))
* modernize global font and navigation semantics ([a73164c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a73164ce82f529e6b75ac2626dd6cea84a6d603a))
* move apply token parsing to server page wrapper ([1403a15](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1403a15d397bb16e605ccbcd36cf1e95191f970b))
* preserve aria radio semantics in apply options ([e959fcf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e959fcfe46ac11418e2080c6d217e0d3caa75055))
* reduce expensive backdrop blur on auth pages ([76127d5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/76127d5f2aceb3c0a53e439c456c1f23e859fa09))
* remove autofocus and stale state update patterns ([13fa8fa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/13fa8fafc8e7c3cd8950cd509cc2bf9488fb529e))
* remove effect-driven derived state in web flows ([c482183](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c482183c50af9325a1f97df4aa221456ce159346))
* replace unstable index keys in dynamic ui lists ([008659e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/008659ea4ad1efa99bd1e0452066120cf841562f))
* split public application page for metadata and suspense ([580142a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/580142afb70577a153271d9e6f1ac7f780e4a533))
* stabilize default array props in scheduling and surrogate tabs ([28acb93](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/28acb93b5b6171fe067fe303284412ae271dc833))
* stabilize publish dialog defaults and label wiring ([c62e8ee](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c62e8ee5ba22a21bd8ae6d749b77f58bbc623fae))
* stabilize workflow builder row keys ([5de592b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5de592beaa6df78cd28891561b4a369c3c1c0b91))
* tighten automation wizard labels and stable keys ([9b742e3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9b742e31992aa917a5846cab3c298603c959e4fb))
* tighten label associations in scheduling and campaign forms ([7caa1c0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7caa1c037be2a56ae05961b926a0a897ce4d14ac))
* use semantic interactive elements for click targets ([099c901](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/099c901a265b4998485bf37d611c0093e26e2ed3))

## [0.85.3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.85.2...surrogacy-crm-platform-v0.85.3) (2026-02-19)


### Bug Fixes

* add appointment link email template variable ([baba14a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/baba14a3dd76176b869498b543a9aab564c36034))
* add missing surrogate template variables test mock ([3f5aaf7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3f5aaf76a6d5f5ce6a916ab10ead7945c38b3585))
* add surrogate template variable preview endpoint ([b1eba5c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b1eba5c9a8a71e7bf3864e0fb2d93cbc6249cc5c))
* **api:** allow admin and developer edits for personal templates ([464d3d9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/464d3d92761ab1829d90e6aaedf20b081cbbfb85))
* correct email editor form label associations ([2f4aca1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2f4aca17840aba309f9ec6550273f81927d691c4))
* enable email customization directly in preview mode ([558f26a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/558f26a1ad1bd015ee3415fe1c825d9f0438ba82))
* keep booking links stable without regeneration ([8e59021](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8e5902117c29263de7105dc547b90bd89e016312))
* render resolved template values in email preview ([9ef961e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ef961e9e7d5905b5dcb8ceec26846047c0180ec))
* reuse active form submission tokens for surrogates ([15b45ef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/15b45ef449e6277837931ac83470f79fa1697a84))
* sync Google Calendar events across visible calendars ([7a1c741](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7a1c74148b688cd5724fb4249195d3536d57e85f))
* update preview samples and booking link settings UI ([2e02742](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2e02742bb87f6ca4eb6fcbc06dc0d451c794ede2))
* URL-encode Google Calendar IDs in event API paths ([9916db6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9916db62b7b697567090deee6cecf7889db5aba4))
* **web:** allow privileged editing and hide inactive email templates ([2f9b807](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2f9b80718d0a627c985fd247370de33e9814fc4a))

## [0.85.2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.85.1...surrogacy-crm-platform-v0.85.2) (2026-02-19)


### Bug Fixes

* add google calendar push-channel watch lifecycle ([c4dd6fa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c4dd6fad639c3d9fa4c1188fd784af9d21f08b3d))
* add google calendar sync and watch test coverage ([8d42e4b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8d42e4b6a4305a413684b4ecd46e76b560ef19f0))
* align google calendar watch index with model metadata ([f86e409](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f86e4099a1172595f4c0bdddf2968e9573c4e4e8))
* move google calendar model access out of routers ([80c9831](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/80c983176ea0b141ac1367c8697799c08e37fa17))
* reconcile google calendar events into appointments ([2d8f4a2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2d8f4a27b0e38074a52e0b4dc4bd3bfc4602cbbc))
* schedule google calendar sync and watch refresh jobs ([b4fc20b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b4fc20be2ac9373bce82aa32acd94b95ac2df5e2))
* trigger ci on latest main ([c1e552f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c1e552f447e9742391fb14192752b5decb2f0484))
* **web:** add type annotation to resolveTemplateLabel callback in EmailComposeDialog ([16f2f67](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/16f2f67cf4ddaf260aba7c9e428f7d663349e576))
* **web:** default email compose to preview mode and fix template hydration ([b89c738](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b89c7381cec698e2efd2576ca369e7e2d4f182dd))

## [0.85.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.85.0...surrogacy-crm-platform-v0.85.1) (2026-02-19)


### Bug Fixes

* **api:** add unit tests for meta lead monitoring organization scoping ([205bc25](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/205bc259d23712b10ad10f1ace55c371d7e7e8d4))
* **api:** enforce organization scoping for meta lead monitoring and dev endpoints ([2679573](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/26795737113cf9224ca6cb446a5678d77bd449d5))
* **ci:** implement retry logic for pnpm audit to handle transient registry errors ([c689107](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c689107dcbb1a7e989871fb376eb65342be79384))
* resolve email templates preview/test loop and stabilize tests ([b3afb90](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b3afb90919c634927a1c180c3343e7536e5de645))
* **tests:** add edge case coverage for integer-only height formatting ([841c6bc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/841c6bc782dd9c851eccf73866d1f3f162834765))
* **web:** add unit tests for signature preview in email templates page ([80b33dd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/80b33dd4ccf3395b0c089ad1693ac465e66a730c))
* **web:** display active signature type in email template preview ([722412a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/722412a98978f227b386290fdeb9f8227080052f))
* **web:** handle string-serialized decimals in height formatting and restore assignee submenu ([438eaf0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/438eaf0a0d8849b3084237deecdf886acbfcf453))
* **web:** improve template name resolution and signature preview in email composer ([f091812](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f091812feffe8ff06d5125d07ba56f3a97371a0f))

## [Unreleased]

### Bug Fixes

* **api:** enforce organization scoping for meta lead monitoring and dev endpoints ([2679573](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/26795737))
* **api:** add unit tests for meta lead monitoring organization scoping ([205bc25](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/205bc259))
* **ci:** implement retry logic for pnpm audit to handle transient registry errors ([c689107](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c689107d))
* **tests:** add edge case coverage for integer-only height formatting ([841c6bc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/841c6bc7))
* **web:** handle string-serialized decimals in height formatting and restore assignee submenu ([438eaf0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/438eaf0a))

## [0.85.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.84.0...surrogacy-crm-platform-v0.85.0) (2026-02-19)


### Features

* **api,web:** allow case managers to manage lost and disqualified stages ([0b50fa1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0b50fa176432b471933b660519a14b4e6666d82b))
* **api:** implement flexible height parsing (feet.inches shorthand) ([dd28910](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dd28910b7278a47bc6d6db32b9ad1002c279c41e))
* **web:** improve height formatting and display in surrogate profiles and IP matches ([0362cc7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0362cc735bf8553f0254a3e770d1e79d20f3c55b))


### Bug Fixes

* **api:** secure pipeline management endpoints with MANAGE_PIPELINES dependency ([f49177a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f49177a8d616378c9efbfcb03167428138475db2))

## [0.84.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.83.0...surrogacy-crm-platform-v0.84.0) (2026-02-19)


### Features

* **api:** grant manage_appointments permission to intake specialists ([311f16c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/311f16c9336a9f09dc1d022b4f47a00aa08089e4))
* improve email emoji rendering with native font stack and enable editor emoji picker ([27e3026](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/27e3026f0c9fc9f66fdcacc8c1c8022997ffd71d))
* **web:** add emoji picker support to rich text editor and surrogate notes ([3501d94](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3501d945a1c2454ce8b61ee3550560e2e90bbe15))


### Bug Fixes

* **web:** use timezone-aware date keys in public booking calendar ([ad2cf4a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ad2cf4a9fe50508f4a1b2e2d2007afe1294bebd7))

## [0.83.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.82.0...surrogacy-crm-platform-v0.83.0) (2026-02-18)


### Features

* **api:** expand AI assistant access to intake specialists and case managers ([3376fe4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3376fe4bd853d08ea3050632c5c237300a5a5174))

## [0.82.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.81.0...surrogacy-crm-platform-v0.82.0) (2026-02-18)


### Features

* implement RBAC for integrations and team settings, update invite resend logic ([1194f9e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/1194f9ef51b1621d07395ed89d89e7985ab29ef0))


### Maintenance

* **web:** override minimatch to 10.2.1 for security compliance ([0678f9d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0678f9d4488a427125976f1130c69cb3a6d71c65))

## [0.81.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.80.0...surrogacy-crm-platform-v0.81.0) (2026-02-18)


### Features

* **ops:** refine support session dialog and add tests ([68b86e3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/68b86e3392cae0dc2305a28bc258cff0a18275d5))

## [0.80.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.79.0...surrogacy-crm-platform-v0.80.0) (2026-02-18)


### Features

* enhance attachment handling with content-type preservation and error surfacing ([d0b1b87](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d0b1b87742185e9f793c6b42320186d91b90cdec))
* enhance support sessions with environment checks and safety guards ([7617ebf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7617ebfe84b2546287253f2de059b03b2ae724ce))


### Maintenance

* improve accessibility and UI robustness of frontend components ([6cfd5ab](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6cfd5abccf878df3276e0d83314fc02383114324))

## [0.79.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.78.1...surrogacy-crm-platform-v0.79.0) (2026-02-13)


### Features

* allow orgs to hide published form templates from their library ([7d11cd8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7d11cd81548196a51e72c7a697d1f6278505310a))


### Bug Fixes

* reuse expired invite rows instead of creating duplicates ([a96202f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a96202f67a09a95a6c89d375ecb3f60bb27057d2))


### Maintenance

* add ruff 0.15.1 to test dependencies ([e10d5f8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e10d5f83fc426a836eb9da5ea95c4b6d08cbb6b5))

## [0.78.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.78.0...surrogacy-crm-platform-v0.78.1) (2026-02-11)


### Bug Fixes

* **migration:** add fallback when base form template row is missing ([2bb531b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2bb531bf6e28f79adf54a97c4f50f5203dec0bd7))

## [0.78.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.77.0...surrogacy-crm-platform-v0.78.0) (2026-02-11)


### Features

* **normalization:** add race key normalization utilities with alias support ([519911c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/519911c3ee20f9f0f4898ebaa2ff9cfb672e3b8b))
* **web:** update race label overrides and mass edit helper text ([a8bbac8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a8bbac8330987f4818ce15b419ff3762cb6ba4c1))


### Bug Fixes

* **deps:** bump cryptography 46.0.4 -&gt; 46.0.5 (CVE-2026-26007) ([9ea1164](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9ea1164bd747a51fd8086b68cde1bb52b4fee30a))

## [0.77.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.76.0...surrogacy-crm-platform-v0.77.0) (2026-02-09)


### Features

* **platform:** Add template delete functionality and improve listing ([ec6ba6a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ec6ba6aeabd27e1bc0acb99452ae4b2257c32250))


### Maintenance

* **db:** Add migration for surrogate full application form template ([3350ec0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3350ec05ca6cdc328c1a845df46195b59c4a04d7))

## [0.76.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.75.0...surrogacy-crm-platform-v0.76.0) (2026-02-09)


### Features

* Implement mass edit stage functionality for surrogates ([99ab76f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/99ab76f06dde1f2f78b3b8bfe5e098de7667b01a))

## [0.75.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.74.1...surrogacy-crm-platform-v0.75.0) (2026-02-08)


### Features

* improve accessibility of AI Chat Panel buttons ([b035969](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b03596903bf58db61d7fec452a09a56a2a582beb))


### Bug Fixes

* **a11y:** improve task calendar keyboard accessibility ([e247847](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e247847e0722ca7ded304d555b3d05a760c6af8d))
* **perf:** reduce DB queries in dashboard stats endpoints ([2ad67f6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2ad67f68907083d593ffbbc6d2158202864ee47b))
* **security:** add HTTP security headers to Next.js responses ([964b464](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/964b46487f8f02de188c0839695b5fca27cad73a))
* **security:** add size and row limits for CSV import ([a406414](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a40641472395b83af3189b6b55c14d87def63311))
* **security:** use constant-time comparison for shared secrets ([02ffda9](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/02ffda9b94c46c2f8b704abdefd8897af63dd9b9))
* **ui:** add Applications filter to notifications page ([afb0b66](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/afb0b66a8ec7c00bd40696711040bee136668771))
* **workflows:** add form_submitted trigger for application submissions ([0b9c360](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0b9c360b1c263fd909b95968a19697b1687b5d80))

## [0.74.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.74.0...surrogacy-crm-platform-v0.74.1) (2026-02-07)


### Bug Fixes

* **ci:** use longer JWT_SECRET to suppress PyJWT warning ([ea461fc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ea461fcc8c22f6241f5aab1663acdbb214398378))
* **forms:** add form deletion with confirmation dialog ([ae19781](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ae197815a3477ccb92e67bae17679288a4dcf6c2))
* **release:** use always-bump-minor versioning strategy ([8d767b2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8d767b2c115b996d4e5bd2d106e5f2d9edb8487b))
* **ui:** temporarily hide Unassigned Queue from sidebar ([aa48ef6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aa48ef6caa2d3103f7b4d4e0b521441d705a5330))
* **workflows:** add retry button for failed workflow executions ([9e08ed0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/9e08ed0727ac6438606196310c20aef3466251dc))
* **workflows:** extract get_execution helper to workflow_service ([affaf11](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/affaf11fda6351093605b7473b1fab7528f1524b))

## [0.74.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.73.0...surrogacy-crm-platform-v0.74.0) (2026-02-07)


### Features

* add server-side form draft autosave ([55bfe8b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/55bfe8b23af9997658e72011e3a2ffde3c7b61d5))
* **ops:** add Support Session dialog for role impersonation ([e9ab727](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e9ab7271cf1ab0b80295c2943092aa154009d36d))
* **workflows:** add form_started trigger and email recipient options ([dc0c562](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/dc0c562ed8de11aedcb4480b84f09da98f741236))
* **workflows:** implement email recipient resolution in action execution ([19d7511](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/19d7511f5c12f9fcdb629dfbf35d28a92003d9a5))


### Bug Fixes

* improve notification delivery and unassigned queue access ([f7eac14](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f7eac14d56aefe2fdcda6d176ebab31afebb31bf))

## [0.73.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.72.0...surrogacy-crm-platform-v0.73.0) (2026-02-06)


### Features

* add Unassigned Queue for intake specialists ([c06055b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c06055b9f6d8b2489992ab9dde7b784d50c26910))
* **api:** add presentation utility for humanizing identifiers ([6e266c1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6e266c170f5f71c7d462599df410eb66db0aab27))
* **email:** add option to ignore opt-out for test emails ([c601942](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c601942c6ae5fab4cd21f5730e932b859a630794))


### Bug Fixes

* **api:** make utils package import-safe for tooling scripts ([4c3993d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4c3993d4d1ef811e892a61b702850dc885886f9b))
* **email:** improve invite email role formatting ([2e89bbc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2e89bbce2bd429fcf04f7784ef54e04fca199356))
* use humanize_identifier for consistent label formatting ([3dbaac6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3dbaac6f8db087b833ba402ae8063bb01ff79b77))
* **web:** improve email template UI and test cases ([4d4bc7e](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4d4bc7e2007d6f29c5204b40697d533e37011909))


### Maintenance

* minor fixes and improvements ([6d05dfd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6d05dfd5e5b3d2e6fa75c2d4c1f84e1f0f64c3b1))

## [0.72.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.71.0...surrogacy-crm-platform-v0.72.0) (2026-02-06)


### Features

* **campaigns:** add include_unsubscribed option to campaigns ([b46668a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b46668a7b465716b1cf0040d5336b95c2e343160))
* **campaigns:** update models and routers for include_unsubscribed ([2127bd3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2127bd3a791e2c64c44258fecaa7f442abf27152))
* **email:** implement one-click unsubscribe and improve signature rendering ([b0c87f6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b0c87f6f56c148cf1c560ae2dc257a58fb43e3d4))


### Bug Fixes

* **email:** improve template variable resolution and unsubscribe URL building ([0c42022](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/0c42022882f7ecf27187522cc50056c067e0e610))
* **email:** wrap email body with consistent typography ([a2f957d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a2f957d7f7a3437ac7b49815300e29bc3058cfd9))

## [0.71.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.70.0...surrogacy-crm-platform-v0.71.0) (2026-02-06)


### Features

* improve accessibility of Surrogates page ([07c4ebf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/07c4ebf58a9049e5759b12a8cd1ea214b3d0660a))


### Bug Fixes

* email background processing, formatting, and test environment stability ([e2258d8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e2258d8e25b8641d397372c52744bf99b6b55567))

## [0.70.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.69.0...surrogacy-crm-platform-v0.70.0) (2026-02-06)


### Features

* **email:** enhance signature rendering, Gmail error handling, and variable catalog ([66c4e61](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/66c4e61bcb2cd83b4aec06d9b52fc24c00847039))
* **email:** improve template scoping, permissions, and workflow selection ([d93681c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d93681cced2f17db8f0562e77babd2542a5baa04))
* **platform:** refactor system template management to service layer ([79b18cd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/79b18cd547254558cc77bdae42ed4d0d7674eac5))
* **platform:** support custom system templates and implement safety filters ([57731cb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/57731cbf6479026624914b0162d21454201c201c))

## [0.69.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.68.0...surrogacy-crm-platform-v0.69.0) (2026-02-06)


### Features

* **a11y:** add aria-labels to file upload buttons ([3c02a66](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3c02a66fdb887d835bb1a04081b5a819c5e49576))
* **email:** add template variable catalog and frontend picker component ([bf89d5c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bf89d5c1fabb7d191aa5ac7af9fefe1f2b273705))
* **email:** implement test send feature for email templates ([2336b08](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2336b08b866836df4d04494334b40d2177074d9e))
* **email:** implement test send service and template HTML rendering ([3254b41](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3254b41cf884e9522651cd2c223feaded954d4a7))
* **platform:** implement test send for platform templates ([368355a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/368355a16ad70749c514a81fb6514fa916cf7e65))
* **web:** add accessible name to surrogate actions menu ([c46858b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c46858b084e9f4da0f341a6cf48913e5375f7a71))


### Bug Fixes

* **platform:** organization slug update and audit logging for test sends ([611d53f](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/611d53f83d073e120af84743a80a124d6f664abc))
* surrogates-optional-totals ([d93e456](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d93e456d0a9693b602663e04eb0c4eb54062b73b))

## [0.68.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.67.0...surrogacy-crm-platform-v0.68.0) (2026-02-02)


### Features

* **templates:** add jotform application template and improve form builder versioning ([b3bf815](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b3bf8159e22133e2dd59c411b2807deabf723e6a))


### Bug Fixes

* **db:** reassign orphaned surrogates to unassigned queue ([5d190d4](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5d190d443f9d2984a557d47dcfb69830af13136c))
* **web:** improve dashboard trend chart stability and lookback windows ([4e6c297](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4e6c297f8bc353584b42c1437b0cd86a04f8efec))

## [0.67.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.66.0...surrogacy-crm-platform-v0.67.0) (2026-02-02)


### Features

* **api:** improve platform logo upload robustness with error handling ([bfd866b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/bfd866bf7c38f3d0dc9f0dcb0a8703b7b799c3ac))
* **web:** improve form builder versioning and apply page navigation UI ([e81e142](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e81e142c1fa78297dbdd061a4a9a761c4ec356df))


### Maintenance

* **web:** remove unused tiptap underline extension from editors ([3c707de](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3c707de47920475924aae2d8f6121d5c54b6e8b9))

## [0.66.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.65.0...surrogacy-crm-platform-v0.66.0) (2026-02-02)


### Features

* Add Content Security Policy & Security Headers ([ffd8986](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ffd89869b437f9df18f2ca367b5444f2daa93087))
* **ops:** enhance platform template management and form application flow ([cc3bcc6](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cc3bcc653cd39b499fd5210522c0fc44ac00ccf3))
* **platform:** implement platform branding logo upload and management ([d610aff](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d610affea0463ef069de6520888bff0b7637d428))
* **templates:** add jotform-based surrogate intake platform form template ([736b0d8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/736b0d81f4ae740db1942d19fe0bdb55f983f625))
* **ui:** improve notification bell accessibility and styling ([3390613](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/33906135d8e57b88968c89a200fe5755b87d4538))


### Bug Fixes

* replace favicon ([6ba04c1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6ba04c1365fbc6f3f09c253bbcd9690be74167f8))

## [0.65.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.64.0...surrogacy-crm-platform-v0.65.0) (2026-02-02)


### Features

* **api:** enhance admin import/export services for better data portability ([02afc3c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/02afc3cb8c20a2a6500adf89a83c1fcc937630d8))
* **appointments:** refine meeting mode logic and hash-based idempotency ([a53cdb3](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/a53cdb39f19c3bd967648e0965a201d9dcb2a396))
* support multiple meeting modes for appointment types and extend idempotency key length ([828104c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/828104c07a9bc1dcaceb1ac7bef56a0dc451513d))

## [0.64.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.63.0...surrogacy-crm-platform-v0.64.0) (2026-02-02)


### Features

* **api:** add platform branding service for global assets ([3ce609b](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3ce609be8f00aad85f79c8a7276e2b3c68bad515))
* implement platform-wide system email templates ([226345a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/226345a0613e0a5dbe47f390e9ea4889d77fb669))
* migrate organization invites to use platform system templates ([8953cf8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8953cf811df332a20a0ed5106ce55f7fadc9478a))
* **ops:** add system email template management dashboard ([327411d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/327411d4846fb2d001270afd51354d0bc8158ba2))
* **web:** add insert logo button to email template editor ([4960168](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4960168ba8292f9f5715f193f4ad031e4866f879))


### Maintenance

* minor ui enhancements and code formatting ([987ba62](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/987ba625186f276bfd14de4afe3056012803aa16))

## [0.63.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.62.0...surrogacy-crm-platform-v0.63.0) (2026-02-02)


### Features

* support organization logos in email templates ([366afcd](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/366afcdb1dbd8d3bafe39f50940f0425ec51e736))

## [0.62.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.61.0...surrogacy-crm-platform-v0.62.0) (2026-02-02)


### Features

* **import:** expose deduplication breakdown in surrogate import history ([aab00e7](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/aab00e757165e61fab9202306d4fde12215be1bf))


### Bug Fixes

* **web:** improve trend chart date labels and Zapier dialog layout ([eb9994a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/eb9994a16ee2d1e3a83abf3dbb1c53ba8e3718f8))


### Maintenance

* **docs:** formalize TDD and bug reproduction rules ([8e16f1a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8e16f1ace782b62ea319a2813f9a9196a12df9a4))

## [0.61.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.60.1...surrogacy-crm-platform-v0.61.0) (2026-02-01)


### Features

* **email:** implement hybrid template editor and expand branding variables ([4bc22bc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/4bc22bc197f06ed8bd276e55f7accd4b222f4111))
* **web:** enhance rich text editor with alignment and underline support ([d06fdef](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d06fdef2f10853a3a14feca7c3b3899a8d13368f))


### Bug Fixes

* **api:** allow OAuth callback host validation on API domain ([c2f6970](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c2f6970c9266e27f6720cde50ee3515efc169e03))
* seed workflow templates with ids ([ba9ac1d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ba9ac1d60bba091391811e88e1861d3780990390))
* **web/ops:** stabilize organization context and template studio loading ([ef8943c](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/ef8943c4fa82b9d744c98f2dbd9df65e46d81fed))

## [0.60.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.60.0...surrogacy-crm-platform-v0.60.1) (2026-02-01)


### Bug Fixes

* invites now ignore past memberhsip ([022cb73](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/022cb737a20ecf4f31d2ba7c3193f479ec9ee199))

## [0.60.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.59.1...surrogacy-crm-platform-v0.60.0) (2026-02-01)


### Features

* **email:** release premium organization invite design (v2) ([3f6d667](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/3f6d667c96266b741ce292b2675543e3c9313236))
* **ops:** implement invite resending for platform admins ([2aea8fb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/2aea8fbb594653ececf1ec0a437f6e0c65174d80))


### Bug Fixes

* **auth:** auto-accept pending invites for existing users during login ([f3c56dc](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/f3c56dcf43d163c8edf1be6665da1688ff85690a))

## [0.59.1](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.59.0...surrogacy-crm-platform-v0.59.1) (2026-02-01)


### Bug Fixes

* **web:** allow MFA route initialization on platform ops subdomain ([6ec8544](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/6ec854413f7dd08678acbaac0c53e2d7d14db8cc))

## [0.59.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.58.0...surrogacy-crm-platform-v0.59.0) (2026-02-01)


### Features

* **api:** implement mfa fallback for platform admins on ops portal ([de68e65](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/de68e659db9d2c7a18838cfe14380e6d69e3a37c))

## [0.58.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.57.0...surrogacy-crm-platform-v0.58.0) (2026-02-01)


### Features

* **api/web:** add platform template management API and hooks ([d1c214d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d1c214d3082d0adbd57c25dd4a78a5107229dca9))
* **api/web:** integrate template library for organizations ([c36221a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/c36221a2419a779e1c80528a395cd763f0c33b38))
* **api:** enhance attachment storage and validation ([68749d8](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/68749d8d41699d74e7e808b66226173e989728d6))
* **api:** implement platform template studio database schema ([64d933a](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/64d933ad9089e880c6ce55d5cac9b4a62b12afc2))
* **web/ops:** implement platform template studio UI ([be9e8f0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/be9e8f0fc30918ee64f64aec0852a91030a8ea90))


### Bug Fixes

* **web/ops:** refine organization management and deletion flows ([80a4092](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/80a40924a3bbf6863a4715a596c1eef5baf05658))


### Maintenance

* **api/web:** core infrastructure and CORS refinements ([01aed2d](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/01aed2d261e7c519292924d429ffb9ff6e8104f0))

## [0.57.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.56.0...surrogacy-crm-platform-v0.57.0) (2026-02-01)


### Features

* **platform:** implement immediate organization deletion and ops route auth optimization ([da064f5](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/da064f59fb6d254caa83940571ca8c5f2839bafd))

## [0.56.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.55.0...surrogacy-crm-platform-v0.56.0) (2026-02-01)


### Features

* **email:** update organization invite template with premium design ([95c17eb](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/95c17ebe2c781b7a743faae083f344bdc58079ea))
* **forms:** implement platform-level form templates ([b83d3af](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/b83d3afe15251859619ddc2d4305ebaf7674d003))
* **import:** enhance column detection for C-section and Meta leads ([5de7eed](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/5de7eedbfe9f5d94913b0ecc019ae9e245927386))
* **integrations:** modernize Meta and Zapier settings with metrics ([9338218](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/93382181d67f246cf5068ef6f22ae3e5f3adc7ce))
* **surrogates:** refine application intake UI for single-form orgs ([8dfd757](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8dfd7575bb8eb4ee0aa347e3f5b0c8a20d183d3f))

## [0.55.0](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/compare/surrogacy-crm-platform-v0.54.0...surrogacy-crm-platform-v0.55.0) (2026-02-01)


### Features

* **meta:** implement Meta form deletion ([84b69e2](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/84b69e27618411f9feda59e825d09c0a5b32cf03))
* **web/ai:** enable global chat and ephemeral history in AI Assistant ([d8fc620](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/d8fc62035415c6f6e2351867b2ac97aaef415593))
* **zapier:** enhance inbound webhook management and field extraction ([e21f192](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/e21f192f1b92d38647bfd95b12fc4eabef20df42))


### Bug Fixes

* **api/tests:** ensure JWT_SECRET is set in test environment to satisfy production safeguards ([8c81a38](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/8c81a389c64985cfc5c740195ebe9feebdc9dc3f))
* **web/ai:** refine chat history persistence and state initialization ([7a6a537](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7a6a5378d8652cdfbd9c80c8df71d44971440909))
* **web/forms:** improve field property synchronization in form builder ([fdf3850](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/fdf3850c0d491c9296cdbe1c01b72d629fb261e8))
* **web/integrations:** stabilize AlertDialog rendering and webhook selection ([48c3c10](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/48c3c1093e22201705f94961508746d164507688))
* **web:** accessibility and test refinements ([7224035](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/7224035bab3b8955cb5d8a3d5c9af21323e68cbe))


### Maintenance

* **api:** refine app versioning and RELEASE_PLEASE support ([40b8eaa](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/40b8eaab6c7d4e35c9528dc9d84bb59ee1d4d7af))
* **api:** update fallback app version to 0.54.0 ([cba13cf](https://github.com/Chasonnnn/GenAI-assited-CRM-Tool/commit/cba13cf8114c92aa4e42490a3c89d330bde872d3))

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
