"use client"

import type { ReactNode } from "react"
import { CircleCheckIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import {
    WORKFLOW_SUBJECT_PLURAL_LABELS,
    describeAppointmentTiming,
    getAppointmentTypeNames,
    getConditionFieldLabel,
    describeSchedule,
    getTriggerLabel,
    isDonorSubject,
} from "@/lib/workflows/workflow-editor-state"
import {
    STAFF_ROLE_OPTIONS,
    getEmailRecipientEmails,
    getEmailRecipientKind,
    getEmailRecipientUserId,
    type EditableAction,
} from "@/components/automation/workflow-editor/shared"
import { cn } from "@/lib/utils"
import { NodeIcon, getActionMeta, getTriggerIcon, type ActionTone } from "./node-meta"

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
        const schedule = describeSchedule(triggerConfig.cron)
        if (schedule) lines.push(schedule)
    }
    if (triggerType === "inactivity" && typeof triggerConfig.days === "number") {
        lines.push(`${triggerConfig.days} days inactive`)
    }
    if (triggerType === "task_due" && typeof triggerConfig.hours_before === "number") {
        lines.push(`${triggerConfig.hours_before} hours before due`)
    }
    if (triggerType === "appointment_time") {
        lines.push(describeAppointmentTiming(triggerConfig))
    }
    if (state.isAppointmentTrigger) {
        const typeNames = getAppointmentTypeNames(triggerConfig)
        if (typeNames.length > 0) lines.push(`Types: ${typeNames.join(", ")}`)
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

function getConditionSummary(state: CanvasState, options: CanvasOptions): string[] {
    return state.conditions.flatMap((condition) => {
        if (!condition.field) return []
        const operator =
            options.conditionOperators.find((option) => option.value === condition.operator)?.label ?? condition.operator
        const choices = options.getConditionOptions(condition.field)
        const rawValues = Array.isArray(condition.value) ? condition.value.map(String) : [String(condition.value ?? "")]
        const value = rawValues
            .filter(Boolean)
            .map((item) => choices?.find((option) => option.value === item)?.label ?? item)
            .join(", ")
        return [[getConditionFieldLabel(condition.field), operator.toLowerCase(), value].filter(Boolean).join(" ")]
    })
}

function getActionSummary(action: EditableAction, options: CanvasOptions, state: CanvasState): string | null {
    switch (action.action_type) {
        case "send_email": {
            const template = options.emailTemplates.find((option) => option.id === action.template_id)
            // Donor workflows save the default surrogate recipient as "donor" (mirrors the action panel).
            const storedKind = getEmailRecipientKind(action)
            const kind = isDonorSubject(state.actionSubjectType) && storedKind === "surrogate" ? "donor" : storedKind
            const recipient =
                kind === "user"
                    ? options.userOptions.find((option) => option.id === getEmailRecipientUserId(action))?.display_name
                    : kind === "queue"
                        ? options.queueOptions.find((queue) => queue.id === action.recipient_queue_id)?.name
                        : kind === "role"
                            ? STAFF_ROLE_OPTIONS.find((role) => role.value === action.recipient_role)?.label
                            : kind === "custom"
                                ? getEmailRecipientEmails(action).join(", ") || null
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

/** Small tag fixed to a node's top-left corner, as in the reference ("When this happens"). */
function NodeTag({ children }: { children: ReactNode }) {
    return (
        <span className="absolute -top-2.5 left-2.5 z-10 rounded border border-border bg-muted px-1.5 py-px text-[10px] font-medium text-muted-foreground">
            {children}
        </span>
    )
}

function Connector({ tall = false }: { tall?: boolean }) {
    return <span aria-hidden="true" className={cn("block w-px bg-border", tall ? "h-12" : "h-8")} />
}

function NodeCard({
    selected,
    onSelect,
    label,
    tag,
    children,
    trailing,
}: {
    selected: boolean
    onSelect: () => void
    label: string
    tag?: string
    children: ReactNode
    trailing?: ReactNode
}) {
    return (
        <div className="group/node relative w-72 max-w-full">
            {tag ? <NodeTag>{tag}</NodeTag> : null}
            <Button
                unstyled
                type="button"
                aria-label={label}
                aria-pressed={selected}
                onClick={onSelect}
                className={cn(
                    "w-full rounded-lg border border-border bg-card text-left shadow-[0_1px_2px_rgb(0_0_0/0.04)] outline-none transition-[box-shadow,border-color] hover:border-foreground/20 focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    selected && "border-primary/60 ring-2 ring-primary/15",
                )}
            >
                {children}
            </Button>
            {trailing}
        </div>
    )
}

function NodeTitle({
    icon,
    tone,
    title,
    subtitle,
}: {
    icon: React.ElementType
    tone: ActionTone
    title: string
    subtitle?: string | null
}) {
    return (
        <div className="flex items-start gap-2 px-3 pt-3 pb-2.5">
            <NodeIcon icon={icon} tone={tone} size="sm" className="mt-px" />
            <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{title}</p>
                {subtitle ? <p className="truncate text-[11px] text-muted-foreground">{subtitle}</p> : null}
            </div>
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
    const { triggerType, savedSubjectType, conditions, conditionLogic, actions } = state
    const TriggerIcon = getTriggerIcon(triggerType)
    const triggerLabel = triggerType
        ? options.triggerTypeOptions.find((option) => option.value === triggerType)?.label ?? getTriggerLabel(triggerType)
        : "Choose a trigger"
    const criteria = [...getTriggerCriteria(state, options), ...getConditionSummary(state, options)]
    const matchLabel =
        conditions.length > 1 ? (conditionLogic === "AND" ? "Records matching all filters" : "Records matching any filter") : null

    return (
        <div
            data-testid="workflow-canvas"
            className="relative min-h-0 flex-1 overflow-auto rounded-lg bg-background [background-image:radial-gradient(var(--border)_1px,transparent_1px)] [background-size:16px_16px]"
        >
            <div className="flex min-h-full w-full flex-col items-center px-4 pt-12 pb-16">
                <NodeCard
                    tag="When this happens"
                    selected={selection.kind === "trigger"}
                    onSelect={() => onSelect({ kind: "trigger" })}
                    label="Trigger step"
                >
                    <NodeTitle
                        icon={TriggerIcon}
                        tone="violet"
                        title={triggerLabel}
                        subtitle={
                            state.isAppointmentTrigger
                                ? `Runs on linked ${WORKFLOW_SUBJECT_PLURAL_LABELS[state.actionSubjectType].toLowerCase()}`
                                : `Runs for ${WORKFLOW_SUBJECT_PLURAL_LABELS[savedSubjectType].toLowerCase()}`
                        }
                    />
                    <div className="border-t border-border px-3 py-2.5">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                            Enrollment criteria
                        </p>
                        {criteria.length > 0 ? (
                            <ul className="mt-1 space-y-0.5 text-[11px]">
                                {matchLabel ? <li className="text-muted-foreground">{matchLabel}:</li> : null}
                                {/* Index keys: two filters can summarize to the same line. */}
                                {criteria.map((line, index) => (
                                    <li key={index} className="truncate">
                                        {line}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="mt-1 text-[11px]">Every matching record</p>
                        )}
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
                            <Connector tall />
                            <NodeCard
                                tag={index === 0 ? "Do this" : "Then"}
                                selected={selected}
                                onSelect={() => onSelect({ kind: "action", clientId: action.clientId })}
                                label={`Action ${index + 1}: ${actionLabel}`}
                                trailing={
                                    <Button
                                        size="icon-sm"
                                        variant="ghost"
                                        aria-label={`Remove action ${index + 1}`}
                                        className="absolute top-1.5 right-1.5 size-6 opacity-0 transition-opacity group-hover/node:opacity-100 focus-visible:opacity-100"
                                        onClick={() => handlers.removeAction(index)}
                                    >
                                        <XIcon aria-hidden="true" className="size-3.5" />
                                    </Button>
                                }
                            >
                                <NodeTitle icon={meta.icon} tone={meta.tone} title={actionLabel} subtitle={summary} />
                                {action.requires_approval ? (
                                    <div className="border-t border-border px-3 py-2 text-[11px] text-amber-600 dark:text-amber-400">
                                        Requires approval
                                    </div>
                                ) : null}
                            </NodeCard>
                        </div>
                    )
                })}

                <Connector />
                <Button
                    size="icon-sm"
                    variant="outline"
                    aria-label="Add action"
                    className="size-6 rounded-full bg-card text-muted-foreground hover:text-foreground"
                    onClick={onRequestAddAction}
                >
                    <PlusIcon aria-hidden="true" className="size-3.5" />
                </Button>
                <Connector />
                <div className="flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[11px] text-muted-foreground shadow-[0_1px_2px_rgb(0_0_0/0.04)]">
                    <CircleCheckIcon aria-hidden="true" className="size-3" />
                    Exit
                </div>
            </div>
        </div>
    )
}
