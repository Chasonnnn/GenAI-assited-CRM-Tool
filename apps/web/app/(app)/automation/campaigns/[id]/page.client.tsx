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
import { Checkbox } from "@/components/ui/checkbox"
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
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
    Dialog,
    DialogContent,
    DialogDescription,
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
import type { Campaign, CampaignRecipient, CampaignRun, FilterCriteria } from "@/lib/api/campaigns"
import type { EmailTemplate, EmailTemplateListItem } from "@/lib/api/email-templates"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { useQuery } from "@tanstack/react-query"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { RecipientPreviewCard } from "@/components/recipient-preview-card"
import { US_STATES } from "@/lib/constants/us-states"
import { getIntendedParentStageOptions } from "@/lib/intended-parent-stage-utils"

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

type CampaignEditRecipientType = "case" | "intended_parent"

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
    | { type: "toggleStage"; stageId: string; checked: boolean }
    | { type: "toggleState"; stateCode: string; checked: boolean }
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
    const recipientType =
        campaign.recipient_type === "intended_parent" ? "intended_parent" : "case"

    return {
        name: campaign.name,
        description: campaign.description ?? "",
        templateId: campaign.email_template_id,
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
        case "toggleStage":
            return {
                ...state,
                stages: action.checked
                    ? [...state.stages, action.stageId]
                    : state.stages.filter((stageId) => stageId !== action.stageId),
            }
        case "toggleState":
            return {
                ...state,
                states: action.checked
                    ? [...state.states, action.stateCode]
                    : state.states.filter((stateValue) => stateValue !== action.stateCode),
            }
        case "toggleIncludeUnsubscribed":
            return { ...state, includeUnsubscribed: action.value }
        case "changeScheduledAt":
            return { ...state, scheduledAt: action.value }
        default:
            return state
    }
}

type CampaignStageOption = {
    id: string
    label: string
    color?: string | null
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
    setShowDeleteDialog,
    setShowRetryDialog,
    setShowCancelDialog,
    setShowSendDialog,
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
    setShowDeleteDialog: BooleanStateSetter
    setShowRetryDialog: BooleanStateSetter
    setShowCancelDialog: BooleanStateSetter
    setShowSendDialog: BooleanStateSetter
    setShowEditDialog: BooleanStateSetter
}) {
    return {
        handleDelete: async () => {
            try {
                await deleteCampaign.mutateAsync(campaignId)
                toast.success("Campaign deleted")
                push("/automation/campaigns")
            } catch {
                toast.error("Failed to delete campaign. Only drafts can be deleted.")
            }
            setShowDeleteDialog(false)
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
                        email_template_id: editDraft.templateId,
                        recipient_type: editDraft.recipientType,
                        filter_criteria: buildCampaignEditFilterCriteria(editDraft),
                        include_unsubscribed: editDraft.includeUnsubscribed,
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
            try {
                const result = await retryFailed.mutateAsync({
                    campaignId,
                    runId: latestRun.id,
                })
                toast.success(result.message)
            } catch {
                toast.error("Failed to retry failed recipients")
            }
            setShowRetryDialog(false)
        },
        handleCancel: async () => {
            try {
                await cancelCampaign.mutateAsync(campaignId)
                toast.success("Campaign stopped")
            } catch {
                toast.error("Failed to stop campaign")
            }
            setShowCancelDialog(false)
        },
        handleSendNow: async () => {
            try {
                await sendCampaign.mutateAsync({ id: campaignId, sendNow: true })
                toast.success("Campaign queued for sending")
            } catch {
                toast.error("Failed to send campaign")
            }
            setShowSendDialog(false)
        },
    }
}

function CampaignDetailHeader({
    campaign,
    canEdit,
    cancelPending,
    onEdit,
    onSendNow,
    onCancel,
    onDuplicate,
    onDelete,
}: {
    campaign: Campaign
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
                    <Button variant="outline" onClick={onDuplicate}>
                        <CopyIcon className="size-4" />
                        Duplicate
                    </Button>
                    {campaign.status === "draft" && (
                        <Button variant="destructive" onClick={onDelete}>
                            <TrashIcon className="size-4" />
                            Delete
                        </Button>
                    )}
                </div>
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
                <CardDescription>Filters applied when recipients are selected for sending.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">Recipient Type</p>
                        <p className="font-medium">
                            {campaign.recipient_type === "case" ? "Surrogates" : "Intended Parents"}
                        </p>
                    </div>
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">
                            {campaign.recipient_type === "intended_parent" ? "Statuses" : "Stages"}
                        </p>
                        {stageLabelsForFilter.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                                {stageLabelsForFilter.map((label) => (
                                    <Badge key={label} variant="secondary" className="text-xs">
                                        {label}
                                    </Badge>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground">All</p>
                        )}
                    </div>
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">States</p>
                        {stateLabelsForFilter.length > 0 ? (
                            <div className="flex flex-wrap gap-2">
                                {stateLabelsForFilter.map((label) => (
                                    <Badge key={label} variant="secondary" className="text-xs">
                                        {label}
                                    </Badge>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground">All</p>
                        )}
                    </div>
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">Created Range</p>
                        {(createdAfter || createdBefore) ? (
                            <p className="text-sm text-muted-foreground">
                                {createdAfter ? format(createdAfter, "MMM d, yyyy") : "Anytime"}{" "}
                                →{" "}
                                {createdBefore ? format(createdBefore, "MMM d, yyyy") : "Now"}
                            </p>
                        ) : (
                            <p className="text-sm text-muted-foreground">Anytime</p>
                        )}
                    </div>
                    <div className="space-y-1">
                        <p className="text-xs text-muted-foreground">Unsubscribed Recipients</p>
                        <p className="text-sm text-muted-foreground">
                            {campaign.include_unsubscribed ? "Included" : "Excluded"}
                        </p>
                    </div>
                </div>
                {(filterCriteria.source || filterCriteria.is_priority) && (
                    <div className="flex flex-wrap gap-2">
                        {filterCriteria.source && (
                            <Badge variant="outline" className="text-xs">
                                Source: {filterCriteria.source}
                            </Badge>
                        )}
                        {filterCriteria.is_priority && (
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
    open,
    onOpenChange,
}: {
    template: EmailTemplate | null | undefined
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
                                <MailIcon className="size-4 text-muted-foreground" />
                                <CardTitle className="text-base">Email Template</CardTitle>
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
                                <div className="bg-muted/50 rounded-lg p-4">
                                    <p className="text-sm text-muted-foreground mb-1">Subject</p>
                                    <p className="font-medium">{template.subject}</p>
                                </div>
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
    latestRun,
    recipients,
    recipientFilter,
    retryPending,
    onRecipientFilterChange,
    onRetryFailed,
}: {
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
                        <CardDescription>
                            {latestRun
                                ? `Last run: ${format(parseDateInput(latestRun.started_at), "MMM d, yyyy 'at' h:mm a")}`
                                : "No runs yet"}
                        </CardDescription>
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
                                <TableHead>Email</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Sent At</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {recipients.map((recipient) => (
                                <TableRow key={recipient.id}>
                                    <TableCell className="font-medium">
                                        {recipient.recipient_name || "-"}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground">
                                        {recipient.recipient_email}
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
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                        <UsersIcon className="size-8 text-muted-foreground mb-2" />
                        <p className="text-muted-foreground">
                            {latestRun ? "No recipients in this run" : "Campaign hasn't been sent yet"}
                        </p>
                    </div>
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
    editStageIdSet,
    editStateCodeSet,
    minScheduleDate,
    updatePending,
    dispatchEditDraft,
    onOpenChange,
    onSave,
}: {
    open: boolean
    campaign: Campaign
    editDraft: CampaignEditDraftState
    templates: EmailTemplateListItem[] | undefined
    editStageOptions: CampaignStageOption[]
    editStageIdSet: ReadonlySet<string>
    editStateCodeSet: ReadonlySet<string>
    minScheduleDate: string
    updatePending: boolean
    dispatchEditDraft: Dispatch<CampaignEditDraftAction>
    onOpenChange: (open: boolean) => void
    onSave: () => void
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Edit Campaign</DialogTitle>
                    <DialogDescription>Update details and recipient filters.</DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="edit-name">Campaign Name *</Label>
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
                    <div className="space-y-2">
                        <Label htmlFor="edit-description">Description</Label>
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
                    <div className="space-y-2">
                        <Label>Template *</Label>
                        <Select
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
                            <SelectTrigger className="w-full">
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
                    <div className="space-y-2">
                        <Label>Recipient Type</Label>
                        <Select
                            value={editDraft.recipientType}
                            onValueChange={(value) => {
                                if (value === "case" || value === "intended_parent") {
                                    dispatchEditDraft({
                                        type: "changeRecipientType",
                                        value,
                                    })
                                }
                            }}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select type">
                                    {(value: string | null) => {
                                        if (value === "case") return "Surrogates"
                                        if (value === "intended_parent") return "Intended Parents"
                                        return "Select type"
                                    }}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="case">Surrogates</SelectItem>
                                <SelectItem value="intended_parent">Intended Parents</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-2">
                        <Label>{editDraft.recipientType === "intended_parent" ? "Filter by Status" : "Filter by Stage"}</Label>
                        <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                            {editStageOptions.map((stage) => (
                                <div key={stage.id} className="flex items-center gap-x-2">
                                    <Checkbox
                                        id={`edit-stage-${stage.id}`}
                                        checked={editStageIdSet.has(stage.id)}
                                        onCheckedChange={(checked) => {
                                            dispatchEditDraft({
                                                type: "toggleStage",
                                                stageId: stage.id,
                                                checked: checked === true,
                                            })
                                        }}
                                    />
                                    <Label htmlFor={`edit-stage-${stage.id}`} className="text-sm">
                                        <span
                                            className="inline-block size-2 rounded-full mr-1.5"
                                            style={{ backgroundColor: stage.color ?? undefined }}
                                        />
                                        {stage.label}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label>Filter by State (optional)</Label>
                        <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto border rounded-md p-3">
                            {US_STATES.map((state) => (
                                <div key={state.value} className="flex items-center gap-x-2">
                                    <Checkbox
                                        id={`edit-state-${state.value}`}
                                        checked={editStateCodeSet.has(state.value)}
                                        onCheckedChange={(checked) => {
                                            dispatchEditDraft({
                                                type: "toggleState",
                                                stateCode: state.value,
                                                checked: checked === true,
                                            })
                                        }}
                                    />
                                    <Label htmlFor={`edit-state-${state.value}`} className="text-sm cursor-pointer">
                                        {state.label}
                                    </Label>
                                </div>
                            ))}
                        </div>
                        {editDraft.states.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                                {editDraft.states.length} state{editDraft.states.length !== 1 ? "s" : ""} selected
                            </p>
                        )}
                    </div>
                    <div className="rounded-lg border bg-card p-4">
                        <div className="flex items-start gap-3">
                            <Checkbox
                                id="edit-include-unsubscribed"
                                checked={editDraft.includeUnsubscribed}
                                onCheckedChange={(checked) =>
                                    dispatchEditDraft({
                                        type: "toggleIncludeUnsubscribed",
                                        value: checked === true,
                                    })
                                }
                            />
                            <div className="space-y-1">
                                <Label htmlFor="edit-include-unsubscribed" className="cursor-pointer">
                                    Include unsubscribed recipients
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                    When enabled, recipients who opted out of marketing emails may be included.
                                    Hard bounces and complaints are always suppressed.
                                </p>
                            </div>
                        </div>
                    </div>
                    {(campaign.status === "draft" || campaign.status === "scheduled") && (
                        <div className="space-y-2">
                            <Label htmlFor="edit-scheduled-at">Scheduled send time (optional)</Label>
                            <Input
                                id="edit-scheduled-at"
                                type="datetime-local"
                                min={minScheduleDate}
                                value={editDraft.scheduledAt}
                                onChange={(event) =>
                                    dispatchEditDraft({
                                        type: "changeScheduledAt",
                                        value: event.target.value,
                                    })
                                }
                            />
                            <p className="text-xs text-muted-foreground">
                                {campaign.status === "scheduled"
                                    ? "Updating this will reschedule the pending send."
                                    : "Leave blank to send manually later."}
                            </p>
                        </div>
                    )}
                </div>

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
    dialogs: CampaignConfirmationDialogState
    onDeleteOpenChange: (open: boolean) => void
    onCancelOpenChange: (open: boolean) => void
    onSendOpenChange: (open: boolean) => void
    onRetryOpenChange: (open: boolean) => void
    onDelete: () => void
    onCancel: () => void
    onSendNow: () => void
    onRetryFailed: () => void
}) {
    return (
        <>
            <AlertDialog open={dialogs.deleteOpen} onOpenChange={onDeleteOpenChange}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Campaign</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to delete this campaign? This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={onDelete}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={dialogs.cancelOpen} onOpenChange={onCancelOpenChange}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Stop Campaign</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will stop any scheduled or in-progress sends. Emails already queued may still deliver.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={onCancel}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Stop
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={dialogs.sendOpen} onOpenChange={onSendOpenChange}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Send Campaign Now</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will immediately start sending this campaign. You can stop it once it begins, but some emails may still deliver.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={onSendNow}>
                            Send now
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={dialogs.retryOpen} onOpenChange={onRetryOpenChange}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Retry failed recipients</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will retry sending to recipients that previously failed in the latest run.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={onRetryFailed}>
                            Retry failed
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
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
    const minScheduleDate = toLocalDateTimeInput(new Date())

    // API hooks
    const { data: campaign, isLoading } = useCampaign(campaignId)
    const { data: runs } = useCampaignRuns(campaignId)
    const latestRun = runs?.[0]
    const { data: preview, isLoading: previewLoading, refetch: refetchPreview } = useCampaignPreview(campaignId)
    const recipientQuery = {
        limit: 50,
        ...(recipientFilter === "all" ? {} : { status: recipientFilter }),
    }
    const { data: recipients } = useRunRecipients(
        campaignId,
        latestRun?.id,
        recipientQuery
    )
    const { data: template } = useEmailTemplate(campaign?.email_template_id ?? null)
    const { data: templates } = useEmailTemplates()

    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()
    const cancelCampaign = useCancelCampaign()
    const sendCampaign = useSendCampaign()
    const updateCampaign = useUpdateCampaign()
    const retryFailed = useRetryFailedCampaignRun()
    const { data: intendedParentStatuses } = useIntendedParentStatuses()

    const { data: pipeline } = useQuery({
        queryKey: ["defaultPipeline", "surrogate"],
        queryFn: () => getDefaultPipeline("surrogate"),
    })
    const pipelineStages = pipeline?.stages || []
    const intendedParentStageOptions = getIntendedParentStageOptions(
        intendedParentStatuses?.statuses,
    ).map((stage) => ({
        id: stage.stage_slug,
        label: stage.label,
        color: stage.color,
        stage_key: stage.stage_key,
        stage_type: stage.stage_type,
    }))
    const editStageOptions =
        editDraft.recipientType === "intended_parent"
            ? intendedParentStageOptions
            : pipelineStages.filter(stage => stage.is_active)
    const canEdit = campaign?.status === "draft" || campaign?.status === "scheduled"
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

    if (!campaign) return null

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
        : getSelectedLabels(pipelineStages, selectedStageFilters, (stage) => stage.id)
    const stateFilters = Array.isArray(filterCriteria.states) ? filterCriteria.states : []
    const selectedStateFilters = toSelectedStringSet(stateFilters)
    const stateLabelsForFilter = getSelectedLabels(US_STATES, selectedStateFilters, (state) => state.value)
    const createdAfter = filterCriteria.created_after ? new Date(filterCriteria.created_after) : null
    const createdBefore = filterCriteria.created_before ? new Date(filterCriteria.created_before) : null
    const editStageIdSet = new Set(editDraft.stages)
    const editStateCodeSet = new Set(editDraft.states)
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
        setShowDeleteDialog,
        setShowRetryDialog,
        setShowCancelDialog,
        setShowSendDialog,
        setShowEditDialog,
    })

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <CampaignDetailHeader
                campaign={campaign}
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

                <RecipientPreviewCard
                    totalCount={preview?.total_count || 0}
                    sampleRecipients={
                        preview?.sample_recipients?.map((recipient) => ({
                            email: recipient.email,
                            name: recipient.name,
                        })) || []
                    }
                    isLoading={previewLoading}
                    onRefresh={() => refetchPreview()}
                    maxVisible={3}
                />

                <CampaignTemplatePreviewCard
                    template={template}
                    open={showTemplatePreview}
                    onOpenChange={setShowTemplatePreview}
                />

                <CampaignRecipientsCard
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
                editStageIdSet={editStageIdSet}
                editStateCodeSet={editStateCodeSet}
                minScheduleDate={minScheduleDate}
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
