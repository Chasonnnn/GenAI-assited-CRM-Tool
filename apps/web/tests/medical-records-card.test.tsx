import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { MedicalRecordsCard } from "@/components/medical-records/MedicalRecordsCard"
import { RecordEditingContext } from "@/components/records/RecordEditingContext"
import type { MedicalRecord, MedicalRecordListResponse } from "@/lib/types/medical-record"

const mockQuery: {
    data: MedicalRecordListResponse | undefined
    isLoading: boolean
    isError: boolean
    refetch: ReturnType<typeof vi.fn>
} = { data: undefined, isLoading: false, isError: false, refetch: vi.fn() }
const mockCreate = vi.fn()
const mockCorrect = vi.fn()
const mockArchive = vi.fn()
const mockRestore = vi.fn()
const mockToastSuccess = vi.fn()

vi.mock("@/lib/hooks/use-medical-records", () => ({
    useMedicalRecords: () => mockQuery,
    useCreateMedicalRecord: () => ({ mutateAsync: mockCreate, isPending: false }),
    useCorrectMedicalRecord: () => ({ mutateAsync: mockCorrect, isPending: false }),
    useArchiveMedicalRecord: () => ({ mutateAsync: mockArchive, isPending: false }),
    useRestoreMedicalRecordSection: () => ({ mutateAsync: mockRestore, isPending: false, variables: undefined }),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: { success: (...args: unknown[]) => mockToastSuccess(...args), error: vi.fn() },
}))

const EMPTY_VALUES = {
    provider_name: null,
    name: null,
    address_line1: null,
    address_line2: null,
    city: null,
    state: null,
    postal: null,
    phone: null,
    fax: null,
    email: null,
    plan_name: null,
    policy_number: null,
    member_id: null,
    group_number: null,
    subscriber_name: null,
    subscriber_dob: null,
}

function record(overrides: Partial<MedicalRecord>): MedicalRecord {
    return {
        ...EMPTY_VALUES,
        id: "rec",
        section: "clinic",
        status: "current",
        effective_date: "2026-01-05",
        end_date: null,
        source: "manual",
        archived_on: null,
        archived_by_name: null,
        revision: 1,
        created_by_name: "Case Manager",
        created_at: "2026-01-05T18:00:00Z",
        corrections: [],
        ...overrides,
    }
}

const currentClinic = record({ id: "clinic-2", name: "Austin Fertility", revision: 3 })
const pastClinic = record({
    id: "clinic-1",
    name: "Dallas IVF",
    status: "past",
    effective_date: "2025-01-01",
    end_date: "2026-01-04",
})
const owner = { kind: "surrogate", id: "sur-1" } as const

function renderCard({ canEdit = true, readOnly = false } = {}) {
    return render(
        <RecordEditingContext value={canEdit}>
            <MedicalRecordsCard owner={owner} readOnly={readOnly} />
        </RecordEditingContext>,
    )
}

function section(name: string) {
    return within(screen.getByRole("region", { name }))
}

beforeEach(() => {
    vi.clearAllMocks()
    mockQuery.data = { today: "2026-10-03", records: [currentClinic, pastClinic] }
    mockQuery.isLoading = false
    mockQuery.isError = false
    mockCreate.mockResolvedValue(undefined)
    mockCorrect.mockResolvedValue(undefined)
    mockArchive.mockResolvedValue(undefined)
    mockRestore.mockResolvedValue(undefined)
})

describe("MedicalRecordsCard", () => {
    it("shows the current record and switches to a past record", async () => {
        renderCard()
        const clinic = section("IVF Clinic")
        expect(clinic.getByText("Austin Fertility")).toBeInTheDocument()

        fireEvent.click(clinic.getByRole("button", { name: "IVF Clinic records, 2 total" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /Dallas IVF/ }))

        expect(clinic.getByText("Dallas IVF")).toBeInTheDocument()
        expect(clinic.getByText("Viewing a past record")).toBeInTheDocument()
        fireEvent.click(clinic.getByRole("button", { name: "Back to current" }))
        expect(clinic.getByText("Austin Fertility")).toBeInTheDocument()
    })

    it("hides every edit control when read-only", () => {
        renderCard({ readOnly: true })
        expect(screen.queryByRole("button", { name: "Edit Info" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "New IVF Clinic record" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /^Edit IVF Clinic/ })).not.toBeInTheDocument()
    })

    it("corrects a non-identity field with the expected revision", async () => {
        renderCard()
        const clinic = section("IVF Clinic")
        fireEvent.click(clinic.getByRole("button", { name: "Edit IVF Clinic City" }))
        fireEvent.change(clinic.getByRole("textbox"), { target: { value: "Austin" } })
        fireEvent.click(clinic.getByRole("button", { name: "Save IVF Clinic City" }))

        await waitFor(() =>
            expect(mockCorrect).toHaveBeenCalledWith({
                recordId: "clinic-2",
                data: { city: "Austin", expected_revision: 3 },
            }),
        )
    })

    it("asks before renaming the current record and can correct it", async () => {
        renderCard()
        const clinic = section("IVF Clinic")
        fireEvent.click(clinic.getByRole("button", { name: "Edit IVF Clinic Name" }))
        fireEvent.change(clinic.getByRole("textbox"), { target: { value: "Round Rock Fertility" } })
        fireEvent.click(clinic.getByRole("button", { name: "Save IVF Clinic Name" }))

        expect(await clinic.findByRole("heading", { name: "Is this a new IVF clinic?" })).toBeInTheDocument()
        expect(mockCorrect).not.toHaveBeenCalled()
        fireEvent.click(clinic.getByRole("button", { name: "No, correct this record" }))

        await waitFor(() =>
            expect(mockCorrect).toHaveBeenCalledWith({
                recordId: "clinic-2",
                data: { name: "Round Rock Fertility", expected_revision: 3 },
            }),
        )
    })

    it("starts a new record from the rename prompt with the new name and copied details", async () => {
        mockQuery.data = {
            today: "2026-10-03",
            records: [{ ...currentClinic, city: "Austin" }, pastClinic],
        }
        renderCard()
        const clinic = section("IVF Clinic")
        fireEvent.click(clinic.getByRole("button", { name: "Edit IVF Clinic Name" }))
        fireEvent.change(clinic.getByRole("textbox"), { target: { value: "Round Rock Fertility" } })
        fireEvent.click(clinic.getByRole("button", { name: "Save IVF Clinic Name" }))
        fireEvent.click(await clinic.findByRole("button", { name: "Yes, start a new record" }))

        expect(clinic.getByLabelText("Name")).toHaveValue("Round Rock Fertility")
        expect(clinic.getByLabelText("City")).toHaveValue("Austin")
        expect(clinic.getByLabelText("Effective date")).toHaveValue("2026-10-03")
        fireEvent.click(clinic.getByRole("button", { name: "Save record" }))

        await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1))
        const payload = mockCreate.mock.calls[0]?.[0]
        expect(payload).toMatchObject({
            section: "clinic",
            effective_date: "2026-10-03",
            name: "Round Rock Fertility",
            city: "Austin",
            phone: null,
        })
        expect(payload.idempotency_key).toEqual(expect.any(String))
        expect(mockToastSuccess).toHaveBeenCalledWith("IVF Clinic: new record saved")
    })

    it("requires a name before saving a new record", async () => {
        mockQuery.data = { today: "2026-10-03", records: [] }
        renderCard()
        fireEvent.click(screen.getByRole("button", { name: "Edit Info" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: /Lab Clinic/ }))

        const lab = section("Lab Clinic")
        fireEvent.click(lab.getByRole("button", { name: "Save record" }))
        expect(lab.getByRole("alert")).toHaveTextContent("Enter the name.")
        expect(mockCreate).not.toHaveBeenCalled()
        fireEvent.click(lab.getByRole("button", { name: "Cancel" }))
        expect(screen.queryByRole("region", { name: "Lab Clinic" })).not.toBeInTheDocument()
    })

    it("archives the current record after confirmation", async () => {
        renderCard()
        fireEvent.click(screen.getByRole("button", { name: "Edit Info" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "IVF Clinic" }))

        const dialog = await screen.findByRole("alertdialog")
        expect(within(dialog).getByText("Archive IVF Clinic?")).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole("button", { name: "Archive" }))

        await waitFor(() => expect(mockArchive).toHaveBeenCalledWith({ recordId: "clinic-2", expectedRevision: 3 }))
        expect(mockToastSuccess).toHaveBeenCalledWith("IVF Clinic archived")
    })

    it("lists archived sections and restores one", async () => {
        mockQuery.data = {
            today: "2026-10-03",
            records: [{ ...pastClinic, archived_on: "2026-09-01", archived_by_name: "Case Manager", end_date: "2026-09-01" }],
        }
        renderCard()
        expect(screen.getByText("No medical or insurance information added yet.")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Archived sections (1)" }))
        const clinic = section("IVF Clinic")
        expect(clinic.getByText(/Archived by Case Manager/)).toBeInTheDocument()
        fireEvent.click(clinic.getByRole("button", { name: "Restore IVF Clinic" }))

        await waitFor(() =>
            expect(mockRestore).toHaveBeenCalledWith({ section: "clinic", idempotencyKey: expect.any(String) }),
        )
    })

    it("shows corrections and hides redacted values", () => {
        mockQuery.data = {
            today: "2026-10-03",
            records: [
                record({
                    id: "ins-1",
                    section: "insurance",
                    name: "Blue Shield",
                    corrections: [
                        {
                            id: "c1",
                            field: "plan_name",
                            old_value: "Silver",
                            new_value: "Gold",
                            redacted: false,
                            source: "manual",
                            corrected_by_name: "Case Manager",
                            corrected_at: "2026-02-01T18:00:00Z",
                        },
                        {
                            id: "c2",
                            field: "member_id",
                            old_value: null,
                            new_value: null,
                            redacted: true,
                            source: "manual",
                            corrected_by_name: "Case Manager",
                            corrected_at: "2026-02-02T18:00:00Z",
                        },
                    ],
                }),
            ],
        }
        renderCard()
        const insurance = section("Insurance")
        fireEvent.click(insurance.getByRole("button", { name: "2 corrections" }))
        const items = insurance.getAllByRole("listitem").map((item) => item.textContent)
        expect(items[0]).toContain("Member ID changed")
        expect(items[1]).toContain("Plan: Silver → Gold")
    })

    it("renders loading and error states", () => {
        mockQuery.isLoading = true
        const view = renderCard()
        expect(screen.getByText("Medical & Insurance")).toBeInTheDocument()
        expect(document.querySelector("[aria-busy='true']")).not.toBeNull()

        mockQuery.isLoading = false
        mockQuery.isError = true
        mockQuery.data = undefined
        view.rerender(
            <RecordEditingContext value={true}>
                <MedicalRecordsCard owner={owner} />
            </RecordEditingContext>,
        )
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(mockQuery.refetch).toHaveBeenCalled()
    })
})
