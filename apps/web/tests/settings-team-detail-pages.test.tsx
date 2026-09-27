import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"

const mocks = vi.hoisted(() => ({
    can: vi.fn(),
    params: { role: "case_manager", id: "member-2" } as Record<string, string>,
    push: vi.fn(),
    user: { user_id: "user-1", email: "admin@example.com", role: "developer" },
    useRoles: vi.fn(),
    useRoleDetail: vi.fn(),
    updateRole: vi.fn(),
    useMember: vi.fn(),
    updateMember: vi.fn(),
    removeMember: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    useParams: () => mocks.params,
    useRouter: () => ({ push: mocks.push, replace: vi.fn() }),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href, ...props }: React.ComponentProps<"a">) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mocks.can(permission),
    }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: mocks.user }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useRoles: () => mocks.useRoles(),
    useRoleDetail: (role: string) => mocks.useRoleDetail(role),
    useUpdateRolePermissions: () => ({ mutateAsync: mocks.updateRole, isPending: false }),
    useMember: (id: string) => mocks.useMember(id),
    useUpdateMember: () => ({ mutateAsync: mocks.updateMember, isPending: false }),
    useRemoveMember: () => ({ mutateAsync: mocks.removeMember, isPending: false }),
    useAvailablePermissions: () => ({ data: [] }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: vi.fn(), error: vi.fn() },
}))

import RolePermissionsPage from "../app/(app)/settings/team/roles/page"
import RoleDetailPage from "../app/(app)/settings/team/roles/[role]/page.client"
import MemberDetailPage from "../app/(app)/settings/team/members/[id]/page.client"

const ROLE_DETAIL = {
    role: "case_manager",
    label: "Case Manager",
    permissions_by_category: {
        Surrogates: [
            {
                key: "view_surrogates",
                label: "View surrogates",
                description: "See surrogate records",
                category: "Surrogates",
                developer_only: false,
                is_granted: true,
            },
        ],
    },
}

const MEMBER = {
    id: "member-2",
    user_id: "user-2",
    email: "case@example.com",
    display_name: "Casey Manager",
    role: "case_manager",
    created_at: "2026-01-01T00:00:00Z",
    last_login_at: null,
    overrides: [],
    effective_permissions: [],
}

function notFoundError() {
    return new ApiError(404, "Not Found", "Not found")
}

beforeEach(() => {
    mocks.can.mockReset()
    mocks.can.mockReturnValue(true)
    mocks.user = { user_id: "user-1", email: "admin@example.com", role: "developer" }
    mocks.push.mockReset()
    mocks.updateRole.mockReset()
    mocks.updateMember.mockReset()
    mocks.removeMember.mockReset()
    mocks.useRoles.mockReset()
    mocks.useRoleDetail.mockReset()
    mocks.useMember.mockReset()
})

describe("Role Permissions list", () => {
    it("uses the shared header with a back link to Team", () => {
        mocks.useRoles.mockReturnValue({
            data: [{ role: "case_manager", label: "Case Manager", permission_count: 12, is_developer: false }],
            isLoading: false,
        })

        render(<RolePermissionsPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Role Permissions" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Team" })).toHaveAttribute("href", "/settings/team")
        expect(screen.getByText("Case Manager")).toBeInTheDocument()
    })

    it("shows the denied state and loads no roles without view_roles", () => {
        mocks.can.mockReturnValue(false)

        render(<RolePermissionsPage />)

        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(mocks.useRoles).not.toHaveBeenCalled()
    })

    it("shows a load error instead of a blank page", () => {
        mocks.useRoles.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(500, "Internal Server Error", "boom"),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<RolePermissionsPage />)

        expect(screen.getByRole("heading", { level: 2, name: "Couldn't load roles" })).toBeInTheDocument()
    })
})

describe("Role detail", () => {
    it("collects toggles in the save bar and saves them", async () => {
        mocks.useRoleDetail.mockReturnValue({ data: ROLE_DETAIL, isLoading: false })
        mocks.updateRole.mockResolvedValue(ROLE_DETAIL)

        render(<RoleDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Case Manager Permissions" })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "Back to Role Permissions" })).toHaveAttribute(
            "href",
            "/settings/team/roles"
        )
        expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("switch", { name: "View surrogates permission" }))

        const bar = screen.getByRole("region", { name: "Unsaved changes" })
        expect(within(bar).getByText("1 unsaved change")).toBeInTheDocument()
        expect(screen.queryByText(/Click Save Changes to apply/)).not.toBeInTheDocument()

        fireEvent.click(within(bar).getByRole("button", { name: "Save changes" }))

        await waitFor(() =>
            expect(mocks.updateRole).toHaveBeenCalledWith({
                role: "case_manager",
                permissions: { view_surrogates: false },
            })
        )
    })

    it("discards pending toggles", () => {
        mocks.useRoleDetail.mockReturnValue({ data: ROLE_DETAIL, isLoading: false })

        render(<RoleDetailPage />)

        const toggle = screen.getByRole("switch", { name: "View surrogates permission" })
        fireEvent.click(toggle)
        fireEvent.click(screen.getByRole("button", { name: "Discard" }))

        expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument()
        expect(toggle).toHaveAttribute("aria-checked", "true")
    })

    it("marks the page read only for non-developers", () => {
        mocks.user = { user_id: "user-1", email: "admin@example.com", role: "admin" }
        mocks.useRoleDetail.mockReturnValue({ data: ROLE_DETAIL, isLoading: false })

        render(<RoleDetailPage />)

        expect(screen.getByText("Read only")).toBeInTheDocument()
        expect(screen.getByRole("switch", { name: "View surrogates permission" })).toHaveAttribute("aria-disabled", "true")
    })

    it("shows a not-found state instead of rendering nothing", () => {
        mocks.useRoleDetail.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: notFoundError(),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<RoleDetailPage />)

        expect(screen.getByRole("heading", { level: 2, name: "Role not found" })).toBeInTheDocument()
    })
})

describe("Member detail", () => {
    it("shows a not-found state instead of rendering nothing", () => {
        mocks.useMember.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: notFoundError(),
            refetch: vi.fn(),
            isFetching: false,
        })

        render(<MemberDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Team Member" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Member not found" })).toBeInTheDocument()
        expect(screen.getAllByRole("link", { name: "Back to Team" })[0]).toHaveAttribute("href", "/settings/team")
    })

    it("shows the denied state without manage_team", () => {
        mocks.can.mockReturnValue(false)

        render(<MemberDetailPage />)

        expect(screen.getByText("Permission required")).toBeInTheDocument()
        expect(mocks.useMember).not.toHaveBeenCalled()
    })

    it("removes the member through an in-app confirm dialog", async () => {
        const confirmSpy = vi.spyOn(window, "confirm")
        mocks.useMember.mockReturnValue({ data: MEMBER, isLoading: false })
        mocks.removeMember.mockResolvedValue(undefined)

        render(<MemberDetailPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Casey Manager" })).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Remove Member" }))

        const dialog = await screen.findByRole("alertdialog")
        expect(within(dialog).getByText("Remove case@example.com?")).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole("button", { name: "Remove member" }))

        await waitFor(() => expect(mocks.removeMember).toHaveBeenCalledWith("member-2"))
        await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/settings/team"))
        expect(confirmSpy).not.toHaveBeenCalled()
        confirmSpy.mockRestore()
    })

    it("keeps the dialog open with a sanitized error when removal fails", async () => {
        mocks.useMember.mockReturnValue({ data: MEMBER, isLoading: false })
        mocks.removeMember.mockRejectedValue(new ApiError(500, "Internal Server Error", "db exploded"))

        render(<MemberDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: "Remove Member" }))
        const dialog = await screen.findByRole("alertdialog")
        fireEvent.click(within(dialog).getByRole("button", { name: "Remove member" }))

        expect(await within(dialog).findByRole("alert")).toHaveTextContent("Couldn't remove this member. Try again.")
        expect(screen.queryByText(/db exploded/)).not.toBeInTheDocument()
        expect(mocks.push).not.toHaveBeenCalled()
    })

    it("shows override types without leading icons", async () => {
        mocks.useMember.mockReturnValue({ data: MEMBER, isLoading: false })

        render(<MemberDetailPage />)

        fireEvent.click(screen.getByRole("button", { name: /add override/i }))
        const dialog = await screen.findByRole("dialog")
        fireEvent.click(within(dialog).getByRole("combobox", { name: "Override Type" }))

        const grant = await screen.findByRole("option", { name: "Grant (add permission)" })
        const revoke = screen.getByRole("option", { name: "Revoke (remove permission)" })
        // Only the trailing selected indicator may render an icon.
        expect(grant.querySelectorAll("svg").length).toBeLessThanOrEqual(1)
        expect(revoke.querySelectorAll("svg")).toHaveLength(0)
    })
})
