"use client"

import { useReducer, useState, type Dispatch, type SetStateAction } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import Link from "@/components/app-link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { EmptyState } from "@/components/empty-state"
import { QueryErrorState } from "@/components/error-state"
import {
    CampaignAudienceFields,
    campaignStageOptions,
} from "@/components/campaigns/campaign-audience-fields"
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    ArrowLeftIcon,
    UsersIcon,
    SendIcon,
    CheckCircle2Icon,
    MousePointerClickIcon,
    CopyIcon,
    TrashIcon,
    Loader2Icon,
    ChevronDownIcon,
    ChevronUpIcon,
    MailIcon,
    RefreshCcwIcon,
    PencilIcon,
    MessageSquareTextIcon,
    MoreHorizontalIcon,
    ShieldAlertIcon,
} from "lucide-react"
import { format } from "date-fns"
import { toast } from "@/components/ui/toast"
import { parseDateInput } from "@/lib/utils/date"
import {
    useCampaign,
    useCampaignRuns,
    useCampaignPreview,
    useRunRecipients,
    useDeleteCampaign,
    useDuplicateCampaign,
    useCancelCampaign,
    useSendCampaign,
    useUpdateCampaign,
    useRetryFailedCampaignRun,
} from "@/lib/hooks/use-campaigns"
import { useEmailTemplate, useEmailTemplates } from "@/lib/hooks/use-email-templates"
import type {
    Campaign,
    CampaignRecipient,
    CampaignRecipientType,
    CampaignRun,
    FilterCriteria,
} from "@/lib/api/campaigns"
import type { EmailTemplate, EmailTemplateListItem } from "@/lib/api/email-templates"
import { listMessagingTemplates, type MessagingTemplateVersion } from "@/lib/api/twilio"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import type { StageOption } from "@/lib/stage-options"
import { useQuery } from "@tanstack/react-query"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { RecipientPreviewCard } from "@/components/recipient-preview-card"
import { US_STATES } from "@/lib/constants/us-states"
import { getIntendedParentStageOptions } from "@/lib/intended-parent-stage-utils"
import {
    getCampaignPipelineEntityType,
    getCampaignRecipientHref,
    getCampaignRecipientLabel,
    getCampaignSendConfirmTitle,
    isCampaignRecipientType,
    isDonorCampaignRecipientType,
} from "@/lib/campaign-recipient"

// Status styles
const statusStyles: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }> = {
    draft: { variant: "secondary" },
    scheduled: { variant: "outline", className: "border-blue-500 text-blue-600" },
    sending: { variant: "outline", className: "border-yellow-500 text-yellow-600 animate-pulse" },
    completed: { variant: "default", className: "bg-green-500" },
    sent: { variant: "default", className: "bg-green-500" },
    failed: { variant: "destructive" },
    cancelled: { variant: "secondary" },
    pending: { variant: "secondary" },
    delivered: { variant: "default", className: "bg-green-500" },
    skipped: { variant: "outline" },
}

const statusLabels: Record<string, string> = {
    draft: "Draft",
    scheduled: "Scheduled",
    sending: "Sending",
    completed: "Sent",
    sent: "Sent",
    failed: "Failed",
    cancelled: "Cancelled",
    pending: "Pending",
    delivered: "Delivered",
    skipped: "Skipped",
}

const toLocalDateTimeInput = (date: Date) => {
    const pad = (value: number) => String(value).padStart(2, "0")
    const year = date.getFullYear()
    const month = pad(date.getMonth() + 1)
    const day = pad(date.getDate())
    const hours = pad(date.getHours())
    const minutes = pad(date.getMinutes())
    return `${year}-${month}-${day}T${hours}:${minutes}`
}

function toSelectedStringSet(values: readonly unknown[]): Set<string> {
    const selected = new Set<string>()
    for (const value of values) {
        if (typeof value !== "string") continue
        const trimmed = value.trim()
        if (trimmed) {
            selected.add(trimmed)
        }
    }
    return selected
}

function getSelectedLabels<T extends { label: string }>(
    options: readonly T[],
    selectedValues: ReadonlySet<string>,
    getValue: (option: T) => string,
): string[] {
    return options.flatMap((option) => (
        selectedValues.has(getValue(option)) ? [option.label] : []
    ))
}

type CampaignEditRecipientType = CampaignRecipientType

type CampaignEditDraftState = {
    name: string
    description: string
    templateId: string
    recipientType: CampaignEditRecipientType
    stages: string[]
    states: string[]
    includeUnsubscribed: boolean
    scheduledAt: string
}

type CampaignEditDraftAction =
    | { type: "hydrate"; draft: CampaignEditDraftState }
    | { type: "changeName"; value: string }
    | { type: "changeDescription"; value: string }
    | { type: "changeTemplate"; value: string }
    | { type: "changeRecipientType"; value: CampaignEditRecipientType }
    | { type: "setStages"; value: string[] }
    | { type: "setStates"; value: string[] }
    | { type: "toggleIncludeUnsubscribed"; value: boolean }
    | { type: "changeScheduledAt"; value: string }

const initialCampaignEditDraft: CampaignEditDraftState = {
    name: "",
    description: "",
    templateId: "",
    recipientType: "case",
    stages: [],
    states: [],
    includeUnsubscribed: false,
    scheduledAt: "",
}

function createCampaignEditDraft(campaign: Campaign): CampaignEditDraftState {
    const criteria = campaign.filter_criteria || {}
    const stageIds = Array.isArray(criteria.stage_ids) ? criteria.stage_ids : []
    const stageSlugs = Array.isArray(criteria.stage_slugs) ? criteria.stage_slugs : []
    const states = Array.isArray(criteria.states) ? criteria.states : []
    const recipientType = isCampaignRecipientType(campaign.recipient_type)
        ? campaign.recipient_type
        : "case"

    return {
        name: campaign.name,
        description: campaign.description ?? "",
        templateId:
            campaign.channel === "messaging"
                ? campaign.message_template_version_id ?? ""
                : campaign.email_template_id ?? "",
        recipientType,
        stages: recipientType === "intended_parent" ? stageSlugs : stageIds,
        states,
        includeUnsubscribed: !!campaign.include_unsubscribed,
        scheduledAt: campaign.scheduled_at
            ? toLocalDateTimeInput(new Date(campaign.scheduled_at))
            : "",
    }
}

function campaignEditDraftReducer(
    state: CampaignEditDraftState,
    action: CampaignEditDraftAction,
): CampaignEditDraftState {
    switch (action.type) {
        case "hydrate":
            return action.draft
        case "changeName":
            return { ...state, name: action.value }
        case "changeDescription":
            return { ...state, description: action.value }
        case "changeTemplate":
            return { ...state, templateId: action.value }
        case "changeRecipientType":
            return { ...state, recipientType: action.value, stages: [] }
        case "setStages":
            return { ...state, stages: action.value }
        case "setStates":
            return { ...state, states: action.value }
        case "toggleIncludeUnsubscribed":
            return { ...state, includeUnsubscribed: action.value }
        case "changeScheduledAt":
            return { ...state, scheduledAt: action.value }
        default:
            return state
    }
}

type BooleanStateSetter = Dispatch<SetStateAction<boolean>>

function buildCampaignEditFilterCriteria(editDraft: CampaignEditDraftState): FilterCriteria {
    const stageFilters =
        editDraft.stages.length > 0
            ? editDraft.recipientType === "intended_parent"
                ? { stage_slugs: editDraft.stages }
                : { stage_ids: editDraft.stages }
            : {}

    return {
        ...stageFilters,
        ...(editDraft.states.length > 0 ? { states: editDraft.states } : {}),
    }
}

function createCampaignDetailHandlers({
    campaign,
    campaignId,
    latestRun,
    editDraft,
    deleteCampaign,
    duplicateCampaign,
    cancelCampaign,
    sendCampaign,
    updateCampaign,
    retryFailed,
    push,
    setShowEditDialog,
}: {
    campaign: Campaign
    campaignId: string
    latestRun: CampaignRun | undefined
    editDraft: CampaignEditDraftState
    deleteCampaign: ReturnType<typeof useDeleteCampaign>
    duplicateCampaign: ReturnType<typeof useDuplicateCampaign>
    cancelCampaign: ReturnType<typeof useCancelCampaign>
    sendCampaign: ReturnType<typeof useSendCampaign>
    updateCampaign: ReturnType<typeof useUpdateCampaign>
    retryFailed: ReturnType<typeof useRetryFailedCampaignRun>
    push: ReturnType<typeof useRouter>["push"]
    setShowEditDialog: BooleanStateSetter
}) {
    // Delete, stop, send and retry run inside ConfirmDialog, which shows failures inline,
    // so those handlers let errors propagate.
    return {
        handleDelete: async () => {
            await deleteCampaign.mutateAsync(campaignId)
            toast.success("Campaign deleted")
            push("/automation/campaigns")
        },
        handleDuplicate: async () => {
            try {
                const newCampaign = await duplicateCampaign.mutateAsync(campaignId)
                toast.success("Campaign duplicated")
                push(`/automation/campaigns/${newCampaign.id}`)
            } catch {
                toast.error("Failed to duplicate campaign")
            }
        },
        handleEditSave: async () => {
            if (!editDraft.name || !editDraft.templateId) {
                toast.error("Please fill in required fields")
                return
            }

            let scheduledAt: string | undefined
            if (editDraft.scheduledAt) {
                const parsedDate = new Date(editDraft.scheduledAt)
                if (Number.isNaN(parsedDate.getTime())) {
                    toast.error("Scheduled date is invalid")
                    return
                }
                if (parsedDate <= new Date()) {
                    toast.error("Scheduled date must be in the future")
                    return
                }
                scheduledAt = parsedDate.toISOString()
            }

            try {
                await updateCampaign.mutateAsync({
                    id: campaign.id,
                    data: {
                        name: editDraft.name,
                        description: editDraft.description,
                        ...(campaign.channel === "messaging"
                            ? { message_template_version_id: editDraft.templateId }
                            : { email_template_id: editDraft.templateId }),
                        recipient_type: editDraft.recipientType,
                        filter_criteria: buildCampaignEditFilterCriteria(editDraft),
                        include_unsubscribed:
                            campaign.channel === "email" && editDraft.includeUnsubscribed,
                        ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
                    },
                })
                toast.success("Campaign updated")
                setShowEditDialog(false)
            } catch {
                toast.error("Failed to update campaign")
            }
        },
        handleRetryFailed: async () => {
            if (!latestRun) {
                return
            }
            const result = await retryFailed.mutateAsync({
                campaignId,
                runId: latestRun.id,
            })
            toast.success(result.message)
        },
        handleCancel: async () => {
            await cancelCampaign.mutateAsync(campaignId)
            toast.success("Campaign stopped")
        },
        handleSendNow: async () => {
            await sendCampaign.mutateAsync({ id: campaignId, sendNow: true })
            toast.success("Campaign queued for sending")
        },
    }
}

function CampaignDetailHeader({
    campaign,
    canManage,
    canEdit,
    cancelPending,
    onEdit,
    onSendNow,
    onCancel,
    onDuplicate,
    onDelete,
}: {
    campaign: Campaign
    /** Viewer holds manage_email_templates, which every campaign action requires. */
    canManage: boolean
    canEdit: boolean
    cancelPending: boolean
    onEdit: () => void
    onSendNow: () => void
    onCancel: () => void
    onDuplicate: () => void
    onDelete: () => void
}) {
    return (
        <div className="border-b bg-card">
            <div className="flex items-center justify-between p-6">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Back to campaigns"
                        render={<Link href="/automation/campaigns" />}
                    >
                        <ArrowLeftIcon className="size-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-semibold">{campaign.name}</h1>
                            <Badge
                                variant={statusStyles[campaign.status]?.variant || "secondary"}
                                className={statusStyles[campaign.status]?.className}
                            >
                                {statusLabels[campaign.status] || campaign.status}
                            </Badge>
                        </div>
                        {campaign.description && (
                            <p className="text-sm text-muted-foreground mt-1">
                                {campaign.description}
                            </p>
                        )}
                    </div>
                </div>
                {canManage ? (
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            onClick={onEdit}
                            disabled={!canEdit}
                        >
                            <PencilIcon className="size-4" />
                            Edit
                        </Button>
                        {campaign.status === "draft" && (
                            <Button onClick={onSendNow}>
                                <SendIcon className="size-4" />
                                Send Now
                            </Button>
                        )}
                        {(campaign.status === "scheduled" || campaign.status === "sending") && (
                            <Button
                                variant="destructive"
                                onClick={onCancel}
                                disabled={cancelPending}
                            >
                                Stop
                            </Button>
                        )}
                        <DropdownMenu>
                            <DropdownMenuTrigger
                                render={
                                    <Button
                                        variant="outline"
                                        size="icon"
                                        aria-label="More campaign actions"
                                    >
                                        <MoreHorizontalIcon className="size-4" aria-hidden="true" />
                                    </Button>
                                }
                            />
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={onDuplicate}>
                                    <CopyIcon className="size-4" aria-hidden="true" />
                                    Duplicate
                                </DropdownMenuItem>
                                {campaign.status === "draft" ? (
                                    <>
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem variant="destructive" onClick={onDelete}>
                                            <TrashIcon className="size-4" aria-hidden="true" />
                                            Delete
                                        </DropdownMenuItem>
                                    </>
                                ) : null}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                ) : null}
            </div>
        </div>
    )
}

function CampaignStatsGrid({
    campaign,
    totalRecipients,
    sentPercent,
    openedCount,
    openPercent,
    clickedCount,
    clickPercent,
}: {
    campaign: Campaign
    totalRecipients: number
    sentPercent: number
    openedCount: number
    openPercent: number
    clickedCount: number
    clickPercent: number
}) {
    return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                        <UsersIcon className="size-4" />
                        Total Recipients
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{totalRecipients}</div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                        <SendIcon className="size-4" />
                        Sent
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">{campaign.sent_count}</div>
                    <p className="text-sm text-muted-foreground">{sentPercent}% of total</p>
                    {campaign.failed_count > 0 && (
                        <p className="text-xs text-muted-foreground">
                            Failed: {campaign.failed_count}
                        </p>
                    )}
                </CardContent>
            </Card>

            {campaign.channel === "messaging" ? (
                <>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <CheckCircle2Icon className="size-4 text-green-500" />
                                Delivered
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-600">
                                {campaign.delivered_count}
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Failed
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-destructive">
                                {campaign.failed_count}
                            </div>
                        </CardContent>
                    </Card>
                </>
            ) : (
                <>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <CheckCircle2Icon className="size-4 text-green-500" />
                                Opened
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-600">{openedCount}</div>
                            <p className="text-sm text-muted-foreground">{openPercent}% of sent</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <MousePointerClickIcon className="size-4 text-blue-500" />
                                Clicked
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-blue-600">{clickedCount}</div>
                            <p className="text-sm text-muted-foreground">{clickPercent}% of sent</p>
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    )
}

function CampaignFilterSummaryCard({
    campaign,
    filterCriteria,
    stageLabelsForFilter,
    stateLabelsForFilter,
    createdAfter,
    createdBefore,
}: {
    campaign: Campaign
    filterCriteria: FilterCriteria
    stageLabelsForFilter: string[]
    stateLabelsForFilter: string[]
    createdAfter: Date | null
    createdBefore: Date | null
}) {
    return (
        <Card>
            <CardHeader>
                <CardTitle>Recipient Filters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* One label style and one value style (text-sm) for every filter. */}
                <dl className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-1">
                        <dt className="text-xs text-muted-foreground">Recipient Type</dt>
                        <dd className="text-sm">
                            {getCampaignRecipientLabel(campaign.recipient_type)}
                        </dd>
                    </div>
                    <div className="space-y-1">
                        <dt className="text-xs text-muted-foreground">
                            {campaign.recipient_type === "intended_parent" ? "Statuses" : "Stages"}
                        </dt>
                        <dd className="text-sm">
                            {stageLabelsForFilter.length > 0 ? (
                                <span className="flex flex-wrap gap-2">
                                    {stageLabelsForFilter.map((label) => (
                                        <Badge key={label} variant="secondary" className="text-xs">
                                            {label}
                                        </Badge>
                                    ))}
                                </span>
                            ) : (
                                "All"
                            )}
                        </dd>
                    </div>
                    <div className="space-y-1">
                        <dt className="text-xs text-muted-foreground">States</dt>
                        <dd className="text-sm">
                            {stateLabelsForFilter.length > 0 ? (
                                <span className="flex flex-wrap gap-2">
                                    {stateLabelsForFilter.map((label) => (
                                        <Badge key={label} variant="secondary" className="text-xs">
                                            {label}
                                        </Badge>
                                    ))}
                                </span>
                            ) : (
                                "All"
                            )}
                        </dd>
                    </div>
                    <div className="space-y-1">
                        <dt className="text-xs text-muted-foreground">Created Range</dt>
                        <dd className="text-sm">
                            {(createdAfter || createdBefore) ? (
                                <>
                                    {createdAfter ? format(createdAfter, "MMM d, yyyy") : "Anytime"}{" "}
                                    →{" "}
                                    {createdBefore ? format(createdBefore, "MMM d, yyyy") : "Now"}
                                </>
                            ) : (
                                "Anytime"
                            )}
                        </dd>
                    </div>
                    {campaign.channel === "email" && (
                        <div className="space-y-1">
                            <dt className="text-xs text-muted-foreground">Unsubscribed Recipients</dt>
                            <dd className="text-sm">
                                {campaign.include_unsubscribed ? "Included" : "Excluded"}
                            </dd>
                        </div>
                    )}
                </dl>
                {(filterCriteria.source ||
                    (filterCriteria.is_priority &&
                        !isDonorCampaignRecipientType(campaign.recipient_type))) && (
                    <div className="flex flex-wrap gap-2">
                        {filterCriteria.source && (
                            <Badge variant="outline" className="text-xs">
                                Source: {filterCriteria.source}
                            </Badge>
                        )}
                        {filterCriteria.is_priority &&
                            !isDonorCampaignRecipientType(campaign.recipient_type) && (
                            <Badge variant="outline" className="text-xs">
                                Priority only
                            </Badge>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function CampaignTemplatePreviewCard({
    template,
    channel,
    open,
    onOpenChange,
}: {
    template: Pick<EmailTemplate, "subject" | "body"> | MessagingTemplateVersion | null | undefined
    channel: Campaign["channel"]
    open: boolean
    onOpenChange: (open: boolean) => void
}) {
    return (
        <Collapsible open={open} onOpenChange={onOpenChange}>
            <Card>
                <CollapsibleTrigger
                    className="w-full"
                    onClick={() => onOpenChange(!open)}
                >
                    <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                {channel === "messaging" ? (
                                    <MessageSquareTextIcon className="size-4 text-muted-foreground" />
                                ) : (
                                    <MailIcon className="size-4 text-muted-foreground" />
                                )}
                                <CardTitle className="text-base">
                                    {channel === "messaging" ? "Messaging Template" : "Email Template"}
                                </CardTitle>
                            </div>
                            {open ? (
                                <ChevronUpIcon className="size-4 text-muted-foreground" />
                            ) : (
                                <ChevronDownIcon className="size-4 text-muted-foreground" />
                            )}
                        </div>
                    </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <CardContent className="pt-0 space-y-4">
                        {template ? (
                            <>
                                {"subject" in template && (
                                    <div className="bg-muted/50 rounded-lg p-4">
                                        <p className="text-sm text-muted-foreground mb-1">Subject</p>
                                        <p className="font-medium">{template.subject}</p>
                                    </div>
                                )}
                                <div className="bg-muted/50 rounded-lg p-4">
                                    <p className="text-sm text-muted-foreground mb-1">Body</p>
                                    <p className="whitespace-pre-wrap text-sm">{template.body}</p>
                                </div>
                            </>
                        ) : (
                            <p className="text-muted-foreground text-sm">Template not found</p>
                        )}
                    </CardContent>
                </CollapsibleContent>
            </Card>
        </Collapsible>
    )
}

function CampaignRecipientsCard({
    channel,
    latestRun,
    recipients,
    recipientFilter,
    retryPending,
    onRecipientFilterChange,
    onRetryFailed,
}: {
    channel: Campaign["channel"]
    latestRun: CampaignRun | undefined
    recipients: CampaignRecipient[] | undefined
    recipientFilter: string
    retryPending: boolean
    onRecipientFilterChange: (value: string) => void
    onRetryFailed: () => void
}) {
    return (
        <Card>
            <CardHeader>
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <CardTitle>Recipients</CardTitle>
                        {latestRun ? (
                            <CardDescription>
                                {`Last run: ${format(parseDateInput(latestRun.started_at), "MMM d, yyyy 'at' h:mm a")}`}
                            </CardDescription>
                        ) : null}
                    </div>
                    {latestRun && latestRun.failed_count > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRetryFailed}
                            disabled={retryPending}
                        >
                            {retryPending ? (
                                <Loader2Icon className="size-4 animate-spin" />
                            ) : (
                                <RefreshCcwIcon className="size-4" />
                            )}
                            Retry failed
                        </Button>
                    )}
                </div>
            </CardHeader>
            <CardContent>
                {latestRun && (
                    <Tabs
                        value={recipientFilter}
                        onValueChange={onRecipientFilterChange}
                        className="mb-4"
                    >
                        <TabsList>
                            <TabsTrigger value="all">All</TabsTrigger>
                            <TabsTrigger value="failed">
                                Failed{latestRun.failed_count ? ` (${latestRun.failed_count})` : ""}
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                )}
                {recipients && recipients.length > 0 ? (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>{channel === "messaging" ? "Phone" : "Email"}</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Sent At</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {recipients.map((recipient) => {
                                const recipientHref = getCampaignRecipientHref(
                                    recipient.entity_type,
                                    recipient.entity_id,
                                )
                                return (
                                    <TableRow key={recipient.id}>
                                        <TableCell className="font-medium">
                                            {recipientHref ? (
                                                <Link
                                                    href={recipientHref}
                                                    className="text-primary hover:underline"
                                                >
                                                    {recipient.recipient_name || "-"}
                                                </Link>
                                            ) : (
                                                recipient.recipient_name || "-"
                                            )}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {channel === "messaging"
                                                ? recipient.recipient_phone_last4
                                                    ? `••• ••• ${recipient.recipient_phone_last4}`
                                                    : "-"
                                                : recipient.recipient_email ?? "-"}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant={statusStyles[recipient.status]?.variant || "secondary"}
                                                className={statusStyles[recipient.status]?.className}
                                            >
                                                {statusLabels[recipient.status] || recipient.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-sm">
                                            {recipient.sent_at
                                                ? format(parseDateInput(recipient.sent_at), "MMM d, yyyy h:mm a")
                                                : "-"}
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                        </TableBody>
                    </Table>
                ) : (
                    <EmptyState
                        icon={UsersIcon}
                        title={latestRun ? "No recipients in this run" : "Not sent yet"}
                        className="py-8"
                    />
                )}
            </CardContent>
        </Card>
    )
}

function CampaignEditDialog({
    open,
    campaign,
    editDraft,
    templates,
    editStageOptions,
    updatePending,
    dispatchEditDraft,
    onOpenChange,
    onSave,
}: {
    open: boolean
    campaign: Campaign
    editDraft: CampaignEditDraftState
    templates: Array<Pick<EmailTemplateListItem, "id" | "name">> | undefined
    editStageOptions: StageOption[]
    updatePending: boolean
    dispatchEditDraft: Dispatch<CampaignEditDraftAction>
    onOpenChange: (open: boolean) => void
    onSave: () => void
}) {
    const templateLabel = campaign.channel === "messaging" ? "SMS template" : "Email template"
    const scheduledAtValue = editDraft.scheduledAt ? new Date(editDraft.scheduledAt) : undefined

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent layout="sectioned" size="2xl">
                <DialogHeader>
                    <DialogTitle>Edit Campaign</DialogTitle>
                </DialogHeader>

                <DialogBody>
                    <section aria-labelledby="edit-campaign-setup" className="flex flex-col gap-4">
                        <h3 id="edit-campaign-setup" className="text-sm font-semibold">Setup</h3>
                        <div className="flex flex-col gap-2">
                            <Label htmlFor="edit-channel">Channel</Label>
                            <Input
                                id="edit-channel"
                                value={campaign.channel === "messaging" ? "SMS / MMS" : "Email"}
                                disabled
                                readOnly
                            />
                        </div>
                        <div className="flex flex-col gap-2">
                            <Label htmlFor="edit-name">Campaign name</Label>
                            <Input
                                id="edit-name"
                                value={editDraft.name}
                                onChange={(event) =>
                                    dispatchEditDraft({
                                        type: "changeName",
                                        value: event.target.value,
                                    })
                                }
                            />
                        </div>
                        <div className="flex flex-col gap-2">
                            <Label htmlFor="edit-description">Description (optional)</Label>
                            <Textarea
                                id="edit-description"
                                value={editDraft.description}
                                onChange={(event) =>
                                    dispatchEditDraft({
                                        type: "changeDescription",
                                        value: event.target.value,
                                    })
                                }
                            />
                        </div>
                    </section>

                    <section aria-labelledby="edit-campaign-audience" className="flex flex-col gap-4 border-t pt-5">
                        <h3 id="edit-campaign-audience" className="text-sm font-semibold">Audience</h3>
                        <CampaignAudienceFields
                            idPrefix="campaign-edit"
                            channel={campaign.channel}
                            recipientType={editDraft.recipientType}
                            onRecipientTypeChange={(value) =>
                                dispatchEditDraft({ type: "changeRecipientType", value })
                            }
                            stageOptions={editStageOptions}
                            selectedStages={editDraft.stages}
                            onSelectedStagesChange={(value) => dispatchEditDraft({ type: "setStages", value })}
                            selectedStates={editDraft.states}
                            onSelectedStatesChange={(value) => dispatchEditDraft({ type: "setStates", value })}
                            includeUnsubscribed={editDraft.includeUnsubscribed}
                            onIncludeUnsubscribedChange={(value) =>
                                dispatchEditDraft({ type: "toggleIncludeUnsubscribed", value })
                            }
                        />
                    </section>

                    <section aria-labelledby="edit-campaign-content" className="flex flex-col gap-4 border-t pt-5">
                        <h3 id="edit-campaign-content" className="text-sm font-semibold">Content</h3>
                        <div className="flex flex-col gap-2">
                            <Label htmlFor="edit-template">{templateLabel}</Label>
                            <Select
                                aria-label={templateLabel}
                                value={editDraft.templateId}
                                onValueChange={(value) => {
                                    if (value) {
                                        dispatchEditDraft({
                                            type: "changeTemplate",
                                            value,
                                        })
                                    }
                                }}
                            >
                                <SelectTrigger id="edit-template" aria-label={templateLabel} className="w-full">
                                    <SelectValue placeholder="Choose a template">
                                        {(value: string | null) => {
                                            if (!value) return "Choose a template"
                                            const selected = templates?.find(t => t.id === value)
                                            return selected?.name ?? "Choose a template"
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent className="min-w-[300px]">
                                    {templates?.map((templateOption) => (
                                        <SelectItem key={templateOption.id} value={templateOption.id}>
                                            {templateOption.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </section>

                    {(campaign.status === "draft" || campaign.status === "scheduled") && (
                        <section aria-labelledby="edit-campaign-schedule" className="flex flex-col gap-2 border-t pt-5">
                            <h3 id="edit-campaign-schedule" className="text-sm font-semibold">Schedule</h3>
                            <Label htmlFor="edit-scheduled-at">Send time (optional)</Label>
                            <DateTimePicker
                                triggerId="edit-scheduled-at"
                                value={scheduledAtValue}
                                onChange={(value) =>
                                    dispatchEditDraft({
                                        type: "changeScheduledAt",
                                        value: value ? toLocalDateTimeInput(value) : "",
                                    })
                                }
                                className="w-full sm:w-72"
                            />
                            <p className="text-xs text-muted-foreground">
                                {campaign.status === "scheduled"
                                    ? "Changing it reschedules the pending send."
                                    : "Leave empty to send manually."}
                            </p>
                        </section>
                    )}
                </DialogBody>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={onSave} disabled={updatePending}>
                        {updatePending ? (
                            <Loader2Icon className="size-4 animate-spin" />
                        ) : (
                            "Save changes"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

type CampaignConfirmationDialogState = {
    deleteOpen: boolean
    cancelOpen: boolean
    sendOpen: boolean
    retryOpen: boolean
}

function CampaignConfirmationDialogs({
    campaignName,
    channel,
    recipientCount,
    dialogs,
    onDeleteOpenChange,
    onCancelOpenChange,
    onSendOpenChange,
    onRetryOpenChange,
    onDelete,
    onCancel,
    onSendNow,
    onRetryFailed,
}: {
    campaignName: string
    channel: Campaign["channel"]
    /** Matching recipients from the preview; null while it loads or when it is unavailable. */
    recipientCount: number | null
    dialogs: CampaignConfirmationDialogState
    onDeleteOpenChange: (open: boolean) => void
    onCancelOpenChange: (open: boolean) => void
    onSendOpenChange: (open: boolean) => void
    onRetryOpenChange: (open: boolean) => void
    onDelete: () => Promise<void>
    onCancel: () => Promise<void>
    onSendNow: () => Promise<void>
    onRetryFailed: () => Promise<void>
}) {
    const messageNoun = channel === "messaging" ? "Messages" : "Emails"

    return (
        <>
            <ConfirmDialog
                open={dialogs.deleteOpen}
                onOpenChange={onDeleteOpenChange}
                title={`Delete ${campaignName}?`}
                description="This can't be undone."
                confirmLabel="Delete"
                errorFallback="Couldn't delete campaign. Only drafts can be deleted."
                onConfirm={onDelete}
            />

            <ConfirmDialog
                open={dialogs.cancelOpen}
                onOpenChange={onCancelOpenChange}
                title={`Stop ${campaignName}?`}
                description={`Scheduled and in-progress sends stop. ${messageNoun} already queued may still deliver.`}
                confirmLabel="Stop"
                errorFallback="Couldn't stop campaign. Try again."
                onConfirm={onCancel}
            />

            <ConfirmDialog
                open={dialogs.sendOpen}
                onOpenChange={onSendOpenChange}
                title={getCampaignSendConfirmTitle(recipientCount)}
                description={`${messageNoun} start sending right away.`}
                confirmVariant="default"
                confirmIcon={<SendIcon aria-hidden="true" />}
                confirmLabel="Send now"
                errorFallback="Couldn't send campaign. Try again."
                onConfirm={onSendNow}
            />

            <ConfirmDialog
                open={dialogs.retryOpen}
                onOpenChange={onRetryOpenChange}
                title="Retry failed recipients?"
                description="Sends again to the recipients that failed in the latest run."
                confirmVariant="default"
                confirmLabel="Retry failed"
                errorFallback="Couldn't retry failed recipients. Try again."
                onConfirm={onRetryFailed}
            />
        </>
    )
}

export default function CampaignDetailPage() {
    const params = useParams()
    const { push } = useRouter()
    const rawCampaignId = params.id
    const campaignId =
        typeof rawCampaignId === "string"
            ? rawCampaignId
            : Array.isArray(rawCampaignId)
              ? rawCampaignId[0] ?? ""
              : ""
    const searchParams = useSearchParams()

    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [showRetryDialog, setShowRetryDialog] = useState(false)
    const [showCancelDialog, setShowCancelDialog] = useState(false)
    const [showSendDialog, setShowSendDialog] = useState(false)
    const [recipientFilter, setRecipientFilter] = useState("all")
    const [showTemplatePreview, setShowTemplatePreview] = useState(true)
    const [showEditDialog, setShowEditDialog] = useState(false)
    const [handledAutoEditRequest, setHandledAutoEditRequest] = useState<string | null>(null)
    const [editDraft, dispatchEditDraft] = useReducer(
        campaignEditDraftReducer,
        initialCampaignEditDraft,
    )
    const { can } = usePermissionCheck()
    // Every campaign write and the recipient preview require the email template manage permission.
    const canManage = can("manage_email_templates")

    // API hooks
    const campaignQuery = useCampaign(campaignId)
    const { data: campaign, isLoading } = campaignQuery
    const { data: runs } = useCampaignRuns(campaignId)
    const latestRun = runs?.[0]
    const { data: preview, isLoading: previewLoading, refetch: refetchPreview } = useCampaignPreview(
        campaignId,
        { enabled: canManage },
    )
    const recipientQuery = {
        limit: 50,
        ...(recipientFilter === "all" ? {} : { status: recipientFilter }),
    }
    const { data: recipients } = useRunRecipients(
        campaignId,
        latestRun?.id,
        recipientQuery
    )
    const { data: emailTemplate } = useEmailTemplate(
        campaign?.channel === "email" ? campaign.email_template_id : null,
    )
    const { data: emailTemplates } = useEmailTemplates()
    const { data: messagingTemplates } = useQuery({
        queryKey: ["messaging-templates", "promotional", "published"],
        queryFn: () => listMessagingTemplates({ purpose: "promotional", status: "published" }),
        enabled: campaign?.channel === "messaging",
    })

    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()
    const cancelCampaign = useCancelCampaign()
    const sendCampaign = useSendCampaign()
    const updateCampaign = useUpdateCampaign()
    const retryFailed = useRetryFailedCampaignRun()
    const { data: intendedParentStatuses } = useIntendedParentStatuses()

    const campaignPipelineEntityType = getCampaignPipelineEntityType(
        campaign?.recipient_type ?? "case",
    )
    const editPipelineEntityType = getCampaignPipelineEntityType(editDraft.recipientType)
    const { data: campaignPipeline } = useQuery({
        queryKey: ["defaultPipeline", campaignPipelineEntityType],
        queryFn: () => getDefaultPipeline(campaignPipelineEntityType ?? "surrogate"),
        enabled: campaignPipelineEntityType !== null,
    })
    const { data: editPipeline } = useQuery({
        queryKey: ["defaultPipeline", editPipelineEntityType],
        queryFn: () => getDefaultPipeline(editPipelineEntityType ?? "surrogate"),
        enabled: editPipelineEntityType !== null,
    })
    const campaignPipelineStages = campaignPipeline?.stages || []
    const intendedParentStageOptions = getIntendedParentStageOptions(
        intendedParentStatuses?.statuses,
    ).map((stage) => ({
        id: stage.stage_slug,
        label: stage.label,
        color: stage.color,
        stage_key: stage.stage_key,
        stage_type: stage.stage_type,
    }))
    const editStageOptions = campaignStageOptions(
        editDraft.recipientType,
        editPipeline?.stages,
        intendedParentStatuses?.statuses,
    )
    const canEdit =
        canManage && (campaign?.status === "draft" || campaign?.status === "scheduled")
    const shouldAutoOpenEdit = searchParams.get("edit") === "1"
    const autoEditRequestKey =
        shouldAutoOpenEdit && canEdit && campaign
            ? `${campaign.id}:${searchParams.toString()}`
            : null

    if (!autoEditRequestKey && handledAutoEditRequest !== null) {
        setHandledAutoEditRequest(null)
    } else if (
        autoEditRequestKey &&
        campaign &&
        handledAutoEditRequest !== autoEditRequestKey
    ) {
        dispatchEditDraft({ type: "hydrate", draft: createCampaignEditDraft(campaign) })
        setShowEditDialog(true)
        setHandledAutoEditRequest(autoEditRequestKey)
    }

    const openEditDialog = () => {
        if (!campaign) return
        dispatchEditDraft({ type: "hydrate", draft: createCampaignEditDraft(campaign) })
        setShowEditDialog(true)
    }

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!campaign) {
        return (
            <QueryErrorState
                error={campaignQuery.error}
                onRetry={() => {
                    void campaignQuery.refetch()
                }}
                isRetrying={campaignQuery.isFetching}
                title="Couldn't load campaign"
                notFound={{
                    title: "Campaign not found",
                    backHref: "/automation/campaigns",
                    backLabel: "Back to Campaigns",
                }}
                headingLevel={1}
            />
        )
    }

    const messageTemplate = messagingTemplates?.find(
        (candidate) => candidate.id === campaign.message_template_version_id,
    )
    const template = campaign.channel === "messaging" ? messageTemplate : emailTemplate
    const templates = campaign.channel === "messaging" ? messagingTemplates : emailTemplates

    // Calculate percentages
    const totalRecipients = campaign.total_recipients || 0
    const sentPercent = totalRecipients > 0 ? Math.round((campaign.sent_count / totalRecipients) * 100) : 0
    const openedCount = campaign.opened_count || 0
    const clickedCount = campaign.clicked_count || 0
    const openPercent = campaign.sent_count > 0 ? Math.round((openedCount / campaign.sent_count) * 100) : 0
    const clickPercent = campaign.sent_count > 0 ? Math.round((clickedCount / campaign.sent_count) * 100) : 0
    const filterCriteria = campaign.filter_criteria || {}
    const rawStageFilters = campaign.recipient_type === "intended_parent"
        ? (Array.isArray(filterCriteria.stage_slugs) ? filterCriteria.stage_slugs : [])
        : (Array.isArray(filterCriteria.stage_ids) ? filterCriteria.stage_ids : [])
    const selectedStageFilters = toSelectedStringSet(rawStageFilters)
    const stageLabelsForFilter = campaign.recipient_type === "intended_parent"
        ? getSelectedLabels(intendedParentStageOptions, selectedStageFilters, (stage) => stage.id)
        : getSelectedLabels(campaignPipelineStages, selectedStageFilters, (stage) => stage.id)
    const stateFilters = Array.isArray(filterCriteria.states) ? filterCriteria.states : []
    const selectedStateFilters = toSelectedStringSet(stateFilters)
    const stateLabelsForFilter = getSelectedLabels(US_STATES, selectedStateFilters, (state) => state.value)
    const createdAfter = filterCriteria.created_after ? new Date(filterCriteria.created_after) : null
    const createdBefore = filterCriteria.created_before ? new Date(filterCriteria.created_before) : null
    const {
        handleDelete,
        handleDuplicate,
        handleEditSave,
        handleRetryFailed,
        handleCancel,
        handleSendNow,
    } = createCampaignDetailHandlers({
        campaign,
        campaignId,
        latestRun,
        editDraft,
        deleteCampaign,
        duplicateCampaign,
        cancelCampaign,
        sendCampaign,
        updateCampaign,
        retryFailed,
        push,
        setShowEditDialog,
    })

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <CampaignDetailHeader
                campaign={campaign}
                canManage={canManage}
                canEdit={canEdit}
                cancelPending={cancelCampaign.isPending}
                onEdit={openEditDialog}
                onSendNow={() => setShowSendDialog(true)}
                onCancel={() => setShowCancelDialog(true)}
                onDuplicate={handleDuplicate}
                onDelete={() => setShowDeleteDialog(true)}
            />

            <div className="flex-1 p-6 space-y-6">
                <CampaignStatsGrid
                    campaign={campaign}
                    totalRecipients={totalRecipients}
                    sentPercent={sentPercent}
                    openedCount={openedCount}
                    openPercent={openPercent}
                    clickedCount={clickedCount}
                    clickPercent={clickPercent}
                />

                <CampaignFilterSummaryCard
                    campaign={campaign}
                    filterCriteria={filterCriteria}
                    stageLabelsForFilter={stageLabelsForFilter}
                    stateLabelsForFilter={stateLabelsForFilter}
                    createdAfter={createdAfter}
                    createdBefore={createdBefore}
                />

                {canManage ? (
                    <RecipientPreviewCard
                        totalCount={preview?.total_count || 0}
                        sampleRecipients={
                            preview?.sample_recipients?.map((recipient) => {
                                const href = getCampaignRecipientHref(
                                    recipient.entity_type,
                                    recipient.entity_id,
                                )
                                return {
                                    email:
                                        campaign.channel === "messaging"
                                            ? recipient.phone_last4
                                                ? `••• ••• ${recipient.phone_last4}`
                                                : "Phone unavailable"
                                            : recipient.email ?? "Email unavailable",
                                    name: recipient.name,
                                    ...(href ? { href } : {}),
                                }
                            }) || []
                        }
                        isLoading={previewLoading}
                        onRefresh={() => refetchPreview()}
                        maxVisible={3}
                    />
                ) : (
                    <Card>
                        <CardContent>
                            <EmptyState
                                icon={ShieldAlertIcon}
                                title="Recipient preview requires campaign access"
                                className="py-6"
                            />
                        </CardContent>
                    </Card>
                )}

                <CampaignTemplatePreviewCard
                    template={template}
                    channel={campaign.channel}
                    open={showTemplatePreview}
                    onOpenChange={setShowTemplatePreview}
                />

                <CampaignRecipientsCard
                    channel={campaign.channel}
                    latestRun={latestRun}
                    recipients={recipients}
                    recipientFilter={recipientFilter}
                    retryPending={retryFailed.isPending}
                    onRecipientFilterChange={setRecipientFilter}
                    onRetryFailed={() => setShowRetryDialog(true)}
                />
            </div>

            <CampaignEditDialog
                open={showEditDialog}
                campaign={campaign}
                editDraft={editDraft}
                templates={templates}
                editStageOptions={editStageOptions}
                updatePending={updateCampaign.isPending}
                dispatchEditDraft={dispatchEditDraft}
                onOpenChange={(open) => {
                    if (open) {
                        openEditDialog()
                    } else {
                        setShowEditDialog(false)
                    }
                }}
                onSave={handleEditSave}
            />

            <CampaignConfirmationDialogs
                campaignName={campaign.name}
                channel={campaign.channel}
                recipientCount={canManage && preview ? preview.total_count : null}
                dialogs={{
                    deleteOpen: showDeleteDialog,
                    cancelOpen: showCancelDialog,
                    sendOpen: showSendDialog,
                    retryOpen: showRetryDialog,
                }}
                onDeleteOpenChange={setShowDeleteDialog}
                onCancelOpenChange={setShowCancelDialog}
                onSendOpenChange={setShowSendDialog}
                onRetryOpenChange={setShowRetryDialog}
                onDelete={handleDelete}
                onCancel={handleCancel}
                onSendNow={handleSendNow}
                onRetryFailed={handleRetryFailed}
            />
        </div>
    )
}
