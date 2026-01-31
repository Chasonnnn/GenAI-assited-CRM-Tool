"use client"

import { useEffect, useState } from "react"
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
import { toast } from "sonner"
import {
    useCampaign,
    useCampaignRuns,
    useCampaignPreview,
    useRunRecipients,
    useDeleteCampaign,
    useDuplicateCampaign,
    useCancelCampaign,
    useUpdateCampaign,
    useRetryFailedCampaignRun,
} from "@/lib/hooks/use-campaigns"
import { NotFoundState } from "@/components/not-found-state"
import { useEmailTemplate, useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useQuery } from "@tanstack/react-query"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { RecipientPreviewCard } from "@/components/recipient-preview-card"
import { US_STATES } from "@/lib/constants/us-states"

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

const INTENDED_PARENT_STAGE_OPTIONS = [
    { id: "new", label: "New", color: "#3B82F6" },
    { id: "ready_to_match", label: "Ready to Match", color: "#F59E0B" },
    { id: "matched", label: "Matched", color: "#10B981" },
    { id: "delivered", label: "Delivered", color: "#14B8A6" },
] as const

export default function CampaignDetailPage() {
    const params = useParams()
    const router = useRouter()
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
    const [recipientFilter, setRecipientFilter] = useState("all")
    const [showTemplatePreview, setShowTemplatePreview] = useState(true)
    const [showEditDialog, setShowEditDialog] = useState(false)
    const [editName, setEditName] = useState("")
    const [editDescription, setEditDescription] = useState("")
    const [editTemplateId, setEditTemplateId] = useState("")
    const [editRecipientType, setEditRecipientType] = useState<"case" | "intended_parent">("case")
    const [editStages, setEditStages] = useState<string[]>([])
    const [editStates, setEditStates] = useState<string[]>([])
    const [editScheduledAt, setEditScheduledAt] = useState("")
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
    const updateCampaign = useUpdateCampaign()
    const retryFailed = useRetryFailedCampaignRun()

    const { data: pipeline } = useQuery({
        queryKey: ["defaultPipeline"],
        queryFn: getDefaultPipeline,
    })
    const pipelineStages = pipeline?.stages || []
    const editStageOptions =
        editRecipientType === "intended_parent"
            ? INTENDED_PARENT_STAGE_OPTIONS
            : pipelineStages.filter(stage => stage.is_active)
    const canEdit = campaign?.status === "draft" || campaign?.status === "scheduled"
    const shouldAutoOpenEdit = searchParams.get("edit") === "1"

    useEffect(() => {
        if (shouldAutoOpenEdit && canEdit) {
            setShowEditDialog(true)
        }
    }, [shouldAutoOpenEdit, canEdit])

    useEffect(() => {
        if (!campaign || !showEditDialog) return
        const criteria = campaign.filter_criteria || {}
        const stageIds = Array.isArray(criteria.stage_ids) ? criteria.stage_ids : []
        const stageSlugs = Array.isArray(criteria.stage_slugs) ? criteria.stage_slugs : []
        const states = Array.isArray(criteria.states) ? criteria.states : []
        const recipientType =
            campaign.recipient_type === "intended_parent" ? "intended_parent" : "case"

        setEditName(campaign.name)
        setEditDescription(campaign.description ?? "")
        setEditTemplateId(campaign.email_template_id)
        setEditRecipientType(recipientType)
        setEditStages(recipientType === "intended_parent" ? stageSlugs : stageIds)
        setEditStates(states)
        setEditScheduledAt(
            campaign.scheduled_at ? toLocalDateTimeInput(new Date(campaign.scheduled_at)) : ""
        )
    }, [campaign, showEditDialog])

    const buildEditFilterCriteria = () => {
        const stageFilters =
            editStages.length > 0
                ? editRecipientType === "intended_parent"
                    ? { stage_slugs: editStages }
                    : { stage_ids: editStages }
                : {}

        return {
            ...stageFilters,
            ...(editStates.length > 0 ? { states: editStates } : {}),
        }
    }

    const handleDelete = async () => {
        try {
            await deleteCampaign.mutateAsync(campaignId)
            toast.success("Campaign deleted")
            router.push("/automation/campaigns")
        } catch {
            toast.error("Failed to delete campaign. Only drafts can be deleted.")
        }
        setShowDeleteDialog(false)
    }

    const handleDuplicate = async () => {
        try {
            const newCampaign = await duplicateCampaign.mutateAsync(campaignId)
            toast.success("Campaign duplicated")
            router.push(`/automation/campaigns/${newCampaign.id}`)
        } catch {
            toast.error("Failed to duplicate campaign")
        }
    }

    const handleEditSave = async () => {
        if (!campaign) return
        if (!editName || !editTemplateId) {
            toast.error("Please fill in required fields")
            return
        }

        let scheduledAt: string | undefined
        if (editScheduledAt) {
            const parsedDate = new Date(editScheduledAt)
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
                    name: editName,
                    description: editDescription,
                    email_template_id: editTemplateId,
                    recipient_type: editRecipientType,
                    filter_criteria: buildEditFilterCriteria(),
                    ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
                },
            })
            toast.success("Campaign updated")
            setShowEditDialog(false)
        } catch {
            toast.error("Failed to update campaign")
        }
    }

    const handleRetryFailed = async () => {
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
    }

    const handleCancel = async () => {
        try {
            await cancelCampaign.mutateAsync(campaignId)
            toast.success("Campaign stopped")
        } catch {
            toast.error("Failed to stop campaign")
        }
        setShowCancelDialog(false)
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
            <NotFoundState
                title="Campaign not found"
                backUrl="/automation/campaigns"
            />
        )
    }

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
    const stageLabelsForFilter = campaign.recipient_type === "intended_parent"
        ? INTENDED_PARENT_STAGE_OPTIONS.filter(stage => rawStageFilters.includes(stage.id)).map(stage => stage.label)
        : pipelineStages.filter(stage => rawStageFilters.includes(stage.id)).map(stage => stage.label)
    const stateFilters = Array.isArray(filterCriteria.states) ? filterCriteria.states : []
    const stateLabelsForFilter = US_STATES.filter(state => stateFilters.includes(state.value)).map(state => state.label)
    const createdAfter = filterCriteria.created_after ? new Date(filterCriteria.created_after) : null
    const createdBefore = filterCriteria.created_before ? new Date(filterCriteria.created_before) : null

    return (
        <div className="flex min-h-screen flex-col bg-background">
            {/* Header */}
            <div className="border-b bg-card">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon-sm" render={<Link href="/automation/campaigns" />}>
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
                            onClick={() => setShowEditDialog(true)}
                            disabled={!canEdit}
                        >
                            <PencilIcon className="size-4" />
                            Edit
                        </Button>
                        {(campaign.status === "scheduled" || campaign.status === "sending") && (
                            <Button
                                variant="destructive"
                                onClick={() => setShowCancelDialog(true)}
                                disabled={cancelCampaign.isPending}
                            >
                                Stop
                            </Button>
                        )}
                        <Button variant="outline" onClick={handleDuplicate}>
                            <CopyIcon className="size-4" />
                            Duplicate
                        </Button>
                        {campaign.status === "draft" && (
                            <Button variant="destructive" onClick={() => setShowDeleteDialog(true)}>
                                <TrashIcon className="size-4" />
                                Delete
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6">
                {/* Stats Cards */}
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

                <Collapsible open={showTemplatePreview} onOpenChange={setShowTemplatePreview}>
                    <Card>
                        <CollapsibleTrigger
                            className="w-full"
                            onClick={() => setShowTemplatePreview(!showTemplatePreview)}
                        >
                            <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <MailIcon className="size-4 text-muted-foreground" />
                                        <CardTitle className="text-base">Email Template</CardTitle>
                                    </div>
                                    {showTemplatePreview ? (
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

                {/* Recipients Table */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <CardTitle>Recipients</CardTitle>
                                <CardDescription>
                                    {latestRun
                                        ? `Last run: ${format(new Date(latestRun.started_at), "MMM d, yyyy 'at' h:mm a")}`
                                        : "No runs yet"}
                                </CardDescription>
                            </div>
                            {latestRun && latestRun.failed_count > 0 && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setShowRetryDialog(true)}
                                    disabled={retryFailed.isPending}
                                >
                                    {retryFailed.isPending ? (
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
                                onValueChange={setRecipientFilter}
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
                                                    ? format(new Date(recipient.sent_at), "MMM d, yyyy h:mm a")
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
            </div>

            {/* Delete Confirmation */}
            <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
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
                                value={editName}
                                onChange={(event) => setEditName(event.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="edit-description">Description</Label>
                            <Textarea
                                id="edit-description"
                                value={editDescription}
                                onChange={(event) => setEditDescription(event.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Template *</Label>
                            <Select value={editTemplateId} onValueChange={(value) => value && setEditTemplateId(value)}>
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
                                value={editRecipientType}
                                onValueChange={(value) => {
                                    if (value === "case" || value === "intended_parent") {
                                        setEditRecipientType(value)
                                        setEditStages([])
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
                            <Label>{editRecipientType === "intended_parent" ? "Filter by Status" : "Filter by Stage"}</Label>
                            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                                {editStageOptions.map((stage) => (
                                    <div key={stage.id} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`edit-stage-${stage.id}`}
                                            checked={editStages.includes(stage.id)}
                                            onCheckedChange={(checked) => {
                                                if (checked) {
                                                    setEditStages([...editStages, stage.id])
                                                } else {
                                                    setEditStages(editStages.filter((s) => s !== stage.id))
                                                }
                                            }}
                                        />
                                        <Label htmlFor={`edit-stage-${stage.id}`} className="text-sm">
                                            <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: stage.color }} />
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
                                    <div key={state.value} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`edit-state-${state.value}`}
                                            checked={editStates.includes(state.value)}
                                            onCheckedChange={(checked) => {
                                                if (checked) {
                                                    setEditStates([...editStates, state.value])
                                                } else {
                                                    setEditStates(editStates.filter((s) => s !== state.value))
                                                }
                                            }}
                                        />
                                        <Label htmlFor={`edit-state-${state.value}`} className="text-sm cursor-pointer">
                                            {state.label}
                                        </Label>
                                    </div>
                                ))}
                            </div>
                            {editStates.length > 0 && (
                                <p className="text-xs text-muted-foreground">
                                    {editStates.length} state{editStates.length !== 1 ? "s" : ""} selected
                                </p>
                            )}
                        </div>
                        {(campaign?.status === "draft" || campaign?.status === "scheduled") && (
                            <div className="space-y-2">
                                <Label htmlFor="edit-scheduled-at">Scheduled send time (optional)</Label>
                                <Input
                                    id="edit-scheduled-at"
                                    type="datetime-local"
                                    min={minScheduleDate}
                                    value={editScheduledAt}
                                    onChange={(event) => setEditScheduledAt(event.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    {campaign?.status === "scheduled"
                                        ? "Updating this will reschedule the pending send."
                                        : "Leave blank to send manually later."}
                                </p>
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleEditSave} disabled={updateCampaign.isPending}>
                            {updateCampaign.isPending ? (
                                <Loader2Icon className="size-4 animate-spin" />
                            ) : (
                                "Save changes"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Campaign</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to delete this campaign? This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Stop Campaign</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will stop any scheduled or in-progress sends. Emails already queued may still deliver.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleCancel} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                            Stop
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={showRetryDialog} onOpenChange={setShowRetryDialog}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Retry failed recipients</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will retry sending to recipients that previously failed in the latest run.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleRetryFailed}>
                            Retry failed
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}
