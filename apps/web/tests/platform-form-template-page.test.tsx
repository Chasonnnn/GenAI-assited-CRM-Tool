import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react"
import type { ImgHTMLAttributes } from "react"
import PlatformFormTemplatePage from "../app/ops/templates/forms/[id]/page.client"

const mockUpdate = vi.fn()
const mockCreate = vi.fn()
const mockPublish = vi.fn()
const mockDelete = vi.fn()

const buildTemplateData = () => ({
    id: "tpl_form_1",
    status: "draft",
    current_version: 1,
    published_version: 0,
    is_published_globally: true,
    target_org_ids: [],
    draft: {
        name: "Surrogate Application Form",
        description: null,
        schema_json: null,
        settings_json: {},
    },
    published: null,
    updated_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
})

let mockTemplateData = buildTemplateData()

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "tpl_form_1" }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
}))

vi.mock("next/image", () => ({
    __esModule: true,
    default: ({ alt, ...props }: ImgHTMLAttributes<HTMLImageElement>) => (
        <span data-testid="next-image-mock" data-alt={alt ?? ""} {...props} />
    ),
}))

vi.mock("@/components/ops/templates/PublishDialog", () => ({
    PublishDialog: () => <div data-testid="publish-dialog" />,
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformFormTemplate: () => ({ data: mockTemplateData, isLoading: false }),
    useCreatePlatformFormTemplate: () => ({ mutateAsync: mockCreate, isPending: false }),
    useUpdatePlatformFormTemplate: () => ({ mutateAsync: mockUpdate, isPending: false }),
    usePublishPlatformFormTemplate: () => ({ mutateAsync: mockPublish, isPending: false }),
    useDeletePlatformFormTemplate: () => ({ mutateAsync: mockDelete, isPending: false }),
}))

describe("PlatformFormTemplatePage", () => {
    beforeEach(() => {
        mockUpdate.mockReset()
        mockCreate.mockReset()
        mockPublish.mockReset()
        mockDelete.mockReset()
        mockTemplateData = buildTemplateData()
        vi.useRealTimers()
    })

    it("does not autosave stale default schema during initial hydration", async () => {
        mockTemplateData = {
            ...buildTemplateData(),
            draft: {
                name: "Stored Surrogate Application Form",
                description: "Intake form",
                schema_json: {
                    pages: [
                        {
                            title: "Page 1",
                            fields: [
                                {
                                    key: "full_name",
                                    label: "Full Name",
                                    type: "text",
                                    required: true,
                                    options: null,
                                    validation: null,
                                    help_text: null,
                                    show_if: null,
                                    columns: null,
                                    min_rows: null,
                                    max_rows: null,
                                },
                            ],
                        },
                    ],
                    public_title: null,
                    logo_url: null,
                    privacy_notice: null,
                },
                settings_json: {},
            },
        }
        mockUpdate.mockResolvedValue({
            ...mockTemplateData,
            current_version: 2,
            updated_at: new Date().toISOString(),
        })

        render(<PlatformFormTemplatePage />)

        const nameInput = await screen.findByPlaceholderText("Form name...")
        await waitFor(() => expect(nameInput).toHaveValue("Stored Surrogate Application Form"))

        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 800))
        })

        expect(mockUpdate).not.toHaveBeenCalled()
    })

    it("uses the latest saved version for subsequent autosaves", async () => {
        mockUpdate
            .mockResolvedValueOnce({
                ...mockTemplateData,
                current_version: 2,
                updated_at: new Date().toISOString(),
            })
            .mockResolvedValueOnce({
                ...mockTemplateData,
                current_version: 3,
                updated_at: new Date().toISOString(),
            })

        render(<PlatformFormTemplatePage />)

        const nameInput = await screen.findByPlaceholderText("Form name...")
        expect(nameInput).toHaveValue("Surrogate Application Form")

        await act(async () => {
            fireEvent.change(nameInput, { target: { value: "Surrogate Application Form v2" } })
        })
        await waitFor(() => expect(mockUpdate.mock.calls.length).toBeGreaterThan(0), { timeout: 2000 })
        const callsAfterFirst = mockUpdate.mock.calls.length
        expect(
            mockUpdate.mock.calls.some(
                (call) => call[0]?.payload?.expected_version === 1
            )
        ).toBe(true)

        await act(async () => {
            fireEvent.change(nameInput, { target: { value: "Surrogate Application Form v3" } })
        })
        await waitFor(
            () => expect(mockUpdate.mock.calls.length).toBeGreaterThan(callsAfterFirst),
            { timeout: 2000 }
        )
        expect(mockUpdate).toHaveBeenLastCalledWith({
            id: "tpl_form_1",
            payload: expect.objectContaining({ expected_version: 2 }),
        })
    })

    it("adds a field from the palette without requiring drag and drop", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /add name field/i }))

        expect(screen.queryByText(/Drag fields here to build your form/i)).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: /select name field/i })).toBeInTheDocument()
    })

    it("uses design-system tab controls for workspace navigation and a dedicated settings tab", async () => {
        render(<PlatformFormTemplatePage />)

        expect(await screen.findByRole("tablist", { name: /workspace sections/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^edit$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^preview$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^settings$/i })).toBeInTheDocument()
        expect(screen.queryByRole("tab", { name: /^builder$/i })).not.toBeInTheDocument()
        expect(screen.getByTestId("form-builder-palette")).toBeInTheDocument()
        expect(screen.queryByRole("tablist", { name: /canvas mode/i })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))

        expect(screen.getByText("Form Settings")).toBeInTheDocument()
        expect(screen.getByLabelText("Form Name")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("hidden")
    })

    it("renders human-readable labels for inspector dropdown triggers across the template builder", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: "Add Name field" }))
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

        fireEvent.click(screen.getByRole("button", { name: "Add Table field" }))
        fireEvent.click(await screen.findByRole("button", { name: /select table field/i }))

        const columnsSection = screen.getByText("Table setup").closest("section")
        expect(columnsSection).not.toBeNull()

        const columnTypeSelect = within(columnsSection as HTMLElement).getAllByRole("combobox")[0]
        expect(columnTypeSelect).toHaveTextContent("Yes / No")
        expect(columnTypeSelect).not.toHaveTextContent("radio")

        fireEvent.mouseDown(columnTypeSelect)
        const longTextOption = await screen.findByRole("option", { name: "Long text" })
        fireEvent.mouseMove(longTextOption)
        fireEvent.click(longTextOption)

        expect(within(columnsSection as HTMLElement).getAllByRole("combobox")[0]).toHaveTextContent("Long text")
        expect(within(columnsSection as HTMLElement).getAllByRole("combobox")[0]).not.toHaveTextContent("textarea")
    })

    it("uses a persistent field browser, live edit canvas, and tabbed field settings rail", async () => {
        render(<PlatformFormTemplatePage />)

        expect(await screen.findByTestId("form-builder-workspace")).toHaveClass("flex-col", "xl:grid")
        expect(screen.getByTestId("form-builder-palette")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-canvas")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-page-shell")).toHaveClass("min-h-[58rem]")
        expect(screen.getByTestId("form-builder-settings")).toHaveClass("xl:min-h-[58rem]", "xl:self-stretch")
        expect(screen.queryByTestId("form-builder-page-rail")).not.toBeInTheDocument()

        fireEvent.click(await screen.findByRole("button", { name: "Add Name field" }))

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

    it("adds contextual aria-labels to form builder icon buttons", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))
        expect(await screen.findByRole("button", { name: "Duplicate Name" })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Delete Name" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Select field" }))
        expect(await screen.findByRole("button", { name: "Remove option Option 1" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Add Repeating Table field" }))
        expect(await screen.findByRole("button", { name: "Remove column Column 1" })).toBeInTheDocument()
    })

    it("keeps multi-select option inputs focused while editing", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: "Add Multi-Select field" }))

        const optionInput = await screen.findByDisplayValue("Option 1")
        optionInput.focus()
        fireEvent.change(optionInput, { target: { value: "Option 1 extended" } })

        const updatedInput = screen.getByDisplayValue("Option 1 extended")
        expect(updatedInput).toHaveFocus()
    })

    it("keeps the field library in the left sidebar, filters categories, and adds fields with click-to-add", async () => {
        render(<PlatformFormTemplatePage />)

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
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add page$/i }))

        expect(screen.queryByLabelText(/^page name$/i)).not.toBeInTheDocument()

        const pageTwoInput = screen.getByRole("textbox", { name: /edit page name/i })
        fireEvent.change(pageTwoInput, { target: { value: "Medical history" } })

        expect(screen.getByDisplayValue("Medical history")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /move medical history up/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: /move medical history down/i })).not.toBeInTheDocument()
    })

    it("adds a fixed table field with editable rows and columns", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: "Uploads and Tables" }))
        fireEvent.click(screen.getByRole("button", { name: "Add Table field" }))

        fireEvent.click(await screen.findByRole("button", { name: /select table field/i }))

        expect(await screen.findByDisplayValue("Item 1")).toBeInTheDocument()
        expect(screen.getByDisplayValue("Response")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add row$/i })).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add column$/i })).toBeInTheDocument()
    })

    it("renders preview as a top-level workspace tab without mutating edit state", async () => {
        render(<PlatformFormTemplatePage />)

        const formNameInput = await screen.findByLabelText("Form name")
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

    it("uses a simple global publish confirmation for form templates", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: /add name field/i }))
        fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))

        expect(await screen.findByText("Publish Form Template")).toBeInTheDocument()
        expect(screen.getByText(/every organization library/i)).toBeInTheDocument()
        expect(screen.queryByText("Publish to all organizations")).not.toBeInTheDocument()
        expect(screen.queryByText("Publish to selected organizations")).not.toBeInTheDocument()
    })

})
