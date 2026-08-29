import { afterEach, describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react"
import type { ImgHTMLAttributes } from "react"
import PlatformFormTemplatePage from "../app/ops/templates/forms/[id]/page.client"

const mockUpdate = vi.fn()
const mockCreate = vi.fn()
const mockPublish = vi.fn()
const mockDelete = vi.fn()
const navigationState = vi.hoisted(() => ({
    templateId: "tpl_form_1",
}))

const buildTemplateData = (id = "tpl_form_1", name = "Surrogate Application Form") => ({
    id,
    status: "draft",
    current_version: 1,
    published_version: 0,
    is_published_globally: true,
    target_org_ids: [],
    draft: {
        name,
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
    useParams: () => ({ id: navigationState.templateId }),
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
        navigationState.templateId = "tpl_form_1"
        mockUpdate.mockReset()
        mockCreate.mockReset()
        mockPublish.mockReset()
        mockDelete.mockReset()
        mockTemplateData = buildTemplateData()
        vi.useRealTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("waits for the routed template response before hydrating the builder draft", async () => {
        const templateA = buildTemplateData("tpl-form-a", "Template A")
        const templateB = buildTemplateData("tpl-form-b", "Template B")

        navigationState.templateId = templateA.id
        mockTemplateData = templateA
        const view = render(<PlatformFormTemplatePage />)
        expect(await screen.findByPlaceholderText("Form name...")).toHaveValue("Template A")

        navigationState.templateId = templateB.id
        mockTemplateData = templateA
        view.rerender(<PlatformFormTemplatePage />)

        mockTemplateData = templateB
        view.rerender(<PlatformFormTemplatePage />)

        expect(await screen.findByPlaceholderText("Form name...")).toHaveValue("Template B")
    })

    it("does not autosave stale default schema during initial hydration", async () => {
        vi.useFakeTimers()
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

        const nameInput = screen.getByPlaceholderText("Form name...")
        expect(nameInput).toHaveValue("Stored Surrogate Application Form")

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1_200)
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
        expect(screen.getByLabelText("Internal template name")).toBeInTheDocument()
        expect(screen.getByText("Public Header")).toBeInTheDocument()
        expect(screen.getByLabelText("Eyebrow")).toBeInTheDocument()
        expect(screen.getByLabelText("Title")).toBeInTheDocument()
        expect(screen.getByLabelText("Subtitle")).toBeInTheDocument()
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
