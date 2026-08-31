import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import DonorActivityHistoryPage from "@/app/(app)/donors/[id]/history/page"

const mockSearchParams = new URLSearchParams()

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "donor-1" }),
    useSearchParams: () => ({ get: (key: string) => mockSearchParams.get(key) }),
}))

vi.mock("@/components/activity/EntityActivityHistory", () => ({
    EntityActivityHistory: ({ backHref }: { backHref: string }) => (
        <a href={backHref}>Back to details</a>
    ),
}))

describe("DonorActivityHistoryPage", () => {
    it("preserves a safe donor-list return target through the history page", () => {
        mockSearchParams.set("return_to", "/donors?type=egg&page=2")
        render(<DonorActivityHistoryPage />)

        expect(screen.getByRole("link", { name: "Back to details" })).toHaveAttribute(
            "href",
            "/donors/donor-1?return_to=%2Fdonors%3Ftype%3Degg%26page%3D2",
        )
    })

    it("rejects an unsafe return target", () => {
        mockSearchParams.set("return_to", "//evil.example")
        render(<DonorActivityHistoryPage />)

        expect(screen.getByRole("link", { name: "Back to details" })).toHaveAttribute(
            "href",
            "/donors/donor-1?return_to=%2Fdonors",
        )
    })
})
