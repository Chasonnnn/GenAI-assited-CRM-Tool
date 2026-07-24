import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import { EmailOperationsDashboard } from "@/components/email-operations/EmailOperationsDashboard"
import { ApiError } from "@/lib/api"

const mockUseReadiness = vi.fn()
const mockUseLiveReadiness = vi.fn()
const mockUseRequestReadinessCheck = vi.fn()
const mockUseMessages = vi.fn()
const mockUseMessage = vi.fn()
const mockUseReconciliationCases = vi.fn()
const mockUseRetryReconciliation = vi.fn()
const mockUseDismissReconciliation = vi.fn()
const mockUseLinkReconciliation = vi.fn()
const mockUseConfirmSentReconciliation = vi.fn()
const mockUseConfirmNotSentReconciliation = vi.fn()
const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockFetchNextPage = vi.fn()
const mockFetchNextReconciliationPage = vi.fn()
const mockRefetchReadiness = vi.fn()
const mockRefetchLiveReadiness = vi.fn()
const mockRefetchMessages = vi.fn()
const mockRefetchReconciliation = vi.fn()
const mockRetryReconciliation = vi.fn()
const mockDismissReconciliation = vi.fn()
const mockLinkReconciliation = vi.fn()
const mockConfirmSentReconciliation = vi.fn()
const mockConfirmNotSentReconciliation = vi.fn()
const mockRequestReadinessCheck = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
    }),
}))

vi.mock("@/lib/hooks/use-email-operations", () => ({
    useEmailOperationsReadiness: () => mockUseReadiness(),
    useEmailOperationsLiveReadiness: (options: unknown) =>
        mockUseLiveReadiness(options),
    useRequestEmailOperationsReadinessCheck: () =>
        mockUseRequestReadinessCheck(),
    useEmailOperationsMessages: () => mockUseMessages(),
    useEmailOperationMessage: (messageId: string | null) => mockUseMessage(messageId),
    useEmailReconciliationCases: (options: unknown) =>
        mockUseReconciliationCases(options),
    useRetryEmailReconciliationCorrelation: () => mockUseRetryReconciliation(),
    useDismissEmailReconciliationCase: () => mockUseDismissReconciliation(),
    useLinkEmailReconciliationEvent: () => mockUseLinkReconciliation(),
    useConfirmEmailReconciliationSent: () =>
        mockUseConfirmSentReconciliation(),
    useConfirmEmailReconciliationNotSent: () =>
        mockUseConfirmNotSentReconciliation(),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: (userId: string | null) =>
        mockUseEffectivePermissions(userId),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: (...args: unknown[]) => mockToastSuccess(...args),
    },
}))

const readiness = {
    overall: "ready",
    can_send: true,
    can_track: true,
    provider: "resend",
    provider_scope: "organization",
    provider_account_id: "stored-account",
    recent_webhook_activity: "unknown",
    last_webhook_received_at: null,
    checks: [
        {
            key: "api_key_configured",
            status: "pass",
            detail: "An encrypted Resend API key is stored.",
            observed_at: null,
        },
        {
            key: "recent_webhook_activity",
            status: "unknown",
            detail: "No recent accepted messages require webhook evidence.",
            observed_at: null,
        },
    ],
    summary_24h: {
        messages: 12,
        pending: 1,
        sent: 10,
        failed: 1,
        delivered: 8,
        bounced: 0,
        complained: 0,
        estimated_opens: 19,
        clicks: 6,
        delivery_attempts: 13,
        webhook_events: 27,
    },
} as const

const liveReadiness = {
    check_status: "idle",
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
        checked_at: "2026-07-23T16:00:00Z",
        last_success_at: "2026-07-23T16:00:00Z",
    },
} as const

const message = {
    id: "message-1",
    recipient_email: "recipient@example.com",
    subject: "Welcome to Surrogacy Force",
    from_email: "operations@example.com",
    purpose: "transactional",
    source_type: "invite",
    source_id: "source-1",
    provider: "resend",
    provider_scope: "organization",
    provider_account_id: "stored-account",
    provider_message_id: "provider-message-1",
    status: "sent",
    provider_status: "delivered",
    delivery_status: "sent",
    attempt_count: 2,
    max_attempts: 5,
    created_at: "2026-07-23T12:00:00Z",
    sent_at: "2026-07-23T12:01:00Z",
    delivered_at: "2026-07-23T12:02:00Z",
    bounced_at: null,
    bounce_type: null,
    complained_at: null,
    estimated_opened_at: "2026-07-23T12:03:00Z",
    estimated_open_count: 2,
    clicked_at: "2026-07-23T12:04:00Z",
    click_count: 1,
    open_tracking: "estimated",
} as const

const detail = {
    ...message,
    delivery: {
        id: "delivery-1",
        status: "sent",
        run_at: "2026-07-23T12:00:00Z",
        attempt_count: 2,
        max_attempts: 5,
        first_attempt_at: "2026-07-23T12:00:30Z",
        last_attempt_at: "2026-07-23T12:01:00Z",
        completed_at: "2026-07-23T12:01:00Z",
        last_error_type: null,
        provider_message_id: "provider-message-1",
        created_at: "2026-07-23T12:00:00Z",
        updated_at: "2026-07-23T12:01:00Z",
    },
    attempts: [
        {
            id: "attempt-1",
            attempt_number: 1,
            started_at: "2026-07-23T12:00:30Z",
            completed_at: "2026-07-23T12:00:45Z",
            outcome: "retryable_error",
            provider_http_status: 429,
            error_type: "rate_limited",
            provider_message_id: null,
            retry_after_seconds: 30,
        },
        {
            id: "attempt-2",
            attempt_number: 2,
            started_at: "2026-07-23T12:01:00Z",
            completed_at: "2026-07-23T12:01:02Z",
            outcome: "succeeded",
            provider_http_status: 200,
            error_type: null,
            provider_message_id: "provider-message-1",
            retry_after_seconds: null,
        },
    ],
    provider_events: [
        {
            id: "event-1",
            provider_event_id: "provider-event-1",
            event_type: "email.sent",
            event_created_at: "2026-07-23T12:01:00Z",
            received_at: "2026-07-23T12:01:01Z",
            processed_at: "2026-07-23T12:01:01Z",
        },
        {
            id: "event-2",
            provider_event_id: "provider-event-2",
            event_type: "email.delivered",
            event_created_at: "2026-07-23T12:02:00Z",
            received_at: "2026-07-23T12:02:01Z",
            processed_at: "2026-07-23T12:02:01Z",
        },
    ],
} as const

const reconciliationCase = {
    id: "11111111-1111-4111-8111-111111111111",
    case_type: "orphan_webhook",
    status: "action_required",
    reason_code: "automatic_correlation_exhausted",
    version: 3,
    provider: "resend",
    event_type: "email.delivered",
    event_created_at: "2026-07-23T12:02:00Z",
    received_at: "2026-07-23T12:02:01Z",
    message_id: null,
    delivery_id: null,
    attempt_count: null,
    max_attempts: null,
    next_attempt_at: null,
    available_actions: ["retry_correlation", "link_event"],
    detected_at: "2026-07-23T12:03:00Z",
    updated_at: "2026-07-23T12:04:00Z",
} as const

const unknownDeliveryCase = {
    ...reconciliationCase,
    id: "22222222-2222-4222-8222-222222222222",
    case_type: "unknown_delivery",
    reason_code: "provider_outcome_unknown",
    event_type: null,
    event_created_at: null,
    received_at: null,
    delivery_id: "33333333-3333-4333-8333-333333333333",
    attempt_count: 5,
    max_attempts: 5,
    available_actions: ["confirm_sent", "confirm_not_sent"],
} as const

function reconciliationQueryResult(
    items: readonly unknown[],
    options: {
        actionRequired?: number
        resolved?: number
        nextCursor?: string | null
        hasNextPage?: boolean
    } = {},
) {
    const nextCursor = options.nextCursor ?? null
    return {
        data: {
            pages: [
                {
                    items,
                    next_cursor: nextCursor,
                    counts: {
                        monitoring: 0,
                        action_required:
                            options.actionRequired ?? items.length,
                        resolved: options.resolved ?? 0,
                    },
                },
            ],
        },
        isLoading: false,
        isError: false,
        isFetching: false,
        hasNextPage: options.hasNextPage ?? nextCursor !== null,
        isFetchingNextPage: false,
        fetchNextPage: mockFetchNextReconciliationPage,
        refetch: mockRefetchReconciliation,
    }
}

describe("EmailOperationsDashboard", () => {
    beforeEach(() => {
        mockFetchNextPage.mockReset()
        mockFetchNextReconciliationPage.mockReset()
        mockRefetchReadiness.mockReset()
        mockRefetchLiveReadiness.mockReset()
        mockRefetchMessages.mockReset()
        mockRefetchReconciliation.mockReset()
        mockRetryReconciliation.mockReset()
        mockDismissReconciliation.mockReset()
        mockLinkReconciliation.mockReset()
        mockConfirmSentReconciliation.mockReset()
        mockConfirmNotSentReconciliation.mockReset()
        mockRequestReadinessCheck.mockReset()
        mockToastSuccess.mockReset()
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "case-user-1",
                role: "case_manager",
            },
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: [],
            },
        })
        mockUseReadiness.mockReturnValue({
            data: readiness,
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: mockRefetchReadiness,
        })
        mockUseLiveReadiness.mockReturnValue({
            data: liveReadiness,
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: mockRefetchLiveReadiness,
        })
        mockUseRequestReadinessCheck.mockReturnValue({
            mutate: mockRequestReadinessCheck,
            isPending: false,
            isError: false,
        })
        mockUseMessages.mockReturnValue({
            data: {
                pages: [
                    {
                        items: [message],
                        next_cursor: "next-page",
                    },
                ],
            },
            isLoading: false,
            isError: false,
            isFetching: false,
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextPage,
            refetch: mockRefetchMessages,
        })
        mockUseMessage.mockImplementation((messageId: string | null) => ({
            data: messageId ? detail : undefined,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([]),
        )
        mockUseRetryReconciliation.mockReturnValue({
            mutate: mockRetryReconciliation,
            isPending: false,
            error: null,
            reset: vi.fn(),
        })
        mockUseDismissReconciliation.mockReturnValue({
            mutate: mockDismissReconciliation,
            isPending: false,
            error: null,
            reset: vi.fn(),
        })
        mockUseLinkReconciliation.mockReturnValue({
            mutate: mockLinkReconciliation,
            isPending: false,
            error: null,
            reset: vi.fn(),
        })
        mockUseConfirmSentReconciliation.mockReturnValue({
            mutate: mockConfirmSentReconciliation,
            isPending: false,
            error: null,
            reset: vi.fn(),
        })
        mockUseConfirmNotSentReconciliation.mockReturnValue({
            mutate: mockConfirmNotSentReconciliation,
            isPending: false,
            error: null,
            reset: vi.fn(),
        })
    })

    it("does not request or render the operator queue without manage_ops", () => {
        render(<EmailOperationsDashboard />)

        expect(mockUseReconciliationCases).toHaveBeenCalledWith({
            enabled: false,
            status: "action_required",
        })
        expect(
            screen.queryByRole("heading", { name: "Reconciliation queue" }),
        ).not.toBeInTheDocument()
    })

    it("shows cached live readiness to viewers but hides the provider check action", () => {
        render(<EmailOperationsDashboard />)

        expect(mockUseLiveReadiness).toHaveBeenCalledWith({ enabled: true })
        expect(
            screen.getByRole("heading", { name: "Live Resend readiness" }),
        ).toBeInTheDocument()
        expect(
            screen.queryByRole("button", { name: "Check Resend now" }),
        ).not.toBeInTheDocument()

        const headings = screen.getAllByRole("heading")
        const liveIndex = headings.findIndex(
            (heading) => heading.textContent === "Live Resend readiness",
        )
        const storedIndex = headings.findIndex(
            (heading) =>
                heading.textContent === "Stored configuration and route activity",
        )
        expect(liveIndex).toBeGreaterThanOrEqual(0)
        expect(storedIndex).toBeGreaterThan(liveIndex)
    })

    it.each([
        {
            name: "integration manager",
            user: { user_id: "manager-1", role: "case_manager" },
            permissions: ["manage_integrations"],
        },
        {
            name: "developer",
            user: { user_id: "developer-1", role: "developer" },
            permissions: [],
        },
    ])("allows a $name to start one read-only provider check", ({ user, permissions }) => {
        mockUseAuth.mockReturnValue({ user })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions },
        })

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Check Resend now" }))
        expect(mockRequestReadinessCheck).toHaveBeenCalledOnce()
    })

    it("refreshes the cached live result without starting a provider check", () => {
        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Refresh" }))

        expect(mockRefetchLiveReadiness).toHaveBeenCalledOnce()
        expect(mockRequestReadinessCheck).not.toHaveBeenCalled()
    })

    it("renders only friendly, sanitized reconciliation details for an authorized operator", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([reconciliationCase]),
        )

        render(<EmailOperationsDashboard />)

        expect(mockUseReconciliationCases).toHaveBeenCalledWith({
            enabled: true,
            status: "action_required",
        })
        expect(
            screen.getByRole("heading", { name: "Reconciliation queue" }),
        ).toBeInTheDocument()
        expect(screen.getByText("1 needs action")).toBeInTheDocument()
        expect(screen.getByText("Orphan provider event")).toBeInTheDocument()
        expect(
            screen.getByText("Automatic correlation exhausted"),
        ).toBeInTheDocument()
        expect(screen.queryByText("orphan_webhook")).not.toBeInTheDocument()
        expect(
            screen.queryByText("automatic_correlation_exhausted"),
        ).not.toBeInTheDocument()
        expect(
            screen.queryByText("11111111-1111-4111-8111-111111111111"),
        ).not.toBeInTheDocument()
    })

    it("requires explicit confirmation before retrying local correlation", () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "developer-1",
                role: "developer",
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([reconciliationCase]),
        )
        mockRetryReconciliation.mockImplementation(
            (_input: unknown, options?: { onSuccess?: () => void }) => {
                options?.onSuccess?.()
            },
        )

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Retry correlation" }))
        const dialog = screen.getByRole("alertdialog")
        expect(
            within(dialog).getByText(
                "This retries local matching only. It does not send or resend email.",
            ),
        ).toBeInTheDocument()

        fireEvent.click(
            within(dialog).getByRole("button", { name: "Retry local matching" }),
        )
        expect(mockRetryReconciliation).toHaveBeenCalledWith(
            {
                caseId: reconciliationCase.id,
                expectedVersion: 3,
            },
            expect.any(Object),
        )
        expect(mockToastSuccess).toHaveBeenCalledWith(
            "Local correlation retry started",
        )
        expect(dialog).not.toBeInTheDocument()
    })

    it("shows a controlled conflict message and blocks duplicate retries", () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "developer-1",
                role: "developer",
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([reconciliationCase]),
        )
        mockUseRetryReconciliation.mockReturnValue({
            mutate: mockRetryReconciliation,
            isPending: true,
            error: new ApiError(
                409,
                "Conflict",
                "raw provider conflict detail that must stay hidden",
            ),
            reset: vi.fn(),
        })

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Retry correlation" }))
        const dialog = screen.getByRole("alertdialog")
        expect(
            within(dialog).getByText("This case changed. Refresh and try again."),
        ).toBeInTheDocument()
        expect(
            within(dialog).queryByText(
                "raw provider conflict detail that must stay hidden",
            ),
        ).not.toBeInTheDocument()
        expect(
            within(dialog).getByRole("button", { name: "Retrying..." }),
        ).toBeDisabled()
    })

    it("dismisses only with a controlled operator reason and no-send warning", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([
                {
                    ...reconciliationCase,
                    available_actions: ["dismiss"],
                },
            ]),
        )

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Dismiss case" }))
        const dialog = screen.getByRole("dialog", {
            name: "Dismiss reconciliation case",
        })
        expect(
            within(dialog).getByText(
                "Dismissal removes this case from the operator queue. It does not change message status or send email.",
            ),
        ).toBeInTheDocument()
        expect(
            within(dialog).getByRole("button", { name: "Dismiss case" }),
        ).toBeDisabled()

        fireEvent.click(
            within(dialog).getByRole("radio", {
                name: /Test provider event/,
            }),
        )
        fireEvent.click(
            within(dialog).getByRole("button", { name: "Dismiss case" }),
        )
        expect(mockDismissReconciliation).toHaveBeenCalledWith(
            {
                caseId: reconciliationCase.id,
                expectedVersion: 3,
                resolutionCode: "test_event",
            },
            expect.any(Object),
        )
        expect(within(dialog).queryByText("test_event")).not.toBeInTheDocument()
    })

    it("links an orphan event through a friendly recent-message picker", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([
                {
                    ...reconciliationCase,
                    available_actions: ["link_event"],
                },
            ]),
        )

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Link to message" }))
        const sheet = screen.getByRole("dialog", {
            name: "Link provider event",
        })
        expect(
            within(sheet).getByText(
                "Linking updates local delivery history only. It does not send or resend email.",
            ),
        ).toBeInTheDocument()
        expect(
            within(sheet).getByText("Welcome to Surrogacy Force"),
        ).toBeInTheDocument()
        expect(within(sheet).getByText("recipient@example.com")).toBeInTheDocument()
        expect(within(sheet).queryByText("message-1")).not.toBeInTheDocument()

        fireEvent.click(
            within(sheet).getByRole("button", {
                name: "Select Welcome to Surrogacy Force to recipient@example.com",
            }),
        )
        fireEvent.click(
            within(sheet).getByRole("button", { name: "Link event" }),
        )
        expect(mockLinkReconciliation).toHaveBeenCalledWith(
            {
                caseId: reconciliationCase.id,
                expectedVersion: 3,
                emailLogId: message.id,
            },
            expect.any(Object),
        )
    })

    it("requires provider evidence before confirming a sent delivery", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([
                {
                    ...unknownDeliveryCase,
                    available_actions: ["confirm_sent"],
                },
            ]),
        )

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Confirm sent" }))
        const dialog = screen.getByRole("dialog", {
            name: "Confirm sent delivery",
        })
        expect(
            within(dialog).getByText(
                "Use only after verifying the Resend dashboard. This updates local delivery history and does not send email.",
            ),
        ).toBeInTheDocument()
        const confirm = within(dialog).getByRole("button", {
            name: "Confirm sent",
        })
        expect(confirm).toBeDisabled()

        fireEvent.change(within(dialog).getByLabelText("Resend message ID"), {
            target: { value: "provider-message-verified" },
        })
        fireEvent.click(confirm)
        expect(mockConfirmSentReconciliation).toHaveBeenCalledWith(
            {
                caseId: unknownDeliveryCase.id,
                expectedVersion: 3,
                providerMessageId: "provider-message-verified",
            },
            expect.any(Object),
        )
    })

    it("uses high-friction confirmation before marking a delivery not sent", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValue(
            reconciliationQueryResult([
                {
                    ...unknownDeliveryCase,
                    available_actions: ["confirm_not_sent"],
                },
            ]),
        )

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Confirm not sent" }))
        const dialog = screen.getByRole("alertdialog")
        expect(
            within(dialog).getByText(
                "Use only after verifying the Resend dashboard. This marks the local delivery as not sent. It does not send or resend email.",
            ),
        ).toBeInTheDocument()
        fireEvent.click(
            within(dialog).getByRole("button", { name: "Confirm not sent" }),
        )
        expect(mockConfirmNotSentReconciliation).toHaveBeenCalledWith(
            {
                caseId: unknownDeliveryCase.id,
                expectedVersion: 3,
            },
            expect.any(Object),
        )
    })

    it("renders complete loading, error, empty, and pagination states for the queue", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })
        mockUseReconciliationCases.mockReturnValueOnce({
            data: undefined,
            isLoading: true,
            isError: false,
            isFetching: true,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextReconciliationPage,
            refetch: mockRefetchReconciliation,
        })

        const loadingView = render(<EmailOperationsDashboard />)
        expect(screen.getByText("Loading reconciliation cases")).toBeInTheDocument()
        loadingView.unmount()

        mockUseReconciliationCases.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextReconciliationPage,
            refetch: mockRefetchReconciliation,
        })
        const errorView = render(<EmailOperationsDashboard />)
        const errorTitle = screen.getByText("Reconciliation queue couldn’t load")
        const queueAlert = errorTitle.closest('[role="alert"]')
        expect(queueAlert).not.toBeNull()
        fireEvent.click(
            within(queueAlert as HTMLElement).getByRole("button", {
                name: "Try again",
            }),
        )
        expect(mockRefetchReconciliation).toHaveBeenCalledTimes(1)
        errorView.unmount()

        mockUseReconciliationCases.mockReturnValueOnce(
            reconciliationQueryResult([], { resolved: 2 }),
        )
        const emptyView = render(<EmailOperationsDashboard />)
        expect(screen.getByText("No cases need action")).toBeInTheDocument()
        emptyView.unmount()

        mockUseReconciliationCases.mockReturnValueOnce(
            reconciliationQueryResult([reconciliationCase], {
                actionRequired: 2,
                nextCursor: "next-page",
            }),
        )
        render(<EmailOperationsDashboard />)
        fireEvent.click(
            screen.getByRole("button", { name: "Load more reconciliation cases" }),
        )
        expect(mockFetchNextReconciliationPage).toHaveBeenCalledTimes(1)
    })

    it("includes the protected reconciliation queue in an authorized refresh", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: {
                permissions: ["manage_ops"],
            },
        })

        render(<EmailOperationsDashboard />)

        fireEvent.click(screen.getByRole("button", { name: "Refresh" }))
        expect(mockRefetchReadiness).toHaveBeenCalledTimes(1)
        expect(mockRefetchMessages).toHaveBeenCalledTimes(1)
        expect(mockRefetchReconciliation).toHaveBeenCalledTimes(1)
    })

    it("separates send and tracking readiness while treating no activity as unknown", () => {
        render(<EmailOperationsDashboard />)

        expect(screen.getByRole("heading", { name: "Email Operations" })).toBeInTheDocument()
        const storedReadinessCard = screen
            .getByRole("heading", {
                name: "Stored configuration and route activity",
            })
            .closest('[data-slot="card"]')
        expect(storedReadinessCard).not.toBeNull()
        expect(
            within(storedReadinessCard as HTMLElement).getByText("Ready", {
                selector: '[data-slot="badge"]',
            }),
        ).toBeInTheDocument()
        expect(
            within(screen.getByTestId("sending-readiness")).getByText("Available"),
        ).toBeInTheDocument()
        expect(
            within(screen.getByTestId("tracking-readiness")).getByText("Available"),
        ).toBeInTheDocument()
        expect(screen.getByText("Awaiting first signal")).toBeInTheDocument()
        expect(screen.getAllByText("Organization credential")).not.toHaveLength(0)
        expect(screen.getByText("stored-account")).toBeInTheDocument()
        expect(screen.getByText("12", { selector: '[data-testid="metric-messages"] *' })).toBeInTheDocument()
        expect(screen.getByText("19", { selector: '[data-testid="metric-opens"] *' })).toBeInTheDocument()
        expect(screen.getByText("Open activity is approximate")).toBeInTheDocument()
        expect(
            screen.getByText(/privacy protections and inbox preloading can inflate open counts/i),
        ).toBeInTheDocument()
    })

    it("paginates messages and opens a sanitized attempt and provider-event sheet", () => {
        render(<EmailOperationsDashboard />)

        expect(screen.getByText("Welcome to Surrogacy Force")).toBeInTheDocument()
        expect(screen.getByText("2 estimated opens")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Load more messages" }))
        expect(mockFetchNextPage).toHaveBeenCalledOnce()

        fireEvent.click(
            screen.getByRole("button", {
                name: "View message Welcome to Surrogacy Force to recipient@example.com",
            }),
        )

        const sheet = screen.getByRole("dialog")
        expect(within(sheet).getByRole("heading", { name: "Message details" })).toBeInTheDocument()
        expect(within(sheet).getByText("Attempt 1")).toBeInTheDocument()
        expect(within(sheet).getByText("Rate limited")).toBeInTheDocument()
        expect(within(sheet).getByText("Sent", { selector: '[data-slot="badge"]' })).toBeInTheDocument()
        expect(within(sheet).getByText("Delivered")).toBeInTheDocument()
        expect(within(sheet).getByText("Estimated opens")).toBeInTheDocument()
        expect(within(sheet).queryByText(/private body/i)).not.toBeInTheDocument()
        expect(within(sheet).queryByText(/https?:\/\//i)).not.toBeInTheDocument()
    })

    it.each(["pending", "suppressed", "cancelled"])(
        "does not claim a %s message was sent",
        (status) => {
            mockUseMessage.mockImplementation((messageId: string | null) => ({
                data: messageId
                    ? {
                          ...detail,
                          status,
                          provider_status: null,
                          delivery_status: status,
                          sent_at: null,
                      }
                    : undefined,
                isLoading: false,
                isError: false,
                refetch: vi.fn(),
            }))

            render(<EmailOperationsDashboard />)
            fireEvent.click(
                screen.getByRole("button", {
                    name: "View message Welcome to Surrogacy Force to recipient@example.com",
                }),
            )

            const sheet = screen.getByRole("dialog")
            expect(
                within(sheet).getByText(
                    /Recipient: recipient@example\.com\. Content, headers, and raw provider payloads are intentionally excluded\./,
                ),
            ).toBeInTheDocument()
            expect(
                within(sheet).queryByText(/Sent to recipient@example\.com/),
            ).not.toBeInTheDocument()
        },
    )

    it("uses the outbox delivery status when provider status is not available", () => {
        const reconciliationMessage = {
            ...message,
            status: "pending",
            provider_status: null,
            delivery_status: "reconciliation_required",
        }
        mockUseMessages.mockReturnValue({
            data: {
                pages: [
                    {
                        items: [reconciliationMessage],
                        next_cursor: null,
                    },
                ],
            },
            isLoading: false,
            isError: false,
            isFetching: false,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextPage,
            refetch: mockRefetchMessages,
        })
        mockUseMessage.mockImplementation((messageId: string | null) => ({
            data: messageId
                ? {
                      ...detail,
                      ...reconciliationMessage,
                      delivery: {
                          ...detail.delivery,
                          status: "reconciliation_required",
                      },
                  }
                : undefined,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))

        render(<EmailOperationsDashboard />)
        expect(
            screen.getByText("Needs reconciliation", {
                selector: '[data-slot="badge"]',
            }),
        ).toBeInTheDocument()

        fireEvent.click(
            screen.getByRole("button", {
                name: "View message Welcome to Surrogacy Force to recipient@example.com",
            }),
        )

        expect(
            within(screen.getByRole("dialog")).getAllByText("Needs reconciliation", {
                selector: '[data-slot="badge"]',
            }),
        ).toHaveLength(2)
    })

    it("shows an in-progress delivery attempt as non-destructive", () => {
        mockUseMessage.mockImplementation((messageId: string | null) => ({
            data: messageId
                ? {
                      ...detail,
                      attempts: [
                          {
                              ...detail.attempts[0],
                              completed_at: null,
                              outcome: "in_progress",
                              provider_http_status: null,
                              error_type: null,
                              retry_after_seconds: null,
                          },
                      ],
                  }
                : undefined,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))

        render(<EmailOperationsDashboard />)
        fireEvent.click(
            screen.getByRole("button", {
                name: "View message Welcome to Surrogacy Force to recipient@example.com",
            }),
        )

        expect(
            within(screen.getByRole("dialog")).getByText("In progress", {
                selector: '[data-slot="badge"]',
            }),
        ).toHaveAttribute("data-variant", "secondary")
    })

    it("marks reconciliation-required messages as needing action", () => {
        const reconciliationMessage = {
            ...message,
            status: "pending",
            provider_status: null,
            delivery_status: "reconciliation_required",
        }
        mockUseMessages.mockReturnValue({
            data: {
                pages: [
                    {
                        items: [reconciliationMessage],
                        next_cursor: null,
                    },
                ],
            },
            isLoading: false,
            isError: false,
            isFetching: false,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextPage,
            refetch: mockRefetchMessages,
        })
        mockUseMessage.mockImplementation((messageId: string | null) => ({
            data: messageId
                ? {
                      ...detail,
                      ...reconciliationMessage,
                      delivery: {
                          ...detail.delivery,
                          status: "reconciliation_required",
                      },
                  }
                : undefined,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        }))

        render(<EmailOperationsDashboard />)
        expect(
            screen.getByText("Needs reconciliation", {
                selector: '[data-slot="badge"]',
            }),
        ).toHaveAttribute("data-variant", "destructive")

        fireEvent.click(
            screen.getByRole("button", {
                name: "View message Welcome to Surrogacy Force to recipient@example.com",
            }),
        )

        const reconciliationBadges = within(screen.getByRole("dialog")).getAllByText(
            "Needs reconciliation",
            {
                selector: '[data-slot="badge"]',
            },
        )
        expect(reconciliationBadges).toHaveLength(2)
        expect(reconciliationBadges).toSatisfy((badges: HTMLElement[]) =>
            badges.every((badge) => badge.dataset.variant === "destructive"),
        )
    })

    it("renders a recoverable error state", () => {
        mockUseReadiness.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            refetch: mockRefetchReadiness,
        })
        mockUseMessages.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            isFetching: false,
            hasNextPage: false,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextPage,
            refetch: mockRefetchMessages,
        })

        render(<EmailOperationsDashboard />)

        expect(screen.getByText("Email operations couldn’t load")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(mockRefetchReadiness).toHaveBeenCalledOnce()
        expect(mockRefetchMessages).toHaveBeenCalledOnce()
    })
})
