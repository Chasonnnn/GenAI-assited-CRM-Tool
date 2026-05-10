import "@testing-library/jest-dom"
import { render, screen } from "@testing-library/react"
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
                platformEmailStatus={{ configured: true, provider: "resend" }}
                platformEmailLoading={false}
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
    })
})
