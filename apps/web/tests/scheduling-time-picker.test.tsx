import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { SchedulingSlotList, SchedulingTimePicker } from "@/components/appointments/SchedulingTimePicker"

const slot = { start: "2026-09-30T16:30:00Z", end: "2026-09-30T17:00:00Z" }

describe("SchedulingTimePicker", () => {
    it("makes initial availability failure recoverable before a date is selected", () => {
        const retry = vi.fn()
        render(<SchedulingTimePicker idPrefix="test" date="" onDateChange={vi.fn()} minDate="2026-09-22" timezone="America/New_York" selectedStart={null} onSelectStart={vi.fn()} error="Availability unavailable." onRetry={retry} />)
        expect(screen.getByRole("alert")).toHaveTextContent("Availability unavailable.")
        fireEvent.click(screen.getByRole("button", { name: "Retry availability" }))
        expect(retry).toHaveBeenCalledOnce()
    })

    it("replaces slot selection with labeled required manual fields", () => {
        const changeMode = vi.fn()
        render(<SchedulingTimePicker idPrefix="override" date="2026-09-30" onDateChange={vi.fn()} minDate="2026-09-22" slots={[slot]} timezone="America/New_York" selectedStart={null} onSelectStart={vi.fn()} override={{ enabled: true, onEnabledChange: changeMode, dateTime: "", onDateTimeChange: vi.fn(), reason: "", onReasonChange: vi.fn() }} />)
        expect(screen.queryByRole("group", { name: "Available times" })).not.toBeInTheDocument()
        expect(screen.getByLabelText("Date and time · America/New York")).toBeRequired()
        expect(screen.getByLabelText("Reason required")).toBeRequired()
        fireEvent.click(screen.getByRole("button", { name: "Use available times" }))
        expect(changeMode).toHaveBeenCalledWith(false)
    })

    it("keeps days outside the available dates disabled while a date's times load", () => {
        const { container } = render(<SchedulingTimePicker idPrefix="open" date="2026-09-30" onDateChange={vi.fn()} minDate="2026-09-22" month={new Date(2026, 8, 1)} availableDates={new Set(["2026-09-30", "2026-10-01"])} timezone="America/New_York" selectedStart={null} onSelectStart={vi.fn()} loading />)
        const day = (key: string) => container.querySelector(`[data-day="${key}"] button`)
        expect(day("2026-09-29")).toBeDisabled()
        expect(day("2026-09-30")).toBeEnabled()
        expect(day("2026-10-01")).toBeEnabled()
        expect(container.querySelector('[data-day="2026-10-01"]')).not.toHaveClass("text-muted-foreground")
        expect(day("2026-09-21")).toBeDisabled()
    })

    it("focuses the selected day once for each focus request", () => {
        const props = { idPrefix: "focus", onDateChange: vi.fn(), minDate: "2026-09-22", month: new Date(2026, 8, 1), timezone: "America/New_York", selectedStart: null, onSelectStart: vi.fn() }
        const { container, rerender } = render(<SchedulingTimePicker {...props} date="" loading />)
        const focus = vi.spyOn(HTMLElement.prototype, "focus")
        expect(document.activeElement).toBe(document.body)
        rerender(<SchedulingTimePicker {...props} date="2026-09-28" dateFocusRequest={1} />)
        expect(container.querySelector('[data-day="2026-09-28"] button')).toHaveFocus()
        rerender(<SchedulingTimePicker {...props} date="2026-09-29" dateFocusRequest={1} />)
        expect(focus).toHaveBeenCalledOnce()
        rerender(<SchedulingTimePicker {...props} date="2026-09-29" dateFocusRequest={2} />)
        expect(container.querySelector('[data-day="2026-09-29"] button')).toHaveFocus()
        focus.mockRestore()
    })

    it("focuses the next-month arrow when the selected day is closed", () => {
        render(<SchedulingTimePicker idPrefix="closed" date="2026-09-26" dateFocusRequest={1} onDateChange={vi.fn()} minDate="2026-09-26" month={new Date(2026, 8, 1)} availableDates={new Set()} timezone="America/New_York" selectedStart={null} onSelectStart={vi.fn()} />)
        expect(screen.getByRole("button", { name: /next month/i })).toHaveFocus()
    })

    it("stops the previous-month arrow at the month of the first selectable day", () => {
        const changeMonth = vi.fn()
        render(<SchedulingTimePicker idPrefix="start" date="2026-09-28" onDateChange={vi.fn()} minDate="2026-09-22" month={new Date(2026, 8, 1)} onMonthChange={changeMonth} timezone="America/New_York" selectedStart={null} onSelectStart={vi.fn()} />)
        const previous = screen.getByRole("button", { name: /previous month/i })
        expect(previous).toHaveAttribute("aria-disabled", "true")
        fireEvent.click(previous)
        expect(changeMonth).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("button", { name: /next month/i }))
        expect(changeMonth).toHaveBeenCalledOnce()
    })

    it("marks the calendar busy while the visible month's open days load", () => {
        const props = { idPrefix: "busy", date: "2026-09-28", onDateChange: vi.fn(), minDate: "2026-09-22", month: new Date(2026, 9, 1), availableDates: new Set<string>(), timezone: "America/New_York", selectedStart: null, onSelectStart: vi.fn() }
        const { container, rerender } = render(<SchedulingTimePicker {...props} datesLoading />)
        const calendar = container.querySelector('[data-slot="calendar"]')?.parentElement
        expect(calendar).toHaveAttribute("aria-busy", "true")
        expect(calendar?.querySelector(".animate-spin")).not.toBeNull()
        rerender(<SchedulingTimePicker {...props} datesLoading={false} />)
        expect(calendar).not.toHaveAttribute("aria-busy")
        expect(calendar?.querySelector(".animate-spin")).toBeNull()
    })

    it("uses human-readable timezone labels and pressed semantics for slots", () => {
        const select = vi.fn()
        render(<SchedulingSlotList slots={[slot]} timezone="America/Los_Angeles" selectedStart={slot.start} onSelectStart={select} />)
        const button = screen.getByRole("button", { name: "9:30 AM PDT" })
        expect(button).toHaveAttribute("aria-pressed", "true")
        fireEvent.click(button)
        expect(select).toHaveBeenCalledWith(slot.start)
    })
})
