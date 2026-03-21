import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"
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

        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("flex-col", "xl:flex-row")
        expect(screen.getByTestId("form-builder-palette")).toHaveClass("w-full", "xl:w-[320px]")
        expect(screen.getByTestId("form-builder-canvas")).toHaveClass("min-w-0", "p-4", "sm:p-6", "xl:p-8")
        expect(screen.getByTestId("form-builder-settings")).toHaveClass("w-full", "xl:w-[280px]")
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

    it("shows preset group navigation, switches visible preset fields, and trims answer previews on field cards", async () => {
        render(<FormBuilderPage />)

        expect(screen.getByRole("button", { name: "Contacts" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Demographics" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Eligibility" })).toBeInTheDocument()

        expect(screen.getByRole("button", { name: "Add preset Full Name field" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add preset Date of Birth field" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add preset Age Eligible field" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Demographics" }))
        expect(screen.getByRole("button", { name: "Add preset Date of Birth field" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add preset Full Name field" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Eligibility" }))
        expect(screen.getByRole("button", { name: "Add preset Age Eligible field" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Add preset Date of Birth field" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Demographics" }))
        fireEvent.click(screen.getByRole("button", { name: "Add preset Date of Birth field" }))
        fireEvent.click(screen.getByRole("button", { name: "Contacts" }))
        fireEvent.click(screen.getByRole("button", { name: "Add preset Full Name field" }))

        const fullNamePreview = await screen.findByLabelText("Preview answer for Full Name")
        expect(fullNamePreview).toHaveClass("mt-2", "p-3")
        expect(within(fullNamePreview).getByPlaceholderText("Enter full name")).toBeInTheDocument()

        const dobPreview = screen.getByLabelText("Preview answer for Date of Birth")
        expect(within(dobPreview).getByText("Month")).toBeInTheDocument()
        expect(within(dobPreview).getByText("Day")).toBeInTheDocument()
        expect(within(dobPreview).getByText("Year")).toBeInTheDocument()
    })
})
