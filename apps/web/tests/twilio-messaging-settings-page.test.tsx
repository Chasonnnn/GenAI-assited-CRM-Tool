import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import MessagingIntegrationPageClient from "@/app/(app)/settings/integrations/messaging/page.client"
import type { TwilioReadiness, TwilioSettings } from "@/lib/api/twilio"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseTwilioSettings = vi.fn()
const mockUseTwilioReadiness = vi.fn()
const mockUpdateSettings = vi.fn()
const mockTestCredentials = vi.fn()
const mockRefetchSettings = vi.fn()
const mockRefetchReadiness = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastError = vi.fn()

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
        back: vi.fn(),
    }),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: (userId: string | null) =>
        mockUseEffectivePermissions(userId),
}))

vi.mock("@/lib/hooks/use-twilio", () => ({
    useTwilioSettings: (enabled?: boolean) => mockUseTwilioSettings(enabled),
    useTwilioReadiness: (enabled?: boolean) => mockUseTwilioReadiness(enabled),
    useUpdateTwilioSettings: () => ({
        mutateAsync: mockUpdateSettings,
        isPending: false,
    }),
    useTestTwilioCredentials: () => ({
        mutateAsync: mockTestCredentials,
        isPending: false,
    }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: (...args: unknown[]) => mockToastSuccess(...args),
        error: (...args: unknown[]) => mockToastError(...args),
    },
}))

const settings: TwilioSettings = {
    enabled: true,
    account_sid_masked: "AC•••8899",
    api_key_sid_masked: "SK•••4411",
    api_secret_configured: true,
    auth_token_configured: true,
    legal_messaging_brand: "Surrogacy Force",
    operational_disclosure: "Reply STOP to opt out. Message and data rates may apply.",
    promotional_disclosure: "Marketing messages require express consent. Reply STOP to opt out.",
    sms_terms_url: "https://example.test/sms-terms",
    privacy_policy_url: "https://example.test/privacy",
    support_contact: "support@example.test",
    expected_frequency: "Up to 4 messages per month",
    counsel_approved_at: "2026-07-30T12:00:00Z",
    compliance_toolkit_enabled: true,
    twilio_edition: "standard",
    baa_verified_at: null,
    compliance_approved_at: "2026-07-30T13:00:00Z",
    phi_enabled: false,
    current_version: 7,
    routes: {
        operational: {
            purpose: "operational",
            messaging_service_sid_masked: "MG•••0101",
            sender_phone_masked: "+1 ••• ••• 0101",
            a2p_status: "approved",
            advanced_opt_out_status: "enabled",
            consent_management_status: "available",
            capability_evidence: { sms: true, mms: true },
            inbound_webhook_url: "https://api.example.test/webhooks/twilio/inbound/opaque-operational",
            status_callback_url: "https://api.example.test/webhooks/twilio/status/opaque-operational",
            webhook_id: "opaque-operational",
            enabled: true,
        },
        promotional: {
            purpose: "promotional",
            messaging_service_sid_masked: "MG•••0102",
            sender_phone_masked: "+1 ••• ••• 0102",
            a2p_status: "pending",
            advanced_opt_out_status: "enabled",
            consent_management_status: "available",
            capability_evidence: { sms: true, mms: true },
            inbound_webhook_url: "https://api.example.test/webhooks/twilio/inbound/opaque-promotional",
            status_callback_url: "https://api.example.test/webhooks/twilio/status/opaque-promotional",
            webhook_id: "opaque-promotional",
            enabled: false,
        },
    },
}

const readiness: TwilioReadiness = {
    overall_status: "degraded",
    checked_at: "2026-07-31T12:00:00Z",
    provider: {
        status: "degraded",
        credentials_valid: true,
        account_status: "active",
        checked_at: "2026-07-31T12:00:00Z",
        capabilities: {
            send_sms: true,
            send_mms: true,
            receive_sms: true,
            receive_mms: true,
            status_callbacks: true,
        },
        routes: {
            operational: {
                status: "ready",
                can_send_sms: true,
                can_send_mms: true,
                can_receive: true,
                issues: [],
            },
            promotional: {
                status: "degraded",
                can_send_sms: false,
                can_send_mms: false,
                can_receive: true,
                issues: ["A2P registration is pending."],
            },
        },
    },
    local: {
        queue: {
            status: "degraded",
            queued_count: 4,
            processing_count: 1,
            failed_count: 2,
            oldest_queued_at: "2026-07-31T11:45:00Z",
        },
        reconciliation: {
            status: "action_required",
            action_required_count: 2,
            unresolved_event_count: 1,
            last_reconciled_at: "2026-07-31T11:58:00Z",
        },
    },
    issues: [
        {
            code: "promotional_a2p_pending",
            severity: "warning",
            message: "Promotional A2P registration is still pending.",
            route: "promotional",
        },
    ],
}

describe("Messaging integration settings page", () => {
    beforeEach(() => {
        mockUseAuth.mockReset()
        mockUseEffectivePermissions.mockReset()
        mockUseTwilioSettings.mockReset()
        mockUseTwilioReadiness.mockReset()
        mockUpdateSettings.mockReset()
        mockTestCredentials.mockReset()
        mockRefetchSettings.mockReset()
        mockRefetchReadiness.mockReset()
        mockToastSuccess.mockReset()
        mockToastError.mockReset()

        mockUseAuth.mockReturnValue({
            user: {
                user_id: "admin-1",
                role: "admin",
                org_name: "Surrogacy Force",
            },
            isLoading: false,
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["manage_integrations"] },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })
        mockUseTwilioSettings.mockReturnValue({
            data: settings,
            isLoading: false,
            isFetching: false,
            isError: false,
            error: null,
            refetch: mockRefetchSettings,
        })
        mockUseTwilioReadiness.mockReturnValue({
            data: readiness,
            isLoading: false,
            isFetching: false,
            isError: false,
            error: null,
            refetch: mockRefetchReadiness,
        })
        mockUpdateSettings.mockResolvedValue(settings)
        mockTestCredentials.mockResolvedValue({
            valid: true,
            account_status: "active",
            twilio_edition: "standard",
            capabilities: { sms: true, mms: true },
            error: null,
            warning: null,
        })
    })

    it("does not load organization settings without integration-management access", () => {
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "intake-1",
                role: "intake_specialist",
                org_name: "Surrogacy Force",
            },
            isLoading: false,
        })
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: [] },
            isLoading: false,
            isError: false,
            refetch: vi.fn(),
        })

        render(<MessagingIntegrationPageClient />)

        expect(screen.getByText("Messaging settings are restricted")).toBeInTheDocument()
        expect(mockUseTwilioSettings).toHaveBeenCalledWith(false)
        expect(mockUseTwilioReadiness).toHaveBeenCalledWith(false)
    })

    it("keeps provider capability evidence separate from local delivery operations", () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.getByRole("heading", { name: "Messaging delivery" })).toBeInTheDocument()
        const provider = screen.getByRole("region", { name: "Provider readiness" })
        const local = screen.getByRole("region", { name: "Local delivery operations" })

        expect(within(provider).getByText("SMS sending")).toBeInTheDocument()
        expect(within(provider).getByText("MMS sending")).toBeInTheDocument()
        expect(within(local).getByText("4 queued")).toBeInTheDocument()
        expect(within(local).getByText("2 action required")).toBeInTheDocument()
        expect(screen.getByText("Operational route")).toBeInTheDocument()
        expect(screen.getByText("Promotional route")).toBeInTheDocument()
        expect(screen.getByText("A2P approved")).toBeInTheDocument()
        expect(screen.getByText("A2P pending")).toBeInTheDocument()
    })

    it("preserves masked identifiers and write-only secrets when their edit fields stay blank", async () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.getByLabelText("Account SID")).toHaveValue("")
        expect(screen.getByLabelText("API Key SID")).toHaveValue("")
        expect(screen.getByLabelText("API Secret")).toHaveValue("")
        expect(screen.getByLabelText("Auth Token")).toHaveValue("")

        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalledTimes(1))
        const payload = mockUpdateSettings.mock.calls[0]?.[0]
        expect(payload).toMatchObject({
            expected_version: 7,
            legal_messaging_brand: "Surrogacy Force",
        })
        expect(payload).not.toHaveProperty("account_sid")
        expect(payload).not.toHaveProperty("api_key_sid")
        expect(payload).not.toHaveProperty("api_secret")
        expect(payload).not.toHaveProperty("auth_token")
        expect(payload.routes.operational).not.toHaveProperty("messaging_service_sid")
        expect(payload.routes.operational).not.toHaveProperty("sender_phone_e164")
    })

    it("never submits provider-derived route evidence", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalledTimes(1))
        const routes = mockUpdateSettings.mock.calls[0]?.[0].routes
        expect(routes.operational).toEqual({ enabled: true })
        expect(routes.promotional).toEqual({ enabled: false })
    })

    it("renders provider evidence as read-only", async () => {
        mockUseTwilioSettings.mockReturnValue({
            data: {
                ...settings,
                routes: {
                    operational: {
                        ...settings.routes.operational,
                        capability_evidence: null,
                    },
                    promotional: settings.routes.promotional,
                },
            },
            isLoading: false,
            isFetching: false,
            isError: false,
            error: null,
            refetch: mockRefetchSettings,
        })
        render(<MessagingIntegrationPageClient />)

        expect(screen.queryByRole("switch", { name: "Operational SMS capable" })).toBeNull()
        expect(screen.queryByRole("switch", { name: "Operational MMS capable" })).toBeNull()
        expect(screen.getAllByText("SMS not evidenced").length).toBeGreaterThan(0)
        expect(screen.getAllByText("Sender pool not verified").length).toBeGreaterThan(0)
    })

    it("tests unsaved credentials and route services without persisting them", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.change(screen.getByLabelText("Account SID"), {
            target: { value: "AC00000000000000000000000000000000" },
        })
        fireEvent.change(screen.getByLabelText("API Key SID"), {
            target: { value: "SK00000000000000000000000000000000" },
        })
        fireEvent.change(screen.getByLabelText("API Secret"), {
            target: { value: "unsaved-api-secret" },
        })
        fireEvent.change(screen.getByLabelText("Auth Token"), {
            target: { value: "unsaved-auth-token" },
        })
        fireEvent.change(screen.getByLabelText("Operational Messaging Service SID"), {
            target: { value: "MG00000000000000000000000000000001" },
        })
        fireEvent.change(screen.getByLabelText("Promotional Messaging Service SID"), {
            target: { value: "MG00000000000000000000000000000002" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Test connection" }))

        await waitFor(() => {
            expect(mockTestCredentials).toHaveBeenCalledWith({
                account_sid: "AC00000000000000000000000000000000",
                api_key_sid: "SK00000000000000000000000000000000",
                api_secret: "unsaved-api-secret",
                auth_token: "unsaved-auth-token",
                routes: {
                    operational: {
                        messaging_service_sid: "MG00000000000000000000000000000001",
                    },
                    promotional: {
                        messaging_service_sid: "MG00000000000000000000000000000002",
                    },
                },
            })
        })
        expect(mockUpdateSettings).not.toHaveBeenCalled()
        expect(screen.getByText("Connection verified. No message was sent.")).toBeInTheDocument()
    })

    it("requires exact E.164 sender numbers before saving a route", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.change(screen.getByLabelText("Operational sender number"), {
            target: { value: "(415) 555-0101" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        expect(await screen.findByText("Use an exact +1 E.164 sender, for example +14155550101.")).toBeInTheDocument()
        expect(mockUpdateSettings).not.toHaveBeenCalled()
    })

    it("clears stored credentials only after an explicit clear choice", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("checkbox", { name: "Clear saved Auth Token" }))
        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalledTimes(1))
        expect(mockUpdateSettings.mock.calls[0]?.[0]).toMatchObject({ auth_token: "" })
    })
})
