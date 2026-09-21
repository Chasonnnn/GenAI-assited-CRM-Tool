import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import PlatformWorkflowTemplatePage from "@/app/ops/templates/workflows/[id]/page.client"
import type { PlatformWorkflowTemplate } from "@/lib/api/platform"

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
    forms: [],
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

vi.mock("next/navigation", () => ({
    useParams: () => ({ id: "workflow-template-1" }),
    useRouter: () => ({
        push: vi.fn(),
        replace: vi.fn(),
    }),
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
        mutationMocks.create.mockReset()
        mutationMocks.update.mockReset()
        mutationMocks.publish.mockReset()
        mutationMocks.remove.mockReset()
        workflowOptionsMocks.use.mockReset()
        workflowOptions.statuses = []
        workflowOptions.trigger_types = []
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

    it("saves donor-only conditions and the explicit automatic creation option", async () => {
        templateState.data = {
            ...templateState.data,
            draft: {
                ...templateState.data.draft,
                trigger_type: "form_submitted",
                conditions: [{ field: "lead_kind", operator: "in", value: ["egg_donor", "sperm_donor"] }],
                actions: [{ action_type: "create_intake_lead", source: "website" }],
            },
        }
        mutationMocks.update.mockResolvedValue(templateState.data)
        render(<PlatformWorkflowTemplatePage />)
        const automaticCreation = screen.getByRole("switch", { name: "Create donor after photo scan" })
        expect(automaticCreation).not.toBeChecked()
        fireEvent.click(automaticCreation)
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))
        await waitFor(() => expect(mutationMocks.update).toHaveBeenCalledWith({
            id: "workflow-template-1",
            payload: expect.objectContaining({
                conditions: [{ field: "lead_kind", operator: "in", value: ["egg_donor", "sperm_donor"] }],
                actions: [{ action_type: "create_intake_lead", source: "website", auto_promote: true }],
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

        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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

        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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
                    {
                        field: "stage_id",
                        operator: "equals",
                        value: "egg-stage-to",
                        stage_key: "egg-ready",
                        stage_keys: ["egg-ready"],
                    },
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

        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))
        expect(mutationMocks.update).not.toHaveBeenCalled()
        expect(screen.getByText("Trigger type is required.")).toBeInTheDocument()

        fireEvent.click(triggerSelect as HTMLButtonElement)
        const donorCreatedOption = screen.getByRole("option", { name: "Donor Created" })
        fireEvent.mouseMove(donorCreatedOption)
        fireEvent.click(donorCreatedOption)

        expect(screen.getByText("Select a stage for each stage condition.")).toBeInTheDocument()
        const stageCondition = screen.getAllByRole("button", { name: "Remove condition" })[0]
            .closest('[data-slot="card"]') as HTMLElement
        fireEvent.click(within(stageCondition).getAllByRole("combobox")[2])
        const spermConditionStage = screen.getByRole("option", { name: "Sperm Ready" })
        fireEvent.mouseMove(spermConditionStage)
        fireEvent.click(spermConditionStage)

        expect(screen.getByText("Update actions need a value.")).toBeInTheDocument()
        const stageAction = screen.getAllByRole("button", { name: "Remove action" })[0]
            .closest('[data-slot="card"]') as HTMLElement
        fireEvent.click(within(stageAction).getAllByRole("combobox")[2])
        const spermActionStage = screen.getAllByRole("option", { name: "Sperm Ready" }).at(-1) as HTMLElement
        fireEvent.mouseMove(spermActionStage)
        fireEvent.click(spermActionStage)
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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
        await waitFor(() => expect(screen.getByRole("button", { name: "Save Draft" })).toBeEnabled())
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))
        await waitFor(() => expect(mutationMocks.update).toHaveBeenLastCalledWith({
            id: "workflow-template-1", payload: expect.objectContaining({ expected_version: 6 }),
        }))
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
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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
        fireEvent.click(screen.getByRole("button", { name: "Save Draft" }))

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
})
