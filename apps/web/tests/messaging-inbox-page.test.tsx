import React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import MessagesPageClient from "../app/(app)/messages/page.client"

const {
    useEffectivePermissions,
    useMessagingConversation,
    useMessagingConversations,
    useLinkMessagingConversation,
    useMarkMessagingConversationRead,
    useUpdateMessagingReconciliation,
} = vi.hoisted(() => ({
    useEffectivePermissions: vi.fn(),
    useMessagingConversation: vi.fn(),
    useMessagingConversations: vi.fn(),
    useLinkMessagingConversation: vi.fn(),
    useMarkMessagingConversationRead: vi.fn(),
    useUpdateMessagingReconciliation: vi.fn(),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: { user_id: "user-1", role: "admin" },
        isLoading: false,
    }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({ useEffectivePermissions }))
vi.mock("@/lib/hooks/use-messaging-inbox", () => ({
    useMessagingConversation,
    useMessagingConversations,
    useLinkMessagingConversation,
    useMarkMessagingConversationRead,
    useUpdateMessagingReconciliation,
}))

const summary = {
    id: "conversation-1",
    contact_id: "contact-1",
    masked_phone: "••• ••• 0110",
    purpose: "operational" as const,
    route_id: "route-1",
    route_label: "Operational route",
    unread_count: 1,
    unlinked: true,
    linked_entities: [],
    last_message_at: "2026-07-31T16:00:00Z",
    last_message_direction: "inbound" as const,
    last_message_preview: "Please send the appointment details.",
}

const detail = {
    ...summary,
    consent_states: { operational: "opted_in", promotional: "unknown" },
    global_suppression_active: false,
    global_suppression_reason: "none",
    messages: [
        {
            id: "message-1",
            direction: "inbound" as const,
            purpose: "operational" as const,
            body: "Please send the appointment details.",
            provider_status: "received",
            is_unread: true,
            created_at: "2026-07-31T16:00:00Z",
            media: [
                {
                    id: "media-1",
                    filename: "appointment.png",
                    content_type: "image/png",
                    byte_size: 1200,
                    scan_status: "clean",
                    provider_deleted: true,
                    quarantined: false,
                },
            ],
            delivery: {
                id: "delivery-1",
                status: "reconciliation_required",
                source_type: "workflow",
                attempt_count: 1,
                max_attempts: 5,
                created_at: "2026-07-31T16:00:00Z",
                completed_at: null,
                last_error_type: "provider_timeout",
                last_error: "Provider acceptance was not confirmed",
                attempts: [
                    {
                        id: "attempt-1",
                        attempt_number: 1,
                        outcome: "ambiguous",
                        started_at: "2026-07-31T16:01:00Z",
                        completed_at: "2026-07-31T16:01:05Z",
                        provider_http_status: null,
                        error_type: "provider_timeout",
                        error_message: "Provider acceptance was not confirmed",
                    },
                ],
                status_events: [
                    {
                        id: "event-1",
                        status: "delivered",
                        received_at: "2026-07-31T16:02:00Z",
                    },
                ],
            },
        },
    ],
    consent_timeline: [
        {
            id: "consent-1",
            purpose: "operational",
            action: "opt_in",
            source: "website_intake",
            occurred_at: "2026-07-31T15:00:00Z",
            instruction_text: null,
            disclosure_hash: "hash",
        },
    ],
    reconciliation_cases: [
        {
            id: "case-1",
            case_type: "ambiguous_delivery",
            status: "action_required",
            reason_code: "provider_timeout",
            detected_at: "2026-07-31T16:02:00Z",
            resolved_at: null,
            resolution_code: null,
            version: 2,
        },
    ],
}

describe("MessagesPageClient", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        useEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_integrations"] },
            isLoading: false,
        })
        useMessagingConversations.mockReturnValue({
            data: { items: [summary], total: 1, limit: 50, offset: 0 },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        useMessagingConversation.mockReturnValue({
            data: detail,
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        useMarkMessagingConversationRead.mockReturnValue({
            mutateAsync: vi.fn().mockResolvedValue(detail),
            isPending: false,
        })
        useLinkMessagingConversation.mockReturnValue({
            mutateAsync: vi.fn().mockResolvedValue(detail),
            isPending: false,
        })
        useUpdateMessagingReconciliation.mockReturnValue({
            mutateAsync: vi.fn().mockResolvedValue({ ...detail.reconciliation_cases[0], status: "resolved" }),
            isPending: false,
        })
    })

    it("renders a masked read-only inbox with friendly operational history", async () => {
        render(<MessagesPageClient />)

        expect(await screen.findByRole("heading", { name: "Messages" })).toBeInTheDocument()
        expect(screen.getAllByText("••• ••• 0110").length).toBeGreaterThan(0)
        expect(screen.getByText("Please send the appointment details.")).toBeInTheDocument()
        expect(screen.getByText("appointment.png")).toBeInTheDocument()
        expect(screen.getByText("Reconciliation required")).toBeInTheDocument()
        expect(screen.getByText("Opted in")).toBeInTheDocument()
        expect(screen.getByRole("combobox", { name: "Read status" })).toHaveTextContent("All messages")
        expect(screen.getByRole("combobox", { name: "Link status" })).toHaveTextContent("All contacts")
        expect(screen.queryByRole("textbox", { name: /message/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument()
        expect(screen.getByText(/Automated workflow and campaign messages only/i)).toBeInTheDocument()
    })

    it("marks the selected conversation read without exposing a reply action", async () => {
        const mutateAsync = vi.fn().mockResolvedValue(detail)
        useMarkMessagingConversationRead.mockReturnValue({ mutateAsync, isPending: false })
        render(<MessagesPageClient />)

        fireEvent.click(await screen.findByRole("button", { name: "Mark as read" }))

        await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith("conversation-1"))
        expect(screen.queryByRole("button", { name: /reply/i })).not.toBeInTheDocument()
    })

    it("shows loading, error, and empty surfaces", () => {
        useMessagingConversations.mockReturnValueOnce({
            data: undefined,
            isLoading: true,
            isError: false,
            refetch: vi.fn(),
        })
        const { rerender } = render(<MessagesPageClient />)
        expect(screen.getByLabelText("Loading messages")).toBeInTheDocument()

        useMessagingConversations.mockReturnValueOnce({
            data: undefined,
            isLoading: false,
            isError: true,
            refetch: vi.fn(),
        })
        rerender(<MessagesPageClient />)
        expect(screen.getByText("Messages could not be loaded")).toBeInTheDocument()

        useMessagingConversations.mockReturnValueOnce({
            data: { items: [], total: 0, limit: 50, offset: 0 },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        rerender(<MessagesPageClient />)
        expect(screen.getByText("No conversations yet")).toBeInTheDocument()
    })
})
