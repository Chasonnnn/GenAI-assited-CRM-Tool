"use client"

import Link from "@/components/app-link"
import { QueryErrorState } from "@/components/error-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import type {
    AppointmentClientMessage,
    AppointmentClientMessageKey,
    AppointmentClientMessages,
} from "@/lib/api/appointments"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { useWorkflows } from "@/lib/hooks/use-workflows"
import { getAppointmentTypeWorkflowHref, getTriggerLabel } from "@/lib/workflows/workflow-editor-state"
import { PlusIcon } from "lucide-react"

const CLIENT_MESSAGE_ROWS: { key: AppointmentClientMessageKey; label: string }[] = [
    { key: "request_received", label: "Request received" },
    { key: "confirmed", label: "Confirmed" },
    { key: "reminder", label: "Reminder" },
    { key: "rescheduled", label: "Rescheduled" },
    { key: "cancelled", label: "Cancelled" },
]

const REMINDER_HOUR_OPTIONS = [1, 2, 4, 12, 24, 48, 72]

// The org-wide templates scheduling falls back to, by system key; the null template choice stands
// for them.
const DEFAULT_APPOINTMENT_TEMPLATE_KEYS = new Set([
    "scheduling_request_received",
    "scheduling_confirmed",
    "scheduling_reminder",
    "scheduling_rescheduled",
    "scheduling_cancelled",
])

const DEFAULT_TEMPLATE_VALUE = "default"

export const DEFAULT_CLIENT_MESSAGES: AppointmentClientMessages = {
    request_received: { enabled: true, template_id: null },
    confirmed: { enabled: true, template_id: null },
    reminder: { enabled: true, template_id: null },
    rescheduled: { enabled: true, template_id: null },
    cancelled: { enabled: true, template_id: null },
}

function formatReminderHours(hours: number): string {
    return hours === 1 ? "1 hour before" : `${hours} hours before`
}

export function AppointmentClientMessagesFields({
    messages,
    reminderHours,
    onMessageChange,
    onReminderHoursChange,
}: {
    messages: AppointmentClientMessages
    reminderHours: number
    onMessageChange: (key: AppointmentClientMessageKey, message: AppointmentClientMessage) => void
    onReminderHoursChange: (hours: number) => void
}) {
    const templatesQuery = useEmailTemplates()
    const templates = (templatesQuery.data ?? []).filter(
        (template) => !template.system_key || !DEFAULT_APPOINTMENT_TEMPLATE_KEYS.has(template.system_key),
    )
    const templateLabel = (value: string | null) => {
        if (!value || value === DEFAULT_TEMPLATE_VALUE) return "Default template"
        return templates.find((template) => template.id === value)?.name ?? "Unknown template"
    }
    const hourOptions = REMINDER_HOUR_OPTIONS.includes(reminderHours)
        ? REMINDER_HOUR_OPTIONS
        : [...REMINDER_HOUR_OPTIONS, reminderHours].sort((a, b) => a - b)

    return (
        <div role="group" aria-labelledby="appointment-client-messages-label" className="space-y-2">
            <p id="appointment-client-messages-label" className="text-sm font-medium">Client messages</p>
            <div className="grid gap-2">
                {CLIENT_MESSAGE_ROWS.map(({ key, label }) => {
                    const message = messages[key]
                    const switchId = `appointment-client-message-${key}`
                    return (
                        <div
                            key={key}
                            className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-border px-3 py-2 text-sm"
                        >
                            <Switch
                                id={switchId}
                                checked={message.enabled}
                                onCheckedChange={(checked) => onMessageChange(key, { ...message, enabled: checked })}
                            />
                            <Label htmlFor={switchId} className="text-sm">{label}</Label>
                            <div className="ml-auto flex min-w-0 flex-wrap items-center gap-2">
                                {key === "reminder" && (
                                    <Select
                                        value={String(reminderHours)}
                                        onValueChange={(value) => value && onReminderHoursChange(Number(value))}
                                        disabled={!message.enabled}
                                    >
                                        <SelectTrigger aria-label="Reminder timing" size="sm" className="w-40">
                                            <SelectValue>
                                                {(value: string | null) =>
                                                    value ? formatReminderHours(Number(value)) : "Select timing"
                                                }
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            {hourOptions.map((hours) => (
                                                <SelectItem key={hours} value={String(hours)}>
                                                    {formatReminderHours(hours)}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                )}
                                <Select
                                    value={message.template_id ?? DEFAULT_TEMPLATE_VALUE}
                                    onValueChange={(value) =>
                                        value &&
                                        onMessageChange(key, {
                                            ...message,
                                            template_id: value === DEFAULT_TEMPLATE_VALUE ? null : value,
                                        })
                                    }
                                    disabled={!message.enabled}
                                >
                                    <SelectTrigger aria-label={`${label} template`} size="sm" className="w-48">
                                        <SelectValue>{templateLabel}</SelectValue>
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value={DEFAULT_TEMPLATE_VALUE}>
                                            {templateLabel(DEFAULT_TEMPLATE_VALUE)}
                                        </SelectItem>
                                        {templates.map((template) => (
                                            <SelectItem key={template.id} value={template.id}>
                                                {template.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    )
                })}
            </div>
            <p className="text-xs text-muted-foreground">
                Google Calendar events use Google invites instead of Confirmed, Rescheduled, and Cancelled.
            </p>
        </div>
    )
}

export function AppointmentTypeWorkflows({ typeName }: { typeName: string }) {
    const { can, policyVersion } = usePermissionCheck()
    const canManageOrgWorkflows =
        can("manage_automation") && ((policyVersion ?? 1) < 2 || can("manage_org_workflows"))
    const workflowsQuery = useWorkflows({ appointment_type_name: typeName })
    const workflows = workflowsQuery.data ?? []

    return (
        <div role="group" aria-labelledby="appointment-type-workflows-label" className="space-y-2">
            <div className="flex items-center justify-between gap-2">
                <p id="appointment-type-workflows-label" className="text-sm font-medium">Workflows</p>
                <Button
                    variant="outline"
                    size="sm"
                    render={
                        <Link
                            href={getAppointmentTypeWorkflowHref(
                                typeName,
                                canManageOrgWorkflows ? "org" : "personal",
                            )}
                        />
                    }
                >
                    <PlusIcon className="size-4" aria-hidden="true" />
                    New workflow
                </Button>
            </div>
            <p className="text-xs text-muted-foreground">
                Matches every host&apos;s &ldquo;{typeName}&rdquo; type.
            </p>
            {workflowsQuery.isLoading ? (
                <Skeleton className="h-10 w-full" />
            ) : workflowsQuery.isError ? (
                <QueryErrorState
                    title="Unable to load workflows"
                    error={workflowsQuery.error}
                    onRetry={() => void workflowsQuery.refetch()}
                    isRetrying={workflowsQuery.isFetching}
                    headingLevel={3}
                    className="min-h-0 py-4"
                />
            ) : workflows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No workflows</p>
            ) : (
                <ul className="grid gap-2">
                    {workflows.map((workflow) => (
                        <li
                            key={workflow.id}
                            className="flex items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                        >
                            <Link href={`/automation/workflows/${workflow.id}`} className="min-w-0 truncate font-medium hover:underline">
                                {workflow.name}
                            </Link>
                            <span className="truncate text-muted-foreground">{getTriggerLabel(workflow.trigger_type)}</span>
                            <Badge variant={workflow.is_enabled ? "default" : "secondary"} className="ml-auto">
                                {workflow.is_enabled ? "Active" : "Off"}
                            </Badge>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
