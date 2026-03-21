import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, screen, within } from "@testing-library/react"
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
        expect(screen.getByRole("tab", { name: /^edit$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^preview$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^settings$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^submissions$/i })).toBeInTheDocument()
        expect(screen.queryByRole("tab", { name: /^builder$/i })).not.toBeInTheDocument()
        expect(
            screen.queryByRole("tablist", { name: /canvas mode/i }),
        ).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))

        expect(screen.getByText("Form Settings")).toBeInTheDocument()
        expect(screen.getByLabelText("Form Name")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("hidden")
    })

    it("uses a persistent field browser, live edit canvas, and docked settings rail", async () => {
        render(<FormBuilderPage />)

        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("flex-col", "xl:grid")
        expect(screen.getByTestId("form-builder-palette")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-canvas")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-page-shell")).toHaveClass("min-h-[58rem]")
        expect(screen.getByTestId("form-builder-settings")).toBeInTheDocument()
        expect(screen.queryByTestId("form-builder-page-rail")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        const canvas = screen.getByTestId("form-builder-canvas")
        expect(within(canvas).getByText("Name")).toBeInTheDocument()
        expect(within(canvas).queryByRole("button", { name: "Name field" })).not.toBeInTheDocument()
        expect(within(canvas).queryByText(/^text$/i)).not.toBeInTheDocument()
        expect(within(canvas).queryByText(/^required$/i)).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /select name field/i }))

        expect(await screen.findByRole("tab", { name: /^general$/i })).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-selected-field-actions")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-selected-field-body")).toHaveClass("pt-3.5")
        expect(screen.getByRole("tab", { name: /^advanced$/i })).toBeInTheDocument()
        expect(screen.getByLabelText(/field title/i)).toHaveValue("Name")
    })

    it("adds contextual aria-labels to automation form builder icon buttons", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        expect(await screen.findByRole("button", { name: "Duplicate Name" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Delete Name" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Select field" }))
        expect(await screen.findByRole("button", { name: "Remove option Option 1" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Repeating Table field" }))
        expect(await screen.findByRole("button", { name: "Remove column Column 1" })).toBeInTheDocument()
    })

    it("keeps multi-select option inputs focused while editing", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Multi-Select field" }))

        const optionInput = await screen.findByDisplayValue("Option 1")
        optionInput.focus()
        fireEvent.change(optionInput, { target: { value: "Option 1 extended" } })

        const updatedInput = screen.getByDisplayValue("Option 1 extended")
        expect(updatedInput).toHaveFocus()
    })

    it("keeps the field library in the left sidebar, filters categories, and adds fields with click-to-add", async () => {
        render(<FormBuilderPage />)

        expect(screen.queryByRole("dialog", { name: /add form fields/i })).not.toBeInTheDocument()
        expect(screen.getByPlaceholderText(/search form fields/i)).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Contacts" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Demographics" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "General" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Choices" })).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-palette-search")).toHaveClass("rounded-xl")
        expect(screen.getAllByTestId("form-builder-palette-field-grid")[0]).toHaveClass("grid-cols-4")
        const nameTile = screen.getByTestId("form-builder-palette-tile-full_name")
        expect(nameTile).toHaveClass("border-transparent", "items-center", "text-center", "gap-1.5")
        expect(nameTile.querySelector("span")).toHaveClass("size-12")
        expect(within(nameTile).getByText("Full Name")).toHaveClass("text-[13px]")

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

        expect(await screen.findByRole("button", { name: /select email field/i })).toBeInTheDocument()
    })

    it("supports page renaming and reordering from the compact page strip", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add page$/i }))

        expect(screen.queryByLabelText(/^page name$/i)).not.toBeInTheDocument()

        const pageTwoInput = screen.getByRole("textbox", { name: /edit page name/i })
        fireEvent.change(pageTwoInput, { target: { value: "Medical history" } })

        expect(screen.getByDisplayValue("Medical history")).toBeInTheDocument()

        await act(async () => {
            fireEvent.click(screen.getByRole("button", { name: "Move Medical history up" }))
        })

        const pageTabs = within(screen.getByRole("tablist", { name: /form pages/i })).getAllByRole("tab")
        expect(pageTabs[0]).toHaveAttribute("aria-label", "Medical history")
    })

    it("adds a fixed table field with editable rows and columns", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: "Uploads and Tables" }))
        fireEvent.click(screen.getByRole("button", { name: "Add Table field" }))

        fireEvent.click(await screen.findByRole("button", { name: /select table field/i }))

        expect(await screen.findByDisplayValue("Item 1")).toBeInTheDocument()
        expect(screen.getByDisplayValue("Response")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add row$/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add column$/i })).toBeInTheDocument()
    })

    it("renders preview as a top-level workspace tab without mutating edit state", async () => {
        render(<FormBuilderPage />)

        const formNameInput = screen.getByLabelText("Form name")
        fireEvent.change(formNameInput, { target: { value: "Enterprise Intake" } })

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        fireEvent.click(screen.getByRole("tab", { name: /^preview$/i }))

        expect(await screen.findByRole("heading", { name: "Enterprise Intake" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^mobile preview$/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^mobile preview$/i }))
        expect(screen.getByTestId("form-builder-preview-shell")).toHaveClass("max-w-sm")

        fireEvent.click(screen.getByRole("tab", { name: /^edit$/i }))
        expect(screen.getByRole("button", { name: /select name field/i })).toBeInTheDocument()
    })
})
