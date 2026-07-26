import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
    getResendSettings,
    updateResendSettings,
    type ResendSettings,
} from "@/lib/api/resend"
import {
    useResendSettings,
    useUpdateResendSettings,
} from "@/lib/hooks/use-resend"

vi.unmock("@tanstack/react-query")

vi.mock("@/lib/api/resend", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/api/resend")>()
    return {
        ...actual,
        getResendSettings: vi.fn(),
        updateResendSettings: vi.fn(),
    }
})

const unconfiguredSettings: ResendSettings = {
    email_provider: "resend",
    api_key_masked: "re_****",
    from_email: "sender@example.test",
    from_name: null,
    reply_to_email: null,
    verified_domain: "example.test",
    last_key_validated_at: "2026-07-26T12:00:00Z",
    default_sender_user_id: null,
    default_sender_name: null,
    default_sender_email: null,
    webhook_url: "https://api.example.test/webhooks/resend/route",
    webhook_signing_secret_configured: false,
    rate_limit_group_configured: false,
    current_version: 1,
}

const configuredSettings: ResendSettings = {
    ...unconfiguredSettings,
    webhook_signing_secret_configured: true,
    current_version: 2,
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

describe("Resend settings hooks", () => {
    beforeEach(() => {
        vi.mocked(getResendSettings).mockReset()
        vi.mocked(updateResendSettings).mockReset()
    })

    it("publishes the saved configured state before a background refetch finishes", async () => {
        vi.mocked(getResendSettings)
            .mockResolvedValueOnce(unconfiguredSettings)
            .mockReturnValue(new Promise(() => {}))
        vi.mocked(updateResendSettings).mockResolvedValue(configuredSettings)
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        const view = renderHook(
            () => ({
                settings: useResendSettings(),
                update: useUpdateResendSettings(),
            }),
            { wrapper: wrapperFor(queryClient) },
        )

        await waitFor(() => {
            expect(view.result.current.settings.data).toEqual(unconfiguredSettings)
        })

        await act(async () => {
            await view.result.current.update.mutateAsync({
                webhook_signing_secret: "whsec_new_secret",
                expected_version: 1,
            })
        })

        await waitFor(() => {
            expect(view.result.current.settings.data).toEqual(configuredSettings)
        })
    })
})
