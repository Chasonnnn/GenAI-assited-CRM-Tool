import { fireEvent, render, screen, within } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ResendLiveReadinessCard } from "@/components/email-operations/ResendLiveReadinessCard"
import type {
    ResendReadinessCapabilityStatus,
    ResendReadinessEnvelope,
} from "@/lib/types/resend-readiness"

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

describe("ResendLiveReadinessCard", () => {
    it("renders a fresh live check with five independently labeled capabilities", () => {
        const onCheck = vi.fn()

        render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope()}
                canCheck
                onCheck={onCheck}
            />,
        )

        expect(
            screen.getByRole("heading", { name: "Live Resend readiness" }),
        ).toBeInTheDocument()
        expect(
            screen.getByText(/read-only and sends no email/i),
        ).toBeInTheDocument()
        expect(screen.getByText("2 verified domains")).toBeInTheDocument()
        expect(screen.getByText("1 enabled webhook")).toBeInTheDocument()

        for (const [testId, label] of [
            ["live-readiness-domain", "Domain"],
            ["live-readiness-sending", "Sending"],
            ["live-readiness-webhook", "Webhook"],
            ["live-readiness-delivery", "Delivery events"],
            ["live-readiness-engagement", "Open and click events"],
        ]) {
            const capability = screen.getByTestId(testId)
            expect(within(capability).getByText(label)).toBeInTheDocument()
            expect(within(capability).getByText("Ready")).toBeInTheDocument()
        }

        fireEvent.click(screen.getByRole("button", { name: "Check Resend now" }))
        expect(onCheck).toHaveBeenCalledOnce()
    })

    it("keeps the live action hidden without integration-management permission", () => {
        render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope()}
                canCheck={false}
                onCheck={vi.fn()}
            />,
        )

        expect(
            screen.queryByRole("button", { name: "Check Resend now" }),
        ).not.toBeInTheDocument()
        expect(
            screen.getByText(/refresh reloads this saved result/i),
        ).toBeInTheDocument()
    })

    it("renders never-checked and stale states without claiming current readiness", () => {
        const neverView = render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope({
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
                })}
                canCheck
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("No live check yet")).toBeInTheDocument()
        expect(
            screen.getByText("Not checked", { selector: '[data-slot="badge"]' }),
        ).toBeInTheDocument()
        neverView.unmount()

        render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope({
                    freshness: "stale",
                    overall_status: "unknown",
                    issue_codes: ["snapshot_stale"],
                })}
                canCheck
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("Saved result is stale")).toBeInTheDocument()
        expect(screen.getByText("Readiness result is out of date")).toBeInTheDocument()
        expect(screen.queryByText("snapshot_stale")).not.toBeInTheDocument()
    })

    it("renders limited and failed probes with friendly closed issue labels", () => {
        const limitedView = render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope({
                    probe_status: "limited",
                    overall_status: "limited",
                    domain_status: "limited",
                    webhook_status: "limited",
                    issue_codes: [
                        "limited_visibility",
                        "credential_rejected",
                        "future_provider_code" as never,
                    ],
                })}
                canCheck
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("Limited provider visibility")).toBeInTheDocument()
        expect(screen.getByText("API key has restricted visibility")).toBeInTheDocument()
        expect(screen.getByText("Resend rejected the stored credential")).toBeInTheDocument()
        expect(
            screen.getByText("Resend readiness needs review"),
        ).toBeInTheDocument()
        expect(screen.queryByText("future_provider_code")).not.toBeInTheDocument()
        limitedView.unmount()

        render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope({
                    probe_status: "failed",
                    overall_status: "needs_attention",
                    sending_status: "needs_attention",
                    issue_codes: ["provider_unavailable"],
                })}
                canCheck
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("Live check failed")).toBeInTheDocument()
        expect(screen.getByText("Resend is temporarily unavailable")).toBeInTheDocument()
    })

    it.each([
        ["queued", "Check queued"],
        ["running", "Checking Resend…"],
    ] as const)("keeps the previous result visible while a check is %s", (state, label) => {
        render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope({}, state)}
                canCheck
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("2 verified domains")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: label })).toBeDisabled()
    })

    it("disables duplicate checks while the request is starting and contains errors", () => {
        const { rerender } = render(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope()}
                canCheck
                isCheckPending
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByRole("button", { name: "Starting check…" })).toBeDisabled()

        rerender(
            <ResendLiveReadinessCard
                envelope={readinessEnvelope()}
                canCheck
                isCheckError
                onCheck={vi.fn()}
            />,
        )

        expect(screen.getByText("Couldn’t start the live check")).toBeInTheDocument()
        expect(screen.queryByText(/provider stack/i)).not.toBeInTheDocument()
    })

    it.each([
        ["ready", "Ready"],
        ["needs_attention", "Needs attention"],
        ["limited", "Limited visibility"],
        ["unknown", "Unknown"],
        ["not_configured", "Not configured"],
    ] as Array<[ResendReadinessCapabilityStatus, string]>)(
        "uses a friendly label for %s capability status",
        (status, label) => {
            render(
                <ResendLiveReadinessCard
                    envelope={readinessEnvelope({
                        domain_status: status,
                    })}
                    canCheck={false}
                    onCheck={vi.fn()}
                />,
            )

            expect(
                within(screen.getByTestId("live-readiness-domain")).getByText(label),
            ).toBeInTheDocument()
        },
    )

    it("renders contained loading and load-error states", () => {
        const loadingView = render(
            <ResendLiveReadinessCard
                isLoading
                canCheck={false}
                onCheck={vi.fn()}
            />,
        )
        expect(screen.getByLabelText("Loading live Resend readiness")).toBeInTheDocument()
        loadingView.unmount()

        render(
            <ResendLiveReadinessCard
                isError
                canCheck={false}
                onCheck={vi.fn()}
            />,
        )
        expect(screen.getByText("Live readiness is unavailable")).toBeInTheDocument()
        expect(
            screen.getByText(/refresh the saved operations data and try again/i),
        ).toBeInTheDocument()
    })
})
