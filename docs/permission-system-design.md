# Permission system design

Status: product model awaiting final review. Application code and production permissions are unchanged.

This milestone covers internal agency staff. External professionals and participants are outside scope, and a new platform-support access mechanism is deferred because no concrete use case was identified.

## Roles and individual additions

Each staff member has one supplied role. Agencies cannot create custom roles or combine multiple roles for a person.

| Role | Default donor/surrogate record access | Configuration |
|---|---|---|
| Intake Specialist | Assigned applicants before approval, plus retained Intake-collaborator records after handoff | Admin/Dev can edit the role baseline and add individual permissions |
| Case Manager | All Approved-and-later records, regardless of owner, for matching and case work | Admin/Dev can edit the role baseline and add individual permissions |
| Admin | Full agency authority within organization and domain rules | Protected baseline |
| Dev | Platform-controlled authority within existing organization boundaries | Protected baseline; not configurable by agency users |

Individual additions can grant actions or explicitly widen record scope. They cannot deny permissions inherited from the role. Removing an addition restores the baseline without overriding another valid source of access.

Only Admin and Dev can change role baselines or individual action/scope additions. Case Managers may manage the agreed per-record Intake collaborators; that does not let them change someone's role or module permissions.

Changing a person's role requires an Admin to review their additions and collaborator access and choose what carries over.

## Record scope and actions

Record scope is configured separately for each module. It defines the same record set for viewing and editing; action permissions determine what the person may do within that set.

A Case Manager with Edit can therefore edit information on every post-approval record they can view, including records owned by another Case Manager.

Within a configured scope rule, assignment and phase/stage restrictions combine with AND. Separate grants, including an individual scope addition or Intake collaboration, add access to their explicitly covered records.

The Intake default resolves the handoff requirement through two routes:

- Before approval: currently assigned applicant records.
- After handoff: records with an active Intake-collaborator relationship.

The collaborator route permits the agreed information follow-up despite the normal before-approval Intake boundary. It does not grant phase-wide access to unrelated post-approval records.

Stage changes, reassignment, applicant approval, exports, and other actions retain their own permissions and domain rules. A view or information-edit permission does not authorize these actions.

| Work | Permission distinction |
|---|---|
| Applicant approval | Explicit approval permission; enabled for Intake and Admin by default, with Intake configurable |
| Campaigns | Editing and sending are separate |
| Workflows | One Manage Workflows permission covers editing and activation |
| Organization content | Management can be delegated by module; defaults to Admin |
| Linked matches and joint documents | Require access to both parties as well as the relevant action |

Intake collaboration does not grant access to the matched Intended Parent. Existing profile, notes, documents, and correspondence sections are available under their action permissions; new field-level restrictions are outside this milestone.

## Approval and handoff

Surrogate, egg-donor, and sperm-donor pipelines each have an approval boundary. Approved itself is the first post-approval milestone.

Ordinary applicant approval does not require a separate reviewer when the actor has approval authority. Approval of a requested backward stage correction remains a separate operation.

At approval handoff:

1. The record enters its approved pool for Case Managers to claim, or follows an authorized direct assignment.
2. The Intake owner at handoff becomes an Intake collaborator.
3. That collaborator can continue viewing and updating normal information.
4. Other collaborators can be added explicitly; prior ownership alone does not grant access.
5. A Case Manager or Admin can remove collaborator access. There is no automatic time or later-stage expiry.

Removing collaboration ends that access route on the next action. Access through another valid route, such as current assignment or an individual addition, is evaluated independently.

A member's departure ends personal access. Role changes require the agreed review of retained relationships.

## Personal and organization work

Campaigns, workflows, and templates support personal and organization scope. Personal campaign support is new work.

| Rule | Personal | Organization |
|---|---|---|
| Ownership | One staff member | The agency |
| Visibility and management | Private from peers; Admin management is audited | Governed by module permissions |
| Workflow/campaign reach | Owner's currently assigned or Intake-collaborator records, within permitted actions | Authorized organization configuration |
| Creator leaves or loses permissions | Unauthorized personal actions stop | Enabled/scheduled work continues under agency authority |
| Reuse after departure | Admin can publish an organization copy | Organization keeps managing its own copy |

Being able to view a record does not by itself make it eligible for a personal workflow or campaign. Admin editing of a personal item does not silently replace its owner or expand its audience.

Organization-work management can be granted to selected roles or people. Activating an organization workflow requires both management authority and the configuring person's authority for its actions. Changes to executable actions, subjects, audiences, or triggers that expand execution reach need the same validation before taking effect.

Explicit organization-work authority may target agency-wide records in authorized modules, beyond the configuring person's ordinary personal record scope. Required action permissions still apply. After authorization, execution does not depend on the original proposer's current role or membership; current organization configuration and domain restrictions still apply.

Publishing personal work creates an independent organization copy. Workflow copies start disabled and campaign copies start as drafts. Personal-template dependencies are copied or replaced with authorized organization templates, so the shared item has no live private-template dependency. Later personal edits do not change the shared version. Direct personal-to-person ownership transfer is outside this milestone.

## Attribution

Organization Details shows Proposed by for the original contributor, including work published from a personal original.

Credit survives departure and later edits. It does not give the proposer ongoing ownership or access. Creation, publication, and edits retain their actual actor attribution in audit history.

An organization reader does not gain access to the private source item through its attribution or publication history.

## Revocation and execution

Permission and collaborator removals take effect on the next server request and queued personal action. Already completed or externally dispatched actions cannot be undone by revoking a permission.

If personal work loses access to one record, skip unauthorized actions for that record, continue authorized work elsewhere, and report the skipped count. Loss of required owner authority across all records stops all affected personal work.

Organization work is stopped through organization controls, not through departure or permission changes of its original contributor.

## Acceptance examples

| Situation | Expected behavior |
|---|---|
| Alice in Intake approves her assigned donor | Donor enters the approved pool; Alice remains an Intake collaborator and can update information |
| Bob claims that donor | Bob becomes owner; Alice's collaborator access continues |
| Carol is another Case Manager | Carol can see the approved donor for matching and edit information if she has Edit |
| Alice opens a joint document with an IP she cannot access | Access is denied until she has the required access to both parties |
| Bob removes Alice as collaborator | Alice loses that route on her next action; her personal work skips the donor unless another eligible ownership/collaboration route remains |
| Alice leaves after contributing an organization workflow | Her personal work stops; the organization workflow continues and still credits Alice |
| Someone manages workflows but lacks applicant-approval authority | They cannot activate an organization workflow that approves applicants |
| Alice changes roles | The Admin reviews her additions and collaborator links before choosing what carries over |

## Migration

Before switching an organization to the new model:

- Compare current and proposed effective access, including role overrides, individual denials, stage rules, assignments, and linked-record access.
- Resolve existing individual denials that additions-only rules cannot represent. Do not silently broaden access, reset users, or retain hidden legacy exceptions.
- Verify the Intake owner at historical approval handoff before proposing collaborator access. Uncertain history goes to Admin review; do not grant access to every past owner.
- Preview role changes, new approval boundaries, and donor pool handoffs without modifying existing records.
- Verify tenant isolation, denied operations, publication, next-action revocation, queued personal work, and organization execution after creator departure.
- Validate surrogate, egg-donor, and sperm-donor handoff journeys in the rendered application.

Implementation, migration execution, and deployment require subsequent work. No provider calls, messages, or production changes are part of this design interview.

## Restricted Case Manager scope

If an agency deliberately configures a Case Manager as assigned-only, unclaimed records outside that scope remain hidden until an authorized person assigns them. There is no implicit pool-review exception. The default all-post-approval Case Manager role still sees the approved pool.

## Operations role under discussion

The user proposed adding a supplied Operations role for organization work. Its default responsibilities, record access, and campaign sending authority remain open; this would be a fifth platform-supplied role rather than agency-created custom roles.

## Administration proposal

Group actions and record scope by module on the role screen. On the person screen, distinguish inherited permissions, individual additions, collaborator relationships, and effective access. Detailed screen design remains a subsequent design task.

## Source and decision records

- [Interview decisions](permission-system-interview.md)
- [One supplied role with individual additions](adr/0001-staff-role-baseline-and-individual-additions.md)
- [Retained Intake collaboration](adr/0002-retain-intake-collaboration-after-handoff.md)
- [Organization authority and proposer credit](adr/0003-organization-authority-and-proposer-credit.md)
- [Domain glossary](../CONTEXT.md)

Current source inspection found personal/org support for workflows and templates, organization-only campaigns, and donor phase categories without the surrogate approval gate/handoff. The interview record contains the source references. These observations are not live runtime or deployment verification.
