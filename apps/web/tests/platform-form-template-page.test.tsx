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

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: /add name field/i }))

        expect(screen.queryByText(/Drag fields here to build your form/i)).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Name field" })).toBeInTheDocument()
    })

    it("uses design-system tab controls for workspace navigation and a dedicated settings tab", async () => {
        render(<PlatformFormTemplatePage />)

        expect(await screen.findByRole("tablist", { name: /workspace sections/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^builder$/i })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: /^settings$/i })).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-page-rail")).toBeInTheDocument()
        expect(screen.queryByRole("tablist", { name: /form pages/i })).not.toBeInTheDocument()
        expect(screen.queryByRole("tablist", { name: /builder settings/i })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("tab", { name: /^settings$/i }))

        expect(screen.getByText("Form Settings")).toBeInTheDocument()
        expect(screen.getByLabelText("Form Name")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-workspace")).toHaveClass("hidden")
    })

    it("uses responsive builder regions instead of fixed desktop-only panes", async () => {
        render(<PlatformFormTemplatePage />)

        expect(await screen.findByTestId("form-builder-workspace")).toHaveClass("xl:grid")
        expect(screen.getByTestId("form-builder-page-rail")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-canvas")).toBeInTheDocument()
        expect(screen.getByTestId("form-builder-settings")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: /^add fields$/i })).toBeInTheDocument()
        expect(screen.getByRole("tablist", { name: /canvas mode/i })).toBeInTheDocument()
    })

    it("adds contextual aria-labels to form builder icon buttons", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))
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
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))
        fireEvent.click(await screen.findByRole("button", { name: "Add Multi-Select field" }))

        const optionInput = await screen.findByDisplayValue("Option 1")
        optionInput.focus()
        fireEvent.change(optionInput, { target: { value: "Option 1 extended" } })

        const updatedInput = screen.getByDisplayValue("Option 1 extended")
        expect(updatedInput).toHaveFocus()
    })

    it("opens the field library, filters categories, and adds fields with click-to-add", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))

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

    it("supports page renaming and reordering from the page rail", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add page$/i }))

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
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: "Add Name field" }))

        const canvas = screen.getByTestId("form-builder-canvas")
        expect(within(canvas).queryByDisplayValue("Name")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Name field" }))

        expect(await screen.findByLabelText("Label")).toHaveValue("Name")
        expect(within(screen.getByTestId("form-builder-settings")).getByText("Text")).toBeInTheDocument()
    })

    it("renders an integrated preview without mutating builder data", async () => {
        render(<PlatformFormTemplatePage />)

        const formNameInput = await screen.findByLabelText("Form name")
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

    it("uses a simple global publish confirmation for form templates", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(await screen.findByRole("button", { name: /^add fields$/i }))
        fireEvent.click(screen.getByRole("button", { name: /add name field/i }))
        fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))

        expect(await screen.findByText("Publish Form Template")).toBeInTheDocument()
        expect(screen.getByText(/every organization library/i)).toBeInTheDocument()
        expect(screen.queryByText("Publish to all organizations")).not.toBeInTheDocument()
        expect(screen.queryByText("Publish to selected organizations")).not.toBeInTheDocument()
    })

})
