"use client"

import { ChevronDownIcon, ChevronUpIcon, ShieldCheckIcon, Trash2Icon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
    getEmailRecipientKind,
    getEmailRecipientUserId,
    type EditableAction,
} from "@/components/automation/workflow-editor/shared"
import { EditorColumn, PanelCard, PanelHeading, PanelSection } from "./inspector-section"
import { getActionMeta } from "./node-meta"

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
    const { actions, subjectType } = state
    const { actionTypeOptions, filteredActionTypes } = options
    const { updateActionType, removeAction, moveAction } = handlers
    const meta = getActionMeta(action.action_type)
    const actionLabel = actionTypeOptions.find((option) => option.value === action.action_type)?.label ?? "Action"
    const approvalLocked = isDonorSubject(subjectType) && action.action_type === "send_message"

    return (
        <EditorColumn aria-label="Action settings">
            <PanelHeading
                title={actionLabel}
                actions={
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
                            disabled={index >= actions.length - 1}
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
                }
            />
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
    const { subjectType } = state
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

    if (action.action_type === "send_email") {
        return (
            <>
                <div className="grid gap-1.5">
                    <Label htmlFor={`workflow-action-${action.clientId}-email-template`}>Email template</Label>
                    <Select
                        value={typeof action.template_id === "string" ? action.template_id : ""}
                        onValueChange={(value) => value && updateAction(index, { template_id: value })}
                    >
                        <SelectTrigger id={`workflow-action-${action.clientId}-email-template`} className="w-full">
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
                </div>
                <div className="grid gap-1.5">
                    <Label>Recipient</Label>
                    <Select
                        value={
                            isDonorSubject(subjectType) && getEmailRecipientKind(action) === "surrogate"
                                ? "donor"
                                : getEmailRecipientKind(action)
                        }
                        onValueChange={(value) => {
                            if (value === "user") {
                                const currentUser = getEmailRecipientUserId(action)
                                updateAction(index, { recipients: currentUser ? [currentUser] : [] })
                                return
                            }
                            updateAction(index, { recipients: value })
                        }}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select recipient" />
                        </SelectTrigger>
                        <SelectContent>
                            {emailRecipientOptions.map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                {getEmailRecipientKind(action) === "user" && (
                    <Select
                        value={getEmailRecipientUserId(action)}
                        onValueChange={(value) => updateAction(index, { recipients: value ? [value] : [] })}
                    >
                        <SelectTrigger className="w-full">
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
                )}
            </>
        )
    }

    if (action.action_type === "send_message") {
        return (
            <>
                <Select
                    aria-label="Message purpose"
                    value={typeof action.purpose === "string" ? action.purpose : ""}
                    onValueChange={(value) => {
                        if (!value) return
                        updateAction(index, { purpose: value, message_template_version_id: "" })
                    }}
                >
                    <SelectTrigger aria-label="Message purpose" className="w-full">
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
                <Select
                    aria-label="Message template"
                    value={
                        typeof action.message_template_version_id === "string" ? action.message_template_version_id : ""
                    }
                    onValueChange={(value) => value && updateAction(index, { message_template_version_id: value })}
                >
                    <SelectTrigger aria-label="Message template" className="w-full">
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
            </>
        )
    }

    if (action.action_type === "create_task") {
        return (
            <>
                <Input
                    placeholder="Task title"
                    aria-label="Task title"
                    value={typeof action.title === "string" ? action.title : ""}
                    onChange={(event) => updateAction(index, { title: event.target.value })}
                />
                <Textarea
                    placeholder="Task description (optional)"
                    aria-label="Task description"
                    value={typeof action.description === "string" ? action.description : ""}
                    onChange={(event) => updateAction(index, { description: event.target.value })}
                    rows={2}
                />
                <Input
                    type="number"
                    min={0}
                    max={365}
                    placeholder="Due in days"
                    aria-label="Due in days"
                    value={typeof action.due_days === "number" ? action.due_days : 1}
                    onChange={(event) => updateAction(index, { due_days: Number(event.target.value) })}
                />
                <Select
                    value={typeof action.assignee === "string" ? action.assignee : "owner"}
                    onValueChange={(value) => value && updateAction(index, { assignee: value })}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder="Assignee" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="owner">{isDonorSubject(subjectType) ? "Donor Owner" : "Case Owner"}</SelectItem>
                        <SelectItem value="creator">Creator</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                        {userOptions.map((user) => (
                            <SelectItem key={user.id} value={user.id}>
                                {user.display_name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </>
        )
    }

    if (action.action_type === "send_notification") {
        return (
            <>
                <Input
                    placeholder="Notification title"
                    aria-label="Notification title"
                    value={typeof action.title === "string" ? action.title : ""}
                    onChange={(event) => updateAction(index, { title: event.target.value })}
                />
                <Textarea
                    placeholder="Notification body (optional)"
                    aria-label="Notification body"
                    value={typeof action.body === "string" ? action.body : ""}
                    onChange={(event) => updateAction(index, { body: event.target.value })}
                    rows={2}
                />
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
                        if (value === "owner" || value === "creator" || value === "all_admins") {
                            updateAction(index, { recipients: value })
                            return
                        }
                        updateAction(index, { recipients: [value] })
                    }}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder="Recipients" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="owner">Owner</SelectItem>
                        <SelectItem value="creator">Creator</SelectItem>
                        <SelectItem value="all_admins">All Admins</SelectItem>
                        {userOptions.map((user) => (
                            <SelectItem key={user.id} value={user.id}>
                                {user.display_name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </>
        )
    }

    if (action.action_type === "assign_surrogate" || action.action_type === "assign_donor") {
        return (
            <>
                <Select
                    aria-label="Assignment owner type"
                    value={typeof action.owner_type === "string" ? action.owner_type : ""}
                    onValueChange={(value) => updateAction(index, { owner_type: value, owner_id: "" })}
                >
                    <SelectTrigger aria-label="Assignment owner type" className="w-full">
                        <SelectValue placeholder="Owner type" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="user">User</SelectItem>
                        <SelectItem value="queue">Queue</SelectItem>
                    </SelectContent>
                </Select>
                <Select
                    aria-label="Assignment owner"
                    value={typeof action.owner_id === "string" ? action.owner_id : ""}
                    onValueChange={(value) => value && updateAction(index, { owner_id: value })}
                >
                    <SelectTrigger aria-label="Assignment owner" className="w-full">
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
            </>
        )
    }

    if (action.action_type === "update_field") {
        return (
            <>
                <Select
                    aria-label={`Field to update ${index + 1}`}
                    value={typeof action.field === "string" ? action.field : ""}
                    onValueChange={(value) => value && updateAction(index, { field: value, value: "" })}
                >
                    <SelectTrigger aria-label={`Field to update ${index + 1}`} className="w-full">
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
                {action.field === "stage_id" ? (
                    <Select
                        aria-label={`Stage value ${index + 1}`}
                        value={typeof action.value === "string" ? action.value : ""}
                        onValueChange={(value) => value && updateAction(index, { value })}
                    >
                        <SelectTrigger aria-label={`Stage value ${index + 1}`} className="w-full">
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
                        <SelectTrigger className="w-full">
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
                        <SelectTrigger aria-label={`Source value ${index + 1}`} className="w-full">
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
                ) : action.field === "owner_type" ? (
                    <Select
                        value={typeof action.value === "string" ? action.value : ""}
                        onValueChange={(value) => value && updateAction(index, { value })}
                    >
                        <SelectTrigger className="w-full">
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
                        <SelectTrigger className="w-full">
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
                        placeholder="Value"
                        aria-label="Value"
                        value={typeof action.value === "string" ? action.value : ""}
                        onChange={(event) => updateAction(index, { value: event.target.value })}
                    />
                )}
            </>
        )
    }

    if (action.action_type === "add_note") {
        return (
            <Textarea
                placeholder="Note content"
                aria-label="Note content"
                value={typeof action.content === "string" ? action.content : ""}
                onChange={(event) => updateAction(index, { content: event.target.value })}
                rows={3}
            />
        )
    }

    if (action.action_type === "auto_match_submission") {
        return (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
                Matches existing applicants and holds conflicting identities for review.
            </p>
        )
    }

    if (action.action_type === "create_intake_lead") {
        return (
            <>
                <Input
                    placeholder="Source (optional, e.g. event_qr)"
                    aria-label="Source"
                    value={typeof action.source === "string" ? action.source : ""}
                    onChange={(event) => updateAction(index, { source: event.target.value })}
                />
                <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                    <Label htmlFor={`auto-promote-donor-${index}`}>Create donor after photo scan</Label>
                    <Switch
                        id={`auto-promote-donor-${index}`}
                        checked={action.auto_promote === true}
                        onCheckedChange={(checked) => updateAction(index, { auto_promote: checked })}
                    />
                </div>
                <p className="text-xs text-muted-foreground">
                    Skips automatically if the submission is already linked or has ambiguous match candidates.
                </p>
            </>
        )
    }

    if (action.action_type === "promote_intake_lead") {
        return (
            <>
                <Input
                    placeholder="Source (optional, e.g. manual)"
                    aria-label="Source"
                    value={typeof action.source === "string" ? action.source : ""}
                    onChange={(event) => updateAction(index, { source: event.target.value })}
                />
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
