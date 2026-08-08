import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getTwilioReadiness,
    getTwilioSettings,
    updateTwilioSettings,
    type TwilioSettings,
} from "@/lib/api/twilio"
import {
    twilioKeys,
    useTwilioReadiness,
    useTwilioSettings,
    useUpdateTwilioSettings,
} from "@/lib/hooks/use-twilio"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/twilio", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/twilio")>()
    return {
        ...actual,
        getTwilioSettings: vi.fn(),
        getTwilioReadiness: vi.fn(),
        updateTwilioSettings: vi.fn(),
    }
})

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
    current_version: 4,
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

function wrapperFor(queryClient: QueryClient) {
    return function Wrapper({ children }: { children: ReactNode }) {
        return (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )
    }
}

function createQueryClient() {
    return new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    })
}

describe("Twilio settings hooks", () => {
    beforeEach(() => {
        vi.mocked(getTwilioSettings).mockReset()
        vi.mocked(getTwilioReadiness).mockReset()
        vi.mocked(updateTwilioSettings).mockReset()
    })

    it("does not load organization configuration when the surface is disabled", async () => {
        const queryClient = createQueryClient()

        renderHook(
            () => ({
                settings: useTwilioSettings(false),
                readiness: useTwilioReadiness(false),
            }),
            { wrapper: wrapperFor(queryClient) },
        )

        await Promise.resolve()

        expect(getTwilioSettings).not.toHaveBeenCalled()
        expect(getTwilioReadiness).not.toHaveBeenCalled()
    })

    it("publishes a saved settings snapshot before background revalidation finishes", async () => {
        const savedSettings = { ...settings, current_version: 5 }
        vi.mocked(getTwilioSettings)
            .mockResolvedValueOnce(settings)
            .mockReturnValue(new Promise(() => {}))
        vi.mocked(updateTwilioSettings).mockResolvedValue(savedSettings)
        const queryClient = createQueryClient()
        const view = renderHook(
            () => ({
                settings: useTwilioSettings(),
                update: useUpdateTwilioSettings(),
            }),
            { wrapper: wrapperFor(queryClient) },
        )

        await waitFor(() => {
            expect(view.result.current.settings.data).toEqual(settings)
        })

        await act(async () => {
            await view.result.current.update.mutateAsync({
                enabled: true,
                expected_version: 4,
            })
        })

        expect(queryClient.getQueryData(twilioKeys.settings())).toEqual(savedSettings)
    })
})
