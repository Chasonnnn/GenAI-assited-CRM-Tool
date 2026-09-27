"use client"

import { useState, type Dispatch, type SetStateAction } from "react"
import Link from "@/components/app-link"
import { useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { DateTimePicker } from "@/components/ui/date-time-picker"
import { ValidatedField } from "@/components/ui/field"
import { Skeleton } from "@/components/ui/skeleton"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { EmptyState } from "@/components/empty-state"
import { PageHeader } from "@/components/page-header"
import { useCurrentMinuteTimestamp } from "@/components/ui/use-current-minute-timestamp"
import { WizardStepper } from "@/components/automation/wizard-stepper"
import {
    CampaignAudienceFields,
    campaignStageOptions,
    summarizeCampaignAudience,
    type CampaignChannel,
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
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    PlusIcon,
    MoreVerticalIcon,
    MailIcon,
    UsersIcon,
    CheckCircle2Icon,
    XCircleIcon,
    SendIcon,
    CopyIcon,
    TrashIcon,
    Loader2Icon,
    CalendarIcon,
    EyeIcon,
    PencilIcon,
    MessageSquareTextIcon,
} from "lucide-react"
import { format } from "date-fns"
import { toast } from "@/components/ui/toast"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"
import {
    useCampaigns,
    useCampaignPreview,
    useCreateCampaign,
    useDeleteCampaign,
    useDuplicateCampaign,
    useCancelCampaign,
    useSendCampaign,
    usePreviewFilters,
} from "@/lib/hooks/use-campaigns"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { useQuery } from "@tanstack/react-query"
import type {
    CampaignListItem,
    CampaignRecipientType,
    FilterCriteria,
} from "@/lib/api/campaigns"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import { listMessagingTemplates } from "@/lib/api/twilio"
import {
    getCampaignPipelineEntityType,
    getCampaignRecipientHref,
    getCampaignRecipientLabel,
    getCampaignSendConfirmTitle,
    isDonorCampaignRecipientType,
} from "@/lib/campaign-recipient"
import type { StageOption } from "@/lib/stage-options"

const statusStyles: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }> = {
    draft: { variant: "secondary" },
    scheduled: { variant: "outline", className: "border-blue-500 text-blue-600" },
    sending: { variant: "outline", className: "border-yellow-500 text-yellow-600 animate-pulse" },
    completed: { variant: "default", className: "bg-green-500" },
    sent: { variant: "default", className: "bg-green-500" },
    failed: { variant: "destructive" },
    cancelled: { variant: "secondary" },
}

const statusLabels: Record<string, string> = {
    draft: "Draft",
    scheduled: "Scheduled",
    sending: "Sending",
    completed: "Sent",
    sent: "Sent",
    failed: "Failed",
    cancelled: "Cancelled",
}

const CAMPAIGN_WIZARD_STEPS = ["Setup", "Audience", "Content", "Review & send"] as const
const SETUP_STEP = 1
const AUDIENCE_STEP = 2
const CONTENT_STEP = 3
const REVIEW_STEP = CAMPAIGN_WIZARD_STEPS.length

type RecipientType = CampaignRecipientType
/** Final action of the wizard. Saving a draft is the default; sends and schedules are explicit. */
type SendMode = "draft" | "now" | "later"
type StateSetter<T> = Dispatch<SetStateAction<T>>

type CampaignWizardState = {
    wizardStep: number
    campaignName: string
    campaignDescription: string
    channel: CampaignChannel
    selectedTemplateId: string
    recipientType: RecipientType
    selectedStages: string[]
    selectedStates: string[]
    includeUnsubscribed: boolean
    sendMode: SendMode
    scheduledAt: Date | undefined
    scheduleError: string | undefined
}

type CampaignTemplateOption = Pick<EmailTemplateListItem, "id" | "name"> & {
    subject?: string
    body?: string
}

type CampaignWizardData = {
    templates: CampaignTemplateOption[] | undefined
    templatesLoading: boolean
    selectedTemplate: CampaignTemplateOption | undefined
    stageOptions: StageOption[]
    /** Null until the recipient preview has loaded. */
    previewTotalCount: number | null
    previewSampleRecipients: { email: string; name: string | null; href?: string }[]
    isPreviewLoading: boolean
}

type CampaignWizardActions = {
    resetWizard: () => void
    setWizardStep: StateSetter<number>
    setCampaignName: StateSetter<string>
    setCampaignDescription: StateSetter<string>
    setChannel: (next: CampaignChannel) => void
    setSelectedTemplateId: StateSetter<string>
    setRecipientType: (next: RecipientType) => void
    setSelectedStages: (next: string[]) => void
    setSelectedStates: (next: string[]) => void
    setIncludeUnsubscribed: (next: boolean) => void
    setSendMode: (next: SendMode) => void
    setScheduledAt: (next: Date | undefined) => void
    previewRecipients: () => void
    submitCampaign: () => Promise<void>
}

type CampaignWizardPending = {
    isSubmitting: boolean
}

type CampaignDialogState = {
    deleteDialogId: string | null
    cancelDialogId: string | null
    sendNowDialogId: string | null
    getCampaignName: (id: string | null) => string | undefined
    sendNowRecipientCount: number | null
}

type CampaignDialogActions = {
    setDeleteDialogId: StateSetter<string | null>
    setCancelDialogId: StateSetter<string | null>
    setSendNowDialogId: StateSetter<string | null>
    handleDeleteCampaign: () => Promise<void>
    handleCancelCampaign: () => Promise<void>
    handleSendNowCampaign: () => Promise<void>
}

function getScheduleError(sendMode: SendMode, scheduledAt: Date | undefined, now: number): string | undefined {
    if (sendMode !== "later" || !scheduledAt) return undefined
    return scheduledAt.getTime() <= now ? "Choose a time in the future." : undefined
}

function getTimeZoneAbbreviation(date: Date): string | undefined {
    return new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
        .formatToParts(date)
        .find((part) => part.type === "timeZoneName")?.value
}

function buildCampaignFilterCriteria(
    recipientType: RecipientType,
    selectedStages: readonly string[],
    selectedStates: readonly string[],
): FilterCriteria {
    const stageFilters =
        selectedStages.length > 0
            ? recipientType === "intended_parent"
                ? { stage_slugs: [...selectedStages] }
                : { stage_ids: [...selectedStages] }
            : {}

    return {
        ...stageFilters,
        ...(selectedStates.length > 0 ? { states: [...selectedStates] } : {}),
    }
}

type PreviewSampleRecipient = {
    entity_type: CampaignRecipientType
    entity_id: string
    email: string | null
    phone_last4: string | null
    name: string | null
}

function toPreviewSampleRecipients(recipients: readonly PreviewSampleRecipient[] | undefined) {
    return (recipients ?? []).map((recipient) => {
        const href = getCampaignRecipientHref(recipient.entity_type, recipient.entity_id)
        return {
            email:
                recipient.email ??
                (recipient.phone_last4 ? `••• ••• ${recipient.phone_last4}` : "Contact unavailable"),
            name: recipient.name,
            ...(href ? { href } : {}),
        }
    })
}

const isSendMode = (value: unknown): value is SendMode =>
    value === "draft" || value === "now" || value === "later"

function useCampaignsPageController() {
    const { push } = useRouter()
    const { can } = usePermissionCheck()
    // Every campaign write and preview endpoint requires the email template manage permission.
    const canManageCampaigns = can("manage_email_templates")
    const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
    const [showCreateWizard, setShowCreateWizard] = useState(false)
    const [wizardStep, setWizardStep] = useState(SETUP_STEP)
    const [page, setPage] = useState(1)
    const perPage = 20
    const [campaignName, setCampaignName] = useState("")
    const [campaignDescription, setCampaignDescription] = useState("")
    const [channel, setChannel] = useState<CampaignChannel>("email")
    const [selectedTemplateId, setSelectedTemplateId] = useState("")
    const [recipientType, setRecipientType] = useState<RecipientType>("case")
    const [selectedStages, setSelectedStages] = useState<string[]>([])
    const [selectedStates, setSelectedStates] = useState<string[]>([])
    const [includeUnsubscribed, setIncludeUnsubscribed] = useState(false)
    const [sendMode, setSendMode] = useState<SendMode>("draft")
    const [scheduledAt, setScheduledAt] = useState<Date | undefined>(undefined)
    const [deleteDialogId, setDeleteDialogId] = useState<string | null>(null)
    const [cancelDialogId, setCancelDialogId] = useState<string | null>(null)
    const [sendNowDialogId, setSendNowDialogId] = useState<string | null>(null)

    const { data: campaigns, isLoading } = useCampaigns(statusFilter)
    const { data: emailTemplates, isLoading: emailTemplatesLoading } = useEmailTemplates()
    const { data: messageTemplates, isLoading: messageTemplatesLoading } = useQuery({
        queryKey: ["messaging-templates", "promotional", "published"],
        queryFn: () => listMessagingTemplates({ purpose: "promotional", status: "published" }),
        // Only the SMS path of the wizard needs these; loading them for every viewer caused 403s.
        enabled: showCreateWizard && channel === "messaging",
    })
    const templates: CampaignTemplateOption[] | undefined = channel === "email"
        ? emailTemplates
        : messageTemplates?.map((template) => ({
            id: template.id,
            name: template.name,
            body: template.body,
        }))
    const createCampaign = useCreateCampaign()
    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()
    const cancelCampaign = useCancelCampaign()
    const sendCampaign = useSendCampaign()
    const previewFilters = usePreviewFilters()
    const sendNowPreview = useCampaignPreview(sendNowDialogId ?? undefined, {
        enabled: Boolean(sendNowDialogId) && canManageCampaigns,
    })
    const { data: intendedParentStatuses } = useIntendedParentStatuses()

    const buildFilterCriteria = () =>
        buildCampaignFilterCriteria(recipientType, selectedStages, selectedStates)

    const pipelineEntityType = getCampaignPipelineEntityType(recipientType)
    const { data: pipeline } = useQuery({
        queryKey: ["defaultPipeline", pipelineEntityType],
        queryFn: () => getDefaultPipeline(pipelineEntityType ?? "surrogate"),
        enabled: showCreateWizard && pipelineEntityType !== null,
    })
    const stageOptions = campaignStageOptions(
        recipientType,
        pipeline?.stages,
        intendedParentStatuses?.statuses,
    )
    const filteredCampaigns = campaigns || []
    const currentMinute = useCurrentMinuteTimestamp()
    const scheduleError =
        currentMinute === null ? undefined : getScheduleError(sendMode, scheduledAt, currentMinute)

    const resetWizard = () => {
        setWizardStep(SETUP_STEP)
        setCampaignName("")
        setCampaignDescription("")
        setChannel("email")
        setSelectedTemplateId("")
        setRecipientType("case")
        setSelectedStages([])
        setSelectedStates([])
        setIncludeUnsubscribed(false)
        setSendMode("draft")
        setScheduledAt(undefined)
        previewFilters.reset()
        setShowCreateWizard(false)
    }

    const previewRecipientSelection = () => {
        previewFilters.mutate({
            channel,
            recipientType,
            filterCriteria: buildFilterCriteria(),
            includeUnsubscribed: channel === "email" && includeUnsubscribed,
        })
    }

    const submitCampaign = async () => {
        if (!campaignName.trim() || !selectedTemplateId) {
            toast.error("Add a campaign name and a template first.")
            return
        }
        if (sendMode === "later" && (!scheduledAt || scheduledAt.getTime() <= Date.now())) {
            toast.error("Choose a send time in the future.")
            return
        }

        let campaignId: string
        try {
            const campaign = await createCampaign.mutateAsync({
                name: campaignName,
                channel,
                ...(channel === "email"
                    ? { email_template_id: selectedTemplateId }
                    : { message_template_version_id: selectedTemplateId }),
                recipient_type: recipientType,
                filter_criteria: buildFilterCriteria(),
                include_unsubscribed: channel === "email" && includeUnsubscribed,
                ...(campaignDescription ? { description: campaignDescription } : {}),
                ...(sendMode === "later" && scheduledAt
                    ? { scheduled_at: scheduledAt.toISOString() }
                    : {}),
            })
            campaignId = campaign.id
        } catch {
            toast.error("Couldn't create campaign. Try again.")
            return
        }

        if (sendMode === "draft") {
            toast.success("Campaign saved as draft")
            resetWizard()
            return
        }

        try {
            await sendCampaign.mutateAsync({ id: campaignId, sendNow: sendMode === "now" })
            toast.success(sendMode === "now" ? "Campaign queued for sending" : "Campaign scheduled")
        } catch {
            toast.error(
                sendMode === "now"
                    ? "Saved as draft, but sending didn't start."
                    : "Saved as draft, but scheduling failed.",
            )
        }
        resetWizard()
    }

    // The confirm dialogs show server failures inline, so these handlers let errors propagate.
    const handleDeleteCampaign = async () => {
        if (!deleteDialogId) return
        await deleteCampaign.mutateAsync(deleteDialogId)
        toast.success("Campaign deleted")
    }

    const handleDuplicateCampaign = async (id: string) => {
        try {
            await duplicateCampaign.mutateAsync(id)
            toast.success("Campaign duplicated")
        } catch {
            toast.error("Couldn't duplicate campaign")
        }
    }

    const handleCancelCampaign = async () => {
        if (!cancelDialogId) return
        await cancelCampaign.mutateAsync(cancelDialogId)
        toast.success("Campaign stopped")
    }

    const handleSendNowCampaign = async () => {
        if (!sendNowDialogId) return
        await sendCampaign.mutateAsync({ id: sendNowDialogId, sendNow: true })
        toast.success("Campaign queued for sending")
    }

    const wizardState: CampaignWizardState = {
        wizardStep,
        campaignName,
        campaignDescription,
        channel,
        selectedTemplateId,
        recipientType,
        selectedStages,
        selectedStates,
        includeUnsubscribed,
        sendMode,
        scheduledAt,
        scheduleError,
    }
    const wizardData: CampaignWizardData = {
        templates,
        templatesLoading: channel === "email" ? emailTemplatesLoading : messageTemplatesLoading,
        selectedTemplate: templates?.find((template) => template.id === selectedTemplateId),
        stageOptions,
        previewTotalCount: previewFilters.data ? previewFilters.data.total_count : null,
        previewSampleRecipients: toPreviewSampleRecipients(previewFilters.data?.sample_recipients),
        isPreviewLoading: previewFilters.isPending,
    }
    const wizardActions: CampaignWizardActions = {
        resetWizard,
        setWizardStep,
        setCampaignName,
        setCampaignDescription,
        setChannel: (next) => {
            setChannel(next)
            setSelectedTemplateId("")
            if (next === "messaging") {
                setIncludeUnsubscribed(false)
                if (isDonorCampaignRecipientType(recipientType)) {
                    setRecipientType("case")
                    setSelectedStages([])
                }
            }
        },
        setSelectedTemplateId,
        setRecipientType: (next) => {
            setRecipientType(next)
            setSelectedStages([])
        },
        setSelectedStages,
        setSelectedStates,
        setIncludeUnsubscribed,
        setSendMode,
        setScheduledAt,
        previewRecipients: previewRecipientSelection,
        submitCampaign,
    }
    const wizardPending: CampaignWizardPending = {
        isSubmitting: createCampaign.isPending || sendCampaign.isPending,
    }
    const dialogState: CampaignDialogState = {
        deleteDialogId,
        cancelDialogId,
        sendNowDialogId,
        getCampaignName: (id) =>
            id ? filteredCampaigns.find((campaign) => campaign.id === id)?.name : undefined,
        sendNowRecipientCount: sendNowPreview.data ? sendNowPreview.data.total_count : null,
    }
    const dialogActions: CampaignDialogActions = {
        setDeleteDialogId,
        setCancelDialogId,
        setSendNowDialogId,
        handleDeleteCampaign,
        handleCancelCampaign,
        handleSendNowCampaign,
    }
    const openCreateWizard = canManageCampaigns ? () => setShowCreateWizard(true) : undefined

    return {
        headerProps: {
            onCreateCampaign: openCreateWizard,
        },
        listProps: {
            statusFilter,
            onStatusFilterChange: setStatusFilter,
            campaigns: filteredCampaigns,
            isLoading,
            page,
            perPage,
            onPageChange: setPage,
            canManageCampaigns,
            onCreateCampaign: openCreateWizard,
            onViewCampaign: (campaignId: string) => push(`/automation/campaigns/${campaignId}`),
            onEditCampaign: (campaignId: string) =>
                push(`/automation/campaigns/${campaignId}?edit=1`),
            onSendNowCampaign: setSendNowDialogId,
            onDuplicateCampaign: handleDuplicateCampaign,
            onCancelCampaign: setCancelDialogId,
            onDeleteCampaign: setDeleteDialogId,
        },
        wizardProps: {
            open: showCreateWizard,
            state: wizardState,
            data: wizardData,
            actions: wizardActions,
            pending: wizardPending,
        },
        confirmationProps: {
            state: dialogState,
            actions: dialogActions,
        },
    }
}

export default function CampaignsPage() {
    const { headerProps, listProps, wizardProps, confirmationProps } =
        useCampaignsPageController()

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <CampaignsPageHeader {...headerProps} />
            <CampaignsListSection {...listProps} />
            <CampaignCreateWizardDialog {...wizardProps} />
            <CampaignConfirmationDialogs {...confirmationProps} />
        </div>
    )
}

function CampaignsPageHeader({ onCreateCampaign }: { onCreateCampaign: (() => void) | undefined }) {
    return (
        <PageHeader
            title="Campaigns"
            actions={
                onCreateCampaign ? (
                    <Button onClick={onCreateCampaign}>
                        <PlusIcon className="size-4" />
                        Create Campaign
                    </Button>
                ) : null
            }
        />
    )
}

function CampaignsListSection({
    statusFilter,
    onStatusFilterChange,
    campaigns,
    isLoading,
    page,
    perPage,
    onPageChange,
    canManageCampaigns,
    onCreateCampaign,
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    statusFilter: string | undefined
    onStatusFilterChange: StateSetter<string | undefined>
    campaigns: CampaignListItem[]
    isLoading: boolean
    page: number
    perPage: number
    onPageChange: StateSetter<number>
    canManageCampaigns: boolean
    onCreateCampaign: (() => void) | undefined
    onViewCampaign: (campaignId: string) => void
    onEditCampaign: (campaignId: string) => void
    onSendNowCampaign: (campaignId: string) => void
    onDuplicateCampaign: (campaignId: string) => Promise<void>
    onCancelCampaign: (campaignId: string) => void
    onDeleteCampaign: (campaignId: string) => void
}) {
    return (
        <div className="flex-1 p-6">
            <Tabs
                value={statusFilter || "all"}
                onValueChange={(value) => {
                    onStatusFilterChange(value === "all" ? undefined : value)
                    onPageChange(1)
                }}
                className="space-y-6"
            >
                <TabsList>
                    <TabsTrigger value="all">All</TabsTrigger>
                    <TabsTrigger value="draft">Draft</TabsTrigger>
                    <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
                    <TabsTrigger value="sending">Sending</TabsTrigger>
                    <TabsTrigger value="completed">Sent</TabsTrigger>
                </TabsList>

                <TabsContent value={statusFilter || "all"} className="space-y-4">
                    {isLoading ? (
                        <CampaignsLoadingState />
                    ) : campaigns.length === 0 ? (
                        <CampaignsEmptyState onCreateCampaign={onCreateCampaign} isFiltered={Boolean(statusFilter)} />
                    ) : (
                        <CampaignsTable
                            campaigns={campaigns}
                            page={page}
                            perPage={perPage}
                            canManageCampaigns={canManageCampaigns}
                            onViewCampaign={onViewCampaign}
                            onEditCampaign={onEditCampaign}
                            onSendNowCampaign={onSendNowCampaign}
                            onDuplicateCampaign={onDuplicateCampaign}
                            onCancelCampaign={onCancelCampaign}
                            onDeleteCampaign={onDeleteCampaign}
                        />
                    )}
                    <CampaignsPagination
                        campaignsCount={campaigns.length}
                        page={page}
                        perPage={perPage}
                        onPageChange={onPageChange}
                    />
                </TabsContent>
            </Tabs>
        </div>
    )
}

function CampaignsLoadingState() {
    return (
        <div className="flex items-center justify-center py-12">
            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
        </div>
    )
}

function CampaignsEmptyState({
    onCreateCampaign,
    isFiltered,
}: {
    onCreateCampaign: (() => void) | undefined
    isFiltered: boolean
}) {
    return (
        <Card className="py-0">
            <EmptyState
                icon={MailIcon}
                title={isFiltered ? "No campaigns with this status" : "No campaigns yet"}
                headingLevel={3}
                action={
                    onCreateCampaign ? (
                        <Button onClick={onCreateCampaign}>
                            <PlusIcon className="size-4" />
                            Create Campaign
                        </Button>
                    ) : null
                }
            />
        </Card>
    )
}

function CampaignsTable({
    campaigns,
    page,
    perPage,
    canManageCampaigns,
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    campaigns: CampaignListItem[]
    page: number
    perPage: number
    canManageCampaigns: boolean
    onViewCampaign: (campaignId: string) => void
    onEditCampaign: (campaignId: string) => void
    onSendNowCampaign: (campaignId: string) => void
    onDuplicateCampaign: (campaignId: string) => Promise<void>
    onCancelCampaign: (campaignId: string) => void
    onDeleteCampaign: (campaignId: string) => void
}) {
    return (
        <Card className="py-0">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Campaign Name</TableHead>
                        <TableHead>Template</TableHead>
                        <TableHead>Recipients</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Sent / Failed</TableHead>
                        <TableHead>Opens</TableHead>
                        <TableHead>Clicks</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead className="w-[50px]"></TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {campaigns
                        .slice((page - 1) * perPage, page * perPage)
                        .map((campaign) => (
                            <CampaignsTableRow
                                key={campaign.id}
                                campaign={campaign}
                                canManageCampaigns={canManageCampaigns}
                                onViewCampaign={onViewCampaign}
                                onEditCampaign={onEditCampaign}
                                onSendNowCampaign={onSendNowCampaign}
                                onDuplicateCampaign={onDuplicateCampaign}
                                onCancelCampaign={onCancelCampaign}
                                onDeleteCampaign={onDeleteCampaign}
                            />
                        ))}
                </TableBody>
            </Table>
        </Card>
    )
}

function CampaignsTableRow({
    campaign,
    canManageCampaigns,
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    campaign: CampaignListItem
    canManageCampaigns: boolean
    onViewCampaign: (campaignId: string) => void
    onEditCampaign: (campaignId: string) => void
    onSendNowCampaign: (campaignId: string) => void
    onDuplicateCampaign: (campaignId: string) => Promise<void>
    onCancelCampaign: (campaignId: string) => void
    onDeleteCampaign: (campaignId: string) => void
}) {
    const openRate = campaign.sent_count > 0
        ? Math.round((campaign.opened_count / campaign.sent_count) * 100)
        : 0
    const clickRate = campaign.sent_count > 0
        ? Math.round((campaign.clicked_count / campaign.sent_count) * 100)
        : 0
    const statusSummary = `${statusLabels[campaign.status] || campaign.status} • ${openRate}% opened • ${campaign.clicked_count} clicks`

    return (
        <TableRow>
            <TableCell>
                <Link
                    href={`/automation/campaigns/${campaign.id}`}
                    className="font-medium text-primary hover:underline"
                >
                    {campaign.name}
                </Link>
            </TableCell>
            <TableCell className="text-muted-foreground">
                <div className="space-y-1">
                    <span>{campaign.email_template_name || campaign.message_template_name || "-"}</span>
                    <Badge variant="outline" className="ml-2 text-[10px]">
                        {campaign.channel === "messaging" ? "SMS/MMS" : "Email"}
                    </Badge>
                </div>
            </TableCell>
            <TableCell>
                <div className="space-y-1">
                    <div className="flex items-center gap-1">
                        <UsersIcon className="size-4 text-muted-foreground" />
                        {campaign.total_recipients}
                    </div>
                    <Badge variant="outline" className="text-[10px]">
                        {getCampaignRecipientLabel(campaign.recipient_type)}
                    </Badge>
                </div>
            </TableCell>
            <TableCell>
                <Badge
                    variant={statusStyles[campaign.status]?.variant || "secondary"}
                    className={statusStyles[campaign.status]?.className}
                    title={statusSummary}
                >
                    {statusLabels[campaign.status] || campaign.status}
                </Badge>
            </TableCell>
            <TableCell>
                <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1 text-green-600">
                        <CheckCircle2Icon className="size-4" />
                        {campaign.sent_count}
                    </span>
                    <span className="flex items-center gap-1 text-red-600">
                        <XCircleIcon className="size-4" />
                        {campaign.failed_count}
                    </span>
                </div>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
                {campaign.channel === "email" ? (
                    <>{campaign.opened_count}<span className="ml-1 text-xs">({openRate}%)</span></>
                ) : "—"}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
                {campaign.channel === "email" ? (
                    <>{campaign.clicked_count}<span className="ml-1 text-xs">({clickRate}%)</span></>
                ) : "—"}
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
                {campaign.scheduled_at
                    ? `Scheduled ${format(parseDateInput(campaign.scheduled_at), "MMM d, yyyy")}`
                    : format(parseDateInput(campaign.created_at), "MMM d, yyyy")}
            </TableCell>
            <TableCell>
                <CampaignActionsMenu
                    campaign={campaign}
                    canManageCampaigns={canManageCampaigns}
                    onViewCampaign={onViewCampaign}
                    onEditCampaign={onEditCampaign}
                    onSendNowCampaign={onSendNowCampaign}
                    onDuplicateCampaign={onDuplicateCampaign}
                    onCancelCampaign={onCancelCampaign}
                    onDeleteCampaign={onDeleteCampaign}
                />
            </TableCell>
        </TableRow>
    )
}

function CampaignActionsMenu({
    campaign,
    canManageCampaigns,
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    campaign: CampaignListItem
    canManageCampaigns: boolean
    onViewCampaign: (campaignId: string) => void
    onEditCampaign: (campaignId: string) => void
    onSendNowCampaign: (campaignId: string) => void
    onDuplicateCampaign: (campaignId: string) => Promise<void>
    onCancelCampaign: (campaignId: string) => void
    onDeleteCampaign: (campaignId: string) => void
}) {
    return (
        <DropdownMenu>
            <DropdownMenuTrigger
                className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }), "inline-flex items-center justify-center")}
                aria-label={`Actions for ${campaign.name}`}
            >
                <MoreVerticalIcon className="size-4" aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onViewCampaign(campaign.id)}>
                    <EyeIcon className="mr-2 size-4" />
                    View Details
                </DropdownMenuItem>
                {canManageCampaigns && campaign.status === "draft" && (
                    <DropdownMenuItem onClick={() => onSendNowCampaign(campaign.id)}>
                        <SendIcon className="mr-2 size-4" />
                        Send Now
                    </DropdownMenuItem>
                )}
                {canManageCampaigns && (campaign.status === "draft" || campaign.status === "scheduled") && (
                    <DropdownMenuItem onClick={() => onEditCampaign(campaign.id)}>
                        <PencilIcon className="mr-2 size-4" />
                        Edit
                    </DropdownMenuItem>
                )}
                {canManageCampaigns ? (
                    <DropdownMenuItem onClick={() => { void onDuplicateCampaign(campaign.id) }}>
                        <CopyIcon className="mr-2 size-4" />
                        Duplicate
                    </DropdownMenuItem>
                ) : null}
                {canManageCampaigns && (campaign.status === "scheduled" || campaign.status === "sending") && (
                    <DropdownMenuItem
                        onClick={() => onCancelCampaign(campaign.id)}
                        className="text-destructive"
                    >
                        <TrashIcon className="mr-2 size-4" />
                        Stop
                    </DropdownMenuItem>
                )}
                {canManageCampaigns && campaign.status === "draft" && (
                    <DropdownMenuItem
                        onClick={() => onDeleteCampaign(campaign.id)}
                        className="text-destructive"
                    >
                        <TrashIcon className="mr-2 size-4" />
                        Delete
                    </DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

function CampaignsPagination({
    campaignsCount,
    page,
    perPage,
    onPageChange,
}: {
    campaignsCount: number
    page: number
    perPage: number
    onPageChange: StateSetter<number>
}) {
    if (campaignsCount <= perPage) return null

    return (
        <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-muted-foreground">
                Showing {((page - 1) * perPage) + 1}-{Math.min(page * perPage, campaignsCount)} of {campaignsCount} campaigns
            </div>
            <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => onPageChange((currentPage) => Math.max(1, currentPage - 1))}
                >
                    Previous
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    disabled={page * perPage >= campaignsCount}
                    onClick={() => onPageChange((currentPage) => currentPage + 1)}
                >
                    Next
                </Button>
            </div>
        </div>
    )
}

function CampaignCreateWizardDialog({
    open,
    state,
    data,
    actions,
    pending,
}: {
    open: boolean
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
    pending: CampaignWizardPending
}) {
    return (
        <Dialog open={open} onOpenChange={(dialogOpen) => !dialogOpen && actions.resetWizard()}>
            <DialogContent layout="sectioned" size="2xl">
                <DialogHeader>
                    <DialogTitle>Create Campaign</DialogTitle>
                </DialogHeader>
                <DialogBody>
                    <WizardStepper steps={CAMPAIGN_WIZARD_STEPS} currentStep={state.wizardStep} />
                    <CampaignWizardStepContent state={state} data={data} actions={actions} />
                </DialogBody>
                <CampaignWizardFooter state={state} data={data} actions={actions} pending={pending} />
            </DialogContent>
        </Dialog>
    )
}

const CHANNEL_LABELS: Record<CampaignChannel, string> = {
    email: "Email",
    messaging: "SMS / MMS",
}

function getChannelLabel(value: string | null): string {
    return value === "email" || value === "messaging" ? CHANNEL_LABELS[value] : "Choose a channel"
}

function CampaignWizardStepContent({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    if (state.wizardStep === SETUP_STEP) {
        return <CampaignSetupStep state={state} actions={actions} />
    }
    if (state.wizardStep === AUDIENCE_STEP) {
        return (
            <CampaignAudienceFields
                idPrefix="campaign-create"
                channel={state.channel}
                recipientType={state.recipientType}
                onRecipientTypeChange={actions.setRecipientType}
                stageOptions={data.stageOptions}
                selectedStages={state.selectedStages}
                onSelectedStagesChange={actions.setSelectedStages}
                selectedStates={state.selectedStates}
                onSelectedStatesChange={actions.setSelectedStates}
                includeUnsubscribed={state.includeUnsubscribed}
                onIncludeUnsubscribedChange={actions.setIncludeUnsubscribed}
            />
        )
    }
    if (state.wizardStep === CONTENT_STEP) {
        return <CampaignContentStep state={state} data={data} actions={actions} />
    }
    return <CampaignReviewStep state={state} data={data} actions={actions} />
}

function CampaignSetupStep({
    state,
    actions,
}: {
    state: CampaignWizardState
    actions: CampaignWizardActions
}) {
    return (
        <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
                <Label htmlFor="campaign-channel">Channel</Label>
                <Select
                    aria-label="Channel"
                    value={state.channel}
                    onValueChange={(value) => {
                        if (value === "email" || value === "messaging") actions.setChannel(value)
                    }}
                >
                    <SelectTrigger id="campaign-channel" className="w-full">
                        <SelectValue placeholder="Choose a channel">{getChannelLabel}</SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="email">{CHANNEL_LABELS.email}</SelectItem>
                        <SelectItem value="messaging">{CHANNEL_LABELS.messaging}</SelectItem>
                    </SelectContent>
                </Select>
                {state.channel === "messaging" ? (
                    <p className="text-xs text-muted-foreground">
                        Recipients without current promotional consent are excluded.
                    </p>
                ) : null}
            </div>
            <div className="flex flex-col gap-2">
                <Label htmlFor="campaign-name">Campaign name</Label>
                <Input
                    id="campaign-name"
                    placeholder="e.g., March Newsletter"
                    value={state.campaignName}
                    onChange={(event) => actions.setCampaignName(event.target.value)}
                />
            </div>
            <div className="flex flex-col gap-2">
                <Label htmlFor="campaign-description">Description (optional)</Label>
                <Textarea
                    id="campaign-description"
                    value={state.campaignDescription}
                    onChange={(event) => actions.setCampaignDescription(event.target.value)}
                />
            </div>
        </div>
    )
}

function CampaignContentStep({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    const isMessaging = state.channel === "messaging"
    const label = isMessaging ? "SMS template" : "Email template"

    if (data.templatesLoading) {
        return (
            <div className="flex flex-col gap-2" aria-busy="true">
                <span className="text-sm font-medium">{label}</span>
                <Skeleton className="h-9 w-full" />
            </div>
        )
    }

    if (!data.templates || data.templates.length === 0) {
        return (
            <div className="flex flex-col gap-2">
                <span className="text-sm font-medium">{label}</span>
                <EmptyState
                    icon={isMessaging ? MessageSquareTextIcon : MailIcon}
                    title={isMessaging ? "No promotional SMS templates" : "No email templates"}
                    className="rounded-lg border border-dashed"
                />
            </div>
        )
    }

    return (
        <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
                <Label htmlFor="campaign-template">{label}</Label>
                <Select
                    aria-label={label}
                    value={state.selectedTemplateId}
                    onValueChange={(value) => value && actions.setSelectedTemplateId(value)}
                >
                    <SelectTrigger id="campaign-template" aria-label={label} className="w-full">
                        <SelectValue placeholder="Choose a template">
                            {(value: string | null) => {
                                if (!value) return "Choose a template"
                                const template = data.templates?.find((option) => option.id === value)
                                return template?.name ?? "Choose a template"
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="min-w-[300px]">
                        {data.templates.map((template) => (
                            <SelectItem key={template.id} value={template.id}>
                                {template.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            {data.selectedTemplate ? (
                <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                    <p className="text-muted-foreground">{isMessaging ? "Message" : "Subject"}</p>
                    <p className="mt-1 whitespace-pre-wrap">
                        {isMessaging ? data.selectedTemplate.body : data.selectedTemplate.subject}
                    </p>
                </div>
            ) : null}
        </div>
    )
}

const SEND_MODE_OPTIONS: ReadonlyArray<{ value: SendMode; label: string }> = [
    { value: "draft", label: "Save as draft" },
    { value: "now", label: "Send now" },
    { value: "later", label: "Schedule for later" },
]

function getRecipientInitials(name: string | null, email: string): string {
    const source = name?.trim() || email
    const parts = source.split(/\s+/).filter(Boolean)
    if (parts.length > 1) {
        return `${parts[0]?.[0] ?? ""}${parts[parts.length - 1]?.[0] ?? ""}`.toUpperCase()
    }
    return source.slice(0, 2).toUpperCase()
}

function CampaignReviewStep({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    const rows = [
        { key: "name", label: "Name", value: state.campaignName, step: SETUP_STEP },
        {
            key: "channel",
            label: "Channel",
            value: `${CHANNEL_LABELS[state.channel]} · ${data.selectedTemplate?.name ?? "No template"}`,
            step: CONTENT_STEP,
        },
        {
            key: "audience",
            label: "Audience",
            value: summarizeCampaignAudience({
                channel: state.channel,
                recipientType: state.recipientType,
                stageOptions: data.stageOptions,
                selectedStages: state.selectedStages,
                selectedStates: state.selectedStates,
                includeUnsubscribed: state.includeUnsubscribed,
            }),
            step: AUDIENCE_STEP,
        },
    ]
    const timeZone = state.scheduledAt ? getTimeZoneAbbreviation(state.scheduledAt) : undefined

    return (
        <div className="flex flex-col gap-5">
            <dl className="flex flex-col">
                {rows.map((row) => (
                    <div key={row.key} className="flex items-start gap-3 border-b py-2 text-sm">
                        <dt className="w-24 shrink-0 text-muted-foreground">{row.label}</dt>
                        <dd className="flex min-w-0 flex-1 items-start justify-between gap-3">
                            <span className="min-w-0 break-words">{row.value}</span>
                            <Button
                                type="button"
                                variant="link"
                                size="sm"
                                className="h-auto shrink-0 p-0"
                                aria-label={`Edit ${row.label.toLowerCase()}`}
                                onClick={() => actions.setWizardStep(row.step)}
                            >
                                Edit
                            </Button>
                        </dd>
                    </div>
                ))}
            </dl>

            <CampaignRecipientSummary data={data} />

            <div className="flex flex-col gap-3">
                <span id="campaign-send-mode-label" className="text-sm font-medium">
                    When to send
                </span>
                <RadioGroup
                    aria-labelledby="campaign-send-mode-label"
                    value={state.sendMode}
                    onValueChange={(value) => {
                        if (isSendMode(value)) actions.setSendMode(value)
                    }}
                    className="flex flex-wrap gap-x-5 gap-y-2"
                >
                    {SEND_MODE_OPTIONS.map((option) => (
                        <div key={option.value} className="flex items-center gap-2">
                            <RadioGroupItem id={`campaign-send-${option.value}`} value={option.value} />
                            <Label htmlFor={`campaign-send-${option.value}`} className="cursor-pointer font-normal">
                                {option.label}
                            </Label>
                        </div>
                    ))}
                </RadioGroup>
                {state.sendMode === "later" ? (
                    <ValidatedField label="Send time" error={state.scheduleError}>
                        {(control) => (
                            <div className="flex flex-wrap items-center gap-2">
                                <DateTimePicker
                                    triggerId={control.id}
                                    aria-invalid={control["aria-invalid"]}
                                    aria-describedby={control["aria-describedby"]}
                                    value={state.scheduledAt}
                                    onChange={actions.setScheduledAt}
                                    className="w-full sm:w-72"
                                />
                                {timeZone ? (
                                    <span className="text-sm text-muted-foreground">{timeZone}</span>
                                ) : null}
                            </div>
                        )}
                    </ValidatedField>
                ) : null}
            </div>
        </div>
    )
}

function CampaignRecipientSummary({ data }: { data: CampaignWizardData }) {
    const samples = data.previewSampleRecipients.slice(0, 3)

    return (
        <section
            aria-label="Recipients"
            aria-busy={data.isPreviewLoading || undefined}
            className="flex flex-col gap-4 rounded-lg border p-4 sm:flex-row sm:items-start"
        >
            <div className="flex w-32 shrink-0 flex-col">
                {data.isPreviewLoading ? (
                    <Skeleton className="h-8 w-16" />
                ) : (
                    <span className="text-3xl font-semibold tabular-nums">
                        {data.previewTotalCount === null ? "—" : data.previewTotalCount.toLocaleString()}
                    </span>
                )}
                <span className="text-xs text-muted-foreground">
                    {data.previewTotalCount === 1 ? "recipient" : "recipients"}
                </span>
            </div>
            {data.isPreviewLoading ? (
                <div className="flex min-w-0 flex-1 flex-col gap-2">
                    <Skeleton className="h-6 w-40" />
                    <Skeleton className="h-6 w-32" />
                </div>
            ) : data.previewTotalCount === 0 ? (
                <p className="min-w-0 flex-1 text-sm text-muted-foreground">No matching recipients</p>
            ) : (
                <ul className="flex min-w-0 flex-1 flex-col gap-2">
                    {samples.map((recipient) => {
                        const name = recipient.name || recipient.email
                        return (
                            <li
                                key={`${recipient.href ?? recipient.email}-${recipient.name ?? ""}`}
                                className="flex min-w-0 items-center gap-2"
                            >
                                <Avatar className="size-6">
                                    <AvatarFallback className="bg-primary/10 text-[10px] text-primary">
                                        {getRecipientInitials(recipient.name, recipient.email)}
                                    </AvatarFallback>
                                </Avatar>
                                {recipient.href ? (
                                    <Link href={recipient.href} className="truncate text-sm text-primary hover:underline">
                                        {name}
                                    </Link>
                                ) : (
                                    <span className="truncate text-sm">{name}</span>
                                )}
                            </li>
                        )
                    })}
                </ul>
            )}
        </section>
    )
}

function CampaignSubmitButton({
    state,
    data,
    actions,
    pending,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
    pending: CampaignWizardPending
}) {
    const spinner = pending.isSubmitting ? <Loader2Icon className="size-4 animate-spin" aria-hidden="true" /> : null

    if (state.sendMode === "now") {
        return (
            <ConfirmDialog
                trigger={
                    <Button
                        disabled={pending.isSubmitting || data.isPreviewLoading || data.previewTotalCount === 0}
                    >
                        {spinner ?? <SendIcon className="size-4" aria-hidden="true" />}
                        Send Campaign
                    </Button>
                }
                title={getCampaignSendConfirmTitle(data.previewTotalCount)}
                description={
                    state.channel === "messaging"
                        ? "Messages start sending right away."
                        : "Emails start sending right away."
                }
                confirmVariant="default"
                confirmIcon={<SendIcon aria-hidden="true" />}
                confirmLabel="Send now"
                onConfirm={actions.submitCampaign}
            />
        )
    }

    if (state.sendMode === "later") {
        return (
            <Button
                onClick={() => { void actions.submitCampaign() }}
                disabled={pending.isSubmitting || !state.scheduledAt || Boolean(state.scheduleError)}
            >
                {spinner ?? <CalendarIcon className="size-4" aria-hidden="true" />}
                Schedule Campaign
            </Button>
        )
    }

    return (
        <Button onClick={() => { void actions.submitCampaign() }} disabled={pending.isSubmitting}>
            {spinner}
            Save Draft
        </Button>
    )
}

function CampaignWizardFooter({
    state,
    data,
    actions,
    pending,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
    pending: CampaignWizardPending
}) {
    const canAdvance =
        state.wizardStep === SETUP_STEP
            ? state.campaignName.trim().length > 0
            : state.wizardStep === CONTENT_STEP
              ? Boolean(state.selectedTemplateId)
              : true
    const goToStep = (nextStep: number) => {
        actions.setWizardStep(nextStep)
        if (nextStep === REVIEW_STEP) {
            actions.previewRecipients()
        }
    }

    return (
        <DialogFooter
            start={
                state.wizardStep > SETUP_STEP ? (
                    <Button
                        variant="outline"
                        disabled={pending.isSubmitting}
                        onClick={() => actions.setWizardStep((previousStep) => previousStep - 1)}
                    >
                        Back
                    </Button>
                ) : undefined
            }
        >
            <Button variant="outline" onClick={actions.resetWizard} disabled={pending.isSubmitting}>
                Cancel
            </Button>
            {state.wizardStep < REVIEW_STEP ? (
                <Button onClick={() => goToStep(state.wizardStep + 1)} disabled={!canAdvance}>
                    Next
                </Button>
            ) : (
                <CampaignSubmitButton state={state} data={data} actions={actions} pending={pending} />
            )}
        </DialogFooter>
    )
}

function CampaignConfirmationDialogs({
    state,
    actions,
}: {
    state: CampaignDialogState
    actions: CampaignDialogActions
}) {
    const deleteName = state.getCampaignName(state.deleteDialogId)
    const cancelName = state.getCampaignName(state.cancelDialogId)

    return (
        <>
            <ConfirmDialog
                open={state.deleteDialogId !== null}
                onOpenChange={(open) => {
                    if (!open) actions.setDeleteDialogId(null)
                }}
                title={deleteName ? `Delete ${deleteName}?` : "Delete campaign?"}
                description="This can't be undone."
                confirmLabel="Delete"
                errorFallback="Couldn't delete campaign. Only drafts can be deleted."
                onConfirm={actions.handleDeleteCampaign}
            />

            <ConfirmDialog
                open={state.cancelDialogId !== null}
                onOpenChange={(open) => {
                    if (!open) actions.setCancelDialogId(null)
                }}
                title={cancelName ? `Stop ${cancelName}?` : "Stop campaign?"}
                description="Scheduled and in-progress sends stop. Messages already queued may still deliver."
                confirmLabel="Stop"
                errorFallback="Couldn't stop campaign. Try again."
                onConfirm={actions.handleCancelCampaign}
            />

            <ConfirmDialog
                open={state.sendNowDialogId !== null}
                onOpenChange={(open) => {
                    if (!open) actions.setSendNowDialogId(null)
                }}
                title={getCampaignSendConfirmTitle(state.sendNowRecipientCount)}
                description="Sending starts right away."
                confirmVariant="default"
                confirmIcon={<SendIcon aria-hidden="true" />}
                confirmLabel="Send now"
                errorFallback="Couldn't send campaign. Try again."
                onConfirm={actions.handleSendNowCampaign}
            />
        </>
    )
}
