import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import FormsListPage from "../app/(app)/automation/forms/page"

const mockPush = vi.fn()
const mockDeleteForm = vi.fn()

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
    useFormTemplates: () => ({ data: [], isLoading: false }),
    useUseFormTemplate: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("FormsListPage delete", () => {
    beforeEach(() => {
        mockPush.mockReset()
        mockDeleteForm.mockReset()
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
})

