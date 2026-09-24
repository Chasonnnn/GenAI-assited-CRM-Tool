import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { PermissionPolicyReview } from "@/components/permissions/permission-policy-review"
import * as api from "@/lib/api/permissions"

vi.mock("@/lib/api/permissions", async (original) => ({ ...await original<typeof api>(), getPolicyConfiguration: vi.fn(), getMembers: vi.fn(), getAvailablePermissions: vi.fn(), previewPolicy: vi.fn(), activatePolicy: vi.fn() }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a> }))

const configuration: api.PolicyConfiguration = { version: 1, configuration_revision: 1, status: "legacy", role_permissions: {}, protected_roles: ["admin", "developer"] }
const initial: api.PolicyPreview = { digest: "initial-digest", current_version: 1, target_version: 2, configuration_revision: 1, ready: false, members: [{ membership_id: "member-1", user_id: "user-1", role: "case_manager", current: [], proposed: ["view_reports"], gained: ["view_reports"], lost: [] }], revokes: [{ override_id: "revoke-1", user_id: "user-1", role: "case_manager", permission: "view_reports", resolution: null, can_deny_for_role: true }], unresolved_revoke_ids: ["revoke-1"], role_permissions: {}, scope_review: { ready: true, collaborators: [], handoff_candidates: [], unresolved_handoffs: [], missing_approval_gate_pipeline_ids: [], legacy_pool_grants: [] }, execution_review: [{ item_type: "workflow", id: "workflow-1", name: "Intake follow-up" }], unresolved_execution_ids: ["workflow:workflow-1"] }

function choose(label: string, option: string) {
    fireEvent.click(screen.getByRole("combobox", { name: label }))
    const item = screen.getByRole("option", { name: option })
    fireEvent.mouseMove(item)
    fireEvent.click(item)
}

describe("permission policy activation review", () => {
    beforeEach(() => {
        vi.mocked(api.getPolicyConfiguration).mockReset().mockResolvedValue(configuration)
        vi.mocked(api.getMembers).mockReset().mockResolvedValue([{ id: "member-1", user_id: "user-1", display_name: "Taylor Morgan", email: "taylor@example.test", role: "case_manager", created_at: "2026-09-07", last_login_at: null }])
        vi.mocked(api.getAvailablePermissions).mockReset().mockResolvedValue([{ key: "view_reports", label: "View Reports", category: "Reports", description: "", developer_only: false }])
        vi.mocked(api.previewPolicy).mockReset().mockResolvedValue(initial)
        vi.mocked(api.activatePolicy).mockReset().mockResolvedValue({ ...configuration, version: 2, status: "active" })
    })

    it("requires explicit resolutions and a fresh digest before confirmation can activate", async () => {
        vi.mocked(api.previewPolicy).mockResolvedValueOnce(initial).mockResolvedValue({ ...initial, digest: "reviewed-digest", ready: true, unresolved_revoke_ids: [], unresolved_execution_ids: [] })
        render(<PermissionPolicyReview />)
        fireEvent.click(await screen.findByRole("button", { name: "Generate preview" }))
        expect(await screen.findByText("Access changes")).toBeVisible()
        expect(screen.getByRole("button", { name: "Review activation" })).toBeDisabled()
        choose("Resolution", "Remove individual revoke")
        fireEvent.click(screen.getByRole("checkbox", { name: /Pause Intake follow-up/ }))
        expect(screen.getByText("Refresh preview to review the latest resolutions.")).toBeVisible()
        expect(screen.getByRole("button", { name: "Review activation" })).toBeDisabled()
        fireEvent.click(screen.getByRole("button", { name: "Refresh preview" }))
        await waitFor(() => expect(screen.getByRole("button", { name: "Review activation" })).toBeEnabled())
        expect(api.activatePolicy).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("button", { name: "Review activation" }))
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Activate policy" }))
        await waitFor(() => expect(vi.mocked(api.activatePolicy).mock.calls[0]?.[0]).toEqual({ digest: "reviewed-digest", revoke_resolutions: [{ override_id: "revoke-1", action: "remove" }], execution_resolutions: [{ item_type: "workflow", id: "workflow-1", action: "pause" }] }))
        expect(await screen.findByText("Permission upgrade active")).toBeVisible()
    })

    it("invalidates a ready preview after a resolution changes", async () => {
        vi.mocked(api.previewPolicy).mockResolvedValue({ ...initial, ready: true })
        render(<PermissionPolicyReview />)
        fireEvent.click(await screen.findByRole("button", { name: "Generate preview" }))
        await waitFor(() => expect(screen.getByRole("button", { name: "Review activation" })).toBeEnabled())
        choose("Resolution", "Remove from all Case Manager members")
        expect(screen.getByRole("button", { name: "Review activation" })).toBeDisabled()
        expect(api.activatePolicy).not.toHaveBeenCalled()
    })

    it("shows server conflicts and requires another preview after rejected activation", async () => {
        vi.mocked(api.previewPolicy).mockResolvedValue({ ...initial, ready: true })
        vi.mocked(api.activatePolicy).mockRejectedValue(new Error("Permissions changed; review a fresh preview before activation"))
        render(<PermissionPolicyReview />)
        fireEvent.click(await screen.findByRole("button", { name: "Generate preview" }))
        await waitFor(() => expect(screen.getByRole("button", { name: "Review activation" })).toBeEnabled())
        fireEvent.click(screen.getByRole("button", { name: "Review activation" }))
        fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Activate policy" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Permissions changed")
        expect(screen.getByRole("button", { name: "Review activation" })).toBeDisabled()
    })

    it("renders preview errors without an activation control", async () => {
        vi.mocked(api.previewPolicy).mockRejectedValue(new Error("Unable to prepare review"))
        render(<PermissionPolicyReview />)
        fireEvent.click(await screen.findByRole("button", { name: "Generate preview" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Unable to prepare review")
        expect(screen.queryByRole("button", { name: "Review activation" })).not.toBeInTheDocument()
    })
})
