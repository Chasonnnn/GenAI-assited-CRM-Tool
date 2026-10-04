import type { ReactNode } from "react"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { assert, beforeEach, describe, expect, it, vi } from "vitest"

import PlatformWorkflowTemplatePage from "@/app/ops/templates/workflows/[id]/page.client"
import type { PlatformWorkflowTemplate } from "@/lib/api/platform"
import type { Condition } from "@/lib/api/workflows"

const templateState = vi.hoisted(() => ({
    data: {
        id: "workflow-template-1",
        status: "draft" as const,
        current_version: 4,
        published_version: 0,
        is_published_globally: true,
        draft: {
            name: "Server workflow",
            description: "Server description",
            icon: "template",
            category: "general",
            trigger_type: "surrogate_created",
            trigger_config: {},
            conditions: [],
            condition_logic: "AND",
            actions: [],
        },
        updated_at: "2026-07-16T12:00:00Z",
        created_at: "2026-07-16T12:00:00Z",
        target_org_ids: [],
    } as PlatformWorkflowTemplate,
}))

const workflowOptions = vi.hoisted(() => ({
    statuses: [] as Array<{ id?: string; value: string; label: string }>,
    action_types: [],
    trigger_types: [] as Array<{ value: string; label: string; description?: string }>,
    update_fields: [],
    condition_operators: [],
    condition_fields: [],
    users: [],
    queues: [],
    forms: [] as Array<{ id: string; name: string; lead_kind?: string; lead_kinds?: string[] }>,
    action_types_by_trigger: {},
}))

const mutationMocks = vi.hoisted(() => ({
    create: vi.fn(),
    update: vi.fn(),
    publish: vi.fn(),
    remove: vi.fn(),
}))

const workflowOptionsMocks = vi.hoisted(() => ({
    use: vi.fn(),
}))

const routeState = vi.hoisted(() => ({
    id: "workflow-template-1",
    push: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
}))

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: routeState.id }),
    useRouter: () => ({
        push: routeState.push,
        replace: vi.fn(),
    }),
}))

vi.mock("@/components/app-link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

vi.mock("@/components/ui/toast", () => ({
    toast: {
        success: routeState.toastSuccess,
        error: routeState.toastError,
    },
}))

vi.mock("@/lib/hooks/use-platform-templates", () => ({
    usePlatformWorkflowTemplate: () => ({
        data: templateState.data,
        isLoading: false,
    }),
    useCreatePlatformWorkflowTemplate: () => ({
        mutateAsync: mutationMocks.create,
    }),
    useUpdatePlatformWorkflowTemplate: () => ({
        mutateAsync: mutationMocks.update,
    }),
    usePublishPlatformWorkflowTemplate: () => ({
        mutateAsync: mutationMocks.publish,
    }),
    useDeletePlatformWorkflowTemplate: () => ({
        mutateAsync: mutationMocks.remove,
        isPending: false,
    }),
}))

vi.mock("@/lib/hooks/use-workflows", () => ({
    useWorkflowOptions: (scope: string, subjectType: string) => {
        workflowOptionsMocks.use(scope, subjectType)
        return { data: workflowOptions }
    },
}))

vi.mock("@/components/ops/templates/PublishDialog", () => ({
    PublishDialog: ({
        open,
        onPublish,
    }: {
        open: boolean
        onPublish: (publishAll: boolean, orgIds: string[]) => void
    }) => open ? <button onClick={() => onPublish(true, [])}>Confirm workflow publish</button> : null,
}))

describe("platform workflow template draft ownership", () => {
    beforeEach(() => {
        routeState.id = "workflow-template-1"
        routeState.push.mockReset()
        routeState.toastError.mockReset()
        routeState.toastSuccess.mockReset()
        mutationMocks.create.mockReset()
        mutationMocks.update.mockReset()
        mutationMocks.publish.mockReset()
        mutationMocks.remove.mockReset()
        workflowOptionsMocks.use.mockReset()
        workflowOptions.statuses = []
        workflowOptions.trigger_types = []
        workflowOptions.forms = []
        mutationMocks.update.mockImplementation(async () => ({
            ...templateState.data,
            current_version: templateState.data.current_version + 1,
        }))
        mutationMocks.publish.mockResolvedValue(templateState.data)
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                name: "Server workflow",
                subject_type: "surrogate",
                trigger_type: "surrogate_created",
                trigger_config: {},
                actions: [],
                conditions: [],
            },
        }
    })

    it("saves donor-only conditions on a form-submitted template", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                trigger_type: "form_submitted",
                conditions: [{ field: "lead_kind", operator: "in", value: ["egg_donor", "sperm_donor"] }],
                actions: [{ action_type: "add_note", content: "Review the application." }],
            },
        }
        mutationMocks.update.mockResolvedValue(templateState.data)
        render(<PlatformWorkflowTemplatePage />)
        expect(screen.queryByRole("switch", { name: "Create donor after photo scan" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        await waitFor(() => expect(mutationMocks.update).toHaveBeenCalledWith({
            id: "workflow-template-1",
            payload: expect.objectContaining({
                conditions: [{ field: "lead_kind", operator: "in", value: ["egg_donor", "sperm_donor"] }],
                actions: [{ action_type: "add_note", content: "Review the application." }],
            }),
        }))
    })

    it("hydrates and saves an explicit donor subject for legacy donor templates", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                subject_type: null,
                trigger_type: "donor_created",
                actions: [{ action_type: "add_note", content: "Review the donor record." }],
            },
        }
        mutationMocks.update.mockResolvedValue(templateState.data)

        render(<PlatformWorkflowTemplatePage />)

        const subjectLabel = screen.getByText("Subject Type *")
        const subjectSelect = subjectLabel.parentElement?.querySelector("button")
        expect(subjectSelect).not.toBeNull()
        expect(subjectSelect).toHaveTextContent("Select subject type")

        fireEvent.click(screen.getByRole("button", { name: "Publish" }))
        expect(screen.queryByRole("button", { name: "Confirm workflow publish" })).not.toBeInTheDocument()

        fireEvent.click(subjectSelect as HTMLButtonElement)
        const spermDonorOption = screen.getByRole("option", { name: "Sperm Donor" })
        fireEvent.mouseMove(spermDonorOption)
        fireEvent.click(spermDonorOption)
        await waitFor(() => {
            expect(screen.getByLabelText("Subject type")).toHaveTextContent("Sperm Donor")
            expect(workflowOptionsMocks.use).toHaveBeenCalledWith("org", "sperm_donor")
        })

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mutationMocks.update).toHaveBeenCalledWith({
                id: "workflow-template-1",
                payload: expect.objectContaining({
                    subject_type: "sperm_donor",
                    trigger_type: "donor_created",
                    actions: [{ action_type: "add_note", content: "Review the donor record." }],
                }),
            })
        })
    })

    it("shows the readable label for a hydrated donor subject", () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                subject_type: "egg_donor",
                trigger_type: "donor_created",
                actions: [{ action_type: "add_note", content: "Review the donor record." }],
            },
        }

        render(<PlatformWorkflowTemplatePage />)

        const subjectLabel = screen.getByText("Subject Type *")
        expect(subjectLabel.parentElement?.querySelector("button")).toHaveTextContent("Egg Donor")
    })

    it("uses donor recipients for donor email templates", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                subject_type: "egg_donor",
                trigger_type: "donor_created",
                actions: [{ action_type: "send_email", requires_approval: true }],
            },
        }
        mutationMocks.update.mockResolvedValue(templateState.data)

        render(<PlatformWorkflowTemplatePage />)

        const recipientLabel = screen.getByText("Recipient")
        expect(recipientLabel.parentElement?.querySelector("button")).toHaveTextContent("Donor")

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mutationMocks.update).toHaveBeenCalledWith({
                id: "workflow-template-1",
                payload: expect.objectContaining({
                    actions: [{ action_type: "send_email", requires_approval: true, recipients: "donor" }],
                }),
            })
        })
    })

    it("requires stage references to be reselected when the donor subtype changes", async () => {
        const legacyStageCondition = {
            field: "stage_id",
            operator: "equals",
            value: "egg-stage-to",
            stage_key: "egg-ready",
            stage_keys: ["egg-ready"],
        } satisfies Condition & { stage_key: string; stage_keys: string[] }
        workflowOptions.statuses = [
            { id: "egg-stage-from", value: "egg_review", label: "Egg Review" },
            { id: "egg-stage-to", value: "egg_ready", label: "Egg Ready" },
            { id: "sperm-stage-to", value: "sperm_ready", label: "Sperm Ready" },
        ]
        workflowOptions.trigger_types = [
            { value: "donor_created", label: "Donor Created" },
            { value: "donor_stage_changed", label: "Donor Stage Changed" },
        ]
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                subject_type: "egg_donor",
                trigger_type: "donor_stage_changed",
                trigger_config: {
                    from_stage_id: "egg-stage-from",
                    to_stage_id: "egg-stage-to",
                    from_stage_key: "egg-review",
                    to_stage_key: "egg-ready",
                },
                conditions: [
                    legacyStageCondition,
                    { field: "education", operator: "equals", value: "college" },
                ],
                actions: [
                    {
                        action_type: "update_field",
                        field: "stage_id",
                        value: "egg-stage-to",
                        value_stage_key: "egg-ready",
                    },
                    { action_type: "add_note", content: "Review the donor record." },
                ],
            },
        }

        render(<PlatformWorkflowTemplatePage />)

        const subjectLabel = screen.getByText("Subject Type *")
        const subjectSelect = subjectLabel.parentElement?.querySelector("button")
        fireEvent.click(subjectSelect as HTMLButtonElement)
        const spermDonorOption = screen.getByRole("option", { name: "Sperm Donor" })
        fireEvent.mouseMove(spermDonorOption)
        fireEvent.click(spermDonorOption)

        await waitFor(() => {
            expect(screen.getByLabelText("Subject type")).toHaveTextContent("Sperm Donor")
        })
        const triggerLabel = screen.getByText("Trigger Type *")
        const triggerSelect = triggerLabel.parentElement?.querySelector("button")
        expect(triggerSelect).toHaveTextContent("Select trigger")
        expect(screen.getByText("Education")).toBeInTheDocument()
        expect(screen.getAllByRole("button", { name: "Remove condition" })).toHaveLength(2)
        expect(screen.queryByText("egg-stage-to")).not.toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        expect(mutationMocks.update).not.toHaveBeenCalled()
        expect(screen.getByText("Trigger type is required.")).toBeInTheDocument()

        fireEvent.click(triggerSelect as HTMLButtonElement)
        const donorCreatedOption = screen.getByRole("option", { name: "Donor Created" })
        fireEvent.mouseMove(donorCreatedOption)
        fireEvent.click(donorCreatedOption)

        expect(screen.getByText("Select a stage for each stage condition.")).toBeInTheDocument()
        const removeCondition = screen.getAllByRole("button", { name: "Remove condition" })[0]
        assert.isDefined(removeCondition)
        const stageCondition = removeCondition.closest<HTMLElement>('[data-slot="card"]')
        assert.isNotNull(stageCondition)
        const conditionStageSelect = within(stageCondition).getAllByRole("combobox")[2]
        assert.isDefined(conditionStageSelect)
        fireEvent.click(conditionStageSelect)
        const spermConditionStage = screen.getByRole("option", { name: "Sperm Ready" })
        fireEvent.mouseMove(spermConditionStage)
        fireEvent.click(spermConditionStage)

        expect(screen.getByText("Update actions need a value.")).toBeInTheDocument()
        const removeAction = screen.getAllByRole("button", { name: "Remove action" })[0]
        assert.isDefined(removeAction)
        const stageAction = removeAction.closest<HTMLElement>('[data-slot="card"]')
        assert.isNotNull(stageAction)
        const actionStageSelect = within(stageAction).getAllByRole("combobox")[2]
        assert.isDefined(actionStageSelect)
        fireEvent.click(actionStageSelect)
        const spermActionStage = screen.getAllByRole("option", { name: "Sperm Ready" }).at(-1) as HTMLElement
        fireEvent.mouseMove(spermActionStage)
        fireEvent.click(spermActionStage)
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => expect(mutationMocks.update).toHaveBeenCalled())
        const savedPayload = mutationMocks.update.mock.calls.at(-1)?.[0].payload
        expect(savedPayload.conditions).toEqual([
            { field: "stage_id", operator: "equals", value: "sperm-stage-to" },
            { field: "education", operator: "equals", value: "college" },
        ])
        expect(savedPayload.actions).toEqual([
            { action_type: "update_field", field: "stage_id", value: "sperm-stage-to" },
            { action_type: "add_note", content: "Review the donor record." },
        ])
    })

    it("uses the surrogate recipient when a donor template changes to surrogate", async () => {
        workflowOptions.trigger_types = [
            { value: "donor_created", label: "Donor Created" },
            { value: "surrogate_created", label: "Surrogate Created" },
        ]
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                subject_type: "egg_donor",
                trigger_type: "donor_created",
                actions: [{ action_type: "send_email", recipients: "donor", requires_approval: true }],
            },
        }

        render(<PlatformWorkflowTemplatePage />)

        fireEvent.click(screen.getByLabelText("Subject type"))
        const surrogateOption = screen.getByRole("option", { name: "Surrogate" })
        fireEvent.mouseMove(surrogateOption)
        fireEvent.click(surrogateOption)

        const recipientLabel = screen.getByText("Recipient")
        expect(recipientLabel.parentElement?.querySelector("button")).toHaveTextContent("Surrogate")

        const triggerLabel = screen.getByText("Trigger Type *")
        const triggerSelect = triggerLabel.parentElement?.querySelector("button")
        fireEvent.click(triggerSelect as HTMLButtonElement)
        const surrogateCreatedOption = screen.getByRole("option", { name: "Surrogate Created" })
        fireEvent.mouseMove(surrogateCreatedOption)
        fireEvent.click(surrogateCreatedOption)
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mutationMocks.update).toHaveBeenCalledWith({
                id: "workflow-template-1",
                payload: expect.objectContaining({
                    subject_type: "surrogate",
                    actions: [{ action_type: "send_email", recipients: "surrogate", requires_approval: true }],
                }),
            })
        })
    })

    it("edits with current_version and publishes the revision returned by the save", async () => {
        templateState.data.draft.actions = [{ action_type: "add_note", content: "Follow up" }]
        mutationMocks.publish.mockResolvedValue({ ...templateState.data, current_version: 6 })
        render(<PlatformWorkflowTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Publish" }))
        fireEvent.click(screen.getByRole("button", { name: "Confirm workflow publish" }))

        await waitFor(() => expect(mutationMocks.update).toHaveBeenCalledWith({
            id: "workflow-template-1",
            payload: expect.objectContaining({ expected_version: 4 }),
        }))
        expect(mutationMocks.publish).toHaveBeenCalledWith({
            id: "workflow-template-1",
            payload: { publish_all: true, org_ids: null, expected_version: 5 },
        })
        await waitFor(() => expect(screen.getByRole("button", { name: "Save draft" })).toBeEnabled())
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        await waitFor(() => expect(mutationMocks.update).toHaveBeenLastCalledWith({
            id: "workflow-template-1", payload: expect.objectContaining({ expected_version: 6 }),
        }))
    })

    it("marks the name field instead of toasting when the name is missing", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                actions: [{ action_type: "add_note", content: "Hello" }],
            },
        }
        render(<PlatformWorkflowTemplatePage />)
        const nameInput = screen.getByRole("textbox", { name: "Workflow template name" })

        fireEvent.change(nameInput, { target: { value: "  " } })
        expect(nameInput).not.toHaveAttribute("aria-invalid")
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        expect(await screen.findByText("Enter a template name.")).toBeInTheDocument()
        expect(nameInput).toHaveAttribute("aria-invalid", "true")
        expect(nameInput).toHaveAttribute("aria-describedby", "workflow-name-error")
        expect(nameInput).toHaveFocus()
        expect(routeState.toastError).not.toHaveBeenCalled()
        expect(mutationMocks.update).not.toHaveBeenCalled()
        expect(screen.getAllByText("Enter a template name.")).toHaveLength(1)

        fireEvent.change(nameInput, { target: { value: "Welcome flow" } })
        expect(nameInput).not.toHaveAttribute("aria-invalid")
        expect(screen.queryByText("Enter a template name.")).not.toBeInTheDocument()
    })

    it("sizes the header name field for full template names at the header font size", () => {
        render(<PlatformWorkflowTemplatePage />)
        const nameInput = screen.getByRole("textbox", { name: "Workflow template name" })

        // At text-lg, w-72 cut seeded names such as "New Surrogate Intake Follow-up". The field grows
        // with its content where field-sizing is supported and falls back to a fixed wide field.
        expect(nameInput).toHaveClass(
            "md:text-lg",
            "field-sizing-content",
            "supports-[field-sizing:content]:w-auto",
            "w-[36rem]",
            "max-w-full",
        )
        expect(nameInput).not.toHaveClass("w-72")
    })

    it("shows the save state and a safe message when saving fails", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                actions: [{ action_type: "add_note", content: "Hello" }],
            },
        }
        mutationMocks.update.mockRejectedValueOnce(new Error("duplicate key value violates unique constraint"))
        render(<PlatformWorkflowTemplatePage />)

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        expect(await screen.findByText("Not saved")).toBeInTheDocument()
        expect(routeState.toastError).toHaveBeenCalledWith("Couldn't save template.")

        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))
        expect(await screen.findByText("Saved")).toBeInTheDocument()
    })

    it("offers sample loaders only on a new, empty workflow", () => {
        const { unmount } = render(<PlatformWorkflowTemplatePage />)
        expect(screen.queryByRole("button", { name: "Load Zapier Conversion Sample" })).not.toBeInTheDocument()
        unmount()

        routeState.id = "new"
        render(<PlatformWorkflowTemplatePage />)
        expect(screen.getByRole("button", { name: "Load Zapier Conversion Sample" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Load Shared Intake Sample" })).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "More actions" })).not.toBeInTheDocument()
    })

    it("deletes from the overflow menu with a destructive confirm", async () => {
        mutationMocks.remove.mockResolvedValue(undefined)
        render(<PlatformWorkflowTemplatePage />)

        expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "More actions" }))
        fireEvent.click(await screen.findByRole("menuitem", { name: "Delete" }))

        const confirm = await screen.findByRole("alertdialog")
        expect(within(confirm).getByText("Delete Server workflow?")).toBeInTheDocument()
        const deleteButton = within(confirm).getByRole("button", { name: "Delete" })
        expect(deleteButton).toHaveClass("bg-destructive")
        expect(deleteButton.className).not.toMatch(/linear-gradient/)

        fireEvent.click(deleteButton)
        await waitFor(() => expect(mutationMocks.remove).toHaveBeenCalledWith({ id: "workflow-template-1" }))
        expect(routeState.push).toHaveBeenCalledWith("/ops/templates?tab=workflows")
    })

    it("preserves an in-progress name edit across an equivalent query rerender", () => {
        const { rerender } = render(<PlatformWorkflowTemplatePage />)
        const nameInput = screen.getByRole("textbox", {
            name: "Workflow template name",
        })

        fireEvent.change(nameInput, {
            target: { value: "Operator draft" },
        })
        expect(nameInput).toHaveValue("Operator draft")

        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
            },
        }
        rerender(<PlatformWorkflowTemplatePage />)

        expect(nameInput).toHaveValue("Operator draft")
    })

    it("resolves a legacy stage label when workflow options arrive after the draft", async () => {
        mutationMocks.update.mockResolvedValue(templateState.data)
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                trigger_type: "status_changed",
                trigger_config: {
                    to_status: "qualified",
                },
                actions: [
                    {
                        action_type: "add_note",
                        content: "Record the stage transition.",
                    },
                ],
            },
        }

        const { rerender } = render(<PlatformWorkflowTemplatePage />)

        workflowOptions.statuses = [
            {
                id: "stage-qualified",
                value: "qualified",
                label: "Qualified",
            },
        ]
        rerender(<PlatformWorkflowTemplatePage />)
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mutationMocks.update).toHaveBeenCalledWith({
                id: "workflow-template-1",
                payload: expect.objectContaining({
                    trigger_config: {
                        to_stage_id: "stage-qualified",
                    },
                }),
            })
        })
    })

    it("drops obsolete scheduled fields when the trigger type changes", async () => {
        mutationMocks.update.mockResolvedValue(templateState.data)
        workflowOptions.trigger_types = [
            {
                value: "scheduled",
                label: "Scheduled",
            },
            {
                value: "status_changed",
                label: "Status Changed",
            },
        ]
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                trigger_type: "scheduled",
                trigger_config: {
                    cron: "0 9 * * *",
                    timezone: "America/New_York",
                },
                actions: [
                    {
                        action_type: "add_note",
                        content: "Record the scheduled run.",
                    },
                ],
            },
        }

        render(<PlatformWorkflowTemplatePage />)

        const triggerLabel = screen.getByText("Trigger Type *")
        const triggerSelect = triggerLabel.parentElement?.querySelector("button")
        expect(triggerSelect).not.toBeNull()
        fireEvent.click(triggerSelect as HTMLButtonElement)
        const statusChangedOption = screen.getByRole("option", { name: "Status Changed" })
        fireEvent.mouseMove(statusChangedOption)
        fireEvent.click(statusChangedOption)
        expect(triggerSelect).toHaveTextContent("Status Changed")
        fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

        await waitFor(() => {
            expect(mutationMocks.update).toHaveBeenCalledWith({
                id: "workflow-template-1",
                payload: expect.objectContaining({
                    trigger_type: "status_changed",
                    trigger_config: {},
                }),
            })
        })
    })

    describe("promote intake lead options", () => {
        const promoteAction = {
            action_type: "promote_intake_lead",
            source: "website",
            is_priority: true,
            assign_to_user: true,
        }
        const renderPromoteTemplate = (triggerConfig: Record<string, string>) => {
            templateState.data = {
                ...templateState.data,
                draft: {
                    ...templateState.data.draft,
                    subject_type: "intake_lead",
                    trigger_type: "intake_lead_created",
                    trigger_config: triggerConfig,
                    actions: [promoteAction],
                },
            }
            mutationMocks.update.mockResolvedValue(templateState.data)
            render(<PlatformWorkflowTemplatePage />)
        }

        it.each([
            { source: "donor lead type", triggerConfig: { lead_type: "egg_donor" } },
            { source: "donor form", triggerConfig: { form_id: "form-sperm-donor" } },
        ])("hides and drops surrogate-only options for a $source", async ({ triggerConfig }) => {
            workflowOptions.forms = [
                { id: "form-sperm-donor", name: "Sperm Donor Application", lead_kind: "sperm_donor" },
            ]
            renderPromoteTemplate(triggerConfig)

            expect(screen.queryByText("Mark as priority")).not.toBeInTheDocument()
            expect(screen.queryByText("Assign to workflow owner if available")).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({
                        actions: [{ action_type: "promote_intake_lead", source: "website" }],
                    }),
                })
            })
        })

        it("keeps surrogate-only options for a generic intake template", async () => {
            renderPromoteTemplate({})

            expect(screen.getByText("Mark as priority")).toBeInTheDocument()
            expect(screen.getByText("Assign to workflow owner if available")).toBeInTheDocument()
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({ actions: [promoteAction] }),
                })
            })
        })
    })

    describe("fixed-trigger subjects", () => {
        const selectTrigger = (label: string) => {
            const triggerSelect = screen.getByText("Trigger Type *").parentElement?.querySelector("button")
            fireEvent.click(triggerSelect as HTMLButtonElement)
            const option = screen.getByRole("option", { name: label })
            fireEvent.mouseMove(option)
            fireEvent.click(option)
        }
        const subjectSelect = () => screen.getByText("Subject Type *").parentElement?.querySelector("button")

        beforeEach(() => {
            mutationMocks.update.mockResolvedValue(templateState.data)
            workflowOptions.trigger_types = [
                { value: "surrogate_created", label: "Surrogate Created" },
                { value: "form_submitted", label: "Application Submitted" },
                { value: "intake_lead_created", label: "Intake Lead Created" },
                { value: "match_proposed", label: "Match Proposed" },
                { value: "appointment_scheduled", label: "Appointment Scheduled" },
            ]
            templateState.data = {
                ...templateState.data,
                draft: {
                    ...templateState.data.draft,
                    actions: [{ action_type: "add_note", content: "Review the record." }],
                },
            }
        })

        it.each([
            { trigger: "Application Submitted", subject: "form_submission", label: "Form Submission" },
            { trigger: "Intake Lead Created", subject: "intake_lead", label: "Intake Lead" },
            { trigger: "Match Proposed", subject: "match", label: "Match" },
            { trigger: "Appointment Scheduled", subject: "appointment", label: "Appointment" },
        ])("saves the $subject subject for the $trigger trigger", async ({ trigger, subject, label }) => {
            render(<PlatformWorkflowTemplatePage />)

            selectTrigger(trigger)
            expect(subjectSelect()).toHaveTextContent(label)
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({ subject_type: subject }),
                })
            })
        })

        it("returns a fixed subject to surrogate when the trigger no longer fixes it", async () => {
            templateState.data = {
                ...templateState.data,
                draft: { ...templateState.data.draft, subject_type: "match", trigger_type: "match_proposed" },
            }
            render(<PlatformWorkflowTemplatePage />)

            selectTrigger("Surrogate Created")
            expect(subjectSelect()).toHaveTextContent("Surrogate")
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({ subject_type: "surrogate", trigger_type: "surrogate_created" }),
                })
            })
        })

        it("publishes the trigger's subject for a draft saved with the surrogate subject", async () => {
            templateState.data = {
                ...templateState.data,
                draft: { ...templateState.data.draft, subject_type: "surrogate", trigger_type: "form_submitted" },
            }
            render(<PlatformWorkflowTemplatePage />)

            fireEvent.click(screen.getByRole("button", { name: "Publish" }))
            fireEvent.click(screen.getByRole("button", { name: "Confirm workflow publish" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({
                        subject_type: "form_submission",
                        trigger_type: "form_submitted",
                    }),
                })
            })
            await waitFor(() => expect(mutationMocks.publish).toHaveBeenCalled())
        })

        it("saves the trigger's subject after an explicit surrogate pick", async () => {
            templateState.data = {
                ...templateState.data,
                draft: { ...templateState.data.draft, subject_type: "form_submission", trigger_type: "form_submitted" },
            }
            render(<PlatformWorkflowTemplatePage />)

            fireEvent.click(subjectSelect() as HTMLButtonElement)
            const surrogateOption = screen.getByRole("option", { name: "Surrogate" })
            fireEvent.mouseMove(surrogateOption)
            fireEvent.click(surrogateOption)
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            await waitFor(() => {
                expect(mutationMocks.update).toHaveBeenCalledWith({
                    id: "workflow-template-1",
                    payload: expect.objectContaining({
                        subject_type: "form_submission",
                        trigger_type: "form_submitted",
                    }),
                })
            })
        })

        it("keeps a donor subject and blocks a trigger it does not support", () => {
            templateState.data = {
                ...templateState.data,
                draft: { ...templateState.data.draft, subject_type: "egg_donor", trigger_type: "donor_created" },
            }
            workflowOptions.trigger_types = [
                ...workflowOptions.trigger_types,
                { value: "donor_created", label: "Donor Created" },
            ]
            render(<PlatformWorkflowTemplatePage />)

            selectTrigger("Application Submitted")
            expect(subjectSelect()).toHaveTextContent("Egg Donor")
            fireEvent.click(screen.getByRole("button", { name: "Save draft" }))

            expect(screen.getByText("Egg Donor does not support this trigger.")).toBeInTheDocument()
            expect(mutationMocks.update).not.toHaveBeenCalled()
        })
    })
})
