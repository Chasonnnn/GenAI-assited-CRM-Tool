import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import OpsLoginPageClient from "@/app/ops/login/page.client"

const assignLocation = vi.mocked(window.location.assign)

describe("OpsLoginPageClient", () => {
    beforeEach(() => {
        assignLocation.mockClear()
        window.sessionStorage.clear()
    })

    it("stores the ops return target and shows redirecting feedback", () => {
        render(<OpsLoginPageClient />)

        const button = screen.getByRole("button", { name: /sign in with google/i })
        fireEvent.click(button)

        expect(button).toBeDisabled()
        expect(button).toHaveTextContent("Signing In...")
        expect(window.sessionStorage.getItem("auth_return_to")).toBe("ops")
        expect(assignLocation).toHaveBeenCalledWith(
            expect.stringContaining("/auth/google/login?return_to=ops"),
        )
    })
})
