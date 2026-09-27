import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import FormsListPage from "../app/(app)/automation/forms/page"
import { ApiError } from "@/lib/api"

const mockPush = vi.fn()
const mockCreateForm = vi.fn()
const mockDeleteForm = vi.fn()
const mockDeleteTemplate = vi.fn()
let mockForms: Array<{
    id: string
    name: string
    status: string
    created_at: string
    updated_at: string
    lead_kind?: "surrogate" | "egg_donor" | "sperm_donor"
}> = []
let mockTemplates: Array<{
    id: string
    name: string
    description?: string | null
    updated_at: string
    published_at?: string | null
}> = []

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

let mockPermissions = new Set(["manage_forms"])
let mockFormsError: Error | null = null
let mockTemplatesError: Error | null = null
const mockRefetchTemplates = vi.fn()
vi.mock("@/lib/hooks/use-permission-check", () => ({
    usePermissionCheck: () => ({
        isLoading: false,
        isError: false,
        retry: vi.fn(),
        isRetrying: false,
        can: (permission: string) => mockPermissions.has(permission),
    }),
}))

const mockUseForms = vi.fn()
const mockUseFormTemplates = vi.fn()
vi.mock("@/lib/hooks/use-forms", () => ({
    useForms: (options?: { enabled?: boolean }) => {
        mockUseForms(options)
        return {
            data: mockFormsError ? undefined : mockForms,
            isLoading: false,
            isError: Boolean(mockFormsError),
            error: mockFormsError,
            isFetching: false,
            refetch: vi.fn(),
        }
    },
    useCreateForm: () => ({ mutateAsync: mockCreateForm, isPending: false }),
    useDeleteForm: () => ({ mutateAsync: mockDeleteForm, isPending: false }),
    useDeleteFormTemplate: () => ({ mutateAsync: mockDeleteTemplate, isPending: false }),
    useFormTemplates: (options?: { enabled?: boolean }) => {
        mockUseFormTemplates(options)
        return {
            data: mockTemplatesError ? undefined : mockTemplates,
            isLoading: false,
            isError: Boolean(mockTemplatesError),
            error: mockTemplatesError,
            isFetching: false,
            refetch: mockRefetchTemplates,
        }
    },
    useUseFormTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("FormsListPage delete", () => {
    beforeEach(() => {
        vi.useRealTimers()
        mockPush.mockReset()
        mockCreateForm.mockReset()
        mockDeleteForm.mockReset()
        mockDeleteTemplate.mockReset()
        mockUseForms.mockReset()
        mockUseFormTemplates.mockReset()
        mockPermissions = new Set(["manage_forms"])
        mockFormsError = null
        mockTemplatesError = null
        mockRefetchTemplates.mockReset()
        mockForms = [
            {
                id: "form-1",
                name: "Test Form",
                status: "draft",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]
        mockTemplates = []
    })

    it("deletes a form after confirmation", async () => {
        mockDeleteForm.mockResolvedValue(undefined)

        render(<FormsListPage />)

        fireEvent.click(screen.getByLabelText("Open menu for Test Form"))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))

        expect(screen.getByText("Delete form?")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Delete" }))

        await waitFor(() => expect(mockDeleteForm).toHaveBeenCalledWith("form-1"))
    })

    it("removes a form template from org library after confirmation", async () => {
        mockTemplates = [
            {
                id: "template-1",
                name: "Jotform Surrogate Intake",
                description: "Template based on the Jotform surrogate intake form.",
                updated_at: new Date().toISOString(),
                published_at: new Date().toISOString(),
            },
        ]
        mockDeleteTemplate.mockResolvedValue(undefined)

        render(<FormsListPage />)

        fireEvent.click(screen.getByRole("tab", { name: /form templates/i }))
        fireEvent.click(
            screen.getByLabelText("Open menu for template Jotform Surrogate Intake")
        )
        fireEvent.click(await screen.findByRole("menuitem", { name: "Remove from library" }))

        expect(screen.getByText("Remove template from library?")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Remove" }))

        await waitFor(() => expect(mockDeleteTemplate).toHaveBeenCalledWith("template-1"))
    })

    it("shows an absolute saved time instead of a negative relative timestamp", () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date("2026-03-21T03:29:29Z"))

        mockForms = [
            {
                id: "form-1",
                name: "Test Form",
                status: "draft",
                created_at: "2026-03-20T23:29:29Z",
                updated_at: "2026-03-21T07:29:29Z",
            },
        ]

        render(<FormsListPage />)

        const expectedTime = new Date("2026-03-21T07:29:29Z").toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
        })

        expect(screen.getByText(`Saved ${expectedTime}`)).toBeInTheDocument()
        expect(screen.queryByText(/Updated -/i)).not.toBeInTheDocument()
    })

    it("creates and labels an egg donor form", async () => {
        mockForms = [
            {
                id: "form-donor",
                name: "Egg Donor Application",
                status: "draft",
                lead_kind: "egg_donor",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ]
        mockCreateForm.mockResolvedValue({ id: "created-donor" })

        render(<FormsListPage />)

        expect(screen.getByText("Egg Donor")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Create Form" }))
        fireEvent.change(screen.getByLabelText("Form Name *"), {
            target: { value: "New Egg Donor Form" },
        })
        const leadTypeSelect = screen.getByRole("combobox", { name: "Lead Type" })
        fireEvent.mouseDown(leadTypeSelect)
        const eggDonorOption = await screen.findByRole("option", { name: "Egg Donor" })
        fireEvent.mouseMove(eggDonorOption)
        fireEvent.click(eggDonorOption)
        fireEvent.click(screen.getAllByRole("button", { name: "Create Form" }).at(-1)!)

        await waitFor(() =>
            expect(mockCreateForm).toHaveBeenCalledWith({
                name: "New Egg Donor Form",
                lead_kind: "egg_donor",
            }),
        )
        expect(mockPush).toHaveBeenCalledWith("/automation/forms/created-donor")
    })

    it("shows a denied state with no Create Form or empty state without manage_forms", () => {
        mockPermissions = new Set()
        mockForms = []

        render(<FormsListPage />)

        expect(screen.getByText("No access to Form Builder")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /create form/i })).not.toBeInTheDocument()
        expect(screen.queryByText("No forms yet")).not.toBeInTheDocument()
        expect(mockUseForms).toHaveBeenCalledWith({ enabled: false })
        expect(mockUseFormTemplates).toHaveBeenCalledWith({ enabled: false })
    })

    it("renders a 403 from the forms request as the denied state", () => {
        mockFormsError = new ApiError(403, "Forbidden", "Missing permission: manage_forms")

        render(<FormsListPage />)

        expect(screen.getByText("No access to Form Builder")).toBeInTheDocument()
        expect(screen.queryByText(/manage_forms/)).not.toBeInTheDocument()
        expect(screen.queryByText("No forms yet")).not.toBeInTheDocument()
    })

    it("shows the first-run empty state with one create action and no helper line", () => {
        mockForms = []

        render(<FormsListPage />)

        expect(screen.getByRole("heading", { level: 2, name: "No forms yet" })).toBeInTheDocument()
        expect(screen.queryByText(/create your first form/i)).not.toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: "Create Form" })).toHaveLength(2)
    })

    it("shows the form templates empty state without helper copy", () => {
        render(<FormsListPage />)
        fireEvent.click(screen.getByRole("tab", { name: /form templates/i }))

        expect(screen.getByRole("heading", { level: 2, name: "No form templates yet" })).toBeInTheDocument()
        expect(screen.queryByText(/platform templates/i)).not.toBeInTheDocument()
    })

    it("shows a load error, not the empty state, when form templates fail to load", () => {
        mockTemplatesError = new ApiError(500, "Internal Server Error", "database exploded")

        render(<FormsListPage />)
        fireEvent.click(screen.getByRole("tab", { name: /form templates/i }))

        expect(
            screen.getByRole("heading", { level: 2, name: "Couldn't load form templates" }),
        ).toBeInTheDocument()
        expect(screen.queryByText("No form templates yet")).not.toBeInTheDocument()
        expect(screen.queryByText(/database exploded/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(mockRefetchTemplates).toHaveBeenCalledTimes(1)
    })

    it("puts Use Template in the template card footer, apart from the menu", () => {
        mockTemplates = [
            {
                id: "template-1",
                name: "Surrogate Application Form Template",
                description: "Full application.",
                updated_at: new Date().toISOString(),
                published_at: null,
            },
        ]

        render(<FormsListPage />)
        fireEvent.click(screen.getByRole("tab", { name: /form templates/i }))

        const useButton = screen.getByRole("button", {
            name: "Use template Surrogate Application Form Template",
        })
        const menuButton = screen.getByLabelText(
            "Open menu for template Surrogate Application Form Template",
        )
        const title = screen.getByText("Surrogate Application Form Template")
        expect(useButton.closest('[data-slot="card-header"]')).toBeNull()
        expect(menuButton.closest('[data-slot="card-header"]')).toContainElement(title)
    })
})
