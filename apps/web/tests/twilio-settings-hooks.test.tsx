import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getTwilioReadiness,
    getTwilioSettings,
    queueTwilioReadinessCheck,
    updateTwilioSettings,
    type TwilioReadiness,
    type TwilioSettings,
} from "@/lib/api/twilio"
import {
    READINESS_POLL_INTERVAL_MS,
    READINESS_POLL_TIMEOUT_MS,
    readinessPollInterval,
    twilioKeys,
    useQueueTwilioReadinessCheck,
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
        queueTwilioReadinessCheck: vi.fn(),
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
        vi.mocked(queueTwilioReadinessCheck).mockReset()
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

    it("replaces cached readiness with the snapshot returned when a check is queued", async () => {
        const queuedReadiness = {
            overall_status: "unknown",
            checked_at: null,
            provider: {
                status: "unknown",
                credentials_valid: false,
                account_status: null,
                checked_at: null,
                capabilities: {
                    send_sms: false,
                    send_mms: false,
                    receive_sms: false,
                    receive_mms: false,
                    status_callbacks: false,
                },
                routes: {},
            },
            local: {
                queue: {
                    status: "ready",
                    queued_count: 0,
                    processing_count: 0,
                    failed_count: 0,
                    oldest_queued_at: null,
                },
                reconciliation: {
                    status: "ready",
                    action_required_count: 0,
                    unresolved_event_count: 0,
                    last_reconciled_at: null,
                },
            },
            issues: [],
            gates: [],
        } as unknown as TwilioReadiness
        vi.mocked(queueTwilioReadinessCheck).mockResolvedValue({
            check_status: "queued",
            queued_at: "2026-09-30T06:12:00Z",
            readiness: queuedReadiness,
        })
        const queryClient = createQueryClient()
        const view = renderHook(() => useQueueTwilioReadinessCheck(), {
            wrapper: wrapperFor(queryClient),
        })

        await act(async () => {
            await view.result.current.mutateAsync()
        })

        expect(queueTwilioReadinessCheck).toHaveBeenCalledTimes(1)
        expect(queryClient.getQueryData(twilioKeys.readiness())).toEqual(queuedReadiness)
    })
})

describe("readinessPollInterval", () => {
    const queuedAt = "2026-09-30T06:12:00Z"
    const now = Date.parse(queuedAt) + 10 * 1000
    const readinessCheckedAt = (checkedAt: string | null) =>
        ({ provider: { checked_at: checkedAt } }) as TwilioReadiness

    it("does not poll unless a check is outstanding", () => {
        expect(readinessPollInterval(readinessCheckedAt(null), null, now)).toBe(false)
    })

    it("polls until evidence checked after the queue time arrives", () => {
        expect(readinessPollInterval(undefined, queuedAt, now)).toBe(READINESS_POLL_INTERVAL_MS)
        expect(readinessPollInterval(readinessCheckedAt(null), queuedAt, now)).toBe(
            READINESS_POLL_INTERVAL_MS,
        )
        expect(
            readinessPollInterval(readinessCheckedAt("2026-09-30T06:11:00Z"), queuedAt, now),
        ).toBe(READINESS_POLL_INTERVAL_MS)
        expect(
            readinessPollInterval(readinessCheckedAt("2026-09-30T06:12:05Z"), queuedAt, now),
        ).toBe(false)
    })

    it("stops polling a check that never reported back", () => {
        const later = Date.parse(queuedAt) + READINESS_POLL_TIMEOUT_MS + 1
        expect(readinessPollInterval(readinessCheckedAt(null), queuedAt, later)).toBe(false)
    })
})
