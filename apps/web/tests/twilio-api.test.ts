import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getTwilioReadiness,
    getTwilioSettings,
    testTwilioCredentials,
    updateTwilioSettings,
} from "@/lib/api/twilio"

const mockGet = vi.fn()
const mockPatch = vi.fn()
const mockPost = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        patch: (...args: unknown[]) => mockPatch(...args),
        post: (...args: unknown[]) => mockPost(...args),
    },
}))

describe("Twilio configuration API", () => {
    beforeEach(() => {
        mockGet.mockReset()
        mockPatch.mockReset()
        mockPost.mockReset()
        mockGet.mockResolvedValue({})
        mockPatch.mockResolvedValue({})
        mockPost.mockResolvedValue({})
    })

    it("reads organization settings and readiness from separate endpoints", async () => {
        await getTwilioSettings()
        await getTwilioReadiness()

        expect(mockGet).toHaveBeenNthCalledWith(1, "/twilio/settings")
        expect(mockGet).toHaveBeenNthCalledWith(2, "/twilio/readiness")
    })

    it("patches versioned settings without reshaping the two messaging routes", async () => {
        const update = {
            enabled: true,
            legal_messaging_brand: "Surrogacy Force",
            expected_version: 4,
            routes: {
                operational: {
                    messaging_service_sid: "MG00000000000000000000000000000001",
                    sender_phone_e164: "+14155550101",
                    enabled: true,
                },
                promotional: {
                    messaging_service_sid: "MG00000000000000000000000000000002",
                    sender_phone_e164: "+14155550102",
                    enabled: false,
                },
            },
        } as const

        await updateTwilioSettings(update)

        expect(mockPatch).toHaveBeenCalledWith("/twilio/settings", update)
    })

    it("tests unsaved credentials without sending a message", async () => {
        const request = {
            account_sid: "AC00000000000000000000000000000000",
            api_key_sid: "SK00000000000000000000000000000000",
            api_secret: "write-only-secret",
            auth_token: "write-only-token",
            routes: {
                operational: {
                    messaging_service_sid: "MG00000000000000000000000000000001",
                },
                promotional: {
                    messaging_service_sid: "MG00000000000000000000000000000002",
                },
            },
        }

        await testTwilioCredentials(request)

        expect(mockPost).toHaveBeenCalledWith("/twilio/settings/test", request)
    })
})
