# Changelog

All notable changes to this project will be documented in this file.

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
