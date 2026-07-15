import { render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { PregnancyTrackerCard } from "@/components/surrogates/PregnancyTrackerCard"
import type { SurrogateRead } from "@/lib/types/surrogate"

const TODAY = new Date("2026-07-14T12:00:00-04:00")

function buildSurrogate(
    overrides: Partial<SurrogateRead> = {}
): SurrogateRead {
    return {
        embryo_stage: "day_5",
        pregnancy_start_date: "2026-03-26",
        pregnancy_due_date: "2026-12-12",
        actual_delivery_date: null,
        delivery_baby_gender: null,
        delivery_baby_weight: null,
        ...overrides,
    } as SurrogateRead
}

function renderTracker(overrides: Partial<SurrogateRead> = {}) {
    return render(
        <PregnancyTrackerCard
            surrogateData={buildSurrogate(overrides)}
            onUpdate={vi.fn().mockResolvedValue(undefined)}
        />
    )
}

describe("PregnancyTrackerCard", () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.setSystemTime(TODAY)
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("labels and displays Day-5 gestational age separately from post-transfer time", () => {
        renderTracker()

        expect(screen.getByText("Gestational Age")).toBeInTheDocument()
        expect(screen.getByText("18")).toBeInTheDocument()
        expect(screen.getByText("3")).toBeInTheDocument()
        expect(screen.getByText("weeks")).toBeInTheDocument()
        expect(screen.getByText("days")).toBeInTheDocument()
        expect(screen.getByText("(15w 5d post transfer)")).toBeInTheDocument()
        expect(screen.getByText("150 days remaining")).toBeInTheDocument()
        expect(screen.getByText("Second Trimester")).toBeInTheDocument()
    })

    it.each([
        ["day_3", "18", "1", "Dec 14, 2026"],
        ["day_6", "18", "4", "Dec 11, 2026"],
    ] as const)(
        "keeps the %s IVF offset unchanged",
        (embryoStage, expectedWeeks, expectedDays, expectedDueDate) => {
            renderTracker({
                embryo_stage: embryoStage,
                pregnancy_due_date: null,
            })

            expect(screen.getByText(expectedWeeks)).toBeInTheDocument()
            expect(screen.getByText(expectedDays)).toBeInTheDocument()
            expect(screen.getByText(expectedDueDate)).toBeInTheDocument()
            expect(screen.getByText("calculated")).toBeInTheDocument()
        }
    )

    it("withholds stage-dependent values but preserves a manual due date", () => {
        renderTracker({ embryo_stage: "unknown" })

        expect(screen.getByText("Gestational Age")).toBeInTheDocument()
        expect(screen.getByText("—")).toBeInTheDocument()
        expect(
            screen.getByText("Unavailable until embryo stage is set")
        ).toBeInTheDocument()
        expect(screen.getByText("(15w 5d post transfer)")).toBeInTheDocument()
        expect(screen.getByText("Dec 12, 2026")).toBeInTheDocument()
        expect(
            screen.getByText("150 days remaining · based on manual due date")
        ).toBeInTheDocument()
        expect(screen.getByText("manual")).toBeInTheDocument()
        expect(screen.queryByText("Second Trimester")).not.toBeInTheDocument()
        expect(screen.queryByText("calculated")).not.toBeInTheDocument()
    })

    it("does not invent a calculated due date when embryo stage is unknown", () => {
        renderTracker({
            embryo_stage: "unknown",
            pregnancy_due_date: null,
        })

        expect(
            screen.getByText("Select embryo stage to calculate")
        ).toBeInTheDocument()
        expect(screen.queryByText("calculated")).not.toBeInTheDocument()
        expect(screen.queryByText(/days remaining/)).not.toBeInTheDocument()
    })

    it("retains the existing warning for a future transfer date", () => {
        renderTracker({ pregnancy_start_date: "2026-07-20" })

        expect(
            screen.getByText("Transferred date is in the future (5 days from now)")
        ).toBeInTheDocument()
        expect(screen.queryByText(/post transfer/)).not.toBeInTheDocument()
    })
})
