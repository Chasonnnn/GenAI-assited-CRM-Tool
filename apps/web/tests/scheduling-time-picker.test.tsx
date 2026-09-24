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

    it("uses human-readable timezone labels and pressed semantics for slots", () => {
        const select = vi.fn()
        render(<SchedulingSlotList slots={[slot]} timezone="America/Los_Angeles" selectedStart={slot.start} onSelectStart={select} />)
        const button = screen.getByRole("button", { name: "9:30 AM PDT" })
        expect(button).toHaveAttribute("aria-pressed", "true")
        fireEvent.click(button)
        expect(select).toHaveBeenCalledWith(slot.start)
    })
})
