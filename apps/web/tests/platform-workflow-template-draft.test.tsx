import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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
    useWorkflowOptions: () => ({
        data: workflowOptions,
    }),
}))

vi.mock("@/components/ops/templates/PublishDialog", () => ({
    PublishDialog: ({ onPublish }: { onPublish: (publishAll: boolean, orgIds: string[]) => void }) => (
        <button onClick={() => onPublish(true, [])}>Confirm workflow publish</button>
    ),
}))

describe("platform workflow template draft ownership", () => {
    beforeEach(() => {
        mutationMocks.create.mockReset()
        mutationMocks.update.mockReset()
        mutationMocks.publish.mockReset()
        mutationMocks.remove.mockReset()
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
