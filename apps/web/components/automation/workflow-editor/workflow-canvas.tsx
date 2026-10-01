"use client"

import type { ReactNode } from "react"
import { CircleStopIcon, FilterIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import {
    WORKFLOW_SUBJECT_PLURAL_LABELS,
    getConditionFieldLabel,
    getTriggerLabel,
    isDonorSubject,
} from "@/lib/workflows/workflow-editor-state"
import { getEmailRecipientKind, getEmailRecipientUserId, type EditableAction } from "@/components/automation/workflow-editor/shared"
import { cn } from "@/lib/utils"
import { NodeIcon, getActionMeta, getTriggerIcon } from "./node-meta"

type CanvasOptions = WorkflowEditorController["options"]
type CanvasState = WorkflowEditorController["state"]

function getTriggerCriteria(state: CanvasState, options: CanvasOptions): string[] {
    const { triggerType, triggerConfig } = state
    const lines: string[] = []
    if (triggerType === "status_changed" || triggerType === "donor_stage_changed") {
        const from = options.statusOptions.find((status) => status.id === triggerConfig.from_stage_id)
        const to = options.statusOptions.find((status) => status.id === triggerConfig.to_stage_id)
        if (from) lines.push(`From ${from.label}`)
        if (to) lines.push(`To ${to.label}`)
    }
    if (triggerType === "scheduled" && typeof triggerConfig.cron === "string" && triggerConfig.cron) {
        lines.push(`Cron ${triggerConfig.cron}`)
    }
    if (triggerType === "inactivity" && typeof triggerConfig.days === "number") {
        lines.push(`${triggerConfig.days} days inactive`)
    }
    if (triggerType === "task_due" && typeof triggerConfig.hours_before === "number") {
        lines.push(`${triggerConfig.hours_before} hours before due`)
    }
    if (typeof triggerConfig.form_id === "string" && triggerConfig.form_id) {
        const form = options.formOptions.find((option) => option.value === triggerConfig.form_id)
        lines.push(form ? `Form: ${form.label}` : "Form selected")
    }
    if (options.selectedTriggerFields.length > 0) {
        lines.push(`Watching ${options.selectedTriggerFields.map(getConditionFieldLabel).join(", ")}`)
    }
    if (typeof triggerConfig.to_user_id === "string" && triggerConfig.to_user_id) {
        const user = options.userOptions.find((option) => option.id === triggerConfig.to_user_id)
        if (user) lines.push(`Assigned to ${user.display_name}`)
    }
    return lines
}

function getActionSummary(action: EditableAction, options: CanvasOptions, state: CanvasState): string | null {
    switch (action.action_type) {
        case "send_email": {
            const template = options.emailTemplates.find((option) => option.id === action.template_id)
            // Donor workflows save the default surrogate recipient as "donor" (mirrors the action panel).
            const storedKind = getEmailRecipientKind(action)
            const kind = isDonorSubject(state.subjectType) && storedKind === "surrogate" ? "donor" : storedKind
            const recipient =
                kind === "user"
                    ? options.userOptions.find((option) => option.id === getEmailRecipientUserId(action))?.display_name
                    : options.emailRecipientOptions.find((option) => option.value === kind)?.label
            return [template?.name, recipient ? `to ${recipient}` : null].filter(Boolean).join(" ") || null
        }
        case "send_message": {
            const template = options.messageTemplates.find(
                (option) => option.id === action.message_template_version_id,
            )
            return template ? `${template.name} v${template.version}` : null
        }
        case "create_task":
        case "send_notification":
            return typeof action.title === "string" && action.title ? action.title : null
        case "update_field":
            return typeof action.field === "string" && action.field ? getConditionFieldLabel(action.field) : null
        case "add_note":
            return typeof action.content === "string" && action.content ? action.content : null
        case "assign_surrogate":
        case "assign_donor": {
            const owners = action.owner_type === "queue" ? options.queueOptions : options.userOptions
            const owner = owners.find((option) => option.id === action.owner_id)
            if (!owner) return null
            return "name" in owner ? `Queue: ${owner.name}` : owner.display_name
        }
        default:
            return null
    }
}

function NodeLabel({ children }: { children: ReactNode }) {
    return (
        <span className="rounded-full border border-border bg-background px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            {children}
        </span>
    )
}

function Connector() {
    return <span aria-hidden="true" className="block h-7 w-px bg-border" />
}

function NodeCard({
    selected,
    onSelect,
    label,
    children,
    trailing,
    className,
}: {
    selected: boolean
    onSelect: () => void
    label: string
    children: ReactNode
    trailing?: ReactNode
    className?: string
}) {
    return (
        <div className="group/node relative w-full">
            <Button
                unstyled
                type="button"
                aria-label={label}
                aria-pressed={selected}
                onClick={onSelect}
                className={cn(
                    "w-full rounded-xl border border-border bg-card text-left shadow-xs transition-[box-shadow,border-color] outline-none hover:border-foreground/20 focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    selected && "border-primary ring-2 ring-primary/30",
                    className,
                )}
            >
                {children}
            </Button>
            {trailing}
        </div>
    )
}

export function WorkflowCanvas({
    controller,
    onSelect,
    onRequestAddAction,
}: {
    controller: WorkflowEditorController
    onSelect: (selection: WorkflowEditorSelection) => void
    onRequestAddAction: () => void
}) {
    const { state, options, selection, handlers } = controller
    const { triggerType, subjectType, conditions, conditionLogic, actions } = state
    const TriggerIcon = getTriggerIcon(triggerType)
    const triggerLabel = triggerType
        ? options.triggerTypeOptions.find((option) => option.value === triggerType)?.label ?? getTriggerLabel(triggerType)
        : "Choose a trigger"
    const criteria = getTriggerCriteria(state, options)
    const conditionCount = conditions.length

    return (
        <div
            data-testid="workflow-canvas"
            className="relative min-h-0 flex-1 overflow-auto rounded-xl border border-border bg-muted/30 [background-image:radial-gradient(var(--border)_1px,transparent_1px)] [background-size:18px_18px]"
        >
            <div className="mx-auto flex w-full max-w-sm flex-col items-center px-4 py-10">
                <NodeLabel>When this happens</NodeLabel>
                <Connector />
                <NodeCard
                    selected={selection.kind === "trigger"}
                    onSelect={() => onSelect({ kind: "trigger" })}
                    label="Trigger step"
                >
                    <div className="flex items-start gap-3 p-3.5">
                        <NodeIcon icon={TriggerIcon} tone="violet" />
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{triggerLabel}</p>
                            <p className="truncate text-xs text-muted-foreground">
                                Runs for {WORKFLOW_SUBJECT_PLURAL_LABELS[subjectType].toLowerCase()}
                            </p>
                        </div>
                    </div>
                    {criteria.length > 0 ? (
                        <div className="border-t border-border px-3.5 py-2.5">
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                                Enrollment criteria
                            </p>
                            <ul className="mt-1 space-y-0.5 text-xs">
                                {criteria.map((line) => (
                                    <li key={line} className="truncate">
                                        {line}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ) : null}
                </NodeCard>

                <Connector />
                <NodeLabel>Only continue if</NodeLabel>
                <Connector />
                <NodeCard
                    selected={selection.kind === "conditions"}
                    onSelect={() => onSelect({ kind: "conditions" })}
                    label="Conditions step"
                >
                    <div className="flex items-start gap-3 p-3.5">
                        <NodeIcon icon={FilterIcon} tone="amber" />
                        <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">
                                {conditionCount === 0
                                    ? "No conditions"
                                    : `${conditionCount} condition${conditionCount === 1 ? "" : "s"}`}
                            </p>
                            <p className="truncate text-xs text-muted-foreground">
                                {conditionCount === 0
                                    ? "Runs for every matching trigger"
                                    : conditionLogic === "AND"
                                        ? "All must match"
                                        : "Any can match"}
                            </p>
                        </div>
                    </div>
                </NodeCard>

                {actions.map((action, index) => {
                    const meta = getActionMeta(action.action_type)
                    const actionLabel = action.action_type
                        ? options.actionTypeOptions.find((option) => option.value === action.action_type)?.label ??
                        action.action_type
                        : "Choose an action"
                    const summary = getActionSummary(action, options, state)
                    const selected = selection.kind === "action" && selection.clientId === action.clientId
                    return (
                        <div key={action.clientId} className="flex w-full flex-col items-center">
                            <Connector />
                            <NodeLabel>{index === 0 ? "Do this" : "Then"}</NodeLabel>
                            <Connector />
                            <NodeCard
                                selected={selected}
                                onSelect={() => onSelect({ kind: "action", clientId: action.clientId })}
                                label={`Action ${index + 1}: ${actionLabel}`}
                                trailing={
                                    <Button
                                        size="icon-sm"
                                        variant="ghost"
                                        aria-label={`Remove action ${index + 1}`}
                                        className="absolute top-2 right-2 opacity-0 transition-opacity group-hover/node:opacity-100 focus-visible:opacity-100"
                                        onClick={() => handlers.removeAction(index)}
                                    >
                                        <XIcon aria-hidden="true" />
                                    </Button>
                                }
                            >
                                <div className="flex items-start gap-3 p-3.5 pr-10">
                                    <NodeIcon icon={meta.icon} tone={meta.tone} />
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-medium">{actionLabel}</p>
                                        {summary ? (
                                            <p className="truncate text-xs text-muted-foreground">{summary}</p>
                                        ) : null}
                                        {action.requires_approval ? (
                                            <p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">
                                                Requires approval
                                            </p>
                                        ) : null}
                                    </div>
                                </div>
                            </NodeCard>
                        </div>
                    )
                })}

                <Connector />
                <NodeLabel>{actions.length === 0 ? "Do this" : "Then"}</NodeLabel>
                <Connector />
                <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-center border-dashed bg-card/60 text-muted-foreground hover:text-foreground"
                    onClick={onRequestAddAction}
                >
                    <PlusIcon aria-hidden="true" />
                    Add action
                </Button>

                <Connector />
                <div className="flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs text-muted-foreground">
                    <CircleStopIcon aria-hidden="true" className="size-3.5" />
                    End
                </div>
            </div>
        </div>
    )
}
