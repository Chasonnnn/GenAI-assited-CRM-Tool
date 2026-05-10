import { render } from "@testing-library/react"
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

    it("unregisters each Embla listener it registers", () => {
        const { unmount } = render(
            <Carousel>
                <div>Slide</div>
            </Carousel>
        )

        const reInitHandler = emblaMocks.api.on.mock.calls.find(([event]) => event === "reInit")?.[1]
        const selectHandler = emblaMocks.api.on.mock.calls.find(([event]) => event === "select")?.[1]

        expect(reInitHandler).toEqual(expect.any(Function))
        expect(selectHandler).toEqual(expect.any(Function))

        unmount()

        expect(emblaMocks.api.off).toHaveBeenCalledWith("reInit", reInitHandler)
        expect(emblaMocks.api.off).toHaveBeenCalledWith("select", selectHandler)
    })

    it("does not notify a new setApi callback for an unchanged API instance", () => {
        const firstSetApi = vi.fn()
        const secondSetApi = vi.fn()
        const { rerender } = render(
            <Carousel setApi={firstSetApi}>
                <div>Slide</div>
            </Carousel>
        )

        expect(firstSetApi).toHaveBeenCalledWith(emblaMocks.api)

        rerender(
            <Carousel setApi={secondSetApi}>
                <div>Slide</div>
            </Carousel>
        )

        expect(secondSetApi).not.toHaveBeenCalled()
    })
})
