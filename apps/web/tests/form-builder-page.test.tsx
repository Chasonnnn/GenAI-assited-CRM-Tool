import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"
import type { ImgHTMLAttributes } from "react"

import FormBuilderPage from "../app/(app)/automation/forms/[id]/page.client"
import type {
    FormRead,
    FormSubmissionRead,
    ListFormSubmissionsParams,
} from "@/lib/api/forms"

const mockPush = vi.fn()
const mockReplace = vi.fn()
const mockUseForm = vi.fn()
const mockFormSubmissions = vi.fn()
const mockCreateForm = vi.fn()
const mockSetFormMappings = vi.fn()
const mockPublishForm = vi.fn()
const mockRefetchIntakeLinks = vi.fn()
const { toastError } = vi.hoisted(() => ({
    toastError: vi.fn(),
}))
const navigationState = vi.hoisted(() => ({
    formId: "new",
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: navigationState.formId }),
    useRouter: () => ({
        push: mockPush,
        replace: mockReplace,
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

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: vi.fn(),
        error: toastError,
    },
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
    useCreateForm: () => ({ mutateAsync: mockCreateForm, isPending: false }),
    useForm: () => mockUseForm(),
    useFormEmbedHealth: () => ({ data: null, isFetching: false, refetch: vi.fn() }),
    useFormIntakeLinks: () => ({ data: [], refetch: mockRefetchIntakeLinks }),
    useFormSubmissions: (formId: string | null, params: ListFormSubmissionsParams) =>
        mockFormSubmissions(formId, params),
    useFormMappings: () => ({ data: [], isLoading: false }),
    usePublishForm: () => ({ mutateAsync: mockPublishForm, isPending: false }),
    useRetrySubmissionMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useResolveSubmissionMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSetFormMappings: () => ({ mutateAsync: mockSetFormMappings, isPending: false }),
    useSetDefaultSurrogateApplicationForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useSubmissionMatchCandidates: () => ({ data: [], isLoading: false }),
    usePromoteIntakeLead: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateFormDeliverySettings: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateFormIntakeLink: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateForm: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUploadFormLogo: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe("FormBuilderPage", () => {
    beforeEach(() => {
        navigationState.formId = "new"
        mockPush.mockReset()
        mockReplace.mockReset()
        mockUseForm.mockReset()
        mockFormSubmissions.mockReset()
        mockCreateForm.mockReset()
        mockSetFormMappings.mockReset()
        mockPublishForm.mockReset()
        mockRefetchIntakeLinks.mockReset()
        toastError.mockReset()
        mockUseForm.mockReturnValue({ data: undefined, isLoading: false })
        mockFormSubmissions.mockReturnValue({
            data: [],
            refetch: vi.fn(),
            isLoading: false,
        })
        mockCreateForm.mockResolvedValue({
            id: "form-1",
            name: "Published Intake",
            status: "draft",
            updated_at: "2026-07-16T00:00:00Z",
        })
        mockSetFormMappings.mockResolvedValue([])
        mockPublishForm.mockResolvedValue({
            id: "form-1",
            status: "published",
        })
        mockRefetchIntakeLinks.mockResolvedValue({
            data: [
                {
                    id: "link-1",
                    form_id: "form-1",
                    slug: "published-intake",
                    is_active: true,
                    submissions_count: 0,
                    embed_enabled: false,
                    allowed_embed_origins: [],
                    tracking_mode: "enhanced_match_lead",
                    thank_you_config: {},
                    embed_theme_json: {},
                    intake_url: "https://example.test/intake/published-intake",
                    created_at: "2026-07-16T00:00:00Z",
                    updated_at: "2026-07-16T00:00:00Z",
                },
            ],
        })
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
        expect(screen.getByLabelText("Internal form name")).toBeInTheDocument()
        expect(screen.getByText("Public Form Title & Subtitle")).toBeInTheDocument()
        expect(screen.getByLabelText("Eyebrow")).toBeInTheDocument()
        expect(screen.getByLabelText("Title")).toBeInTheDocument()
        expect(screen.getByLabelText("Subtitle")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("hidden")
    })

    it("renders human-readable labels for automation settings dropdown triggers", () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))

        const purposeSelect = screen.getByRole("combobox", { name: "Form Purpose" })
        expect(purposeSelect).toHaveTextContent("Surrogate Application")
        expect(purposeSelect).not.toHaveTextContent("surrogate_application")

        const templateSelect = screen.getByRole("combobox", { name: "Default application email template" })
        expect(templateSelect).toHaveTextContent("No default template")
        expect(templateSelect).not.toHaveTextContent("none")
    })

    it("waits for the routed form response before hydrating the builder draft", async () => {
        const buildForm = (id: string, name: string): FormRead => ({
            id,
            name,
            status: "draft",
            purpose: "surrogate_application",
            created_at: "2026-07-16T00:00:00Z",
            updated_at: "2026-07-16T00:00:00Z",
            description: null,
            form_schema: {
                pages: [{ title: `${name} Page`, fields: [] }],
            },
            published_schema: null,
            max_file_size_bytes: 10 * 1024 * 1024,
            max_file_count: 10,
            allowed_mime_types: null,
            default_application_email_template_id: null,
        })
        const formA = buildForm("form-a", "Form A")
        const formB = buildForm("form-b", "Form B")

        navigationState.formId = formA.id
        mockUseForm.mockReturnValue({ data: formA, isLoading: false })
        const view = render(<FormBuilderPage />)
        expect(await screen.findByLabelText("Form name")).toHaveValue("Form A")

        navigationState.formId = formB.id
        mockUseForm.mockReturnValue({ data: formA, isLoading: false })
        view.rerender(<FormBuilderPage />)

        mockUseForm.mockReturnValue({ data: formB, isLoading: false })
        view.rerender(<FormBuilderPage />)

        expect(await screen.findByLabelText("Form name")).toHaveValue("Form B")
    })

    it("blocks publishing shared intake forms without all identity mappings", async () => {
        render(<FormBuilderPage />)

        fireEvent.change(screen.getByLabelText("Form name"), {
            target: { value: "Incomplete Intake" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        fireEvent.click(screen.getByRole("button", { name: "Add Email field" }))
        fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))

        expect(toastError).toHaveBeenCalledWith(expect.stringContaining("Date of Birth"))
        expect(toastError).toHaveBeenCalledWith(expect.stringContaining("Phone"))
        expect(screen.queryByRole("alertdialog", { name: /publish form/i })).not.toBeInTheDocument()
    })

    it("opens sharing from the link returned by a successful publish", async () => {
        render(<FormBuilderPage />)

        fireEvent.change(screen.getByLabelText("Form name"), {
            target: { value: "Published Intake" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Add preset Full Name field" }))
        fireEvent.click(screen.getByRole("button", { name: "Add preset Email field" }))
        fireEvent.click(screen.getByRole("button", { name: "Add preset Phone field" }))
        fireEvent.click(screen.getByRole("button", { name: "Demographics" }))
        fireEvent.click(screen.getByRole("button", { name: "Add preset Date of Birth field" }))

        fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))
        fireEvent.click(
            await screen.findByRole("button", { name: /^publish$/i }),
        )

        expect(
            await screen.findByRole("heading", { name: "Share Application Intake" }),
        ).toBeInTheDocument()
    })

    it("clears submission review notes when leaving the submissions workspace", async () => {
        const form: FormRead = {
            id: "form-1",
            name: "Surrogate Application",
            status: "draft",
            purpose: "surrogate_application",
            created_at: "2026-07-16T00:00:00Z",
            updated_at: "2026-07-16T00:00:00Z",
            description: null,
            form_schema: {
                pages: [{ title: "Application", fields: [] }],
            },
            published_schema: null,
            max_file_size_bytes: 10 * 1024 * 1024,
            max_file_count: 10,
            allowed_mime_types: null,
            default_application_email_template_id: null,
        }
        const submission: FormSubmissionRead = {
            id: "submission-1",
            form_id: "form-1",
            surrogate_id: null,
            status: "pending_review",
            submitted_at: "2026-07-16T00:00:00Z",
            reviewed_at: null,
            reviewed_by_user_id: null,
            review_notes: null,
            answers: {
                full_name: "Alex Applicant",
                email: "alex@example.com",
            },
            schema_snapshot: null,
            source_mode: "shared",
            intake_link_id: "link-1",
            intake_lead_id: null,
            match_status: "ambiguous_review",
            match_reason: null,
            matched_at: null,
            files: [],
        }

        navigationState.formId = form.id
        mockUseForm.mockReturnValue({ data: form, isLoading: false })
        mockFormSubmissions.mockImplementation(
            (_formId: string | null, params: ListFormSubmissionsParams = {}) => ({
                data: params.match_status === "ambiguous_review" ? [submission] : [],
                refetch: vi.fn(),
                isLoading: false,
            }),
        )

        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("tab", { name: /^submissions$/i }))
        fireEvent.click(await screen.findByRole("button", { name: "Review Candidates" }))
        fireEvent.change(screen.getByLabelText("Reviewer notes"), {
            target: { value: "Only for the first review" },
        })

        fireEvent.click(screen.getByRole("tab", { name: /^edit$/i }))
        fireEvent.click(screen.getByRole("tab", { name: /^submissions$/i }))
        fireEvent.click(await screen.findByRole("button", { name: "Review Candidates" }))

        expect(screen.getByLabelText("Reviewer notes")).toHaveValue("")
    })

    it("renders human-readable labels for inspector dropdown triggers", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        fireEvent.click(screen.getByRole("button", { name: "Add Email field" }))
        fireEvent.click(await screen.findByRole("button", { name: /select email field/i }))
        fireEvent.click(screen.getByRole("tab", { name: /^advanced$/i }))

        const logicSection = screen.getByText("Logic").closest("section")
        expect(logicSection).not.toBeNull()

        const displayRuleSelect = within(logicSection as HTMLElement).getAllByRole("combobox")[0]
        expect(displayRuleSelect).toHaveTextContent("Always show")
        expect(displayRuleSelect).not.toHaveTextContent("none")

        fireEvent.mouseDown(displayRuleSelect)
        const nameFieldOption = await screen.findByRole("option", { name: "Name" })
        fireEvent.mouseMove(nameFieldOption)
        fireEvent.click(nameFieldOption)

        expect(within(logicSection as HTMLElement).getAllByRole("combobox")[0]).toHaveTextContent("Name")

        const operatorSelect = within(logicSection as HTMLElement).getAllByRole("combobox")[1]
        fireEvent.mouseDown(operatorSelect)
        const notEqualsOption = await screen.findByRole("option", { name: "Does not equal" })
        fireEvent.mouseMove(notEqualsOption)
        fireEvent.click(notEqualsOption)

        expect(within(logicSection as HTMLElement).getAllByRole("combobox")[1]).toHaveTextContent("Does not equal")
        expect(within(logicSection as HTMLElement).getAllByRole("combobox")[1]).not.toHaveTextContent("not_equals")

        const mappingSection = screen.getByText("Mapping").closest("section")
        expect(mappingSection).not.toBeNull()

        const mappingSelect = within(mappingSection as HTMLElement).getByRole("combobox")
        expect(mappingSelect).toHaveTextContent("None")
        expect(mappingSelect).not.toHaveTextContent("none")

        fireEvent.mouseDown(mappingSelect)
        const fullNameMappingOption = await screen.findByRole("option", { name: "Full Name" })
        fireEvent.mouseMove(fullNameMappingOption)
        fireEvent.click(fullNameMappingOption)

        expect(within(mappingSection as HTMLElement).getByRole("combobox")).toHaveTextContent("Full Name")
        expect(within(mappingSection as HTMLElement).getByRole("combobox")).not.toHaveTextContent("full_name")
    })

    it("uses a persistent field browser, live edit canvas, and docked settings rail", async () => {
        render(<FormBuilderPage />)

        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("flex-col", "xl:grid")
        expect(screen.getByTestId("form-builder-palette")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-canvas")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-page-shell")).toHaveClass("min-h-[58rem]")
        expect(screen.getByTestId("form-builder-settings")).toHaveClass("xl:min-h-[58rem]", "xl:self-stretch")
        expect(screen.queryByTestId("form-builder-page-rail")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        const canvas = screen.getByTestId("form-builder-canvas")
        expect(within(canvas).getByText("Name")).toBeInTheDocument()
        expect(within(canvas).queryByRole("button", { name: "Name field" })).not.toBeInTheDocument()
        expect(within(canvas).queryByText(/^text$/i)).not.toBeInTheDocument()
        expect(within(canvas).queryByText(/^required$/i)).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /select name field/i }))

        expect(await screen.findByRole("tab", { name: /^general$/i })).toBeInTheDocument()
        const selectedFieldActions = screen.getByTestId("form-builder-selected-field-actions")
        expect(selectedFieldActions).toHaveClass("gap-1.5", "pointer-events-none")
        expect(selectedFieldActions).not.toHaveClass("rounded-full", "border", "bg-white/95")
        expect(selectedFieldActions.childElementCount).toBe(2)
        expect(selectedFieldActions.querySelectorAll("button")).toHaveLength(2)
        expect(screen.getByRole("button", { name: "Duplicate Name" })).toHaveClass("rounded-full", "border")
        expect(screen.getByRole("button", { name: "Delete Name" })).toHaveClass("rounded-full", "border")
        expect(selectedFieldActions.nextElementSibling).not.toHaveClass("pr-24")
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

    it("returns field settings to General when another field is selected", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        fireEvent.click(await screen.findByRole("tab", { name: "Advanced" }))

        expect(screen.getByRole("tab", { name: "Advanced" })).toHaveAttribute("aria-selected", "true")

        fireEvent.click(screen.getByRole("button", { name: "Add Email field" }))

        expect(await screen.findByRole("tab", { name: "General" })).toHaveAttribute("aria-selected", "true")
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

    it("supports page renaming and omits page reorder buttons from the compact page strip", async () => {
        render(<FormBuilderPage />)

        fireEvent.click(screen.getByRole("button", { name: /^add page$/i }))

        expect(screen.queryByLabelText(/^page name$/i)).not.toBeInTheDocument()

        const pageTwoInput = screen.getByRole("textbox", { name: /edit page name/i })
        fireEvent.change(pageTwoInput, { target: { value: "Medical history" } })

        expect(screen.getByDisplayValue("Medical history")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /move medical history up/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /move medical history down/i })).not.toBeInTheDocument()
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
        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Enterprise Intake" } })

        fireEvent.click(screen.getByRole("tab", { name: /^preview$/i }))

        expect(await screen.findByRole("heading", { name: "Enterprise Intake" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^mobile preview$/i })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: /^mobile preview$/i }))
        expect(screen.getByTestId("form-builder-preview-shell")).toHaveClass("max-w-sm")

        fireEvent.click(screen.getByRole("tab", { name: /^edit$/i }))
        expect(screen.getByRole("button", { name: /select name field/i })).toBeInTheDocument()
    })
})
