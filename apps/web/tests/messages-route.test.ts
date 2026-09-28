import { describe, expect, it, vi } from "vitest"

const mockRedirect = vi.fn()

vi.mock("next/navigation", () => ({
    redirect: (url: string) => mockRedirect(url),
}))

import MessagesPage from "@/app/(app)/messages/page"

describe("/messages route", () => {
    it("redirects to the SMS/MMS view of the Tickets workspace", () => {
        MessagesPage()
        expect(mockRedirect).toHaveBeenCalledWith("/tickets?view=messages")
    })
})
