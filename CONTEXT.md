# Surrogacy Force

## Records and relationships

**Intended Parent (IP)**: The intended-parent record that may participate in multiple independent match cases, concurrently or at different times.

**Donor**: An egg or sperm donor who may participate in match cases with multiple IPs, including concurrent cases and later cases with the same IP.

**Surrogate**: A surrogate who may participate in successive match cases with IPs and has at most one confirmed active case at a time. Unconfirmed proposals may overlap.

**Match case**: One occurrence of a relationship containing exactly one IP and either one surrogate or one donor. Every case has its own start dates, lifecycle, work, and history. Restarting an ended relationship creates a new case, including when the participants are unchanged. Cases are independent; there is no parent IP-journey entity.

**Treatment attempt**: An attempt within a continuing match case. Another attempt does not by itself create a new case.

**Donor cycle**: A donor retrieval or collection that may serve multiple IP match cases. The procedure remains one donor-owned occurrence with explicit links to the cases it serves.

**Match workspace**: A shared view of the two parties' information and the work and updates belonging to their match case. General record facts remain distinct from case-specific history.

**Surrogate lifetime timeline**: The history associated with the surrogate across their involvement with the agency. The existing surrogate journey view represents this history across cases and attempts; it is not a parent container for match cases.

**Organization SMS**: Messages sent on behalf of an agency through its organization-owned sender, configured by an administrator. Automated transactional messages may reference a record, match case, or treatment attempt.
