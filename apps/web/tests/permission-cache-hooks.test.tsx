import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    bulkUpdateRoles,
    getMyEffectivePermissions,
    removeMember,
    updateMember,
    updateRolePermissions,
    type EffectivePermissions,
} from "@/lib/api/permissions"
import {
    useBulkUpdateRoles,
    useEffectivePermissions,
    useRemoveMember,
    useUpdateMember,
    useUpdateRolePermissions,
} from "@/lib/hooks/use-permissions"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/permissions", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/permissions")>()
    return {
        ...actual,
        getMyEffectivePermissions: vi.fn(),
        updateMember: vi.fn(),
        removeMember: vi.fn(),
        updateRolePermissions: vi.fn(),
        bulkUpdateRoles: vi.fn(),
    }
})

const originalPermissions: EffectivePermissions = {
    user_id: "user-1",
    role: "case_manager",
    permissions: ["view_reports", "view_surrogates"],
    overrides: [],
}

const updatedPermissions: EffectivePermissions = {
    ...originalPermissions,
    permissions: ["view_surrogates"],
}

function createQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: { retry: false, staleTime: Infinity },
            mutations: { retry: false },
        },
    })
}

function wrapperFor(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

describe("permission cache hooks", () => {
    beforeEach(() => {
        vi.mocked(getMyEffectivePermissions).mockReset()
        vi.mocked(updateMember).mockReset()
        vi.mocked(removeMember).mockReset()
        vi.mocked(updateRolePermissions).mockReset()
        vi.mocked(bulkUpdateRoles).mockReset()
    })

    it.each(["user-2", null])(
        "does not expose the previous user's permissions when identity changes to %s",
        async (nextUserId) => {
            vi.mocked(getMyEffectivePermissions)
                .mockResolvedValueOnce(originalPermissions)
                .mockReturnValue(new Promise(() => {}))
            const view = renderHook(
                ({ userId }: { userId: string | null }) => useEffectivePermissions(userId),
                {
                    initialProps: { userId: "user-1" },
                    wrapper: wrapperFor(createQueryClient()),
                },
            )

            await waitFor(() => {
                expect(view.result.current.data).toEqual(originalPermissions)
            })

            view.rerender({ userId: nextUserId })

            expect(view.result.current.data).toBeUndefined()
            expect(getMyEffectivePermissions).toHaveBeenCalledTimes(nextUserId ? 2 : 1)
        },
    )

    it.each(["member", "removal", "role", "bulk"] as const)(
        "refreshes effective permissions and visible application data after a %s change",
        async (change) => {
            vi.mocked(getMyEffectivePermissions)
                .mockResolvedValueOnce(originalPermissions)
                .mockResolvedValue(updatedPermissions)
            vi.mocked(updateMember).mockResolvedValue({
                id: "member-1",
                user_id: "user-1",
                email: "member@example.test",
                display_name: "Test Member",
                role: "case_manager",
                last_login_at: null,
                created_at: "2026-09-07T12:00:00Z",
                effective_permissions: updatedPermissions.permissions,
                overrides: [],
            })
            vi.mocked(removeMember).mockResolvedValue({ removed: true, user_id: "user-1" })
            vi.mocked(updateRolePermissions).mockResolvedValue({
                role: "case_manager",
                label: "Case Manager",
                permissions_by_category: {},
            })
            vi.mocked(bulkUpdateRoles).mockResolvedValue({ success: 1, failed: 1 })

            const queryClient = createQueryClient()
            const inactiveEffectiveKey = ["permissions", "effective", "inactive-user"]
            const memberKey = ["permissions", "members", "member-1"]
            const editorKey = change === "role"
                ? ["permissions", "roles", "case_manager"]
                : memberKey
            queryClient.setQueryData(inactiveEffectiveKey, {
                ...originalPermissions,
                user_id: "inactive-user",
            })
            queryClient.setQueryData(memberKey, {})
            queryClient.setQueryData(editorKey, {})
            queryClient.setQueryData(["surrogates"], [])
            const view = renderHook(
                () => ({
                    effective: useEffectivePermissions("user-1"),
                    member: useUpdateMember(),
                    removal: useRemoveMember(),
                    role: useUpdateRolePermissions(),
                    bulk: useBulkUpdateRoles(),
                }),
                { wrapper: wrapperFor(queryClient) },
            )

            await waitFor(() => {
                expect(view.result.current.effective.data).toEqual(originalPermissions)
            })

            await act(async () => {
                switch (change) {
                    case "member":
                        await view.result.current.member.mutateAsync({
                            memberId: "member-1",
                            data: {
                                add_overrides: [{ permission: "view_reports", override_type: "revoke" }],
                            },
                        })
                        break
                    case "removal":
                        await view.result.current.removal.mutateAsync("member-1")
                        break
                    case "role":
                        await view.result.current.role.mutateAsync({
                            role: "case_manager",
                            permissions: { view_reports: false },
                        })
                        break
                    case "bulk":
                        await view.result.current.bulk.mutateAsync({
                            memberIds: ["member-1", "member-2"],
                            role: "intake_specialist",
                        })
                }
            })

            await waitFor(() => {
                expect(view.result.current.effective.data).toEqual(updatedPermissions)
            })
            expect(getMyEffectivePermissions).toHaveBeenCalledTimes(2)
            expect(queryClient.getQueryState(inactiveEffectiveKey)?.isInvalidated).toBe(true)
            expect(queryClient.getQueryState(editorKey)?.isInvalidated).toBe(true)
            expect(queryClient.getQueryState(memberKey)?.isInvalidated).toBe(true)
            expect(queryClient.getQueryState(["surrogates"])?.isInvalidated).toBe(true)
        },
    )
})
