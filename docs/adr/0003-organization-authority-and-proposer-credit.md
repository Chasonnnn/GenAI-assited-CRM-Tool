---
status: accepted
---

# Separate organization authority from proposer credit

Organization workflow actions are authorized at activation and then operate under agency ownership, so the original contributor's departure or permission loss does not stop enabled or scheduled organization work. Personal work instead depends on its owner's current authority and skips records it can no longer access. Organization Details retains Proposed by for contributor credit, without giving that attribution execution authority or continued personal access.

Publishing personal work creates an independent organization copy; it does not create a live link to privately editable content. Current organization configuration and domain restrictions still apply to execution.

A generated shared-intake routing workflow has no human authorizer. Publishing its form grants it a system authority (`system:shared_intake_routing`) bound to the exact generated configuration, only when the publisher can create the form's record type. Any configuration change voids that grant, and the workflow then needs an administrator's authorization. Activation still pauses routing workflows that have no grant.

Implemented locally behind reviewed organization activation. See [verification](../permission-upgrade-verification.md).
