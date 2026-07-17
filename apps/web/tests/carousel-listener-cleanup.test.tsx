import { fireEvent, render } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"

const emblaMocks = vi.hoisted(() => {
    const api = {
        canScrollPrev: vi.fn(() => false),
        canScrollNext: vi.fn(() => true),
        scrollPrev: vi.fn(),
        scrollNext: vi.fn(),
        on: vi.fn(),
        off: vi.fn(),
    }
    const carouselRef = vi.fn()

    return { api, carouselRef }
})

vi.mock("embla-carousel-react", () => ({
    default: vi.fn(() => [emblaMocks.carouselRef, emblaMocks.api]),
}))

import { Carousel } from "@/components/ui/carousel"

describe("Carousel listener cleanup", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("renders the carousel as a named native region", () => {
        const { getByRole } = render(
            <Carousel>
                <div>Slide</div>
            </Carousel>
        )

        const carousel = getByRole("region", { name: "Carousel" })

        expect(carousel.tagName).toBe("SECTION")
    })

    it("does not register Embla listeners when there is no state to synchronize", () => {
        render(
            <Carousel>
                <div>Slide</div>
            </Carousel>
        )

        expect(emblaMocks.api.on).not.toHaveBeenCalled()
        expect(emblaMocks.api.off).not.toHaveBeenCalled()
    })

    it("keeps arrow key carousel navigation wired to Embla", () => {
        const { getByRole } = render(
            <Carousel>
                <div>Slide</div>
            </Carousel>
        )

        const carousel = getByRole("region", { name: "Carousel" })

        fireEvent.keyDown(carousel, { key: "ArrowRight" })
        fireEvent.keyDown(carousel, { key: "ArrowLeft" })

        expect(emblaMocks.api.scrollNext).toHaveBeenCalledTimes(1)
        expect(emblaMocks.api.scrollPrev).toHaveBeenCalledTimes(1)
    })
})
