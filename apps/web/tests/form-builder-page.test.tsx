import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import type { ImgHTMLAttributes } from "react"

import FormBuilderPage from "../app/(app)/automation/forms/[id]/page.client"

const mockPush = vi.fn()

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "new" }),
    useRouter: () => ({
        push: mockPush,
        replace: vi.fn(),
    }),
}))

vi.mock("next/image", () => ({
    __esModule: true,
    default: ({ alt, ...props }: ImgHTMLAttributes<HTMLImageElement>) => (
        <span data-testid="next-image-mock" data-alt={alt ?? ""} {...props} />
    ),
}))

vi.mock("qrcode.react", () => ({
    QRCodeSVG: () => <div data-testid="qr-code" />,
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({
        user: {
            org_id: "org-1",
        },
    }),
}))

vi.mock("@/lib/hooks/use-form-mapping-options", () => ({
    useFormMappingOptions: () => ({ data: [] }),
}))

vi.mock("@/lib/hooks/use-email-templates", () => ({
    useEmailTemplates: () => ({ data: [], isLoading: false }),
}))

vi.mock("@/lib/hooks/use-signature", () => ({
    useOrgSignature: () => ({ data: null }),
}))

vi.mock("@/lib/hooks/use-forms", () => ({
    useCreateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useForm: () => ({ data: undefined, isLoading: false }),
    useFormIntakeLinks: () => ({ data: [], refetch: vi.fn() }),
    useFormSubmissions: () => ({ data: [], refetch: vi.fn(), isLoading: false }),
    useFormMappings: () => ({ data: [], isLoading: false }),
    usePublishForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useRetrySubmissionMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useResolveSubmissionMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSetFormMappings: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSetDefaultSurrogateApplicationForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmissionMatchCandidates: () => ({ data: [], isLoading: false }),
    usePromoteIntakeLead: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateFormDeliverySettings: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUploadFormLogo: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("FormBuilderPage", () => {
    beforeEach(() => {
        mockPush.mockReset()
    })

    it("uses design-system tab controls for workspace sections and a dedicated settings tab", () => {
        render(<FormBuilderPage />)

        expect(
            screen.getByRole("tablist", { name: /workspace sections/i }),
        ).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^builder$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^settings$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^submissions$/i })).toBeInTheDocument()
        expect(
            screen.queryByRole("tablist", { name: /builder settings/i }),
        ).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))

        expect(screen.getByText("Form Settings")).toBeInTheDocument()
        expect(screen.getByLabelText("Form Name")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("hidden")
    })

    it("stacks the builder workspace into responsive regions", () => {
        render(<FormBuilderPage />)

        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("xl:grid")
        expect(screen.getByTestId("form-builder-page-rail")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-canvas")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-settings")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add fields$/i })).toBeInTheDocument()
        expect(screen.getByRole("tablist", { name: /canvas mode/i })).toBeInTheDocument()
    })

    it("adds contextual aria-labels to automation form builder icon buttons", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        expect(await screen.findByRole("button", { name: "Duplicate Name" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Delete Name" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Select field" }))
        expect(await screen.findByRole("button", { name: "Remove option Option 1" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Repeating Table field" }))
        expect(await screen.findByRole("button", { name: "Remove column Column 1" })).toBeInTheDocument()
    })

    it("keeps multi-select option inputs focused while editing", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Multi-Select field" }))

        const optionInput = await screen.findByDisplayValue("Option 1")
        optionInput.focus()
        fireEvent.change(optionInput, { target: { value: "Option 1 extended" } })

        const updatedInput = screen.getByDisplayValue("Option 1 extended")
        expect(updatedInput).toHaveFocus()
    })

    it("opens the field library, filters categories, and adds fields with click-to-add", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))

        expect(screen.getByRole("dialog", { name: /add form fields/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Contacts" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Demographics" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "General" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Choices" })).toBeInTheDocument()

        expect(screen.getByRole("button", { name: "Add preset Full Name field" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Demographics" }))
        expect(screen.getByRole("button", { name: "Add preset Date of Birth field" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add preset Full Name field" })).not.toBeInTheDocument()

        fireEvent.change(screen.getByPlaceholderText(/search form fields/i), {
            target: { value: "email" },
        })
        expect(screen.getByRole("button", { name: /add preset email field/i })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /add preset date of birth field/i })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /add preset email field/i }))

        await waitFor(() =>
            expect(screen.queryByRole("dialog", { name: /add form fields/i })).not.toBeInTheDocument(),
        )
        expect(screen.getByRole("button", { name: "Email field" })).toBeInTheDocument()
    })

    it("supports page renaming and reordering from the page rail", () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add page$/i }))

        const pageTwoInput = screen.getByLabelText("Page 2 name")
        fireEvent.change(pageTwoInput, { target: { value: "Medical history" } })

        expect(screen.getByDisplayValue("Medical history")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Move Medical history up" }))

        const pageButtons = within(screen.getByTestId("form-builder-page-rail"))
            .getAllByRole("button", { name: /select page/i })
            .map((button) => button.textContent)
        expect(pageButtons[0]).toContain("Medical history")
    })

    it("keeps canvas cards as summary cards and drives editing from the inspector", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        const canvas = screen.getByTestId("form-builder-canvas")
        expect(within(canvas).queryByDisplayValue("Name")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Name field" }))

        expect(await screen.findByLabelText("Label")).toHaveValue("Name")
        expect(within(screen.getByTestId("form-builder-settings")).getByText("Text")).toBeInTheDocument()
    })

    it("renders an integrated preview without mutating builder data", async () => {
        render(<FormBuilderPage />)

        const formNameInput = screen.getByLabelText("Form name")
        fireEvent.change(formNameInput, { target: { value: "Enterprise Intake" } })

        fireEvent.click(screen.getByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        fireEvent.click(screen.getByRole("tab", { name: /^preview$/i }))

        expect(await screen.findByRole("heading", { name: "Enterprise Intake" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^mobile preview$/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^mobile preview$/i }))
        expect(screen.getByTestId("form-builder-preview-shell")).toHaveClass("max-w-sm")

        fireEvent.click(screen.getByRole("tab", { name: /^compose$/i }))
        expect(screen.getByRole("button", { name: "Name field" })).toBeInTheDocument()
    })
})
