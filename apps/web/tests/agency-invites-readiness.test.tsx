import type { ReactNode } from "react"
import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AgencyInvitesTab } from "@/components/ops/agencies/AgencyInvitesTab"
import type { ResendReadinessEnvelope } from "@/lib/types/resend-readiness"

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

const handlers = {
    onInviteOpenChange: vi.fn(),
    onInviteEmailChange: vi.fn(),
    onInviteRoleChange: vi.fn(),
    onCreateInvite: vi.fn(),
    onResendInvite: vi.fn(),
    onRevokeInvite: vi.fn(),
}

function readinessEnvelope(
    overrides: Partial<ResendReadinessEnvelope["last_snapshot"]> = {},
    checkStatus: ResendReadinessEnvelope["check_status"] = "idle",
): ResendReadinessEnvelope {
    return {
        check_status: checkStatus,
        last_snapshot: {
            freshness: "fresh",
            probe_status: "succeeded",
            overall_status: "ready",
            domain_status: "ready",
            webhook_status: "ready",
            sending_status: "ready",
            delivery_tracking_status: "ready",
            engagement_tracking_status: "ready",
            verified_domain_count: 2,
            enabled_webhook_count: 1,
            issue_codes: [],
            checked_at: "2026-07-23T16:00:00Z",
            last_success_at: "2026-07-23T16:00:00Z",
            ...overrides,
        },
    }
}

function renderInvites(
    readiness: ResendReadinessEnvelope | null,
    options: {
        loading?: boolean
        error?: boolean
        checkPending?: boolean
        checkError?: boolean
        onCheck?: () => void
        senderConfigured?: boolean
        senderLoading?: boolean
    } = {},
) {
    return render(
        <AgencyInvitesTab
            orgName="Northstar Agency"
            invites={[]}
            inviteOpen={false}
            inviteSubmitting={false}
            inviteResending={null}
            inviteForm={{ email: "", role: "admin" }}
            inviteError={null}
            platformEmailStatus={{
                configured: options.senderConfigured ?? true,
                from_email: options.senderConfigured === false
                    ? null
                    : "invites@example.com",
                provider: "resend",
            }}
            platformEmailStatusLoading={options.senderLoading ?? false}
            platformEmailReadiness={readiness}
            platformEmailReadinessLoading={options.loading ?? false}
            platformEmailReadinessError={options.error ?? false}
            platformEmailCheckPending={options.checkPending ?? false}
            platformEmailCheckError={options.checkError ?? false}
            onCheckPlatformEmailReadiness={options.onCheck ?? vi.fn()}
            {...handlers}
        />,
    )
}

describe("AgencyInvitesTab shared sender readiness", () => {
    it("shows a compact ready summary and starts a read-only check", () => {
        const onCheck = vi.fn()
        renderInvites(readinessEnvelope(), { onCheck })

        const summary = screen.getByTestId("platform-email-readiness")
        expect(
            within(summary).getByText("Shared sender readiness"),
        ).toBeInTheDocument()
        expect(
            within(summary).getByText("Ready", {
                selector: '[data-slot="badge"]',
            }),
        ).toBeInTheDocument()
        expect(within(summary).getByText("Domain ready")).toBeInTheDocument()
        expect(within(summary).getByText("Sending ready")).toBeInTheDocument()
        expect(within(summary).getByText("Webhook ready")).toBeInTheDocument()
        expect(
            within(summary).getByText(/read-only and sends no email/i),
        ).toBeInTheDocument()

        fireEvent.click(
            within(summary).getByRole("button", { name: "Check Resend now" }),
        )
        expect(onCheck).toHaveBeenCalledOnce()
    })

    it("warns about provider readiness without disabling invitation creation", () => {
        renderInvites(
            readinessEnvelope({
                probe_status: "failed",
                overall_status: "needs_attention",
                domain_status: "needs_attention",
                sending_status: "needs_attention",
                webhook_status: "needs_attention",
                issue_codes: ["domain_not_verified", "webhook_missing"],
            }),
        )

        expect(screen.getByText("Shared sender needs attention")).toBeInTheDocument()
        expect(screen.getByText("Sending domain is not fully verified")).toBeInTheDocument()
        expect(screen.getByText("No matching webhook was found")).toBeInTheDocument()
        expect(
            screen.getByText(/status is advisory.*invitation creation remains available/i),
        ).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Invite User" })).toBeEnabled()
    })

    it("preserves the stored sender warning before any live check has run", () => {
        renderInvites(
            readinessEnvelope({
                freshness: "never_checked",
                probe_status: null,
                overall_status: "unknown",
                domain_status: "unknown",
                webhook_status: "unknown",
                sending_status: "unknown",
                delivery_tracking_status: "unknown",
                engagement_tracking_status: "unknown",
                checked_at: null,
                last_success_at: null,
            }),
            { senderConfigured: false },
        )

        expect(
            screen.getByText(
                "Platform sender not configured; invite emails may fail.",
            ),
        ).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Invite User" })).toBeEnabled()
    })

    it.each([
        ["queued", "Check queued"],
        ["running", "Checking Resend…"],
    ] as const)("disables only the provider check while it is %s", (state, label) => {
        renderInvites(readinessEnvelope({}, state))

        expect(screen.getByRole("button", { name: label })).toBeDisabled()
        expect(screen.getByRole("button", { name: "Invite User" })).toBeEnabled()
    })

    it("contains check and load failures without exposing or blocking invite controls", () => {
        const errorView = renderInvites(null, { error: true })
        expect(screen.getByText("Shared sender status unavailable")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Invite User" })).toBeEnabled()
        errorView.unmount()

        renderInvites(readinessEnvelope(), { checkError: true })
        expect(screen.getByText("Couldn’t start the sender check")).toBeInTheDocument()
        expect(screen.queryByText(/raw provider/i)).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Invite User" })).toBeEnabled()
    })
})
