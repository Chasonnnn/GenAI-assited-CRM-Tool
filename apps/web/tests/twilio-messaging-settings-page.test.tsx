import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import MessagingIntegrationPageClient from "@/app/(app)/settings/integrations/messaging/page.client"
import type { TwilioReadiness, TwilioReadinessGate, TwilioSettings } from "@/lib/api/twilio"

const mockUseAuth = vi.fn()
const mockUseEffectivePermissions = vi.fn()
const mockUseTwilioSettings = vi.fn()
const mockUseTwilioReadiness = vi.fn()
const mockUpdateSettings = vi.fn()
const mockTestCredentials = vi.fn()
const mockQueueReadinessCheck = vi.fn()
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

vi.mock("@/lib/hooks/use-twilio", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/hooks/use-twilio")>()
    return {
        ...actual,
        useTwilioSettings: (enabled?: boolean) => mockUseTwilioSettings(enabled),
        useTwilioReadiness: (enabled?: boolean, awaitingCheckSince?: string | null) =>
            mockUseTwilioReadiness(enabled, awaitingCheckSince),
        useUpdateTwilioSettings: () => ({
            mutateAsync: mockUpdateSettings,
            isPending: false,
        }),
        useTestTwilioCredentials: () => ({
            mutateAsync: mockTestCredentials,
            isPending: false,
        }),
        useQueueTwilioReadinessCheck: () => ({
            mutateAsync: mockQueueReadinessCheck,
            isPending: false,
        }),
    }
})

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
            a2p_status: "unconfigured",
            advanced_opt_out_status: "verified",
            consent_management_status: "unknown",
            capability_evidence: { provider: { sms: true, mms: true, sender_in_pool: true } },
            inbound_webhook_url: "https://api.example.test/webhooks/twilio/inbound/opaque-operational",
            status_callback_url: "https://api.example.test/webhooks/twilio/status/opaque-operational",
            webhook_id: "opaque-operational",
            enabled: true,
        },
        promotional: {
            purpose: "promotional",
            messaging_service_sid_masked: null,
            sender_phone_masked: null,
            a2p_status: "unconfigured",
            advanced_opt_out_status: "unconfigured",
            consent_management_status: "unknown",
            capability_evidence: null,
            inbound_webhook_url: "https://api.example.test/webhooks/twilio/inbound/opaque-promotional",
            status_callback_url: "https://api.example.test/webhooks/twilio/status/opaque-promotional",
            webhook_id: "opaque-promotional",
            enabled: false,
        },
    },
}

const gates: TwilioReadinessGate[] = [
    { key: "messaging_enabled", label: "Organization messaging", status: "pass", detail: null, route: null },
    { key: "connection", label: "Connection", status: "pass", detail: "Account AC•••8899 is active.", route: null },
    { key: "consent_record", label: "Consent record", status: "pass", detail: "Surrogacy Force", route: null },
    { key: "dispatch_worker", label: "Dispatch worker", status: "fail", detail: "The messaging dispatch worker is disabled.", route: null },
    { key: "operational_route", label: "Operational route", status: "pass", detail: "+1•••0101 · toll-free", route: "operational" },
    { key: "operational_sender_registration", label: "Toll-free verification", status: "pass", detail: "Approved by Twilio.", route: "operational" },
    { key: "operational_inbound_webhook", label: "Inbound replies", status: "pending", detail: "Run a readiness check for the current settings.", route: "operational" },
]

const readiness: TwilioReadiness = {
    overall_status: "blocked",
    checked_at: null,
    provider: {
        status: "ready",
        credentials_valid: true,
        account_status: "active",
        checked_at: null,
        capabilities: {
            send_sms: false,
            send_mms: false,
            receive_sms: true,
            receive_mms: true,
            status_callbacks: true,
        },
        routes: {
            operational: {
                status: "blocked",
                can_send_sms: false,
                can_send_mms: false,
                can_receive: true,
                sender_type: "toll_free",
                toll_free_verification_status: "TWILIO_APPROVED",
                issues: ["The messaging dispatch worker is disabled."],
            },
            promotional: {
                status: "not_configured",
                can_send_sms: false,
                can_send_mms: false,
                can_receive: false,
                sender_type: null,
                toll_free_verification_status: null,
                issues: ["Messaging Service and sender are not configured."],
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
            code: "messaging_dispatch_worker_disabled",
            severity: "error",
            message: "The messaging dispatch worker is disabled.",
            route: "operational",
        },
        {
            code: "twilio_provider_check_failed",
            severity: "error",
            message: "The last no-send Twilio provider check failed.",
            route: null,
        },
    ],
    gates,
}

const queuedAt = new Date().toISOString()

function readinessResult(data: TwilioReadiness = readiness) {
    return {
        data,
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
        refetch: mockRefetchReadiness,
    }
}

function settingsResult(data: TwilioSettings = settings) {
    return {
        data,
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
        refetch: mockRefetchSettings,
    }
}

describe("Messaging integration settings page", () => {
    beforeEach(() => {
        mockUseAuth.mockReset()
        mockUseEffectivePermissions.mockReset()
        mockUseTwilioSettings.mockReset()
        mockUseTwilioReadiness.mockReset()
        mockUpdateSettings.mockReset()
        mockTestCredentials.mockReset()
        mockQueueReadinessCheck.mockReset()
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
        mockUseTwilioSettings.mockReturnValue(settingsResult())
        mockUseTwilioReadiness.mockReturnValue(readinessResult())
        mockUpdateSettings.mockResolvedValue(settings)
        mockTestCredentials.mockResolvedValue({
            valid: true,
            account_status: "active",
            twilio_edition: "standard",
            capabilities: { sms: true, mms: true },
            route_capabilities: {},
            error: null,
            warning: null,
        })
        mockQueueReadinessCheck.mockResolvedValue({
            check_status: "queued",
            queued_at: queuedAt,
            readiness,
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

        expect(screen.getByRole("heading", { level: 1, name: "Messaging delivery" })).toBeInTheDocument()
        expect(screen.getByRole("heading", { level: 2, name: "Messaging settings are restricted" })).toBeInTheDocument()
        expect(mockUseTwilioSettings).toHaveBeenCalledWith(false)
        expect(mockUseTwilioReadiness).toHaveBeenCalledWith(false, null)
    })

    it("lists one launch gate per requirement with its status", () => {
        render(<MessagingIntegrationPageClient />)

        const list = screen.getByRole("list", { name: "Launch gates" })
        const rows = within(list).getAllByRole("listitem")
        expect(rows).toHaveLength(gates.length)
        expect(within(rows[3]!).getByText("Dispatch worker")).toBeInTheDocument()
        expect(within(rows[3]!).getByText("The messaging dispatch worker is disabled.")).toBeInTheDocument()
        expect(within(rows[3]!).getByText("Blocked")).toBeInTheDocument()
        expect(within(rows[6]!).getByText("Inbound replies")).toBeInTheDocument()
        expect(within(rows[6]!).getByText("Check required")).toBeInTheDocument()
        expect(screen.getByRole("status", { name: "Last readiness check" })).toHaveTextContent("Settings changed since the last check")

        const local = screen.getByRole("region", { name: "Local delivery operations" })
        expect(within(local).getByText("4 queued")).toBeInTheDocument()
        expect(within(local).getByText("2 action required")).toBeInTheDocument()

        // Issues already represented by a gate are not repeated; others still surface.
        const issues = screen.getByRole("list", { name: "Other issues" })
        expect(within(issues).getAllByRole("listitem")).toHaveLength(1)
        expect(within(issues).getByText("The last no-send Twilio provider check failed.")).toBeInTheDocument()
    })

    it("queues a readiness check from the header and polls until fresh evidence arrives", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("button", { name: "Run readiness check" }))

        await waitFor(() => expect(mockQueueReadinessCheck).toHaveBeenCalledTimes(1))
        await waitFor(() =>
            expect(mockUseTwilioReadiness).toHaveBeenLastCalledWith(true, queuedAt),
        )
        expect(screen.getByRole("button", { name: "Checking" })).toBeDisabled()
        expect(screen.getByRole("status", { name: "Last readiness check" })).toHaveTextContent("Checking with Twilio")
    })

    it("summarizes saved credentials until the operator chooses to replace them", () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.queryByLabelText("Account SID")).toBeNull()
        const summary = screen.getByLabelText("Saved credentials")
        expect(within(summary).getByText("AC•••8899")).toBeInTheDocument()
        expect(within(summary).getAllByText("Stored")).toHaveLength(2)

        fireEvent.click(screen.getByRole("button", { name: "Replace credentials" }))

        expect(screen.getByLabelText("Account SID")).toHaveValue("")
        expect(screen.getByLabelText("Auth Token")).toHaveValue("")
        expect(screen.getByLabelText("Account SID")).toHaveAttribute("placeholder", "Leave blank to keep saved value")

        fireEvent.click(screen.getByRole("button", { name: "Cancel replacing credentials" }))

        expect(screen.queryByLabelText("Account SID")).toBeNull()
    })

    it("labels a toll-free route by its verification instead of an A2P campaign", () => {
        render(<MessagingIntegrationPageClient />)

        const route = screen.getByLabelText("Operational route summary")
        expect(within(route).getByText("Toll-free verification")).toBeInTheDocument()
        expect(within(route).getByText("Toll-free")).toBeInTheDocument()
        expect(within(route).queryByText(/A2P/)).toBeNull()
        const inbound = within(route).getByText("Inbound replies").closest("div")
        expect(within(inbound!).getByText("Check required")).toBeInTheDocument()
        expect(within(route).queryByText("Consent API")).toBeNull()
        expect(within(route).queryByText("Advanced Opt-Out")).toBeNull()
        expect(within(route).getByText("SMS evidenced")).toBeInTheDocument()
        expect(within(route).getByText("Sender pool verified")).toBeInTheDocument()
    })

    it("offers to set up an unconfigured route instead of showing empty fields", () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.getByText("No sender or Messaging Service saved.")).toBeInTheDocument()
        expect(screen.queryByLabelText("Promotional Messaging Service SID")).toBeNull()

        fireEvent.click(screen.getByRole("button", { name: "Set up route" }))

        expect(screen.getByLabelText("Promotional Messaging Service SID")).toHaveValue("")
        expect(screen.getByLabelText("Promotional sender number")).toHaveValue("")
    })

    it("keeps webhook URLs behind a disclosure with the shared copy button", () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.queryByLabelText("Operational inbound webhook URL")).toBeNull()

        fireEvent.click(screen.getAllByRole("button", { name: "Webhooks" })[0]!)

        const inbound = screen.getByLabelText("Operational inbound webhook URL")
        expect(inbound).toHaveValue("https://api.example.test/webhooks/twilio/inbound/opaque-operational")
        expect(inbound).toHaveAttribute("readonly")
        expect(screen.getByRole("button", { name: "Copy Operational inbound webhook URL" })).toBeInTheDocument()
    })

    it("shows the save bar only once the draft differs from the saved settings", async () => {
        render(<MessagingIntegrationPageClient />)

        expect(screen.queryByRole("button", { name: "Save messaging settings" })).toBeNull()

        fireEvent.click(screen.getByRole("switch", { name: "Organization messaging" }))

        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalledTimes(1))
        const payload = mockUpdateSettings.mock.calls[0]?.[0]
        expect(payload).toMatchObject({
            enabled: false,
            expected_version: 7,
            legal_messaging_brand: "Surrogacy Force",
        })
        expect(payload).not.toHaveProperty("account_sid")
        expect(payload).not.toHaveProperty("auth_token")
        expect(payload.routes).toEqual({
            operational: { enabled: true },
            promotional: { enabled: false },
        })
    })

    it("discards unsaved changes and closes open editors", () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("button", { name: "Edit operational route" }))
        fireEvent.change(screen.getByLabelText("Operational sender number"), {
            target: { value: "+14155550199" },
        })
        expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Discard" }))

        expect(screen.queryByRole("region", { name: "Unsaved changes" })).toBeNull()
        expect(screen.queryByLabelText("Operational sender number")).toBeNull()
        expect(mockUpdateSettings).not.toHaveBeenCalled()
    })

    it("tests unsaved credentials and route services without persisting them", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("button", { name: "Replace credentials" }))
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
        fireEvent.click(screen.getByRole("button", { name: "Edit operational route" }))
        fireEvent.change(screen.getByLabelText("Operational Messaging Service SID"), {
            target: { value: "MG00000000000000000000000000000001" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Set up route" }))
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

        fireEvent.click(screen.getByRole("button", { name: "Edit operational route" }))
        fireEvent.change(screen.getByLabelText("Operational sender number"), {
            target: { value: "(415) 555-0101" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        expect(await screen.findByText("Use an exact +1 E.164 sender, for example +14155550101.")).toBeInTheDocument()
        expect(mockUpdateSettings).not.toHaveBeenCalled()
    })

    it("clears stored credentials only after an explicit clear choice", async () => {
        render(<MessagingIntegrationPageClient />)

        fireEvent.click(screen.getByRole("button", { name: "Replace credentials" }))
        fireEvent.click(screen.getByRole("checkbox", { name: "Clear saved Auth Token" }))
        fireEvent.click(screen.getByRole("button", { name: "Save messaging settings" }))

        await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalledTimes(1))
        expect(mockUpdateSettings.mock.calls[0]?.[0]).toMatchObject({ auth_token: "" })
    })

    it("shows the consent record read-only until edited", () => {
        render(<MessagingIntegrationPageClient />)

        const record = screen.getByLabelText("Consent record")
        expect(within(record).getByText("Surrogacy Force")).toBeInTheDocument()
        expect(within(record).getByRole("link", { name: "example.test/sms-terms" })).toHaveAttribute(
            "href",
            "https://example.test/sms-terms",
        )
        expect(screen.queryByLabelText("Legal messaging brand")).toBeNull()

        fireEvent.click(screen.getByRole("button", { name: "Edit consent and disclosure" }))

        expect(screen.getByLabelText("Legal messaging brand")).toHaveValue("Surrogacy Force")
    })
})
