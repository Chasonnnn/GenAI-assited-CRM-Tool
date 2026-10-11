"use client"

import { useState } from "react"
import { ChevronDownIcon, ChevronUpIcon, ShieldCheckIcon, Trash2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { WorkflowEditorController } from "@/lib/workflows/use-workflow-editor"
import {
    UPDATE_SOURCE_OPTIONS,
    getConditionFieldLabel,
    getUpdateSourceLabel,
    isDonorSubject,
} from "@/lib/workflows/workflow-editor-state"
import {
    CONTACT_STATUS_OPTIONS,
    STAFF_ROLE_OPTIONS,
    getEmailRecipientEmails,
    getEmailRecipientKind,
    getEmailRecipientUserId,
    type EditableAction,
} from "@/components/automation/workflow-editor/shared"
import { EditorColumn, FieldRow, PanelCard, PanelSection } from "./inspector-section"
import { getActionMeta } from "./node-meta"

const NOTIFICATION_RECIPIENT_LABELS: Record<string, string> = {
    owner: "Owner",
    creator: "Creator",
    all_admins: "All Admins",
    host: "Appointment Host",
}

/** Move and remove controls for the selected step, shown in the inspector header. */
export function ActionStepControls({ controller, index }: { controller: WorkflowEditorController; index: number }) {
    const { moveAction, removeAction } = controller.handlers
    const count = controller.state.actions.length
    return (
        <div className="flex items-center">
            <Button
                size="icon-sm"
                variant="ghost"
                className="size-7"
                aria-label="Move action up"
                disabled={index === 0}
                onClick={() => moveAction(index, -1)}
            >
                <ChevronUpIcon aria-hidden="true" />
            </Button>
            <Button
                size="icon-sm"
                variant="ghost"
                className="size-7"
                aria-label="Move action down"
                disabled={index >= count - 1}
                onClick={() => moveAction(index, 1)}
            >
                <ChevronDownIcon aria-hidden="true" />
            </Button>
            <Button
                size="icon-sm"
                variant="destructive-ghost"
                className="size-7"
                aria-label="Remove action"
                onClick={() => removeAction(index)}
            >
                <Trash2Icon aria-hidden="true" />
            </Button>
        </div>
    )
}

export function WorkflowActionPanel({
    controller,
    action,
    index,
}: {
    controller: WorkflowEditorController
    action: EditableAction
    index: number
}) {
    const { state, options, handlers } = controller
    const { actionSubjectType } = state
    const { actionTypeOptions, filteredActionTypes } = options
    const { updateActionType } = handlers
    const meta = getActionMeta(action.action_type)
    const approvalLocked = isDonorSubject(actionSubjectType) && action.action_type === "send_message"

    return (
        <EditorColumn aria-label="Action settings">
            <PanelSection title={`Step ${index + 1}`}>
                <PanelCard icon={meta.icon} title="Action">
                    <Select
                        aria-label={`Action type ${index + 1}`}
                        value={action.action_type}
                        onValueChange={(value) => value && updateActionType(index, value)}
                    >
                        <SelectTrigger aria-label={`Action type ${index + 1}`} className="w-full">
                            <SelectValue placeholder="Action type">
                                {(value: string | null) => {
                                    if (!value) return "Action type"
                                    const actionType = actionTypeOptions.find((option) => option.value === value)
                                    return actionType?.label ?? "Unknown action type"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {filteredActionTypes.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <WorkflowActionFields controller={controller} action={action} index={index} />
                </PanelCard>
            </PanelSection>

            {action.action_type && action.action_type !== "promote_intake_lead" ? (
                <PanelSection title="Approval">
                    <PanelCard
                        icon={ShieldCheckIcon}
                        title="Requires Approval"
                        actions={
                            <Switch
                                aria-label="Requires Approval"
                                checked={!!action.requires_approval}
                                onCheckedChange={(checked) => handlers.updateAction(index, { requires_approval: checked })}
                                disabled={approvalLocked}
                            />
                        }
                    >
                        {approvalLocked ? (
                            <p className="text-xs text-muted-foreground">Required for donor SMS</p>
                        ) : null}
                    </PanelCard>
                </PanelSection>
            ) : null}
        </EditorColumn>
    )
}

/** Keeps the typed text so separators survive while the action stores the parsed list. */
function EmailAddressListInput({
    id,
    initialEmails,
    onChange,
}: {
    id: string
    initialEmails: string[]
    onChange: (emails: string[]) => void
}) {
    const [text, setText] = useState(() => initialEmails.join(", "))
    return (
        <Input
            id={id}
            type="text"
            inputMode="email"
            placeholder="name@agency.com, team@agency.com"
            value={text}
            onChange={(event) => {
                setText(event.target.value)
                onChange(
                    event.target.value
                        .split(",")
                        .map((email) => email.trim())
                        .filter(Boolean),
                )
            }}
        />
    )
}

function WorkflowActionFields({
    controller,
    action,
    index,
}: {
    controller: WorkflowEditorController
    action: EditableAction
    index: number
}) {
    const { state, options, handlers } = controller
    const { actionSubjectType, isAppointmentTrigger } = state
    const {
        emailTemplates,
        emailRecipientOptions,
        userOptions,
        queueOptions,
        messageTemplates,
        updateFields,
        statusOptions,
        isDonorIntakeTrigger,
    } = options
    const { updateAction } = handlers
    const fieldId = (name: string) => `workflow-action-${action.clientId}-${name}`

    if (action.action_type === "send_email") {
        return (
            <>
                <FieldRow label="Email template" htmlFor={fieldId("email-template")}>
                    <Select
                        value={typeof action.template_id === "string" ? action.template_id : ""}
                        onValueChange={(value) => value && updateAction(index, { template_id: value })}
                    >
                        <SelectTrigger id={fieldId("email-template")} aria-label="Email template" className="w-full">
                            <SelectValue placeholder="Select email template">
                                {(value: string | null) => {
                                    if (!value) return "Select email template"
                                    const template = emailTemplates.find((option) => option.id === value)
                                    return template?.name ?? "Unknown template"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {emailTemplates.map((template) => (
                                <SelectItem key={template.id} value={template.id}>
                                    {template.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
                <FieldRow label="Recipient" htmlFor={fieldId("email-recipient")}>
                    <Select
                        value={
                            isDonorSubject(actionSubjectType) && getEmailRecipientKind(action) === "surrogate"
                                ? "donor"
                                : getEmailRecipientKind(action)
                        }
                        onValueChange={(value) => {
                            if (!value) return
                            // Clear the other kinds' targets so a saved action carries only its own.
                            const targets = {
                                recipient_queue_id: value === "queue" ? (action.recipient_queue_id ?? null) : null,
                                recipient_role: value === "role" ? (action.recipient_role ?? null) : null,
                                recipient_emails: value === "custom" ? (action.recipient_emails ?? null) : null,
                            }
                            if (value === "user") {
                                const currentUser = getEmailRecipientUserId(action)
                                updateAction(index, { recipients: currentUser ? [currentUser] : [], ...targets })
                                return
                            }
                            updateAction(index, { recipients: value, ...targets })
                        }}
                    >
                        <SelectTrigger id={fieldId("email-recipient")} aria-label="Recipient" className="w-full">
                            <SelectValue placeholder="Select recipient">
                                {(value: string | null) => {
                                    if (!value) return "Select recipient"
                                    return (
                                        emailRecipientOptions.find((option) => option.value === value)?.label ??
                                        "Unknown recipient"
                                    )
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {emailRecipientOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
                {getEmailRecipientKind(action) === "user" && (
                    <FieldRow label="User" htmlFor={fieldId("email-user")}>
                        <Select
                            value={getEmailRecipientUserId(action)}
                            onValueChange={(value) => updateAction(index, { recipients: value ? [value] : [] })}
                        >
                            <SelectTrigger id={fieldId("email-user")} aria-label="User" className="w-full">
                                <SelectValue placeholder="Select user">
                                    {(value: string | null) => {
                                        if (!value) return "Select user"
                                        const user = userOptions.find((option) => option.id === value)
                                        return user?.display_name ?? "Unknown user"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {userOptions.map((user) => (
                                    <SelectItem key={user.id} value={user.id}>
                                        {user.display_name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </FieldRow>
                )}
                {getEmailRecipientKind(action) === "queue" && (
                    <FieldRow label="Queue" htmlFor={fieldId("email-queue")}>
                        <Select
                            value={typeof action.recipient_queue_id === "string" ? action.recipient_queue_id : ""}
                            onValueChange={(value) => value && updateAction(index, { recipient_queue_id: value })}
                        >
                            <SelectTrigger id={fieldId("email-queue")} aria-label="Queue" className="w-full">
                                <SelectValue placeholder="Select queue">
                                    {(value: string | null) => {
                                        if (!value) return "Select queue"
                                        return queueOptions.find((queue) => queue.id === value)?.name ?? "Unknown queue"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {queueOptions.map((queue) => (
                                    <SelectItem key={queue.id} value={queue.id}>
                                        {queue.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </FieldRow>
                )}
                {getEmailRecipientKind(action) === "role" && (
                    <FieldRow label="Role" htmlFor={fieldId("email-role")}>
                        <Select
                            value={typeof action.recipient_role === "string" ? action.recipient_role : ""}
                            onValueChange={(value) => value && updateAction(index, { recipient_role: value })}
                        >
                            <SelectTrigger id={fieldId("email-role")} aria-label="Role" className="w-full">
                                <SelectValue placeholder="Select role">
                                    {(value: string | null) => {
                                        if (!value) return "Select role"
                                        return STAFF_ROLE_OPTIONS.find((role) => role.value === value)?.label ?? "Unknown role"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {STAFF_ROLE_OPTIONS.map((role) => (
                                    <SelectItem key={role.value} value={role.value}>
                                        {role.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </FieldRow>
                )}
                {getEmailRecipientKind(action) === "custom" && (
                    <FieldRow label="Email addresses" htmlFor={fieldId("email-addresses")}>
                        <EmailAddressListInput
                            key={action.clientId}
                            id={fieldId("email-addresses")}
                            initialEmails={getEmailRecipientEmails(action)}
                            onChange={(emails) => updateAction(index, { recipient_emails: emails })}
                        />
                    </FieldRow>
                )}
            </>
        )
    }

    if (action.action_type === "send_message") {
        return (
            <>
                <FieldRow label="Message purpose" htmlFor={fieldId("message-purpose")}>
                    <Select
                        aria-label="Message purpose"
                        value={typeof action.purpose === "string" ? action.purpose : ""}
                        onValueChange={(value) => {
                            if (!value) return
                            updateAction(index, { purpose: value, message_template_version_id: "" })
                        }}
                    >
                        <SelectTrigger id={fieldId("message-purpose")} aria-label="Message purpose" className="w-full">
                            <SelectValue placeholder="Message purpose">
                                {(value: string | null) => {
                                    if (value === "operational") return "Operational"
                                    if (value === "promotional") return "Promotional"
                                    return "Message purpose"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="operational">Operational</SelectItem>
                            <SelectItem value="promotional">Promotional</SelectItem>
                        </SelectContent>
                    </Select>
                </FieldRow>
                <FieldRow label="Message template" htmlFor={fieldId("message-template")}>
                    <Select
                        aria-label="Message template"
                        value={
                            typeof action.message_template_version_id === "string" ? action.message_template_version_id : ""
                        }
                        onValueChange={(value) => value && updateAction(index, { message_template_version_id: value })}
                    >
                        <SelectTrigger id={fieldId("message-template")} aria-label="Message template" className="w-full">
                            <SelectValue placeholder="Message template">
                                {(value: string | null) => {
                                    if (!value) return "Message template"
                                    const template = messageTemplates.find((candidate) => candidate.id === value)
                                    return template ? `${template.name} v${template.version}` : "Unknown template"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {messageTemplates.flatMap((template) =>
                                template.purpose === action.purpose
                                    ? [
                                        <SelectItem key={template.id} value={template.id}>
                                            {template.name} v{template.version}
                                        </SelectItem>,
                                    ]
                                    : [],
                            )}
                        </SelectContent>
                    </Select>
                </FieldRow>
            </>
        )
    }

    if (action.action_type === "create_task") {
        return (
            <>
                <FieldRow label="Task title" htmlFor={fieldId("task-title")}>
                    <Input
                        id={fieldId("task-title")}
                        aria-label="Task title"
                        value={typeof action.title === "string" ? action.title : ""}
                        onChange={(event) => updateAction(index, { title: event.target.value })}
                    />
                </FieldRow>
                <FieldRow label="Task description" htmlFor={fieldId("task-description")}>
                    <Textarea
                        id={fieldId("task-description")}
                        placeholder="Optional"
                        aria-label="Task description"
                        value={typeof action.description === "string" ? action.description : ""}
                        onChange={(event) => updateAction(index, { description: event.target.value })}
                        rows={2}
                    />
                </FieldRow>
                <FieldRow label="Due in days" htmlFor={fieldId("task-due-days")}>
                    <Input
                        id={fieldId("task-due-days")}
                        type="number"
                        min={0}
                        max={365}
                        aria-label="Due in days"
                        value={typeof action.due_days === "number" ? action.due_days : 1}
                        onChange={(event) => updateAction(index, { due_days: Number(event.target.value) })}
                    />
                </FieldRow>
                <FieldRow label="Assignee" htmlFor={fieldId("task-assignee")}>
                    <Select
                        value={typeof action.assignee === "string" ? action.assignee : "owner"}
                        onValueChange={(value) => value && updateAction(index, { assignee: value })}
                    >
                        <SelectTrigger id={fieldId("task-assignee")} aria-label="Task assignee" className="w-full">
                            <SelectValue placeholder="Assignee" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="owner">{isDonorSubject(actionSubjectType) ? "Donor Owner" : "Case Owner"}</SelectItem>
                            <SelectItem value="creator">Creator</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                            {userOptions.map((user) => (
                                <SelectItem key={user.id} value={user.id}>
                                    {user.display_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
            </>
        )
    }

    if (action.action_type === "send_notification") {
        return (
            <>
                <FieldRow label="Notification title" htmlFor={fieldId("notification-title")}>
                    <Input
                        id={fieldId("notification-title")}
                        aria-label="Notification title"
                        value={typeof action.title === "string" ? action.title : ""}
                        onChange={(event) => updateAction(index, { title: event.target.value })}
                    />
                </FieldRow>
                <FieldRow label="Notification body" htmlFor={fieldId("notification-body")}>
                    <Textarea
                        id={fieldId("notification-body")}
                        placeholder="Optional"
                        aria-label="Notification body"
                        value={typeof action.body === "string" ? action.body : ""}
                        onChange={(event) => updateAction(index, { body: event.target.value })}
                        rows={2}
                    />
                </FieldRow>
                <FieldRow label="Recipients" htmlFor={fieldId("notification-recipients")}>
                    <Select
                        value={
                            Array.isArray(action.recipients)
                                ? action.recipients[0] ?? "owner"
                                : typeof action.recipients === "string"
                                    ? action.recipients
                                    : "owner"
                        }
                        onValueChange={(value) => {
                            if (!value) return
                            if (typeof value === "string" && Object.hasOwn(NOTIFICATION_RECIPIENT_LABELS, value)) {
                                updateAction(index, { recipients: value })
                                return
                            }
                            updateAction(index, { recipients: [value] })
                        }}
                    >
                        <SelectTrigger id={fieldId("notification-recipients")} aria-label="Notification recipients" className="w-full">
                            <SelectValue placeholder="Recipients">
                                {(value: string | null) => {
                                    if (!value) return "Recipients"
                                    return (
                                        NOTIFICATION_RECIPIENT_LABELS[value] ??
                                        userOptions.find((user) => user.id === value)?.display_name ??
                                        "Unknown user"
                                    )
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="owner">{NOTIFICATION_RECIPIENT_LABELS.owner}</SelectItem>
                            <SelectItem value="creator">{NOTIFICATION_RECIPIENT_LABELS.creator}</SelectItem>
                            <SelectItem value="all_admins">{NOTIFICATION_RECIPIENT_LABELS.all_admins}</SelectItem>
                            {isAppointmentTrigger && (
                                <SelectItem value="host">{NOTIFICATION_RECIPIENT_LABELS.host}</SelectItem>
                            )}
                            {userOptions.map((user) => (
                                <SelectItem key={user.id} value={user.id}>
                                    {user.display_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
            </>
        )
    }

    if (action.action_type === "assign_surrogate" || action.action_type === "assign_donor") {
        return (
            <>
                <FieldRow label="Owner type" htmlFor={fieldId("owner-type")}>
                    <Select
                        aria-label="Assignment owner type"
                        value={typeof action.owner_type === "string" ? action.owner_type : ""}
                        onValueChange={(value) => updateAction(index, { owner_type: value, owner_id: "" })}
                    >
                        <SelectTrigger id={fieldId("owner-type")} aria-label="Assignment owner type" className="w-full">
                            <SelectValue placeholder="Owner type" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="user">User</SelectItem>
                            <SelectItem value="queue">Queue</SelectItem>
                        </SelectContent>
                    </Select>
                </FieldRow>
                <FieldRow label="Owner" htmlFor={fieldId("owner")}>
                    <Select
                        aria-label="Assignment owner"
                        value={typeof action.owner_id === "string" ? action.owner_id : ""}
                        onValueChange={(value) => value && updateAction(index, { owner_id: value })}
                    >
                        <SelectTrigger id={fieldId("owner")} aria-label="Assignment owner" className="w-full">
                            <SelectValue placeholder="Select owner" />
                        </SelectTrigger>
                        <SelectContent>
                            {(action.owner_type === "queue" ? queueOptions : userOptions).map((owner) => (
                                <SelectItem key={owner.id} value={owner.id}>
                                    {"name" in owner ? owner.name : owner.display_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
            </>
        )
    }

    if (action.action_type === "update_field") {
        return (
            <>
                <FieldRow label="Field to update" htmlFor={fieldId("update-field")}>
                    <Select
                        aria-label={`Field to update ${index + 1}`}
                        value={typeof action.field === "string" ? action.field : ""}
                        onValueChange={(value) => value && updateAction(index, { field: value, value: "" })}
                    >
                        <SelectTrigger id={fieldId("update-field")} aria-label={`Field to update ${index + 1}`} className="w-full">
                            <SelectValue placeholder="Select field" />
                        </SelectTrigger>
                        <SelectContent>
                            {updateFields.map((field) => (
                                <SelectItem key={field} value={field}>
                                    {getConditionFieldLabel(field)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FieldRow>
                {action.field ? (
                    <FieldRow label="New value" htmlFor={fieldId("update-value")}>
                        {action.field === "stage_id" ? (
                            <Select
                                aria-label={`Stage value ${index + 1}`}
                                value={typeof action.value === "string" ? action.value : ""}
                                onValueChange={(value) => value && updateAction(index, { value })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Stage value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select stage" />
                                </SelectTrigger>
                                <SelectContent>
                                    {statusOptions.map((stage) => (
                                        <SelectItem key={stage.id ?? stage.value} value={stage.id ?? stage.value}>
                                            {stage.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        ) : action.field === "is_priority" ? (
                            <Select
                                value={typeof action.value === "boolean" ? String(action.value) : ""}
                                onValueChange={(value) => updateAction(index, { value: value === "true" })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Priority value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select priority" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="true">Priority</SelectItem>
                                    <SelectItem value="false">Normal</SelectItem>
                                </SelectContent>
                            </Select>
                        ) : action.field === "source" ? (
                            <Select
                                aria-label={`Source value ${index + 1}`}
                                value={typeof action.value === "string" ? action.value : ""}
                                onValueChange={(value) => value && updateAction(index, { value })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Source value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select source">{getUpdateSourceLabel}</SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {UPDATE_SOURCE_OPTIONS.map((source) => (
                                        <SelectItem key={source.value} value={source.value}>
                                            {source.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        ) : action.field === "contact_status" ? (
                            <Select
                                value={typeof action.value === "string" ? action.value : ""}
                                onValueChange={(value) => value && updateAction(index, { value })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Contact status value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select contact status" />
                                </SelectTrigger>
                                <SelectContent>
                                    {CONTACT_STATUS_OPTIONS.map((status) => (
                                        <SelectItem key={status.value} value={status.value}>
                                            {status.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        ) : action.field === "owner_type" ? (
                            <Select
                                value={typeof action.value === "string" ? action.value : ""}
                                onValueChange={(value) => value && updateAction(index, { value })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Owner type value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select owner type" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="user">User</SelectItem>
                                    <SelectItem value="queue">Queue</SelectItem>
                                </SelectContent>
                            </Select>
                        ) : action.field === "owner_id" ? (
                            <Select
                                value={typeof action.value === "string" ? action.value : ""}
                                onValueChange={(value) => value && updateAction(index, { value })}
                            >
                                <SelectTrigger id={fieldId("update-value")} aria-label={`Owner value ${index + 1}`} className="w-full">
                                    <SelectValue placeholder="Select owner" />
                                </SelectTrigger>
                                <SelectContent>
                                    {userOptions.map((user) => (
                                        <SelectItem key={user.id} value={user.id}>
                                            {user.display_name}
                                        </SelectItem>
                                    ))}
                                    {queueOptions.map((queue) => (
                                        <SelectItem key={queue.id} value={queue.id}>
                                            {queue.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        ) : (
                            <Input
                                id={fieldId("update-value")}
                                aria-label="Value"
                                value={typeof action.value === "string" ? action.value : ""}
                                onChange={(event) => updateAction(index, { value: event.target.value })}
                            />
                        )}
                    </FieldRow>
                ) : null}
            </>
        )
    }

    if (action.action_type === "add_note") {
        return (
            <FieldRow label="Note content" htmlFor={fieldId("note-content")}>
                <Textarea
                    id={fieldId("note-content")}
                    aria-label="Note content"
                    value={typeof action.content === "string" ? action.content : ""}
                    onChange={(event) => updateAction(index, { content: event.target.value })}
                    rows={3}
                />
            </FieldRow>
        )
    }

    if (action.action_type === "promote_intake_lead") {
        return (
            <>
                <FieldRow label="Source" htmlFor={fieldId("promote-source")}>
                    <Input
                        id={fieldId("promote-source")}
                        placeholder="Optional, e.g. manual"
                        aria-label="Source"
                        value={typeof action.source === "string" ? action.source : ""}
                        onChange={(event) => updateAction(index, { source: event.target.value })}
                    />
                </FieldRow>
                {!isDonorIntakeTrigger && (
                    <>
                        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                            <div className="text-sm">Mark as priority</div>
                            <Switch
                                checked={typeof action.is_priority === "boolean" ? action.is_priority : false}
                                onCheckedChange={(checked) => updateAction(index, { is_priority: checked })}
                            />
                        </div>
                        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                            <div className="text-sm">Assign to workflow owner if available</div>
                            <Switch
                                checked={typeof action.assign_to_user === "boolean" ? action.assign_to_user : false}
                                onCheckedChange={(checked) => updateAction(index, { assign_to_user: checked })}
                            />
                        </div>
                    </>
                )}
            </>
        )
    }

    return null
}
