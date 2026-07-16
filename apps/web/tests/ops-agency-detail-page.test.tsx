import type { ReactNode } from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, describe, expect, it, vi } from "vitest"

import AgencyDetailPage from "../app/ops/agencies/[orgId]/page.client"

const mockGetOrganization = vi.fn()
const mockGetSubscription = vi.fn()
const mockListMembers = vi.fn()
const mockListInvites = vi.fn()
const mockGetAdminActionLogs = vi.fn()
const mockGetPlatformEmailStatus = vi.fn()
const mockListAlerts = vi.fn()

vi.unmock("@tanstack/react-query")

vi.mock("next/navigation", () => ({
    useParams: () => ({ orgId: "org-1" }),
    useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/lib/api/platform", () => ({
    getOrganization: (...args: unknown[]) => mockGetOrganization(...args),
    getSubscription: (...args: unknown[]) => mockGetSubscription(...args),
    listMembers: (...args: unknown[]) => mockListMembers(...args),
    listInvites: (...args: unknown[]) => mockListInvites(...args),
    getAdminActionLogs: (...args: unknown[]) => mockGetAdminActionLogs(...args),
    getPlatformEmailStatus: (...args: unknown[]) => mockGetPlatformEmailStatus(...args),
    listAlerts: (...args: unknown[]) => mockListAlerts(...args),
    acknowledgeAlert: vi.fn(),
    resolveAlert: vi.fn(),
    updateSubscription: vi.fn(),
    extendSubscription: vi.fn(),
    updateMember: vi.fn(),
    resetMemberMfa: vi.fn(),
    createInvite: vi.fn(),
    revokeInvite: vi.fn(),
    resendInvite: vi.fn(),
    deleteOrganization: vi.fn(),
    restoreOrganization: vi.fn(),
    purgeOrganization: vi.fn(),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("@/components/ui/tabs", async () => {
    const React = await import("react")
    const TabsContext = React.createContext<{
        value: string
        onValueChange: (value: string) => void
    }>({
        value: "",
        onValueChange: () => undefined,
    })

    return {
        Tabs: ({
            value,
            onValueChange,
            children,
        }: {
            value: string
            onValueChange: (value: string) => void
            children: ReactNode
        }) => (
            <TabsContext.Provider value={{ value, onValueChange }}>
                <div>{children}</div>
            </TabsContext.Provider>
        ),
        TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
        TabsTrigger: ({ value, children }: { value: string; children: ReactNode }) => {
            const context = React.use(TabsContext)
            return (
                <button type="button" onClick={() => context.onValueChange(value)}>
                    {children}
                </button>
            )
        },
        TabsContent: ({ value, children }: { value: string; children: ReactNode }) => {
            const context = React.use(TabsContext)
            return context.value === value ? <div>{children}</div> : null
        },
    }
})

vi.mock("@/components/ops/agencies/AgencyOverviewTab", () => ({
    AgencyOverviewTab: () => <div>Agency overview</div>,
}))
vi.mock("@/components/ops/agencies/AgencyUsersTab", () => ({
    AgencyUsersTab: () => <div>Agency users</div>,
}))
vi.mock("@/components/ops/agencies/AgencyInvitesTab", () => ({
    AgencyInvitesTab: ({
        platformEmailStatus,
        platformEmailLoading,
    }: {
        platformEmailStatus: { provider?: string | null } | null
        platformEmailLoading: boolean
    }) => (
        <div>
            {platformEmailLoading
                ? "Loading sender status"
                : `Sender: ${platformEmailStatus?.provider ?? "unavailable"}`}
        </div>
    ),
}))
vi.mock("@/components/ops/agencies/AgencySubscriptionTab", () => ({
    AgencySubscriptionTab: () => <div>Agency subscription</div>,
}))
vi.mock("@/components/ops/agencies/AgencyAlertsTab", () => ({
    AgencyAlertsTab: () => <div>Agency alerts</div>,
}))
vi.mock("@/components/ops/agencies/AgencyAuditTab", () => ({
    AgencyAuditTab: () => <div>Agency audit</div>,
}))
vi.mock("@/components/ops/agencies/SupportSessionDialog", () => ({
    SupportSessionDialog: () => <button type="button">Start support session</button>,
}))

function renderAgencyDetailPage(
    queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    }),
) {
    return render(
        <QueryClientProvider client={queryClient}>
            <AgencyDetailPage />
        </QueryClientProvider>,
    )
}

describe("AgencyDetailPage", () => {
    beforeEach(() => {
        mockGetOrganization.mockReset()
        mockGetSubscription.mockReset()
        mockListMembers.mockReset()
        mockListInvites.mockReset()
        mockGetAdminActionLogs.mockReset()
        mockGetPlatformEmailStatus.mockReset()
        mockListAlerts.mockReset()

        mockGetOrganization.mockResolvedValue({
            id: "org-1",
            name: "Test Agency",
            slug: "test-agency",
            portal_base_url: "https://test-agency.example.com",
            member_count: 0,
            subscription_plan: "professional",
            subscription_status: "active",
            deleted_at: null,
            purge_at: null,
        })
        mockGetSubscription.mockResolvedValue(null)
        mockListMembers.mockResolvedValue([])
        mockListInvites.mockResolvedValue([])
        mockGetAdminActionLogs.mockResolvedValue({ items: [] })
        mockListAlerts.mockResolvedValue({ items: [], total: 0 })
        mockGetPlatformEmailStatus.mockResolvedValue({
            configured: true,
            provider: "resend",
        })
    })

    it("reuses fresh platform email status when the Invites tab is reopened", async () => {
        renderAgencyDetailPage()
        expect(
            await screen.findByRole("heading", { name: "Test Agency" }),
        ).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Invites" }))
        expect(await screen.findByText("Sender: resend")).toBeInTheDocument()
        expect(mockGetPlatformEmailStatus).toHaveBeenCalledTimes(1)

        fireEvent.click(screen.getByRole("button", { name: "Overview" }))
        fireEvent.click(screen.getByRole("button", { name: "Invites" }))

        await waitFor(() => {
            expect(screen.getByText("Sender: resend")).toBeInTheDocument()
            expect(mockGetPlatformEmailStatus).toHaveBeenCalledTimes(1)
        })
    })

    it("reuses fresh organization alerts when the agency route remounts", async () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        })

        const firstView = renderAgencyDetailPage(queryClient)
        expect(
            await screen.findByRole("heading", { name: "Test Agency" }),
        ).toBeInTheDocument()
        await waitFor(() => expect(mockListAlerts).toHaveBeenCalledTimes(1))

        firstView.unmount()
        renderAgencyDetailPage(queryClient)
        expect(
            await screen.findByRole("heading", { name: "Test Agency" }),
        ).toBeInTheDocument()

        await waitFor(() => expect(mockListAlerts).toHaveBeenCalledTimes(1))
    })
})
