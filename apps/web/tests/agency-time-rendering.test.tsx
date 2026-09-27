import "@testing-library/jest-dom"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"
import { renderToString } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"

vi.mock("@/components/app-link", () => ({
    default: ({
        href,
        children,
        ...props
    }: {
        href: string
        children: ReactNode
        [key: string]: unknown
    }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

import { AgencyInvitesTab } from "@/components/ops/agencies/AgencyInvitesTab"
import { AgencySubscriptionTab } from "@/components/ops/agencies/AgencySubscriptionTab"

const inviteHandlers = {
    onInviteOpenChange: vi.fn(),
    onInviteEmailChange: vi.fn(),
    onInviteRoleChange: vi.fn(),
    onCreateInvite: vi.fn(),
    onResendInvite: vi.fn(),
    onRevokeInvite: vi.fn(),
}

describe("agency time rendering", () => {
    it("server-renders invitation timestamps as deterministic UTC fallback labels", () => {
        const html = renderToString(
            <AgencyInvitesTab
                orgName="EWI"
                invites={[
                    {
                        id: "invite_1",
                        email: "candidate@example.com",
                        role: "admin",
                        status: "pending",
                        created_at: "2026-06-03T00:30:00.000Z",
                        open_count: 1,
                        opened_at: "2026-06-04T00:30:00.000Z",
                        click_count: 1,
                        clicked_at: "2026-06-05T00:30:00.000Z",
                    },
                ]}
                inviteOpen={false}
                inviteSubmitting={false}
                inviteResending={null}
                inviteForm={{ email: "", role: "admin" }}
                inviteError={null}
                platformEmailStatus={{
                    configured: true,
                    from_email: "invites@example.com",
                    provider: "resend",
                }}
                platformEmailStatusLoading={false}
                platformEmailReadiness={{
                    check_status: "idle",
                    queued_at: null,
                    last_snapshot: {
                        freshness: "fresh",
                        probe_status: "succeeded",
                        overall_status: "ready",
                        domain_status: "ready",
                        webhook_status: "ready",
                        sending_status: "ready",
                        delivery_tracking_status: "ready",
                        engagement_tracking_status: "ready",
                        verified_domain_count: 1,
                        enabled_webhook_count: 1,
                        issue_codes: [],
                        checked_at: "2026-06-03T00:30:00.000Z",
                        last_success_at: "2026-06-03T00:30:00.000Z",
                    },
                }}
                platformEmailReadinessLoading={false}
                platformEmailReadinessError={false}
                platformEmailCheckPending={false}
                platformEmailCheckError={false}
                onCheckPlatformEmailReadiness={vi.fn()}
                {...inviteHandlers}
            />,
        )

        expect(html).toContain("Jun 3, 2026")
        expect(html).toContain("Jun 4, 2026")
        expect(html).toContain("Jun 5, 2026")
        expect(html).not.toContain("ago")
    })

    it("renders subscription dates by UTC calendar day", () => {
        render(
            <AgencySubscriptionTab
                subscription={{
                    id: "sub_1",
                    organization_id: "org_1",
                    plan_key: "professional",
                    status: "active",
                    auto_renew: true,
                    current_period_end: "2026-06-03T00:30:00.000Z",
                    trial_end: "2026-06-04T00:30:00.000Z",
                    notes: "",
                    created_at: "2026-05-01T00:00:00.000Z",
                    updated_at: "2026-05-01T00:00:00.000Z",
                }}
                subscriptionStatus="found"
                onRetry={vi.fn()}
                notesDraft=""
                notesDirty={false}
                notesSaving={false}
                onNotesChange={vi.fn()}
                onSaveNotes={vi.fn()}
                onExtendSubscription={vi.fn()}
                onToggleAutoRenew={vi.fn()}
            />,
        )

        expect(screen.getByText("June 3, 2026")).toBeInTheDocument()
        expect(screen.getByText("June 4, 2026")).toBeInTheDocument()
        expect(screen.getByText("Professional")).toBeInTheDocument()
        expect(screen.getByText("Active")).toBeInTheDocument()
    })

    const subscriptionHandlers = {
        notesDraft: "",
        notesDirty: false,
        notesSaving: false,
        onNotesChange: vi.fn(),
        onSaveNotes: vi.fn(),
        onExtendSubscription: vi.fn(),
        onToggleAutoRenew: vi.fn(),
    }

    it("shows an empty state when the agency has no subscription record", () => {
        render(
            <AgencySubscriptionTab
                subscription={null}
                subscriptionStatus="missing"
                onRetry={vi.fn()}
                {...subscriptionHandlers}
            />,
        )

        expect(screen.getByRole("heading", { name: "No subscription record" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument()
    })

    it("shows a retryable error when the subscription fails to load", () => {
        const onRetry = vi.fn()
        render(
            <AgencySubscriptionTab
                subscription={null}
                subscriptionStatus="error"
                onRetry={onRetry}
                {...subscriptionHandlers}
            />,
        )

        expect(screen.getByRole("heading", { name: "Couldn't load subscription" })).toBeInTheDocument()
        expect(screen.queryByText("No subscription record")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(onRetry).toHaveBeenCalledOnce()
    })
})
