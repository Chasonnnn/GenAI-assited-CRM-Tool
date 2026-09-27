# Surrogacy Force

## Records and relationships

**Intended Parent (IP)**: The intended-parent record that may participate in multiple independent matches, concurrently or at different times.

**Donor**: An egg or sperm donor who may participate in matches with multiple IPs, including concurrent matches and later matches with the same IP.

**Surrogate**: A surrogate who may participate in successive matches with IPs and has at most one confirmed active match at a time. Unconfirmed proposals may overlap.

**Match**: One occurrence of a relationship containing exactly one IP and either one surrogate or one donor. Every match has its own start dates, lifecycle, work, and history. Restarting an ended relationship creates a new match, including when the participants are unchanged. Matches are independent; there is no parent IP-journey entity.
_Avoid_: Match case, case, journey

## Match lifecycle

**Under Review**: The state of a proposed match until it is accepted or declined.
_Avoid_: Proposed, reviewing, pending

**Accepted**: The state of a match both sides have committed to. A surrogate holds at most one accepted match at a time.
_Avoid_: Active, confirmed

**Declined**: A match ended while Under Review, either rejected by a decider or retracted by its proposer. The match history records who declined it.
_Avoid_: Rejected, denied, withdrawn

**Cancellation request**: A request to end an accepted match. It takes effect only after a second person approves it.

**Cancelled**: An accepted match ended through an approved cancellation request.

**Completed**: An accepted match that reached its outcome and closed normally.

## Match work

**Treatment attempt**: An attempt within a continuing match. Another attempt does not by itself create a new match.

**Donor cycle**: A donor retrieval or collection that may serve multiple IP matches. The procedure remains one donor-owned occurrence with explicit links to the matches it serves.

**Match workspace**: A shared view of the two parties' information and the work and updates belonging to their match. General record facts remain distinct from match-specific history.

**Surrogate lifetime timeline**: The history associated with the surrogate across their involvement with the agency. The existing surrogate journey view represents this history across matches and attempts; it is not a parent container for matches.

**Organization SMS**: Messages sent on behalf of an agency through its organization-owned sender, configured by an administrator. Automated transactional messages may reference a record, match, or treatment attempt.

## Staff access

**Role preset**: One of five supplied staff roles: Intake Specialist, Case Manager, Operations, Admin, or Dev. Each staff member has one role; agencies may edit Intake Specialist, Case Manager, and Operations baselines, while Admin and Dev baselines remain protected. Operations manages organization automation and templates and views records/reports without record-write or send authority by default.

**Individual permission addition**: Removable extra authority assigned to a specific staff member beyond their role preset, consisting of additional actions or an explicit expansion of record scope. Removing it restores inherited role access without changing anyone else's permissions.

**Record scope**: The set of agency records a staff member may access within a module, shared by viewing and editing and defined separately from action permissions. A person's scope can differ between modules.

**Approval boundary**: The Approved milestone in a surrogate, egg-donor, or sperm-donor pipeline, which begins post-approval access.

**Applicant approval**: An authorized decision that a surrogate or donor applicant has reached the Approved milestone. It is distinct from approval of a requested stage correction.

**Approved donor pool**: A shared pool of approved donors awaiting ownership by a Case Manager.

**Intake collaborator**: The Intake owner retained at approval handoff, or another Intake staff member explicitly added to continue follow-up. The collaborator may view and update normal information until removed by a Case Manager or Admin; stage changes and reassignment require separate permissions.

**Personal work**: A workflow, campaign, or template belonging to one staff member and private from peers, with audited agency-Admin management. Personal workflows and campaigns operate on the owner's currently assigned or Intake-collaborator records within the owner's permitted actions.

**Organization work**: A workflow, campaign, or template belonging to the agency rather than an individual staff member. Enabled or scheduled organization work continues independently of the original proposer's membership.

**Organization publication**: An independent organization-owned copy of personal work. Changes to the personal original do not change the published copy.

**Proposer**: The original contributor credited for organization work, including work shared from a personal original. Attribution remains after departure and does not confer ownership or access rights.
