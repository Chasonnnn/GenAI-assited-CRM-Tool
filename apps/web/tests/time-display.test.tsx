import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { RelativeTime, UtcDate } from "@/components/ui/time-display"

describe("time display components", () => {
    it("renders UTC calendar dates without locale or timezone drift", () => {
        render(<UtcDate value="2026-06-03T23:30:00.000Z" month="long" />)

        expect(screen.getByText("June 3, 2026")).toBeInTheDocument()
    })

    it("renders relative time from a stable client snapshot", () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date("2026-06-04T23:30:00.000Z"))

        render(<RelativeTime value="2026-06-03T23:30:00.000Z" />)

        expect(screen.getByText("1 day ago")).toBeInTheDocument()

        vi.useRealTimers()
    })

    it("renders fallback text for missing values", () => {
        render(<RelativeTime value={null} fallback="Never" />)

        expect(screen.getByText("Never")).toBeInTheDocument()
    })
})
