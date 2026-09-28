import { afterEach, describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react"
import { Activity, type ImgHTMLAttributes } from "react"
import PlatformFormTemplatePage from "../app/ops/templates/forms/[id]/page.client"

const mockUpdate = vi.fn()
const mockCreate = vi.fn()
const mockPublish = vi.fn()
const mockDelete = vi.fn()
const navigationState = vi.hoisted(() => ({
    templateId: "tpl_form_1",
}))
const routerReplace = vi.hoisted(() => vi.fn())

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
        replace: routerReplace,
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
        routerReplace.mockReset()
        mockTemplateData = buildTemplateData()
        vi.useRealTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it("lets OPS choose donor templates without changing existing surrogate defaults", async () => {
        mockUpdate.mockResolvedValue({ ...mockTemplateData, current_version: 2 })
        render(<PlatformFormTemplatePage />)
        fireEvent.click(await screen.findByRole("button", { name: "Add Name field", exact: true }))
        fireEvent.click(await screen.findByRole("tab", { name: "Settings", exact: true }))
        const typeSelect = screen.getByRole("combobox", { name: "Template type" })
        expect(typeSelect).toHaveTextContent("Surrogate")
        expect(mockUpdate).not.toHaveBeenCalled()
        fireEvent.mouseDown(typeSelect)
        const donorOption = await screen.findByRole("option", { name: "Donor", exact: true })
        fireEvent.mouseMove(donorOption)
        fireEvent.click(donorOption)
        await waitFor(() => expect(mockUpdate).toHaveBeenLastCalledWith({
            id: "tpl_form_1",
            payload: expect.objectContaining({ settings_json: expect.objectContaining({
                purpose: "other", lead_kind: "egg_donor",
            }) }),
        }), { timeout: 2000 })
    })

    it("keeps donor routing settings and mappings when OPS autosaves a shared template", async () => {
        mockTemplateData = {
            ...buildTemplateData(),
            draft: {
                name: "Donor pre-screening",
                description: null,
                schema_json: { pages: [{ title: "Questionnaire", fields: [{
                    key: "donor_type", label: "Donor program", type: "radio", required: true,
                    options: [
                        { label: "Egg donor", value: "Egg donor" },
                        { label: "Sperm donor", value: "Sperm donor" },
                    ],
                }] }] },
                settings_json: {
                    purpose: "other", lead_kind: "egg_donor",
                    mappings: [{ field_key: "donor_type", surrogate_field: "donor_type" }],
                    allowed_mime_types: ["image/png", "image/jpeg"],
                    max_file_count: 1,
                },
            },
        }
        mockUpdate.mockResolvedValue({ ...mockTemplateData, current_version: 2 })
        render(<PlatformFormTemplatePage />)
        fireEvent.change(await screen.findByPlaceholderText("Form name..."), {
            target: { value: "Shared donor pre-screening" },
        })
        await waitFor(() => expect(mockUpdate).toHaveBeenCalled(), { timeout: 2000 })
        expect(mockUpdate).toHaveBeenLastCalledWith({
            id: "tpl_form_1",
            payload: expect.objectContaining({ settings_json: expect.objectContaining({
                purpose: "other", lead_kind: "egg_donor",
                mappings: [{ field_key: "donor_type", surrogate_field: "donor_type" }],
                max_file_count: 1, allowed_mime_types: ["image/png", "image/jpeg"],
            }) }),
        })
    })

    it("saves donor data classification from the field editor", async () => {
        mockTemplateData = {
            ...buildTemplateData(),
            draft: {
                name: "Donor screening", description: null,
                settings_json: { lead_kind: "egg_donor", purpose: "other" },
                schema_json: { pages: [{ title: "Questionnaire", fields: [{
                    key: "medical_history", label: "Medical history", type: "text", required: true,
                }] }] },
            },
        }
        mockUpdate.mockResolvedValue({ ...mockTemplateData, current_version: 2 })
        render(<PlatformFormTemplatePage />)
        fireEvent.click(await screen.findByRole("button", { name: "Select Medical history field" }))
        fireEvent.click(screen.getByRole("tab", { name: "Advanced", exact: true }))
        const classification = screen.getByRole("combobox", { name: "Data classification" })
        fireEvent.mouseDown(classification)
        const healthOption = await screen.findByRole("option", { name: "Health", exact: true })
        fireEvent.mouseMove(healthOption)
        fireEvent.click(healthOption)
        await waitFor(() => expect(mockUpdate).toHaveBeenLastCalledWith({
            id: "tpl_form_1",
            payload: expect.objectContaining({ schema_json: expect.objectContaining({
                pages: [expect.objectContaining({ fields: [expect.objectContaining({
                    key: "medical_history", sensitivity: "sensitive_health",
                })] })],
            }) }),
        }), { timeout: 2000 })
        expect(classification).toHaveTextContent("Health")
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

    it("does not autosave a template opened from another template without edits", async () => {
        vi.useFakeTimers()
        const templateA = buildTemplateData("tpl-form-a", "Template A")
        const templateB = buildTemplateData("tpl-form-b", "Template B")

        navigationState.templateId = templateA.id
        mockTemplateData = templateA
        const view = render(<PlatformFormTemplatePage />)
        expect(screen.getByPlaceholderText("Form name...")).toHaveValue("Template A")

        navigationState.templateId = templateB.id
        mockTemplateData = templateB
        view.rerender(<PlatformFormTemplatePage />)
        await act(async () => {
            await vi.advanceTimersByTimeAsync(5_000)
        })

        expect(screen.getByPlaceholderText("Form name...")).toHaveValue("Template B")
        expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument()
        expect(mockUpdate).not.toHaveBeenCalled()
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

    it("separates template delete in the overflow menu from the page toolbar's Delete page", async () => {
        mockDelete.mockRejectedValueOnce(new Error("foreign key violation on form_submissions"))
        render(<PlatformFormTemplatePage />)

        const deletePage = await screen.findByRole("button", { name: /^Delete page/ })
        expect(deletePage).toHaveTextContent("Delete page")
        expect(deletePage).not.toHaveClass("border")
        expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))
        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Delete Surrogate Application Form?")).toBeInTheDocument()
        const confirmButton = within(confirm).getByRole("button", { name: "Delete" })
        expect(confirmButton).toHaveClass("bg-destructive")
        expect(confirmButton.className).not.toMatch(/linear-gradient/)

        fireEvent.click(confirmButton)
        expect(await within(confirm).findByText("Couldn't delete template.")).toBeInTheDocument()
        expect(screen.queryByText(/foreign key/)).not.toBeInTheDocument()
        expect(mockDelete).toHaveBeenCalledWith({ id: "tpl_form_1" })
    })

    it("uses a simple global publish confirmation for form templates", async () => {
        render(<PlatformFormTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: /add name field/i }))
        fireEvent.click(screen.getByRole("button", { name: /^publish$/i }))

        expect(await screen.findByText("Publish Form Template")).toBeInTheDocument()
        expect(screen.getByText(/every organization library/i)).toBeInTheDocument()
        expect(screen.queryByText("Publish to all organizations")).not.toBeInTheDocument()
        expect(screen.queryByText("Publish to selected organizations")).not.toBeInTheDocument()
        // The description already says it goes to every library; no second box restates it.
        expect(screen.queryByText(/does not need org targeting/i)).not.toBeInTheDocument()
    })

    it("can republish saved edits to an already published template", async () => {
        mockTemplateData = { ...buildTemplateData(), status: "published", published_version: 1 }
        mockUpdate.mockResolvedValue({ ...mockTemplateData, current_version: 2 })
        mockPublish.mockResolvedValue({ ...mockTemplateData, current_version: 3, published_version: 2 })

        render(<PlatformFormTemplatePage />)
        fireEvent.click(await screen.findByRole("button", { name: /add name field/i }))
        fireEvent.click(screen.getByRole("button", { name: /^save$/i }))
        await waitFor(() => expect(mockUpdate).toHaveBeenCalled())

        const publishButton = screen.getByRole("button", { name: /^publish$/i })
        await waitFor(() => expect(publishButton).toBeEnabled())
        fireEvent.click(publishButton)
        const dialog = await screen.findByRole("dialog", { name: "Publish Form Template" })
        expect(mockPublish).not.toHaveBeenCalled()
        fireEvent.click(within(dialog).getByRole("button", { name: /^publish$/i }))

        await waitFor(() => expect(mockPublish).toHaveBeenCalledWith({
            id: "tpl_form_1",
            payload: { publish_all: true, org_ids: null, expected_version: 2 },
        }))
        await waitFor(() => expect(screen.queryByRole("dialog", { name: "Publish Form Template" })).not.toBeInTheDocument())
        fireEvent.click(screen.getByRole("button", { name: /add name field/i }))
        fireEvent.click(screen.getByRole("button", { name: /^save$/i }))
        await waitFor(() => expect(mockUpdate).toHaveBeenLastCalledWith({
            id: "tpl_form_1", payload: expect.objectContaining({ expected_version: 3 }),
        }))
    })

    it("sends a rename made during an in-flight autosave exactly once", async () => {
        vi.useFakeTimers()
        const saves: Array<{ name: string; settled: boolean; finish: () => void }> = []
        mockUpdate.mockImplementation(({ payload }: { payload: { name: string } }) =>
            new Promise((resolve) => {
                const version = saves.length + 2
                const save = {
                    name: payload.name,
                    settled: false,
                    finish: () => {
                        save.settled = true
                        resolve({
                            ...mockTemplateData,
                            current_version: version,
                            draft: { ...mockTemplateData.draft, name: payload.name },
                        })
                    },
                }
                saves.push(save)
            }))
        const advance = async (ms: number) => {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(ms)
            })
        }
        const settleStartedSaves = async () => {
            for (const save of saves) {
                if (!save.settled) save.finish()
            }
            await advance(10)
        }

        render(<PlatformFormTemplatePage />)
        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed once" } })
        await advance(1200)
        expect(saves.map((save) => save.name)).toEqual(["Renamed once"])

        fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed twice" } })
        await advance(3000)
        saves[0].finish()
        await advance(10)
        await advance(3000)
        await settleStartedSaves()
        await settleStartedSaves()
        await advance(5000)

        expect(saves.map((save) => save.name)).toEqual(["Renamed once", "Renamed twice"])
        expect(screen.getByText(/^Saved /)).toBeInTheDocument()
    })

    describe("while a save is pending", () => {
        const advance = async (ms: number) => {
            await act(async () => {
                await vi.advanceTimersByTimeAsync(ms)
            })
        }
        const saveButton = () => screen.getByRole("button", { name: /^save$/i })
        const publishButton = () => screen.getByRole("button", { name: /^publish$/i })
        const deferred = (mock: typeof mockUpdate) => {
            const requests: Array<{ finish: () => void }> = []
            mock.mockImplementation(({ payload }: { payload: { name: string } }) =>
                new Promise((resolve) => {
                    requests.push({
                        finish: () =>
                            resolve({
                                ...mockTemplateData,
                                id: "tpl_form_1",
                                current_version: 2,
                                draft: { ...mockTemplateData.draft, name: payload.name },
                            }),
                    })
                }))
            return requests
        }

        beforeEach(() => {
            vi.useFakeTimers()
        })

        it("ignores Save and Publish while a new template is being created", async () => {
            navigationState.templateId = "new"
            mockTemplateData = undefined as unknown as typeof mockTemplateData
            const creates: Array<{ finish: () => void }> = []
            mockCreate.mockImplementation((payload: { name: string }) =>
                new Promise((resolve) => {
                    creates.push({
                        finish: () =>
                            resolve({
                                ...buildTemplateData("tpl-form-new", payload.name),
                                current_version: 1,
                            }),
                    })
                }))
            render(<PlatformFormTemplatePage />)
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "New intake" } })
            fireEvent.click(screen.getByRole("button", { name: /add name field/i }))

            fireEvent.click(saveButton())
            await advance(10)
            expect(creates).toHaveLength(1)
            expect(saveButton()).toBeDisabled()
            expect(publishButton()).toBeDisabled()

            fireEvent.click(saveButton())
            fireEvent.click(publishButton())
            await advance(10)
            expect(screen.queryByRole("dialog", { name: "Publish Form Template" })).not.toBeInTheDocument()

            creates[0].finish()
            await advance(10)
            await advance(5000)

            expect(mockCreate).toHaveBeenCalledTimes(1)
            expect(mockUpdate).not.toHaveBeenCalled()
            expect(mockPublish).not.toHaveBeenCalled()
            expect(routerReplace.mock.calls).toEqual([["/ops/templates/forms/tpl-form-new"]])
            expect(saveButton()).toBeEnabled()
        })

        it("does not resend a draft whose autosave failed until it changes", async () => {
            mockUpdate.mockImplementation(() =>
                new Promise((_resolve, reject) => {
                    setTimeout(() => reject(new Error("Template changed since it was loaded")), 300)
                }))
            render(<PlatformFormTemplatePage />)
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed once" } })
            await advance(1200)
            await advance(400)
            expect(mockUpdate).toHaveBeenCalledTimes(1)

            await advance(12000)
            expect(mockUpdate).toHaveBeenCalledTimes(1)
            expect(screen.getByText("Autosave failed")).toBeInTheDocument()

            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed twice" } })
            await advance(1200)
            await advance(10)
            await advance(12000)

            expect(mockUpdate.mock.calls.map(([{ payload }]) => payload.name)).toEqual([
                "Renamed once",
                "Renamed twice",
            ])
        })

        it("autosaves a failed draft again after it is edited away and back", async () => {
            mockUpdate.mockImplementation(() =>
                new Promise((_resolve, reject) => {
                    setTimeout(() => reject(new Error("Template changed since it was loaded")), 300)
                }))
            render(<PlatformFormTemplatePage />)
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed once" } })
            await advance(1200)
            await advance(400)
            expect(mockUpdate).toHaveBeenCalledTimes(1)

            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed twice" } })
            await advance(500)
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed once" } })
            await advance(1200)
            await advance(400)

            expect(mockUpdate.mock.calls.map(([{ payload }]) => payload.name)).toEqual([
                "Renamed once",
                "Renamed once",
            ])
        })

        it("keeps a template created while the builder is hidden and redirects when it is shown", async () => {
            navigationState.templateId = "new"
            mockTemplateData = undefined as unknown as typeof mockTemplateData
            const creates: Array<{ finish: () => void }> = []
            mockCreate.mockImplementation((payload: { name: string }) =>
                new Promise((resolve) => {
                    creates.push({
                        finish: () =>
                            resolve({
                                ...buildTemplateData("tpl-form-new", payload.name),
                                current_version: 1,
                            }),
                    })
                }))
            mockUpdate.mockImplementation(async ({ id, payload }: { id: string; payload: { name: string } }) => ({
                ...buildTemplateData(id, payload.name),
                current_version: 2,
            }))
            const renderBuilder = (mode: "visible" | "hidden") => (
                <Activity mode={mode}>
                    <PlatformFormTemplatePage />
                </Activity>
            )
            const view = render(renderBuilder("visible"))
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "New intake" } })
            fireEvent.click(saveButton())
            await advance(10)
            expect(creates).toHaveLength(1)

            view.rerender(renderBuilder("hidden"))
            await advance(10)
            creates[0].finish()
            await advance(10)
            expect(routerReplace).not.toHaveBeenCalled()

            view.rerender(renderBuilder("visible"))
            await advance(10)
            expect(routerReplace.mock.calls).toEqual([["/ops/templates/forms/tpl-form-new"]])

            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "New intake v2" } })
            fireEvent.click(saveButton())
            await advance(10)

            expect(mockCreate).toHaveBeenCalledTimes(1)
            expect(mockUpdate).toHaveBeenCalledWith({
                id: "tpl-form-new",
                payload: expect.objectContaining({ name: "New intake v2", expected_version: 1 }),
            })
            expect(routerReplace).toHaveBeenCalledTimes(1)
        })

        it("clears Save when the builder is hidden and shown again during the save", async () => {
            const saves = deferred(mockUpdate)
            const renderBuilder = (mode: "visible" | "hidden") => (
                <Activity mode={mode}>
                    <PlatformFormTemplatePage />
                </Activity>
            )
            const view = render(renderBuilder("visible"))
            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed" } })
            fireEvent.click(saveButton())
            await advance(10)
            expect(saves).toHaveLength(1)

            view.rerender(renderBuilder("hidden"))
            await advance(10)
            view.rerender(renderBuilder("visible"))
            await advance(10)
            saves[0].finish()
            await advance(10)
            await advance(5000)

            expect(saves).toHaveLength(1)
            expect(saveButton()).toBeEnabled()
            expect(publishButton()).toBeEnabled()
            expect(screen.getByText(/^Saved /)).toBeInTheDocument()
        })
    })

    describe("publish state", () => {
        const liveSchema = {
            pages: [{ title: "Application", fields: [
                { key: "full_name", label: "Full Name", type: "text", required: true },
            ] }],
            public_title: "Apply today",
        }
        // Same content as liveSchema, with every object's keys in a different order.
        const reorderedLiveSchema = {
            public_title: "Apply today",
            pages: [{ fields: [
                { required: true, type: "text", label: "Full Name", key: "full_name" },
            ], title: "Application" }],
        }
        const buildPublishedTemplate = (draftSchema: Record<string, unknown>) => ({
            ...buildTemplateData(),
            status: "published",
            published_version: 1,
            draft: { name: "Surrogate Application Form", description: null, schema_json: draftSchema, settings_json: {} },
            published: { name: "Surrogate Application Form", description: null, schema_json: liveSchema, settings_json: {} },
        })
        const header = () => within(screen.getByLabelText("Form name").parentElement as HTMLElement)

        it("shows Published when the saved draft matches the published template", () => {
            mockTemplateData = buildPublishedTemplate(reorderedLiveSchema)
            render(<PlatformFormTemplatePage />)

            expect(header().getByText("Published")).toBeInTheDocument()
        })

        it("shows Unpublished changes when the saved draft differs from the published template", () => {
            mockTemplateData = buildPublishedTemplate({ ...liveSchema, public_title: "Apply now" })
            render(<PlatformFormTemplatePage />)

            expect(header().getByText("Unpublished changes")).toBeInTheDocument()
            expect(header().queryByText("Published")).not.toBeInTheDocument()
            expect(screen.getByRole("button", { name: /^publish$/i })).toBeEnabled()
        })

        it("shows Unpublished changes for an unsaved rename of a published template", () => {
            mockTemplateData = buildPublishedTemplate(liveSchema)
            render(<PlatformFormTemplatePage />)

            fireEvent.change(screen.getByLabelText("Form name"), { target: { value: "Renamed template" } })

            expect(header().getByText("Unpublished changes")).toBeInTheDocument()
        })
    })
})
