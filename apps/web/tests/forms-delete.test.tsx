import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import FormsListPage from "../app/(app)/automation/forms/page"

const mockPush = vi.fn()
const mockDeleteForm = vi.fn()
const mockDeleteTemplate = vi.fn()
let mockTemplates: Array<{
    id: string
    name: string
    description?: string | null
    updated_at: string
    published_at?: string | null
}> = []

vi.mock("sonner", () => ({
    toast: {
        success: vi.fn(),
        error: vi.fn(),
    },
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: mockPush }),
}))

vi.mock("@/lib/hooks/use-forms", () => ({
    useForms: () => ({
        data: [
            {
                id: "form-1",
                name: "Test Form",
                status: "draft",
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ],
        isLoading: false,
    }),
    useCreateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useDeleteForm: () => ({ mutateAsync: mockDeleteForm, isPending: false }),
    useDeleteFormTemplate: () => ({ mutateAsync: mockDeleteTemplate, isPending: false }),
    useFormTemplates: () => ({ data: mockTemplates, isLoading: false }),
    useUseFormTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("FormsListPage delete", () => {
    beforeEach(() => {
        mockPush.mockReset()
        mockDeleteForm.mockReset()
        mockDeleteTemplate.mockReset()
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
})
