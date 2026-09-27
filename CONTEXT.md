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
