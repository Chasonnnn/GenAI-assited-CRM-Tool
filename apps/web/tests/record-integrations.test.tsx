import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RecordAppointmentsCard } from "@/components/records/RecordAppointmentsCard"
import { RecordCorrespondenceCard } from "@/components/records/RecordCorrespondenceCard"

const mocks = vi.hoisted(() => ({ appointments: vi.fn(), get: vi.fn(), put: vi.fn(), remove: vi.fn(), tickets: vi.fn(), refetch: vi.fn(), types: vi.fn(), create: vi.fn() }))
vi.mock("@/lib/hooks/use-appointments", () => ({
    appointmentKeys: { all: ["appointments"] },
    useAppointments: (params: unknown, options: unknown) => mocks.appointments(params, options),
    useAppointmentTypes: () => mocks.types(),
    useBookingPreviewSlots: () => ({ data: { slots: [{ start: "2026-09-12T14:00:00Z", end: "2026-09-12T14:30:00Z" }] }, isLoading: false, isError: false }),
}))
vi.mock("@/components/appointments/AppointmentsList", () => ({ AppointmentDetailDialog: ({ appointmentId, open }: { appointmentId: string | null; open: boolean }) => open ? <div role="dialog">Manage {appointmentId}</div> : null }))
vi.mock("@/lib/api", () => ({ default: { get: (...args: unknown[]) => mocks.get(...args), put: (...args: unknown[]) => mocks.put(...args), delete: (...args: unknown[]) => mocks.remove(...args) } }))
vi.mock("@/lib/api/appointments", () => ({ createStaffAppointment: (...args: unknown[]) => mocks.create(...args) }))
vi.mock("@/lib/api/tickets", () => ({ getTickets: (...args: unknown[]) => mocks.tickets(...args) }))
vi.mock("@/components/app-link", () => ({ default: ({ children, href, ...props }: React.ComponentProps<"a">) => <a href={href} {...props}>{children}</a> }))

function mount(children: React.ReactNode) {
    return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{children}</QueryClientProvider>)
}
const record = { kind: "donor" as const, id: "donor-1", name: "QA Donor", email: "qa@example.com", phone: "6075550100" }

beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] })
    vi.setSystemTime(new Date("2026-09-01T12:00:00Z"))
    vi.clearAllMocks()
    mocks.appointments.mockReturnValue({ data: { items: [], pages: 0 }, isLoading: false, isError: false, refetch: mocks.refetch })
    mocks.types.mockReturnValue({ data: [], isLoading: false, isError: false })
    mocks.create.mockResolvedValue({ id: "new-appointment" })
    mocks.get.mockResolvedValue({ items: [], total: 0 })
    mocks.put.mockResolvedValue(undefined)
    mocks.remove.mockResolvedValue(undefined)
    mocks.tickets.mockResolvedValue({ items: [{ id: "ticket-1", ticket_code: "T1001", subject: "QA conversation" }] })
})

afterEach(() => vi.useRealTimers())

describe("Light record appointments", () => {
    it("queries the explicit donor and opens the existing management dialog", () => {
        mocks.appointments.mockReturnValue({ data: { items: [{ id: "appointment-1", appointment_type_name: "Consultation", scheduled_start: "2026-09-12T14:00:00Z", status: "confirmed" }], pages: 1 }, isLoading: false, isError: false })
        mount(<RecordAppointmentsCard record={record} canView canCreate archived={false} />)
        expect(screen.getByText("Confirmed")).toBeInTheDocument()
        expect(mocks.appointments).toHaveBeenCalledWith({ donor_id: "donor-1", page: 1, per_page: 10 }, { enabled: true })
        fireEvent.click(screen.getByRole("button", { name: /Consultation/ }))
        expect(screen.getByRole("dialog")).toHaveTextContent("Manage appointment-1")
    })
    it("supports empty, loading and retry states while suppressing archived scheduling", () => {
        const view = mount(<RecordAppointmentsCard record={record} canView canCreate archived />)
        expect(screen.getByText("No appointments")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Schedule" })).not.toBeInTheDocument()
        view.unmount()
        mocks.appointments.mockReturnValue({ isLoading: true })
        const loading = mount(<RecordAppointmentsCard record={record} canView canCreate archived={false} />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading appointments")
        loading.unmount()
        mocks.appointments.mockReturnValue({ isLoading: false, isError: true, refetch: mocks.refetch })
        mount(<RecordAppointmentsCard record={record} canView canCreate archived={false} />)
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(mocks.refetch).toHaveBeenCalled()
    })
    it("schedules an appointment with an explicitly selected case and attempt", async () => {
        mocks.types.mockReturnValue({ data: [{ id: "type-1", name: "Consultation" }], isLoading: false, isError: false })
        mocks.get.mockImplementation((path: string) => Promise.resolve(path.endsWith("/attempts") ? [{ id: "attempt-1", match_id: "match-1", sequence: 1, attempt_type: "retrieval", status: "planned" }] : { items: [{ id: "match-1", match_number: "M10001", ip_name: "Avery" }] }))
        mount(<RecordAppointmentsCard record={record} canView canCreate canViewMatches archived={false} />)
        fireEvent.click(screen.getByRole("button", { name: "Schedule" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Appointment Type" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Consultation" }))
        fireEvent.click(await screen.findByRole("option", { name: "Consultation" }))
        fireEvent.click(screen.getByRole("combobox", { name: "Match Case" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "M10001 · Avery" }))
        fireEvent.click(await screen.findByRole("option", { name: "M10001 · Avery" }))
        fireEvent.click(await screen.findByRole("combobox", { name: "Attempt" }))
        fireEvent.mouseMove(await screen.findByRole("option", { name: "Attempt 1 · Retrieval · Planned" }))
        fireEvent.click(await screen.findByRole("option", { name: "Attempt 1 · Retrieval · Planned" }))
        fireEvent.change(screen.getByLabelText(/Date ·/), { target: { value: "2026-09-12" } })
        fireEvent.click(screen.getByRole("button", { name: /[0-9]+:[0-9]+ [AP]M/ }))
        fireEvent.click(screen.getAllByRole("button", { name: "Schedule" }).at(-1)!)
        await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ donor_id: "donor-1", match_id: "match-1", attempt_id: "attempt-1", client_email: "qa@example.com" }), expect.anything()))
    })
    it("does not load appointments without permission", () => {
        mount(<RecordAppointmentsCard record={record} canView={false} canCreate={false} archived={false} />)
        expect(mocks.appointments).toHaveBeenCalledWith(expect.anything(), { enabled: false })
        expect(screen.queryByText("Appointments")).not.toBeInTheDocument()
    })
})

describe("Explicit record correspondence", () => {
    it("links a selected conversation and never searches by the record contact email", async () => {
        mount(<RecordCorrespondenceCard kind="intended_parent" recordId="ip-1" canView canEdit />)
        expect(await screen.findByText("No linked correspondence")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Link Conversation" }))
        fireEvent.click(await screen.findByRole("button", { name: "T1001 · QA conversation" }))
        await waitFor(() => expect(mocks.put).toHaveBeenCalledWith("/records/intended_parent/ip-1/correspondence/ticket-1"))
        expect(mocks.tickets).toHaveBeenCalledWith({ q: "", limit: 20 })
    })
    it("shows an error and allows retry", async () => {
        mocks.get.mockRejectedValue(new Error("Unavailable"))
        mount(<RecordCorrespondenceCard kind="donor" recordId="donor-1" canView canEdit={false} />)
        expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load correspondence")
        mocks.get.mockResolvedValue({ items: [], total: 0 })
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(await screen.findByText("No linked correspondence")).toBeInTheDocument()
    })
    it("keeps the existing ticket beta access gate", () => {
        mount(<RecordCorrespondenceCard kind="donor" recordId="donor-1" canView={false} canEdit={false} />)
        expect(mocks.get).not.toHaveBeenCalled()
        expect(screen.queryByText("Correspondence")).not.toBeInTheDocument()
    })
})
