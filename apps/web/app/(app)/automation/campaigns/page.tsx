"use client"

import { useState, type Dispatch, type SetStateAction } from "react"
import Link from "@/components/app-link"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { buttonVariants } from "@/components/ui/button-variants"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
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
    ArrowLeftIcon,
    CalendarIcon,
    EyeIcon,
    PencilIcon,
} from "lucide-react"
import { format } from "date-fns"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { parseDateInput } from "@/lib/utils/date"
import {
    useCampaigns,
    useCreateCampaign,
    useDeleteCampaign,
    useDuplicateCampaign,
    useCancelCampaign,
    useSendCampaign,
    usePreviewFilters,
} from "@/lib/hooks/use-campaigns"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { useIntendedParentStatuses } from "@/lib/hooks/use-metadata"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { useQuery } from "@tanstack/react-query"
import { RecipientPreviewCard } from "@/components/recipient-preview-card"
import { US_STATES } from "@/lib/constants/us-states"
import { getIntendedParentStageOptions } from "@/lib/intended-parent-stage-utils"
import type { CampaignListItem, FilterCriteria } from "@/lib/api/campaigns"
import type { EmailTemplateListItem } from "@/lib/api/email-templates"

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

const toLocalDateTimeInput = (date: Date) => {
    const pad = (value: number) => String(value).padStart(2, "0")
    const year = date.getFullYear()
    const month = pad(date.getMonth() + 1)
    const day = pad(date.getDate())
    const hours = pad(date.getHours())
    const minutes = pad(date.getMinutes())
    return `${year}-${month}-${day}T${hours}:${minutes}`
}

const TOTAL_STEPS = 7
const TERRITORY_CODES = new Set(["PR", "GU", "VI", "AS", "MP"])
const STATE_OPTIONS = US_STATES.filter((state) => !TERRITORY_CODES.has(state.value))
const TERRITORY_OPTIONS = US_STATES.filter((state) => TERRITORY_CODES.has(state.value))

type RecipientType = "case" | "intended_parent"
type ScheduleFor = "now" | "later"
type StateSetter<T> = Dispatch<SetStateAction<T>>
type StateOption = (typeof US_STATES)[number]

type CampaignStageOption = {
    id: string
    label: string
    color: string
    stage_key: string
    category?: string | null
    stage_type?: string | null
    semantics?: {
        capabilities?: {
            shows_pregnancy_tracking?: boolean
            requires_delivery_details?: boolean
        } | undefined
        pause_behavior?: string | null
        terminal_outcome?: string | null
    } | null | undefined
}

type StagePreset = {
    key: string
    label: string
    stageIds: string[]
}

type CampaignWizardState = {
    wizardStep: number
    campaignName: string
    campaignDescription: string
    selectedTemplateId: string
    recipientType: RecipientType
    selectedStages: string[]
    selectedStageIdSet: Set<string>
    selectedStates: string[]
    selectedStateCodeSet: Set<string>
    includeUnsubscribed: boolean
    stateSearch: string
    showTerritories: boolean
    scheduleFor: ScheduleFor
    scheduledDate: string
    minScheduleDate: string
}

type CampaignWizardData = {
    templates: EmailTemplateListItem[] | undefined
    selectedTemplate: EmailTemplateListItem | undefined
    stageOptions: CampaignStageOption[]
    stagePresetsAvailable: StagePreset[]
    selectedStageLabels: string[]
    selectedStateLabels: string[]
    visibleStateOptions: StateOption[]
    filteredTerritories: StateOption[]
    includeTerritories: boolean
    normalizedStateSearch: string
    stageById: Map<string, CampaignStageOption>
    stateLabelByCode: Map<string, string>
    previewTotalCount: number
    previewSampleRecipients: { email: string; name: string | null }[]
    isPreviewLoading: boolean
}

type CampaignWizardActions = {
    resetWizard: () => void
    setWizardStep: StateSetter<number>
    setCampaignName: StateSetter<string>
    setCampaignDescription: StateSetter<string>
    setSelectedTemplateId: StateSetter<string>
    setRecipientType: StateSetter<RecipientType>
    setSelectedStages: StateSetter<string[]>
    setSelectedStates: StateSetter<string[]>
    setIncludeUnsubscribed: StateSetter<boolean>
    setStateSearch: StateSetter<string>
    setShowTerritories: StateSetter<boolean>
    setScheduleFor: StateSetter<ScheduleFor>
    setScheduledDate: StateSetter<string>
    previewRecipients: () => void
    handleCreateCampaign: () => Promise<void>
}

type CampaignWizardPending = {
    isCreating: boolean
    isSending: boolean
}

type CampaignDialogState = {
    deleteDialogId: string | null
    cancelDialogId: string | null
    sendNowDialogId: string | null
}

type CampaignDialogActions = {
    setDeleteDialogId: StateSetter<string | null>
    setCancelDialogId: StateSetter<string | null>
    setSendNowDialogId: StateSetter<string | null>
    handleDeleteCampaign: () => Promise<void>
    handleCancelCampaign: () => Promise<void>
    handleSendNowCampaign: () => Promise<void>
}

function getStageIdsByPredicate(
    stages: readonly CampaignStageOption[],
    predicate: (stage: CampaignStageOption) => boolean,
): string[] {
    const stageIds: string[] = []
    for (const stage of stages) {
        if (predicate(stage)) stageIds.push(stage.id)
    }
    return stageIds
}

function buildCampaignStagePresets(
    recipientType: RecipientType,
    stageOptions: readonly CampaignStageOption[],
): StagePreset[] {
    if (recipientType === "intended_parent") {
        return [
            {
                key: "ip-new-ready",
                label: "New + Ready",
                stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                    ["new", "ready_to_match"].includes(stage.stage_key)
                ),
            },
            {
                key: "ip-active",
                label: "Active",
                stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                    ["new", "ready_to_match", "matched"].includes(stage.stage_key)
                ),
            },
            {
                key: "ip-delivered",
                label: "Delivered",
                stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                    stage.stage_key === "delivered"
                ),
            },
        ]
    }

    return [
        {
            key: "surrogate-intake",
            label: "Intake",
            stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                (stage.category ?? stage.stage_type) === "intake"
            ),
        },
        {
            key: "surrogate-post-approval",
            label: "Post-Approval",
            stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                (stage.category ?? stage.stage_type) === "post_approval" &&
                !stage.semantics?.capabilities?.shows_pregnancy_tracking
            ),
        },
        {
            key: "surrogate-pregnancy",
            label: "Pregnancy",
            stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                Boolean(
                    stage.semantics?.capabilities?.shows_pregnancy_tracking ||
                        stage.semantics?.capabilities?.requires_delivery_details,
                )
            ),
        },
        {
            key: "surrogate-paused",
            label: "Paused",
            stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                stage.semantics?.pause_behavior === "resume_previous_stage"
            ),
        },
        {
            key: "surrogate-terminal",
            label: "Terminal",
            stageIds: getStageIdsByPredicate(stageOptions, (stage) =>
                Boolean(
                    stage.semantics?.terminal_outcome &&
                        stage.semantics.terminal_outcome !== "none"
                )
            ),
        },
    ]
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

function buildCampaignWizardDerivedData({
    recipientType,
    stageOptions,
    selectedStages,
    selectedStates,
    stateSearch,
    showTerritories,
    templates,
    selectedTemplateId,
    previewFiltersData,
}: {
    recipientType: RecipientType
    stageOptions: CampaignStageOption[]
    selectedStages: string[]
    selectedStates: string[]
    stateSearch: string
    showTerritories: boolean
    templates: EmailTemplateListItem[] | undefined
    selectedTemplateId: string
    previewFiltersData: { sample_recipients?: { email: string; name: string | null }[] } | undefined
}) {
    const normalizedStateSearch = stateSearch.trim().toLowerCase()
    const filteredStates = STATE_OPTIONS.filter((state) =>
        normalizedStateSearch
            ? state.label.toLowerCase().includes(normalizedStateSearch)
            : true
    )
    const filteredTerritories = TERRITORY_OPTIONS.filter((state) =>
        normalizedStateSearch
            ? state.label.toLowerCase().includes(normalizedStateSearch)
            : true
    )
    const includeTerritories = showTerritories || normalizedStateSearch.length > 0
    const visibleStateOptions = includeTerritories
        ? [...filteredStates, ...filteredTerritories]
        : filteredStates
    const stagePresets = buildCampaignStagePresets(recipientType, stageOptions)
    const stagePresetsAvailable = stagePresets.filter((preset) => preset.stageIds.length > 0)
    const stageById = new Map<string, CampaignStageOption>(
        stageOptions.map((stage) => [stage.id, stage]),
    )
    const stageLabelById = new Map<string, string>(
        stageOptions.map((stage) => [stage.id, stage.label]),
    )
    const stateLabelByCode = new Map<string, string>(
        US_STATES.map((state) => [state.value, state.label]),
    )
    const selectedStageLabels: string[] = []
    for (const stageId of selectedStages) {
        const label = stageLabelById.get(stageId)
        if (label) selectedStageLabels.push(label)
    }
    const selectedStateLabels: string[] = []
    for (const stateCode of selectedStates) {
        const label = stateLabelByCode.get(stateCode)
        if (label) selectedStateLabels.push(label)
    }
    const selectedStageIdSet = new Set(selectedStages)
    const selectedStateCodeSet = new Set(selectedStates)
    const selectedTemplate = templates?.find((template) => template.id === selectedTemplateId)
    const previewSampleRecipients =
        previewFiltersData?.sample_recipients?.map((recipient) => ({
            email: recipient.email,
            name: recipient.name,
        })) || []

    return {
        selectedTemplate,
        stagePresetsAvailable,
        selectedStageLabels,
        selectedStateLabels,
        visibleStateOptions,
        filteredTerritories,
        includeTerritories,
        normalizedStateSearch,
        stageById,
        stateLabelByCode,
        selectedStageIdSet,
        selectedStateCodeSet,
        previewSampleRecipients,
    }
}

const isRecipientType = (value: string | null): value is RecipientType =>
    value === "case" || value === "intended_parent"

const isScheduleFor = (value: unknown): value is ScheduleFor =>
    value === "now" || value === "later"

export default function CampaignsPage() {
    const { push } = useRouter()
    const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
    const [showCreateWizard, setShowCreateWizard] = useState(false)
    const [wizardStep, setWizardStep] = useState(1)
    const [page, setPage] = useState(1)
    const perPage = 20
    const [campaignName, setCampaignName] = useState("")
    const [campaignDescription, setCampaignDescription] = useState("")
    const [selectedTemplateId, setSelectedTemplateId] = useState("")
    const [recipientType, setRecipientType] = useState<RecipientType>("case")
    const [selectedStages, setSelectedStages] = useState<string[]>([])
    const [selectedStates, setSelectedStates] = useState<string[]>([])
    const [includeUnsubscribed, setIncludeUnsubscribed] = useState(false)
    const [stateSearch, setStateSearch] = useState("")
    const [showTerritories, setShowTerritories] = useState(false)
    const [scheduleFor, setScheduleFor] = useState<ScheduleFor>("now")
    const [scheduledDate, setScheduledDate] = useState("")
    const [deleteDialogId, setDeleteDialogId] = useState<string | null>(null)
    const [cancelDialogId, setCancelDialogId] = useState<string | null>(null)
    const [sendNowDialogId, setSendNowDialogId] = useState<string | null>(null)
    const minScheduleDate = toLocalDateTimeInput(new Date())

    const { data: campaigns, isLoading } = useCampaigns(statusFilter)
    const { data: templates } = useEmailTemplates()
    const createCampaign = useCreateCampaign()
    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()
    const cancelCampaign = useCancelCampaign()
    const sendCampaign = useSendCampaign()
    const previewFilters = usePreviewFilters()
    const { data: intendedParentStatuses } = useIntendedParentStatuses()

    const buildFilterCriteria = () =>
        buildCampaignFilterCriteria(recipientType, selectedStages, selectedStates)

    const { data: pipeline } = useQuery({
        queryKey: ["defaultPipeline", "surrogate"],
        queryFn: () => getDefaultPipeline("surrogate"),
    })
    const pipelineStages = pipeline?.stages || []
    const intendedParentStageOptions: CampaignStageOption[] = getIntendedParentStageOptions(
        intendedParentStatuses?.statuses,
    ).map((stage) => ({
        id: stage.stage_slug,
        label: stage.label,
        color: stage.color,
        stage_key: stage.stage_key,
        category: stage.stage_type,
        stage_type: stage.stage_type,
        semantics: undefined,
    }))
    const stageOptions: CampaignStageOption[] =
        recipientType === "intended_parent"
            ? intendedParentStageOptions
            : pipelineStages.filter((stage) => stage.is_active)

    const wizardDerivedData = buildCampaignWizardDerivedData({
        recipientType,
        stageOptions,
        selectedStages,
        selectedStates,
        stateSearch,
        showTerritories,
        templates,
        selectedTemplateId,
        previewFiltersData: previewFilters.data,
    })
    const filteredCampaigns = campaigns || []

    const resetWizard = () => {
        setWizardStep(1)
        setCampaignName("")
        setCampaignDescription("")
        setSelectedTemplateId("")
        setRecipientType("case")
        setSelectedStages([])
        setSelectedStates([])
        setIncludeUnsubscribed(false)
        setStateSearch("")
        setShowTerritories(false)
        setScheduleFor("now")
        setScheduledDate("")
        setShowCreateWizard(false)
    }

    const previewRecipientSelection = () => {
        previewFilters.mutate({
            recipientType,
            filterCriteria: buildFilterCriteria(),
            includeUnsubscribed,
        })
    }

    const handleCreateCampaign = async () => {
        if (!campaignName || !selectedTemplateId) {
            toast.error("Please fill in required fields")
            return
        }

        if (scheduleFor === "later") {
            if (!scheduledDate) {
                toast.error("Please select a scheduled date and time")
                return
            }
            const parsedDate = new Date(scheduledDate)
            if (Number.isNaN(parsedDate.getTime())) {
                toast.error("Scheduled date is invalid")
                return
            }
            if (parsedDate <= new Date()) {
                toast.error("Scheduled date must be in the future")
                return
            }
        }

        try {
            const scheduledAt =
                scheduleFor === "later" && scheduledDate
                    ? new Date(scheduledDate).toISOString()
                    : undefined
            const campaign = await createCampaign.mutateAsync({
                name: campaignName,
                email_template_id: selectedTemplateId,
                recipient_type: recipientType,
                filter_criteria: buildFilterCriteria(),
                include_unsubscribed: includeUnsubscribed,
                ...(campaignDescription ? { description: campaignDescription } : {}),
                ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
            })

            toast.success("Campaign created successfully")

            try {
                await sendCampaign.mutateAsync({ id: campaign.id, sendNow: scheduleFor === "now" })
                if (scheduleFor === "now") {
                    toast.success("Campaign queued for sending")
                } else {
                    toast.success("Campaign scheduled successfully")
                }
            } catch {
                toast.error("Campaign created but failed to start")
            }

            resetWizard()
        } catch {
            toast.error("Failed to create campaign")
        }
    }

    const handleDeleteCampaign = async () => {
        if (!deleteDialogId) return

        const closeDeleteDialog = () => setDeleteDialogId(null)
        try {
            await deleteCampaign.mutateAsync(deleteDialogId)
            toast.success("Campaign deleted")
            closeDeleteDialog()
        } catch {
            toast.error("Failed to delete campaign. Only drafts can be deleted.")
            closeDeleteDialog()
        }
    }

    const handleDuplicateCampaign = async (id: string) => {
        try {
            await duplicateCampaign.mutateAsync(id)
            toast.success("Campaign duplicated")
        } catch {
            toast.error("Failed to duplicate campaign")
        }
    }

    const handleCancelCampaign = async () => {
        if (!cancelDialogId) return

        const closeCancelDialog = () => setCancelDialogId(null)
        try {
            await cancelCampaign.mutateAsync(cancelDialogId)
            toast.success("Campaign stopped")
            closeCancelDialog()
        } catch {
            toast.error("Failed to stop campaign")
            closeCancelDialog()
        }
    }

    const handleSendNowCampaign = async () => {
        if (!sendNowDialogId) return

        const closeSendNowDialog = () => setSendNowDialogId(null)
        try {
            await sendCampaign.mutateAsync({ id: sendNowDialogId, sendNow: true })
            toast.success("Campaign queued for sending")
            closeSendNowDialog()
        } catch {
            toast.error("Failed to send campaign")
            closeSendNowDialog()
        }
    }

    const wizardState: CampaignWizardState = {
        wizardStep,
        campaignName,
        campaignDescription,
        selectedTemplateId,
        recipientType,
        selectedStages,
        selectedStageIdSet: wizardDerivedData.selectedStageIdSet,
        selectedStates,
        selectedStateCodeSet: wizardDerivedData.selectedStateCodeSet,
        includeUnsubscribed,
        stateSearch,
        showTerritories,
        scheduleFor,
        scheduledDate,
        minScheduleDate,
    }
    const wizardData: CampaignWizardData = {
        templates,
        selectedTemplate: wizardDerivedData.selectedTemplate,
        stageOptions,
        stagePresetsAvailable: wizardDerivedData.stagePresetsAvailable,
        selectedStageLabels: wizardDerivedData.selectedStageLabels,
        selectedStateLabels: wizardDerivedData.selectedStateLabels,
        visibleStateOptions: wizardDerivedData.visibleStateOptions,
        filteredTerritories: wizardDerivedData.filteredTerritories,
        includeTerritories: wizardDerivedData.includeTerritories,
        normalizedStateSearch: wizardDerivedData.normalizedStateSearch,
        stageById: wizardDerivedData.stageById,
        stateLabelByCode: wizardDerivedData.stateLabelByCode,
        previewTotalCount: previewFilters.data?.total_count || 0,
        previewSampleRecipients: wizardDerivedData.previewSampleRecipients,
        isPreviewLoading: previewFilters.isPending,
    }
    const wizardActions: CampaignWizardActions = {
        resetWizard,
        setWizardStep,
        setCampaignName,
        setCampaignDescription,
        setSelectedTemplateId,
        setRecipientType,
        setSelectedStages,
        setSelectedStates,
        setIncludeUnsubscribed,
        setStateSearch,
        setShowTerritories,
        setScheduleFor,
        setScheduledDate,
        previewRecipients: previewRecipientSelection,
        handleCreateCampaign,
    }
    const wizardPending: CampaignWizardPending = {
        isCreating: createCampaign.isPending,
        isSending: sendCampaign.isPending,
    }
    const dialogState: CampaignDialogState = {
        deleteDialogId,
        cancelDialogId,
        sendNowDialogId,
    }
    const dialogActions: CampaignDialogActions = {
        setDeleteDialogId,
        setCancelDialogId,
        setSendNowDialogId,
        handleDeleteCampaign,
        handleCancelCampaign,
        handleSendNowCampaign,
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            <CampaignsPageHeader onCreateCampaign={() => setShowCreateWizard(true)} />
            <CampaignsListSection
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                campaigns={filteredCampaigns}
                isLoading={isLoading}
                page={page}
                perPage={perPage}
                onPageChange={setPage}
                onCreateCampaign={() => setShowCreateWizard(true)}
                onViewCampaign={(campaignId) => push(`/automation/campaigns/${campaignId}`)}
                onEditCampaign={(campaignId) => push(`/automation/campaigns/${campaignId}?edit=1`)}
                onSendNowCampaign={setSendNowDialogId}
                onDuplicateCampaign={handleDuplicateCampaign}
                onCancelCampaign={setCancelDialogId}
                onDeleteCampaign={setDeleteDialogId}
            />
            <CampaignCreateWizardDialog
                open={showCreateWizard}
                state={wizardState}
                data={wizardData}
                actions={wizardActions}
                pending={wizardPending}
            />
            <CampaignConfirmationDialogs state={dialogState} actions={dialogActions} />
        </div>
    )
}

function CampaignsPageHeader({ onCreateCampaign }: { onCreateCampaign: () => void }) {
    return (
        <div className="border-b bg-card">
            <div className="flex items-center justify-between p-6">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Back to automation"
                        render={<Link href="/automation" />}
                    >
                        <ArrowLeftIcon className="size-4" />
                    </Button>
                    <div>
                        <h1 className="text-2xl font-semibold">Campaigns</h1>
                        <p className="text-sm text-muted-foreground">
                            Send targeted emails to groups of surrogates
                        </p>
                    </div>
                </div>
                <Button onClick={onCreateCampaign}>
                    <PlusIcon className="size-4" />
                    Create Campaign
                </Button>
            </div>
        </div>
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
    onCreateCampaign: () => void
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
                        <CampaignsEmptyState onCreateCampaign={onCreateCampaign} />
                    ) : (
                        <CampaignsTable
                            campaigns={campaigns}
                            page={page}
                            perPage={perPage}
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

function CampaignsEmptyState({ onCreateCampaign }: { onCreateCampaign: () => void }) {
    return (
        <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
                <MailIcon className="size-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium">No campaigns found</h3>
                <p className="text-sm text-muted-foreground mb-4">
                    Create your first campaign to start sending targeted emails
                </p>
                <Button onClick={onCreateCampaign}>
                    <PlusIcon className="size-4" />
                    Create Campaign
                </Button>
            </CardContent>
        </Card>
    )
}

function CampaignsTable({
    campaigns,
    page,
    perPage,
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
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    campaign: CampaignListItem
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
                {campaign.email_template_name || "-"}
            </TableCell>
            <TableCell>
                <div className="flex items-center gap-1">
                    <UsersIcon className="size-4 text-muted-foreground" />
                    {campaign.total_recipients}
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
                {campaign.opened_count}
                <span className="ml-1 text-xs">({openRate}%)</span>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
                {campaign.clicked_count}
                <span className="ml-1 text-xs">({clickRate}%)</span>
            </TableCell>
            <TableCell className="text-muted-foreground text-sm">
                {campaign.scheduled_at
                    ? `Scheduled ${format(parseDateInput(campaign.scheduled_at), "MMM d, yyyy")}`
                    : format(parseDateInput(campaign.created_at), "MMM d, yyyy")}
            </TableCell>
            <TableCell>
                <CampaignActionsMenu
                    campaign={campaign}
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
    onViewCampaign,
    onEditCampaign,
    onSendNowCampaign,
    onDuplicateCampaign,
    onCancelCampaign,
    onDeleteCampaign,
}: {
    campaign: CampaignListItem
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
                {campaign.status === "draft" && (
                    <DropdownMenuItem onClick={() => onSendNowCampaign(campaign.id)}>
                        <SendIcon className="mr-2 size-4" />
                        Send Now
                    </DropdownMenuItem>
                )}
                {(campaign.status === "draft" || campaign.status === "scheduled") && (
                    <DropdownMenuItem onClick={() => onEditCampaign(campaign.id)}>
                        <PencilIcon className="mr-2 size-4" />
                        Edit
                    </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => { void onDuplicateCampaign(campaign.id) }}>
                    <CopyIcon className="mr-2 size-4" />
                    Duplicate
                </DropdownMenuItem>
                {(campaign.status === "scheduled" || campaign.status === "sending") && (
                    <DropdownMenuItem
                        onClick={() => onCancelCampaign(campaign.id)}
                        className="text-destructive"
                    >
                        <TrashIcon className="mr-2 size-4" />
                        Stop
                    </DropdownMenuItem>
                )}
                {campaign.status === "draft" && (
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
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Create Campaign</DialogTitle>
                    <DialogDescription>
                        Step {state.wizardStep} of {TOTAL_STEPS}
                    </DialogDescription>
                </DialogHeader>
                <CampaignWizardProgress wizardStep={state.wizardStep} />
                <CampaignWizardStepContent state={state} data={data} actions={actions} />
                <CampaignWizardFooter state={state} actions={actions} pending={pending} />
            </DialogContent>
        </Dialog>
    )
}

function CampaignWizardProgress({ wizardStep }: { wizardStep: number }) {
    return (
        <div className="flex items-center justify-between py-4">
            {Array.from({ length: TOTAL_STEPS }, (_, index) => index + 1).map((step) => (
                <div key={step} className="flex items-center flex-1 last:flex-none">
                    <div
                        className={`flex size-8 items-center justify-center rounded-full text-sm font-medium shrink-0 ${step <= wizardStep
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground"
                            }`}
                    >
                        {step}
                    </div>
                    {step < TOTAL_STEPS && (
                        <div
                            className={`flex-1 h-0.5 mx-2 ${step < wizardStep ? "bg-primary" : "bg-muted"
                                }`}
                        />
                    )}
                </div>
            ))}
        </div>
    )
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
    return (
        <div className="min-h-[300px]">
            {state.wizardStep === 1 && <CampaignDetailsStep state={state} actions={actions} />}
            {state.wizardStep === 2 && <CampaignTemplateStep state={state} data={data} actions={actions} />}
            {state.wizardStep === 3 && <CampaignRecipientsStep state={state} data={data} actions={actions} />}
            {state.wizardStep === 4 && <CampaignStateFilterStep state={state} data={data} actions={actions} />}
            {state.wizardStep === 5 && <CampaignReviewStep state={state} data={data} />}
            {state.wizardStep === 6 && <CampaignRecipientPreviewStep data={data} actions={actions} />}
            {state.wizardStep === 7 && <CampaignScheduleStep state={state} actions={actions} />}
        </div>
    )
}

function CampaignDetailsStep({
    state,
    actions,
}: {
    state: CampaignWizardState
    actions: CampaignWizardActions
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Campaign Details</h3>
            <div className="space-y-2">
                <Label htmlFor="name">Campaign Name *</Label>
                <Input
                    id="name"
                    placeholder="e.g., March Newsletter"
                    value={state.campaignName}
                    onChange={(event) => actions.setCampaignName(event.target.value)}
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                    id="description"
                    placeholder="Optional description..."
                    value={state.campaignDescription}
                    onChange={(event) => actions.setCampaignDescription(event.target.value)}
                />
            </div>
        </div>
    )
}

function CampaignTemplateStep({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Select Email Template</h3>
            <div className="space-y-2">
                <Label>Template *</Label>
                <Select
                    value={state.selectedTemplateId}
                    onValueChange={(value) => value && actions.setSelectedTemplateId(value)}
                >
                    <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a template">
                            {(value: string | null) => {
                                if (!value) return "Choose a template"
                                const template = data.templates?.find((option) => option.id === value)
                                return template?.name ?? "Choose a template"
                            }}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="min-w-[300px]">
                        {data.templates?.map((template) => (
                            <SelectItem key={template.id} value={template.id}>
                                {template.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>
            {data.selectedTemplate && (
                <Card className="mt-4">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Preview</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-sm">
                            <p className="font-medium text-muted-foreground">Subject:</p>
                            <p className="mb-2">{data.selectedTemplate.subject}</p>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    )
}

function CampaignRecipientsStep({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Recipients</h3>
            <div className="space-y-2">
                <Label>Recipient Type</Label>
                <Select
                    value={state.recipientType}
                    onValueChange={(value) => {
                        if (isRecipientType(value)) {
                            actions.setRecipientType(value)
                            actions.setSelectedStages([])
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
            <CampaignStageFilter state={state} data={data} actions={actions} />
            <div className="rounded-lg border bg-card p-4">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id="include-unsubscribed"
                        checked={state.includeUnsubscribed}
                        onCheckedChange={(checked) =>
                            actions.setIncludeUnsubscribed(checked === true)
                        }
                    />
                    <div className="space-y-1">
                        <Label htmlFor="include-unsubscribed" className="cursor-pointer">
                            Include unsubscribed recipients
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            By default, recipients who opted out of marketing emails are excluded.
                            Enable this only if you have explicit consent. Hard bounces and
                            complaints are always suppressed.
                        </p>
                    </div>
                </div>
            </div>
            <Card className="bg-muted/50">
                <CardContent className="py-4">
                    <p className="text-sm text-muted-foreground">
                        Recipients will be filtered when the campaign is sent. Hard bounces and
                        complaints are always suppressed. Marketing opt-outs are excluded by
                        default (unless enabled above).
                    </p>
                </CardContent>
            </Card>
        </div>
    )
}

function CampaignStageFilter({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    const { selectedStageIdSet } = state

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label>
                    {state.recipientType === "intended_parent"
                        ? "Filter by Status (optional)"
                        : "Filter by Stage (optional)"}
                </Label>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => actions.setSelectedStages(data.stageOptions.map((stage) => stage.id))}
                        disabled={data.stageOptions.length === 0}
                    >
                        Select all
                    </Button>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => actions.setSelectedStages([])}
                        disabled={state.selectedStages.length === 0}
                    >
                        Clear
                    </Button>
                </div>
            </div>
            {data.stagePresetsAvailable.length > 0 && (
                <div className="flex flex-wrap gap-2">
                    {data.stagePresetsAvailable.map((preset) => (
                        <Button
                            key={preset.key}
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => actions.setSelectedStages(preset.stageIds)}
                        >
                            {preset.label}
                        </Button>
                    ))}
                </div>
            )}
            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto border rounded-md p-3">
                {data.stageOptions.map((stage) => (
                    <div key={stage.id} className="flex items-center gap-x-2">
                        <Checkbox
                            id={stage.id}
                            checked={selectedStageIdSet.has(stage.id)}
                            onCheckedChange={(checked) => {
                                actions.setSelectedStages((previousStages) =>
                                    checked
                                        ? [...previousStages, stage.id]
                                        : previousStages.filter((stageId) => stageId !== stage.id)
                                )
                            }}
                        />
                        <Label htmlFor={stage.id} className="text-sm cursor-pointer">
                            <span
                                className="inline-block size-2 rounded-full mr-1.5"
                                style={{ backgroundColor: stage.color }}
                            />
                            {stage.label}
                        </Label>
                    </div>
                ))}
            </div>
            {data.selectedStageLabels.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                    {data.selectedStageLabels.map((label) => (
                        <Badge key={label} variant="secondary" className="text-xs">
                            {label}
                        </Badge>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-muted-foreground">All stages included.</p>
            )}
        </div>
    )
}

function CampaignStateFilterStep({
    state,
    data,
    actions,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    const { selectedStateCodeSet } = state

    return (
        <div className="space-y-4">
            <h3 className="font-medium">Filter by State (optional)</h3>
            <div className="space-y-2">
                <Label htmlFor="state-search">Search states</Label>
                <Input
                    id="state-search"
                    placeholder="Search by state name"
                    value={state.stateSearch}
                    onChange={(event) => actions.setStateSearch(event.target.value)}
                />
            </div>
            <div className="flex flex-wrap items-center gap-2">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                        actions.setSelectedStates((previousStates) => {
                            const next = new Set(previousStates)
                            data.visibleStateOptions.forEach((option) => next.add(option.value))
                            return Array.from(next)
                        })
                    }
                    disabled={data.visibleStateOptions.length === 0}
                >
                    {data.normalizedStateSearch ? "Select results" : "Select all"}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => actions.setSelectedStates([])}
                    disabled={state.selectedStates.length === 0}
                >
                    Clear
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => actions.setShowTerritories((showTerritories) => !showTerritories)}
                >
                    {state.showTerritories ? "Hide territories" : "Show territories"}
                </Button>
            </div>
            <div className="grid grid-cols-3 gap-2 max-h-56 overflow-y-auto border rounded-md p-3">
                {data.visibleStateOptions.length === 0 && (
                    <p className="text-sm text-muted-foreground col-span-3">
                        No states match your search.
                    </p>
                )}
                {data.visibleStateOptions.map((state) => (
                    <div key={state.value} className="flex items-center gap-x-2">
                        <Checkbox
                            id={`state-${state.value}`}
                            checked={selectedStateCodeSet.has(state.value)}
                            onCheckedChange={(checked) => {
                                actions.setSelectedStates((previousStates) =>
                                    checked
                                        ? [...previousStates, state.value]
                                        : previousStates.filter((stateCode) => stateCode !== state.value)
                                )
                            }}
                        />
                        <Label htmlFor={`state-${state.value}`} className="text-sm cursor-pointer">
                            {state.label}
                        </Label>
                    </div>
                ))}
            </div>
            {data.includeTerritories && data.filteredTerritories.length > 0 && (
                <p className="text-xs text-muted-foreground">
                    Territories included in results.
                </p>
            )}
            {data.selectedStateLabels.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                    {data.selectedStateLabels.map((label) => (
                        <Badge key={label} variant="secondary" className="text-xs">
                            {label}
                        </Badge>
                    ))}
                </div>
            ) : (
                <p className="text-xs text-muted-foreground">All states included.</p>
            )}
        </div>
    )
}

function CampaignReviewStep({
    state,
    data,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Review Selection</h3>
            <Card>
                <CardContent className="py-4 space-y-3">
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Campaign Name:</span>
                        <span className="font-medium">{state.campaignName}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Template:</span>
                        <span className="font-medium">{data.selectedTemplate?.name || "-"}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Recipients:</span>
                        <span className="font-medium">
                            {state.recipientType === "case" ? "Surrogates" : "Intended Parents"}
                        </span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Unsubscribed Recipients:</span>
                        <span className="font-medium">
                            {state.includeUnsubscribed ? "Included" : "Excluded"}
                        </span>
                    </div>
                    <CampaignReviewStageSummary state={state} data={data} />
                    <CampaignReviewStateSummary state={state} data={data} />
                </CardContent>
            </Card>
        </div>
    )
}

function CampaignReviewStageSummary({
    state,
    data,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
}) {
    if (state.selectedStages.length === 0) return null

    return (
        <div className="flex justify-between items-start">
            <span className="text-muted-foreground">
                {state.recipientType === "intended_parent"
                    ? "Filtered by Status:"
                    : "Filtered by Stage:"}
            </span>
            <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
                {state.selectedStages.map((stageId) => {
                    const stage = data.stageById.get(stageId)
                    return stage ? (
                        <Badge key={stageId} variant="secondary" className="text-xs">
                            <span className="inline-block size-2 rounded-full mr-1" style={{ backgroundColor: stage.color }} />
                            {stage.label}
                        </Badge>
                    ) : null
                })}
            </div>
        </div>
    )
}

function CampaignReviewStateSummary({
    state,
    data,
}: {
    state: CampaignWizardState
    data: CampaignWizardData
}) {
    if (state.selectedStates.length === 0) return null

    return (
        <div className="flex justify-between items-start">
            <span className="text-muted-foreground">Filtered by State:</span>
            <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
                {state.selectedStates.map((stateCode) => {
                    const label = data.stateLabelByCode.get(stateCode)
                    return label ? (
                        <Badge key={stateCode} variant="secondary" className="text-xs">
                            {label}
                        </Badge>
                    ) : null
                })}
            </div>
        </div>
    )
}

function CampaignRecipientPreviewStep({
    data,
    actions,
}: {
    data: CampaignWizardData
    actions: CampaignWizardActions
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Recipient Preview</h3>
            <RecipientPreviewCard
                totalCount={data.previewTotalCount}
                sampleRecipients={data.previewSampleRecipients}
                isLoading={data.isPreviewLoading}
                onRefresh={actions.previewRecipients}
                maxVisible={3}
            />
        </div>
    )
}

function CampaignScheduleStep({
    state,
    actions,
}: {
    state: CampaignWizardState
    actions: CampaignWizardActions
}) {
    return (
        <div className="space-y-4">
            <h3 className="font-medium">Schedule & Send</h3>
            <div className="space-y-2">
                <p className="text-sm font-medium">When to send?</p>
                <RadioGroup
                    value={state.scheduleFor}
                    onValueChange={(value) => {
                        if (isScheduleFor(value)) {
                            actions.setScheduleFor(value)
                        }
                    }}
                    className="flex gap-4"
                >
                    <div className="flex items-center gap-2">
                        <RadioGroupItem id="campaign-send-now" value="now" />
                        <Label htmlFor="campaign-send-now" className="cursor-pointer">
                            Send now
                        </Label>
                    </div>
                    <div className="flex items-center gap-2">
                        <RadioGroupItem id="campaign-send-later" value="later" />
                        <Label htmlFor="campaign-send-later" className="cursor-pointer">
                            Schedule for later
                        </Label>
                    </div>
                </RadioGroup>
            </div>
            {state.scheduleFor === "later" && (
                <div className="space-y-2">
                    <Label htmlFor="scheduled-date">Scheduled Date & Time</Label>
                    <Input
                        id="scheduled-date"
                        type="datetime-local"
                        min={state.minScheduleDate}
                        value={state.scheduledDate}
                        onChange={(event) => actions.setScheduledDate(event.target.value)}
                    />
                </div>
            )}
            <Card className="bg-green-50 dark:bg-green-950/20 border-green-200">
                <CardContent className="py-4 flex items-center gap-3">
                    <CheckCircle2Icon className="size-5 text-green-600" />
                    <span className="text-sm text-green-700 dark:text-green-400">
                        Campaign is ready to {state.scheduleFor === "now" ? "send" : "schedule"}
                    </span>
                </CardContent>
            </Card>
        </div>
    )
}

function CampaignWizardFooter({
    state,
    actions,
    pending,
}: {
    state: CampaignWizardState
    actions: CampaignWizardActions
    pending: CampaignWizardPending
}) {
    const goToStep = (nextStep: number) => {
        actions.setWizardStep(nextStep)
        if (nextStep === 6) {
            actions.previewRecipients()
        }
    }

    return (
        <DialogFooter className="gap-2">
            <Button variant="outline" onClick={actions.resetWizard}>
                Cancel
            </Button>
            {state.wizardStep > 1 && (
                <Button
                    variant="outline"
                    onClick={() => actions.setWizardStep((previousStep) => previousStep - 1)}
                >
                    Back
                </Button>
            )}
            {(state.wizardStep === 3 || state.wizardStep === 4) && (
                <Button
                    variant="ghost"
                    onClick={() => {
                        if (state.wizardStep === 3) {
                            actions.setSelectedStages([])
                        }
                        if (state.wizardStep === 4) {
                            actions.setSelectedStates([])
                        }
                        goToStep(state.wizardStep + 1)
                    }}
                >
                    Skip
                </Button>
            )}
            {state.wizardStep < TOTAL_STEPS ? (
                <Button
                    onClick={() => goToStep(state.wizardStep + 1)}
                    disabled={
                        (state.wizardStep === 1 && !state.campaignName) ||
                        (state.wizardStep === 2 && !state.selectedTemplateId)
                    }
                >
                    Next
                </Button>
            ) : (
                <Button
                    onClick={() => { void actions.handleCreateCampaign() }}
                    disabled={
                        pending.isCreating ||
                        pending.isSending ||
                        (state.scheduleFor === "later" && !state.scheduledDate)
                    }
                >
                    {pending.isCreating || pending.isSending ? (
                        <Loader2Icon className="size-4 animate-spin" />
                    ) : state.scheduleFor === "now" ? (
                        <>
                            <SendIcon className="size-4" />
                            Send Campaign
                        </>
                    ) : (
                        <>
                            <CalendarIcon className="size-4" />
                            Schedule Campaign
                        </>
                    )}
                </Button>
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
    return (
        <>
            <AlertDialog
                open={!!state.deleteDialogId}
                onOpenChange={(open) => !open && actions.setDeleteDialogId(null)}
            >
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
                            onClick={() => { void actions.handleDeleteCampaign() }}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Delete
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={!!state.cancelDialogId}
                onOpenChange={(open) => !open && actions.setCancelDialogId(null)}
            >
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
                            onClick={() => { void actions.handleCancelCampaign() }}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Stop
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog
                open={!!state.sendNowDialogId}
                onOpenChange={(open) => !open && actions.setSendNowDialogId(null)}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Send Campaign Now</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will immediately start sending this campaign. You can stop it once it begins, but some emails may still deliver.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => { void actions.handleSendNowCampaign() }}>
                            Send now
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}
