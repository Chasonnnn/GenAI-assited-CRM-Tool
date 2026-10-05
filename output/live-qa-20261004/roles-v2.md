# V2 permission browser comparison

Revision `65bca746e`; 2026-10-04. Separate disposable organization `db116dd1-242f-4e24-9b27-ecf3a7a6aeff`. Four new synthetic users have unmodified Admin, Case Manager, Intake Specialist, and Operations role defaults.

Activation used the normal `permission_policy_service.preview` and `activate` functions with the reviewed digest. Preview was ready with no unresolved scope/execution decisions. Activation committed policy version 2 and its audit record. The primary QA organization remains version 1.

| Check | Version1 result | Version2 result |
| --- | --- | --- |
| Case manager creates surrogate through UI | Created then detail 403 | Same defect: created then detail 403; `d0991d4f-73c6-40ab-9955-9c2fa4c6d194` |
| Operations Dashboard | Permission-driven card load failures | Loads normal zero/empty states without permission errors |
| Operations Surrogates | Permission required | All 3 synthetic records visible; New surrogate absent; row menu contains View Details only |
| Operations Reports | Permission required | Report data loads:3 surrogates, stage/distribution charts and individual performance table |
| Operations Tasks list | Permission required | Empty task list loads |
| Operations Add task | Form submits then 403 `view_tasks` | Form submits then 403 `create_tasks`; same missing creation-control gating |
| Operations Appointments | Permission required plus booking-link Retry | Same mixed permission/load error state |
| Operations Form Builder | No access | No access; Form Submissions remains in authorized Operations navigation |
| Intake assigned pre-approval record | Allowed in earlier pass | Assigned record appears in list and opens with expected edit controls |
| Intake other owner's record | Not covered in earlier pass | Absent from list; direct URL 403 with No access |
| Cross-organization known surrogate | Foreign admin404 | V2 intake direct primary-org URL 404 with Surrogate not found |

The V2 intake list contains only its assigned `8fe0c2f0-4676-4c34-9d9c-87f7f1a8bdc2` record. Admin-owned `a80869e9-0d49-4fc6-a194-a5321f4263d0` is denied. Primary-organization `364bf4bf-c2e9-4adf-8efe-f04e19383184` is not found. These controls distinguish permitted, same-organization out-of-scope, and cross-organization access.

Confirmed findings ROLE-01 and ROLE-03 therefore reproduce under both versions. ROLE-02's Dashboard portion is specific to version 1, while its Appointments portion also reproduces under version 2. V2 custom permission grants, member exceptions, handoff migration resolutions, and every record module were not exhaustively exercised.

- [V2 case manager created record denied](roles-v2-case-manager-created-denied.jpg)
- [V2 operations dashboard](roles-v2-operations-dashboard.jpg)
- [V2 operations task creation denied](roles-v2-operations-task-create-denied.jpg)
- [V2 intake unassigned record denied](roles-v2-intake-unassigned-denied.jpg)
