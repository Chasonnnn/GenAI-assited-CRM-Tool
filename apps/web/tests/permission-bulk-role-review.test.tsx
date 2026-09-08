import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PermissionBulkRoleReview } from "@/components/permissions/permission-bulk-role-review"
import { Dialog } from "@/components/ui/dialog"
import * as api from "@/lib/api/permissions"
import * as scopes from "@/lib/api/record-scopes"

vi.mock("@/lib/api/permissions", async (original) => ({ ...await original<typeof api>(), getMember: vi.fn(), getRoles: vi.fn(), getRoleDetail: vi.fn(), bulkUpdateRoles: vi.fn() }))
vi.mock("@/lib/api/record-scopes", async (original) => ({ ...await original<typeof scopes>(), getRoleScopes: vi.fn(), getScopeAdditions: vi.fn(), getScopeMigrationReview: vi.fn() }))
function choose(label: string, option: string) { fireEvent.click(screen.getByRole("combobox", { name: label })); const item = screen.getByRole("option", { name: option }); fireEvent.mouseMove(item); fireEvent.click(item) }

describe("bulk member role review", () => {
    beforeEach(() => {
        vi.mocked(api.getMember).mockReset().mockResolvedValue({ id: "member-1", user_id: "user-1", display_name: "Taylor Morgan", email: "taylor@example.test", role: "intake_specialist", created_at: "2026-09-07", last_login_at: null, effective_permissions: ["send_email"], overrides: [{ permission: "send_email", label: "Send Email", category: "Communications", override_type: "grant" }] })
        vi.mocked(api.getRoles).mockReset().mockResolvedValue([{ role: "case_manager", label: "Case Manager", is_developer: false, permission_count: 1 }])
        vi.mocked(api.getRoleDetail).mockReset().mockResolvedValue({ role: "case_manager", label: "Case Manager", permissions_by_category: { Surrogates: [{ key: "view_surrogates", label: "View Surrogates", description: "", is_granted: true, developer_only: false }] } })
        vi.mocked(scopes.getRoleScopes).mockReset().mockImplementation(async (role) => ({ surrogates: { assignment: role === "operations" ? "all" : "assigned", phase: role === "operations" ? "all" : "post_approval", stage_ids: [] }, donors: { assignment: "all", phase: "post_approval", stage_ids: [] }, intended_parents: { assignment: "all", phase: "all", stage_ids: [] } }))
        vi.mocked(scopes.getScopeAdditions).mockReset().mockResolvedValue([])
        vi.mocked(scopes.getScopeMigrationReview).mockReset().mockResolvedValue({ ready: true, collaborators: [], handoff_candidates: [], unresolved_handoffs: [], missing_approval_gate_pipeline_ids: [], legacy_pool_grants: [] })
        vi.mocked(api.bulkUpdateRoles).mockReset().mockResolvedValue({ success: 1, failed: 0 })
    })
    it("requires carry decisions and submits only after review", async () => {
        const onSaved = vi.fn()
        render(<Dialog open><PermissionBulkRoleReview memberIds={["member-1"]} v2 canAssignDeveloper={false} onClose={vi.fn()} onSaved={onSaved} /></Dialog>)
        await screen.findByRole("combobox", { name: "New role" })
        expect(screen.getByRole("button", { name: "Apply reviewed roles" })).toBeDisabled()
        choose("Action and scope additions", "Remove each member’s existing additions")
        expect(screen.getByRole("button", { name: "Apply reviewed roles" })).toBeDisabled()
        choose("Record collaborations", "Keep each member’s collaborations")
        fireEvent.click(screen.getByRole("button", { name: "Apply reviewed roles" }))
        await waitFor(() => expect(api.bulkUpdateRoles).toHaveBeenCalledWith(["member-1"], "case_manager", { access_reviewed: true, retain_additions: false, retain_collaborators: true }))
        expect(onSaved).toHaveBeenCalledOnce()
    })
    it("preserves a partial failure for review rather than reporting completion", async () => {
        const onSaved = vi.fn()
        vi.mocked(api.bulkUpdateRoles).mockResolvedValue({ success: 0, failed: 1 })
        render(<Dialog open><PermissionBulkRoleReview memberIds={["member-1"]} v2={false} canAssignDeveloper={false} onClose={vi.fn()} onSaved={onSaved} /></Dialog>)
        await screen.findByRole("combobox", { name: "New role" })
        fireEvent.click(screen.getByRole("button", { name: "Apply reviewed roles" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("0 updated; 1 failed")
        expect(onSaved).not.toHaveBeenCalled()
    })
})
