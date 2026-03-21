import { useCallback, useEffect, useMemo, useState } from "react"
import { describe, expect, it } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { DateRangePicker, type DateRangePreset } from "@/components/ui/date-range-picker"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

type CustomRange = {
    from: Date | undefined
    to: Date | undefined
}

const VALID_DATE_RANGES: DateRangePreset[] = ["all", "today", "week", "month", "custom"]

const isDateRangePreset = (value: string | null): value is DateRangePreset =>
    value !== null && VALID_DATE_RANGES.includes(value as DateRangePreset)

const parseDateParam = (value: string | null): Date | undefined => {
    if (!value) return undefined
    const parsed = parseDateInput(value)
    return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

const datesEqual = (left?: Date, right?: Date) => (left?.getTime() ?? null) === (right?.getTime() ?? null)

function SurrogatesDateRangeHarness() {
    const [query, setQuery] = useState("")
    const searchParams = useMemo(() => new URLSearchParams(query), [query])

    const initialRange = isDateRangePreset(searchParams.get("range")) ? searchParams.get("range") as DateRangePreset : "all"
    const initialCustomRange = initialRange === "custom"
        ? {
            from: parseDateParam(searchParams.get("from")),
            to: parseDateParam(searchParams.get("to")),
        }
        : { from: undefined, to: undefined }

    const [dateRange, setDateRange] = useState<DateRangePreset>(initialRange)
    const [customRange, setCustomRange] = useState<CustomRange>(initialCustomRange)

    const updateUrlParams = useCallback((
        range: DateRangePreset,
        rangeDates: CustomRange,
    ) => {
        const nextParams = new URLSearchParams(searchParams.toString())

        if (range !== "all") {
            nextParams.set("range", range)
            if (range === "custom") {
                if (rangeDates.from) {
                    nextParams.set("from", formatLocalDate(rangeDates.from))
                } else {
                    nextParams.delete("from")
                }
                if (rangeDates.to) {
                    nextParams.set("to", formatLocalDate(rangeDates.to))
                } else {
                    nextParams.delete("to")
                }
            } else {
                nextParams.delete("from")
                nextParams.delete("to")
            }
        } else {
            nextParams.delete("range")
            nextParams.delete("from")
            nextParams.delete("to")
        }

        setQuery(nextParams.toString())
    }, [searchParams])

    const handlePresetChange = useCallback((preset: DateRangePreset) => {
        setDateRange(preset)
        if (preset !== "custom") {
            setCustomRange({ from: undefined, to: undefined })
        }
        updateUrlParams(
            preset,
            preset === "custom" ? customRange : { from: undefined, to: undefined },
        )
    }, [customRange, updateUrlParams])

    const handleCustomRangeChange = useCallback((range: CustomRange) => {
        setCustomRange(range)
        if (dateRange !== "custom") {
            setDateRange("custom")
        }
        updateUrlParams("custom", range)
    }, [dateRange, updateUrlParams])

    useEffect(() => {
        const nextRange = isDateRangePreset(searchParams.get("range")) ? searchParams.get("range") as DateRangePreset : "all"
        if (nextRange !== dateRange) {
            setDateRange(nextRange)
        }

        if (nextRange === "custom") {
            const nextFrom = parseDateParam(searchParams.get("from"))
            const nextTo = parseDateParam(searchParams.get("to"))
            if (!datesEqual(nextFrom, customRange.from) || !datesEqual(nextTo, customRange.to)) {
                setCustomRange({ from: nextFrom, to: nextTo })
            }
        } else if (customRange.from || customRange.to) {
            setCustomRange({ from: undefined, to: undefined })
        }
    }, [customRange.from, customRange.to, dateRange, searchParams])

    return (
        <div>
            <DateRangePicker
                preset={dateRange}
                onPresetChange={handlePresetChange}
                customRange={customRange}
                onCustomRangeChange={handleCustomRangeChange}
            />
            <output data-testid="query">{query}</output>
        </div>
    )
}

const getCalendarDayButton = (date: Date) => {
    const button = document.querySelector<HTMLButtonElement>(`button[data-day="${date.toLocaleDateString()}"]`)
    expect(button).not.toBeNull()
    return button as HTMLButtonElement
}

const shortDateLabel = (date: Date) =>
    new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date)

const selectCustomRange = (startDate: Date, endDate: Date) => {
    fireEvent.click(screen.getByRole("button", { name: /all time/i }))
    fireEvent.click(screen.getByRole("button", { name: /custom range/i }))
    fireEvent.click(getCalendarDayButton(startDate))
    fireEvent.click(getCalendarDayButton(endDate))

    const applyButton = screen.getByRole("button", { name: /apply/i })
    expect(applyButton).toBeEnabled()
    fireEvent.click(applyButton)
}

function SetterHarness() {
    const [preset, setPreset] = useState<DateRangePreset>("all")
    const [customRange, setCustomRange] = useState<CustomRange>({ from: undefined, to: undefined })

    return (
        <div>
            <DateRangePicker
                preset={preset}
                onPresetChange={setPreset}
                customRange={customRange}
                onCustomRangeChange={setCustomRange}
            />
            <output data-testid="preset">{preset}</output>
            <output data-testid="range">
                {customRange.from ? formatLocalDate(customRange.from) : ""}
                {customRange.to ? `:${formatLocalDate(customRange.to)}` : ""}
            </output>
        </div>
    )
}

describe("DateRangePicker", () => {
    it("uses a stable minimum trigger width for custom date ranges", async () => {
        render(<SetterHarness />)

        const startDate = new Date()
        startDate.setDate(11)
        const endDate = new Date()
        endDate.setDate(13)
        const expectedLabel = `${shortDateLabel(startDate)} - ${shortDateLabel(endDate)}`

        selectCustomRange(startDate, endDate)

        const trigger = await screen.findByRole("button", { name: new RegExp(expectedLabel, "i") })
        expect(trigger).toHaveClass("min-w-[13rem]")
        expect(trigger).not.toHaveClass("w-44")
    })

    it("keeps the first applied custom range in sync with the trigger label", async () => {
        render(<SurrogatesDateRangeHarness />)

        const startDate = new Date()
        startDate.setDate(10)
        const endDate = new Date()
        endDate.setDate(12)
        const expectedLabel = `${shortDateLabel(startDate)} - ${shortDateLabel(endDate)}`

        selectCustomRange(startDate, endDate)

        await waitFor(() => {
            expect(screen.getByTestId("query")).toHaveTextContent(
                `range=custom&from=${formatLocalDate(startDate)}&to=${formatLocalDate(endDate)}`,
            )
        })
        expect(screen.getByRole("button", { name: new RegExp(expectedLabel, "i") })).toBeInTheDocument()
    })

    it("still switches plain setter parents into the custom preset on apply", async () => {
        render(<SetterHarness />)

        const startDate = new Date()
        startDate.setDate(14)
        const endDate = new Date()
        endDate.setDate(18)
        const expectedLabel = `${shortDateLabel(startDate)} - ${shortDateLabel(endDate)}`

        selectCustomRange(startDate, endDate)

        await waitFor(() => {
            expect(screen.getByTestId("preset")).toHaveTextContent("custom")
            expect(screen.getByTestId("range")).toHaveTextContent(
                `${formatLocalDate(startDate)}:${formatLocalDate(endDate)}`,
            )
        })
        expect(screen.getByRole("button", { name: new RegExp(expectedLabel, "i") })).toBeInTheDocument()
    })
})
