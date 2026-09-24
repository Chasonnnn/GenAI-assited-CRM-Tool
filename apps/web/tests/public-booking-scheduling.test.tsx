import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { PublicBookingPage } from "../components/appointments/PublicBookingPage"
import { ApiError } from "../lib/api"

const createBookingMock = vi.fn()
const slotStart = "2026-10-02T01:00:00.000Z"

function typeInto(input: HTMLInputElement | HTMLTextAreaElement, value: string) {
    for (const character of value) {
        fireEvent.input(input, { target: { value: input.value + character }, data: character, inputType: "insertText" })
    }
}

vi.mock("@/lib/hooks/use-appointments", () => ({
    usePublicBookingPage: () => ({
        data: {
            staff: { user_id: "staff-1", display_name: "Test Staff", avatar_url: null },
            appointment_types: [{
                id: "type-1", name: "Consultation", duration_minutes: 30,
                meeting_mode: "phone", meeting_modes: ["phone"],
                meeting_location: null, dial_in_number: null, auto_approve: true,
            }],
            org_name: "Test Organization", org_timezone: "America/Los_Angeles",
        },
        isLoading: false,
        error: null,
    }),
    useAvailableSlots: () => ({
        data: { slots: [{ start: slotStart, end: "2026-10-02T01:30:00.000Z" }], appointment_type: null },
        isLoading: false, isError: false, refetch: vi.fn(),
    }),
    useCreateBooking: () => ({ mutate: createBookingMock, isPending: false }),
    useBookingPreviewPage: () => ({ data: null, isLoading: false, error: null }),
    useBookingPreviewSlots: () => ({ data: null, isLoading: false, isError: false, refetch: vi.fn() }),
}))

describe("public booking timezone", () => {
    let dateTimeFormatSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true })
        vi.setSystemTime(new Date("2026-10-01T12:00:00.000Z"))
        createBookingMock.mockReset()
        const originalDateTimeFormat = Intl.DateTimeFormat
        dateTimeFormatSpy = vi.spyOn(Intl, "DateTimeFormat").mockImplementation((
            function MockDateTimeFormat(locales?: Intl.LocalesArgument, options?: Intl.DateTimeFormatOptions) {
                const formatter = originalDateTimeFormat(locales, options)
                if (locales === undefined && options === undefined) {
                    return Object.assign(formatter, {
                        resolvedOptions: () => ({ ...formatter.resolvedOptions(), timeZone: "America/Los_Angeles" }),
                    })
                }
                return formatter
            }
        ) as typeof Intl.DateTimeFormat)
    })

    afterEach(() => {
        dateTimeFormatSpy.mockRestore()
        vi.useRealTimers()
    })

    it("keeps a UTC next-day slot on the Pacific date through contact and confirmation", () => {
        createBookingMock.mockImplementation((_args, callbacks) => callbacks.onSuccess({
            status: "confirmed", scheduled_start: slotStart, meeting_mode: "phone",
            meeting_location: null, dial_in_number: null, zoom_join_url: null, google_meet_url: null,
        }))
        render(<PublicBookingPage publicSlug="test-booking" />)
        fireEvent.click(screen.getByRole("button", { name: "Consultation" }))
        expect(screen.getByText("Choose a date.")).toBeInTheDocument()
        expect(screen.queryByText("No available times on this date.")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "1" }))
        fireEvent.click(screen.getByRole("button", { name: /6:00 PM/ }))
        fireEvent.click(screen.getByRole("button", { name: "Enter contact details" }))

        expect(screen.getByText("Thursday, October 1, 2026")).toBeInTheDocument()
        expect(screen.getByText(/6:00 PM · Pacific Time/)).toBeInTheDocument()
        const name = screen.getByLabelText(/Full name/) as HTMLInputElement
        const email = screen.getByLabelText(/Email/) as HTMLInputElement
        const phone = screen.getByLabelText(/Phone number/) as HTMLInputElement
        const note = screen.getByLabelText(/Note/) as HTMLTextAreaElement
        typeInto(name, "Sample Visitor")
        typeInto(email, "sample@example.com")
        typeInto(phone, "555-0100")
        typeInto(note, "Please call first")
        expect(name).toHaveValue("Sample Visitor")
        expect(email).toHaveValue("sample@example.com")
        expect(phone).toHaveValue("555-0100")
        expect(note).toHaveValue("Please call first")
        fireEvent.click(screen.getByRole("button", { name: "Confirm Appointment" }))

        expect(createBookingMock).toHaveBeenCalledWith(
            expect.objectContaining({ data: expect.objectContaining({
                scheduled_start: slotStart, client_timezone: "America/Los_Angeles",
                client_name: "Sample Visitor", client_email: "sample@example.com", client_phone: "555-0100",
                client_notes: "Please call first",
            }) }),
            expect.any(Object),
        )
        expect(screen.getByText("Thursday, October 1, 2026")).toBeInTheDocument()
        expect(screen.getByText(/6:00 PM · Pacific Time/)).toBeInTheDocument()
        expect(screen.queryByText(/confirmation email|What.s Next|safely close/i)).not.toBeInTheDocument()
    })

    it("shows a rejected email, retains details, and allows a corrected retry", () => {
        createBookingMock
            .mockImplementationOnce((_args, callbacks) => callbacks.onError(
                new ApiError(422, "Unprocessable Entity", "client_email: reserved email domain"),
            ))
            .mockImplementationOnce((_args, callbacks) => callbacks.onSuccess({
                status: "confirmed", scheduled_start: slotStart, meeting_mode: "phone",
                meeting_location: null, dial_in_number: null, zoom_join_url: null, google_meet_url: null,
            }))
        render(<PublicBookingPage publicSlug="test-booking" />)
        fireEvent.click(screen.getByRole("button", { name: "Consultation" }))
        fireEvent.click(screen.getByRole("button", { name: "1" }))
        fireEvent.click(screen.getByRole("button", { name: /6:00 PM/ }))
        fireEvent.click(screen.getByRole("button", { name: "Enter contact details" }))

        const name = screen.getByLabelText(/Full name/) as HTMLInputElement
        const email = screen.getByLabelText(/Email/) as HTMLInputElement
        const phone = screen.getByLabelText(/Phone number/) as HTMLInputElement
        typeInto(name, "Sample Visitor")
        typeInto(email, "sample@example.test")
        typeInto(phone, "555-0100")
        fireEvent.click(screen.getByRole("button", { name: "Confirm Appointment" }))

        expect(screen.getByRole("alert")).toHaveTextContent("Enter a valid email address.")
        expect(email).toHaveAttribute("aria-invalid", "true")
        expect(name).toHaveValue("Sample Visitor")
        expect(email).toHaveValue("sample@example.test")
        expect(phone).toHaveValue("555-0100")
        expect(screen.queryByText("Appointment Confirmed!")).not.toBeInTheDocument()

        fireEvent.input(email, { target: { value: "sample@example.com" } })
        expect(screen.queryByRole("alert")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Confirm Appointment" }))
        expect(createBookingMock).toHaveBeenCalledTimes(2)
        expect(createBookingMock).toHaveBeenLastCalledWith(
            expect.objectContaining({ data: expect.objectContaining({ client_email: "sample@example.com" }) }),
            expect.any(Object),
        )
        expect(screen.getByText("Appointment Confirmed!")).toBeInTheDocument()
    })
})
