"use client"

import type { MouseEvent, PointerEvent as ReactPointerEvent, RefObject } from "react"
import { CircleCheckIcon, PlusIcon, XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { WorkflowEditorController, WorkflowEditorSelection } from "@/lib/workflows/use-workflow-editor"
import type { WorkflowTestRunController } from "@/lib/workflows/use-workflow-test-run"
import {
    WORKFLOW_SUBJECT_PLURAL_LABELS,
    getActionValidationError,
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
import { getActionMeta, getTriggerIcon } from "./node-meta"
import type { StepDrag } from "./use-step-drag"
import { CriterionLine, NODE_WIDTH_CLASS, WorkflowNode } from "./workflow-node"

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

/** One line per filter, in filter order; blank filters give null so results stay aligned. */
function getConditionSummary(state: CanvasState, options: CanvasOptions): (string | null)[] {
    return state.conditions.map((condition) => {
        if (!condition.field) return null
        const operator =
            options.conditionOperators.find((option) => option.value === condition.operator)?.label ?? condition.operator
        const choices = options.getConditionOptions(condition.field)
        const rawValues = Array.isArray(condition.value) ? condition.value.map(String) : [String(condition.value ?? "")]
        const value = rawValues
            .filter(Boolean)
            .map((item) => choices?.find((option) => option.value === item)?.label ?? item)
            .join(", ")
        return [getConditionFieldLabel(condition.field), operator.toLowerCase(), value].filter(Boolean).join(" ")
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

/** Line between steps with an insert button, or the drop slot while a step is dragged over it. */
function Connector({
    slot,
    drag,
    lit,
    onInsert,
    insertLabel,
}: {
    slot: number
    drag: StepDrag | null
    lit: boolean
    onInsert: (slot: number) => void
    insertLabel: string
}) {
    if (drag && drag.slot === slot) {
        return (
            <div className="flex flex-col items-center" aria-hidden="true">
                <span className="block h-4 w-px bg-primary/40" />
                <div
                    className={cn(
                        "flex h-12 items-center justify-center rounded-xl border border-dashed border-primary/50 bg-primary/5 text-xs font-medium text-primary animate-in fade-in-0 zoom-in-95 motion-reduce:animate-none",
                        NODE_WIDTH_CLASS,
                    )}
                >
                    {drag.label}
                </div>
                <span className="block h-4 w-px bg-primary/40" />
            </div>
        )
    }
    const line = cn("block w-px flex-1", lit ? "bg-emerald-500/60" : "bg-border")
    return (
        <div className="group/connector flex h-14 flex-col items-center">
            <span aria-hidden="true" className={line} />
            <Button
                size="icon-sm"
                variant="outline"
                aria-label={insertLabel}
                className="size-5 shrink-0 rounded-full bg-card text-muted-foreground opacity-0 transition-opacity group-hover/connector:opacity-100 hover:text-foreground focus-visible:opacity-100 [&_svg]:size-3"
                onClick={() => onInsert(slot)}
            >
                <PlusIcon aria-hidden="true" />
            </Button>
            <span aria-hidden="true" className={line} />
        </div>
    )
}

export function WorkflowCanvas({
    controller,
    testRun,
    drag,
    canvasRef,
    insetLeft,
    insetRight,
    onSelect,
    onRequestAddAction,
    onInsertAt,
    onStepPointerDown,
}: {
    controller: WorkflowEditorController
    testRun: WorkflowTestRunController
    drag: StepDrag | null
    canvasRef: RefObject<HTMLDivElement | null>
    /** Space kept clear for floating panels, so steps center in the visible area. */
    insetLeft: string
    insetRight: string
    onSelect: (selection: WorkflowEditorSelection) => void
    onRequestAddAction: () => void
    onInsertAt: (slot: number) => void
    onStepPointerDown: (index: number, label: string, event: ReactPointerEvent) => void
}) {
    const { state, options, selection, handlers } = controller
    const { triggerType, savedSubjectType, conditions, conditionLogic, actions } = state
    const TriggerIcon = getTriggerIcon(triggerType)
    const triggerLabel = triggerType
        ? options.triggerTypeOptions.find((option) => option.value === triggerType)?.label ?? getTriggerLabel(triggerType)
        : "Choose a trigger"
    const triggerCriteria = getTriggerCriteria(state, options)
    const conditionLines = getConditionSummary(state, options)
    const hasCriteria = triggerCriteria.length > 0 || conditionLines.some(Boolean)
    const matchLabel =
        conditions.length > 1 ? (conditionLogic === "AND" ? "Records matching all filters" : "Records matching any filter") : null
    const result = testRun.run && !testRun.isStale ? testRun.run.result : null
    const stepStates = result ? testRun.stepStates : null
    const actionLabel = (actionType: string) =>
        actionType
            ? options.actionTypeOptions.find((option) => option.value === actionType)?.label ?? actionType
            : "Choose an action"

    const deselectOnBackground = (event: MouseEvent) => {
        if (event.target === event.currentTarget) onSelect({ kind: "none" })
    }

    return (
        <div
            ref={canvasRef}
            data-testid="workflow-canvas"
            onClick={deselectOnBackground}
            className="absolute inset-0 overflow-auto bg-muted/30 [background-image:radial-gradient(var(--border)_1px,transparent_1px)] [background-size:18px_18px] dark:bg-background"
        >
            <div
                onClick={deselectOnBackground}
                style={{ paddingLeft: insetLeft, paddingRight: insetRight }}
                className="flex min-h-full min-w-max flex-col items-center pt-14 pb-24 transition-[padding] duration-200 motion-reduce:transition-none"
            >
                <WorkflowNode
                    icon={TriggerIcon}
                    tone="violet"
                    typeLabel="Trigger"
                    tag="When"
                    ariaLabel="Trigger step"
                    selected={selection.kind === "trigger"}
                    onSelect={() => onSelect({ kind: "trigger" })}
                    hasInput={false}
                    title={triggerLabel}
                    subtitle={
                        state.isAppointmentTrigger
                            ? `Runs on linked ${WORKFLOW_SUBJECT_PLURAL_LABELS[state.actionSubjectType].toLowerCase()}`
                            : `Runs for ${WORKFLOW_SUBJECT_PLURAL_LABELS[savedSubjectType].toLowerCase()}`
                    }
                    footer={
                        <span className="mt-1.5 block border-t border-border pt-2 text-[11px]">
                            <span className="block text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                                Enrollment criteria
                            </span>
                            {hasCriteria ? (
                                <ul className="mt-1 space-y-0.5">
                                    {matchLabel ? <li className="text-muted-foreground">{matchLabel}:</li> : null}
                                    {/* Index keys: two criteria can summarize to the same line. */}
                                    {triggerCriteria.map((line, index) => (
                                        <CriterionLine key={`trigger-${index}`} text={line} />
                                    ))}
                                    {conditionLines.map((line, index) => {
                                        if (!line) return null
                                        const evaluated = result?.conditions_evaluated[index]
                                        return (
                                            <CriterionLine
                                                key={`condition-${index}`}
                                                text={line}
                                                {...(evaluated
                                                    ? { result: { passed: evaluated.result, actual: evaluated.actual } }
                                                    : {})}
                                            />
                                        )
                                    })}
                                </ul>
                            ) : (
                                <span className="mt-1 block">Every matching record</span>
                            )}
                        </span>
                    }
                />

                {actions.map((action, index) => {
                    const meta = getActionMeta(action.action_type)
                    const label = actionLabel(action.action_type)
                    const selected = selection.kind === "action" && selection.clientId === action.clientId
                    const stepState = stepStates?.[index] ?? null
                    return (
                        <div key={action.clientId} className="flex flex-col items-center">
                            <Connector
                                slot={index}
                                drag={drag}
                                lit={Boolean(result?.conditions_matched) && stepState === "would_run"}
                                onInsert={onInsertAt}
                                insertLabel={`Insert step ${index + 1}`}
                            />
                            <WorkflowNode
                                stepIndex={index}
                                icon={meta.icon}
                                tone={meta.tone}
                                typeLabel={label}
                                ariaLabel={`Action ${index + 1}: ${label}`}
                                selected={selected}
                                dragging={drag?.source.kind === "step" && drag.source.index === index}
                                onSelect={() => onSelect({ kind: "action", clientId: action.clientId })}
                                onDragStart={(event) => onStepPointerDown(index, label, event)}
                                stepState={stepState}
                                stepOrder={index}
                                title={getActionSummary(action, options, state) ?? (action.action_type ? `Step ${index + 1}` : "Not set up")}
                                issue={action.action_type ? getActionValidationError(action) : null}
                                requiresApproval={Boolean(action.requires_approval)}
                                trailing={
                                    <Button
                                        size="icon-sm"
                                        variant="ghost"
                                        aria-label={`Remove action ${index + 1}`}
                                        className="absolute top-1.5 right-1.5 size-6 bg-card/80 opacity-0 transition-opacity group-hover/node:opacity-100 focus-visible:opacity-100"
                                        onClick={() => handlers.removeAction(index)}
                                    >
                                        <XIcon aria-hidden="true" className="size-3.5" />
                                    </Button>
                                }
                            />
                        </div>
                    )
                })}

                {drag && drag.slot === actions.length ? (
                    <Connector slot={actions.length} drag={drag} lit={false} onInsert={onInsertAt} insertLabel="Add action" />
                ) : (
                    <span aria-hidden="true" className="block h-8 w-px bg-border" />
                )}
                <Button
                    size="icon-sm"
                    variant="outline"
                    aria-label="Add action"
                    className="size-6 rounded-full bg-card text-muted-foreground shadow-[0_1px_2px_rgb(0_0_0/0.06)] hover:text-foreground"
                    onClick={onRequestAddAction}
                >
                    <PlusIcon aria-hidden="true" className="size-3.5" />
                </Button>
                <span aria-hidden="true" className="block h-6 w-px bg-border" />
                <div className="flex items-center gap-1 rounded-full border border-border bg-card px-2.5 py-1 text-[11px] text-muted-foreground shadow-[0_1px_2px_rgb(0_0_0/0.04)]">
                    <CircleCheckIcon aria-hidden="true" className="size-3" />
                    Exit
                </div>
            </div>
        </div>
    )
}
