import { describe, expect, it, vi } from "vitest"

const mockRedirect = vi.fn()

vi.mock("next/navigation", () => ({
    redirect: (url: string) => mockRedirect(url),
}))

import SessionsRedirectPage from "@/app/(app)/settings/sessions/page"

describe("/settings/sessions route", () => {
    it("redirects to Settings, where the General tab lists active sessions", () => {
        SessionsRedirectPage()
        expect(mockRedirect).toHaveBeenCalledWith("/settings")
    })
})
