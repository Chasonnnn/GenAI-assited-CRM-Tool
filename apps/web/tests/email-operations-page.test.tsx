import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import { EmailOperationsDashboard } from "@/components/email-operations/EmailOperationsDashboard"

const mockUseReadiness = vi.fn()
const mockUseMessages = vi.fn()
const mockUseMessage = vi.fn()
const mockFetchNextPage = vi.fn()
const mockRefetchReadiness = vi.fn()
const mockRefetchMessages = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
    }),
}))

vi.mock("@/lib/hooks/use-email-operations", () => ({
    useEmailOperationsReadiness: () => mockUseReadiness(),
    useEmailOperationsMessages: () => mockUseMessages(),
    useEmailOperationMessage: (messageId: string | null) => mockUseMessage(messageId),
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

describe("EmailOperationsDashboard", () => {
    beforeEach(() => {
        mockFetchNextPage.mockReset()
        mockRefetchReadiness.mockReset()
        mockRefetchMessages.mockReset()
        mockUseReadiness.mockReturnValue({
            data: readiness,
            isLoading: false,
            isError: false,
            isFetching: false,
            refetch: mockRefetchReadiness,
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
    })

    it("separates send and tracking readiness while treating no activity as unknown", () => {
        render(<EmailOperationsDashboard />)

        expect(screen.getByRole("heading", { name: "Email Operations" })).toBeInTheDocument()
        expect(screen.getByText("Ready", { selector: '[data-slot="badge"]' })).toBeInTheDocument()
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
