"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
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
    LoaderIcon,
    ArrowLeftIcon,
    CalendarIcon,
    EyeIcon,
} from "lucide-react"
import { format } from "date-fns"
import { toast } from "sonner"
import {
    useCampaigns,
    useCreateCampaign,
    useDeleteCampaign,
    useDuplicateCampaign,
    useSendCampaign,
    useCampaignPreview,
} from "@/lib/hooks/use-campaigns"
import { useEmailTemplates } from "@/lib/hooks/use-email-templates"
import { getDefaultPipeline } from "@/lib/api/pipelines"
import { useQuery } from "@tanstack/react-query"
import type { CampaignListItem } from "@/lib/api/campaigns"

// Status badge styles
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

export default function CampaignsPage() {
    const router = useRouter()
    const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
    const [showCreateWizard, setShowCreateWizard] = useState(false)

    // Wizard state
    const [wizardStep, setWizardStep] = useState(1)
    const [campaignName, setCampaignName] = useState("")
    const [campaignDescription, setCampaignDescription] = useState("")
    const [selectedTemplateId, setSelectedTemplateId] = useState("")
    const [recipientType, setRecipientType] = useState<"case" | "intended_parent">("case")
    const [selectedStages, setSelectedStages] = useState<string[]>([])
    const [selectedStates, setSelectedStates] = useState<string[]>([])
    const [scheduleFor, setScheduleFor] = useState<"now" | "later">("now")
    const [scheduledDate, setScheduledDate] = useState("")
    const [previewCampaignId, setPreviewCampaignId] = useState<string | null>(null)

    // API hooks
    const { data: campaigns, isLoading } = useCampaigns(statusFilter)
    const { data: templates } = useEmailTemplates()
    const createCampaign = useCreateCampaign()
    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()
    const sendCampaign = useSendCampaign()

    // Fetch pipeline stages for status filter
    const { data: pipeline } = useQuery({
        queryKey: ["defaultPipeline"],
        queryFn: getDefaultPipeline,
    })
    const pipelineStages = pipeline?.stages || []

    // Filtered campaigns
    const filteredCampaigns = campaigns || []

    const resetWizard = () => {
        setWizardStep(1)
        setCampaignName("")
        setCampaignDescription("")
        setSelectedTemplateId("")
        setRecipientType("case")
        setSelectedStages([])
        setSelectedStates([])
        setScheduleFor("now")
        setScheduledDate("")
        setShowCreateWizard(false)
        setPreviewCampaignId(null)
    }

    const handleCreateCampaign = async () => {
        if (!campaignName || !selectedTemplateId) {
            toast.error("Please fill in required fields")
            return
        }

        try {
            const campaign = await createCampaign.mutateAsync({
                name: campaignName,
                description: campaignDescription || undefined,
                email_template_id: selectedTemplateId,
                recipient_type: recipientType,
                filter_criteria: {
                    stage_ids: selectedStages.length > 0 ? selectedStages : undefined,
                    states: selectedStates.length > 0 ? selectedStates : undefined,
                },
                scheduled_at: scheduleFor === "later" && scheduledDate ? new Date(scheduledDate).toISOString() : undefined,
            })

            toast.success("Campaign created successfully")

            if (scheduleFor === "now") {
                // Send immediately
                try {
                    await sendCampaign.mutateAsync({ id: campaign.id, sendNow: true })
                    toast.success("Campaign queued for sending")
                } catch {
                    toast.error("Campaign created but failed to start sending")
                }
            }

            resetWizard()
        } catch {
            toast.error("Failed to create campaign")
        }
    }

    const handleDeleteCampaign = async (id: string) => {
        if (!confirm("Are you sure you want to delete this campaign?")) return

        try {
            await deleteCampaign.mutateAsync(id)
            toast.success("Campaign deleted")
        } catch {
            toast.error("Failed to delete campaign. Only drafts can be deleted.")
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

    const selectedTemplate = templates?.find(t => t.id === selectedTemplateId)

    return (
        <div className="flex min-h-screen flex-col bg-background">
            {/* Header */}
            <div className="border-b bg-card">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-4">
                        <Link href="/automation">
                            <Button variant="ghost" size="icon-sm">
                                <ArrowLeftIcon className="size-4" />
                            </Button>
                        </Link>
                        <div>
                            <h1 className="text-2xl font-bold">Campaigns</h1>
                            <p className="text-sm text-muted-foreground">
                                Send targeted emails to groups of cases
                            </p>
                        </div>
                    </div>
                    <Button onClick={() => setShowCreateWizard(true)}>
                        <PlusIcon className="size-4" />
                        Create Campaign
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                {/* Filter Tabs */}
                <Tabs value={statusFilter || "all"} onValueChange={(v) => setStatusFilter(v === "all" ? undefined : v)} className="space-y-6">
                    <TabsList>
                        <TabsTrigger value="all">All</TabsTrigger>
                        <TabsTrigger value="draft">Draft</TabsTrigger>
                        <TabsTrigger value="scheduled">Scheduled</TabsTrigger>
                        <TabsTrigger value="sending">Sending</TabsTrigger>
                        <TabsTrigger value="completed">Sent</TabsTrigger>
                    </TabsList>

                    <TabsContent value={statusFilter || "all"} className="space-y-4">
                        {isLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
                            </div>
                        ) : filteredCampaigns.length === 0 ? (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-12">
                                    <MailIcon className="size-12 text-muted-foreground mb-4" />
                                    <h3 className="text-lg font-medium">No campaigns found</h3>
                                    <p className="text-sm text-muted-foreground mb-4">
                                        Create your first campaign to start sending targeted emails
                                    </p>
                                    <Button onClick={() => setShowCreateWizard(true)}>
                                        <PlusIcon className="size-4" />
                                        Create Campaign
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <Card className="py-0">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Campaign Name</TableHead>
                                            <TableHead>Template</TableHead>
                                            <TableHead>Recipients</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Sent / Failed</TableHead>
                                            <TableHead>Date</TableHead>
                                            <TableHead className="w-[50px]"></TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredCampaigns.map((campaign) => (
                                            <TableRow key={campaign.id}>
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
                                                <TableCell className="text-muted-foreground text-sm">
                                                    {campaign.scheduled_at
                                                        ? `Scheduled ${format(new Date(campaign.scheduled_at), "MMM d, yyyy")}`
                                                        : format(new Date(campaign.created_at), "MMM d, yyyy")}
                                                </TableCell>
                                                <TableCell>
                                                    <DropdownMenu>
                                                        <DropdownMenuTrigger>
                                                            <Button variant="ghost" size="icon-sm">
                                                                <MoreVerticalIcon className="size-4" />
                                                            </Button>
                                                        </DropdownMenuTrigger>
                                                        <DropdownMenuContent align="end">
                                                            <DropdownMenuItem
                                                                onClick={() => router.push(`/automation/campaigns/${campaign.id}`)}
                                                            >
                                                                <EyeIcon className="mr-2 size-4" />
                                                                View Details
                                                            </DropdownMenuItem>
                                                            <DropdownMenuItem onClick={() => handleDuplicateCampaign(campaign.id)}>
                                                                <CopyIcon className="mr-2 size-4" />
                                                                Duplicate
                                                            </DropdownMenuItem>
                                                            {campaign.status === "draft" && (
                                                                <DropdownMenuItem
                                                                    onClick={() => handleDeleteCampaign(campaign.id)}
                                                                    className="text-destructive"
                                                                >
                                                                    <TrashIcon className="mr-2 size-4" />
                                                                    Delete
                                                                </DropdownMenuItem>
                                                            )}
                                                        </DropdownMenuContent>
                                                    </DropdownMenu>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </Card>
                        )}
                    </TabsContent>
                </Tabs>
            </div>

            {/* Create Campaign Wizard */}
            <Dialog open={showCreateWizard} onOpenChange={(open) => !open && resetWizard()}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>Create Campaign</DialogTitle>
                        <DialogDescription>
                            Step {wizardStep} of 4
                        </DialogDescription>
                    </DialogHeader>

                    {/* Progress Indicator */}
                    <div className="flex items-center gap-2 py-4">
                        {[1, 2, 3, 4].map((step) => (
                            <div key={step} className="flex items-center flex-1">
                                <div
                                    className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${step <= wizardStep
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-muted text-muted-foreground"
                                        }`}
                                >
                                    {step}
                                </div>
                                {step < 4 && (
                                    <div
                                        className={`flex-1 h-0.5 mx-2 ${step < wizardStep ? "bg-primary" : "bg-muted"
                                            }`}
                                    />
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Step Content */}
                    <div className="min-h-[300px]">
                        {wizardStep === 1 && (
                            <div className="space-y-4">
                                <h3 className="font-medium">Campaign Details</h3>
                                <div className="space-y-2">
                                    <Label htmlFor="name">Campaign Name *</Label>
                                    <Input
                                        id="name"
                                        placeholder="e.g., March Newsletter"
                                        value={campaignName}
                                        onChange={(e) => setCampaignName(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="description">Description</Label>
                                    <Textarea
                                        id="description"
                                        placeholder="Optional description..."
                                        value={campaignDescription}
                                        onChange={(e) => setCampaignDescription(e.target.value)}
                                    />
                                </div>
                            </div>
                        )}

                        {wizardStep === 2 && (
                            <div className="space-y-4">
                                <h3 className="font-medium">Select Email Template</h3>
                                <div className="space-y-2">
                                    <Label>Template *</Label>
                                    <Select
                                        value={selectedTemplateId}
                                        onValueChange={(v) => v && setSelectedTemplateId(v)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Choose a template" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {templates?.map((template) => (
                                                <SelectItem key={template.id} value={template.id}>
                                                    {template.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                {selectedTemplate && (
                                    <Card className="mt-4">
                                        <CardHeader className="pb-2">
                                            <CardTitle className="text-sm">Preview</CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="text-sm">
                                                <p className="font-medium text-muted-foreground">Subject:</p>
                                                <p className="mb-2">{selectedTemplate.subject}</p>
                                            </div>
                                        </CardContent>
                                    </Card>
                                )}
                            </div>
                        )}

                        {wizardStep === 3 && (
                            <div className="space-y-4">
                                <h3 className="font-medium">Recipients</h3>
                                <div className="space-y-2">
                                    <Label>Recipient Type</Label>
                                    <Select
                                        value={recipientType}
                                        onValueChange={(v) => setRecipientType(v as "case" | "intended_parent")}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="case">Cases (Surrogates)</SelectItem>
                                            <SelectItem value="intended_parent">Intended Parents</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Filter by Status</Label>
                                    <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
                                        {pipelineStages.filter(s => s.is_active).map((stage) => (
                                            <div key={stage.id} className="flex items-center space-x-2">
                                                <Checkbox
                                                    id={stage.id}
                                                    checked={selectedStages.includes(stage.id)}
                                                    onCheckedChange={(checked) => {
                                                        if (checked) {
                                                            setSelectedStages([...selectedStages, stage.id])
                                                        } else {
                                                            setSelectedStages(selectedStages.filter((s) => s !== stage.id))
                                                        }
                                                    }}
                                                />
                                                <Label htmlFor={stage.id} className="text-sm">
                                                    <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ backgroundColor: stage.color }} />
                                                    {stage.label}
                                                </Label>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <Card className="bg-muted/50">
                                    <CardContent className="py-4">
                                        <p className="text-sm text-muted-foreground">
                                            Recipients will be filtered when the campaign is sent.
                                            Suppressed emails (opt-outs, bounces) are automatically excluded.
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>
                        )}

                        {wizardStep === 4 && (
                            <div className="space-y-4">
                                <h3 className="font-medium">Review & Send</h3>
                                <Card>
                                    <CardContent className="py-4 space-y-3">
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Campaign Name:</span>
                                            <span className="font-medium">{campaignName}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Template:</span>
                                            <span className="font-medium">{selectedTemplate?.name || "-"}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-muted-foreground">Recipients:</span>
                                            <span className="font-medium capitalize">{recipientType.replace(/_/g, " ")}s</span>
                                        </div>
                                        {selectedStages.length > 0 && (
                                            <div className="flex justify-between items-start">
                                                <span className="text-muted-foreground">Filtered by Status:</span>
                                                <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
                                                    {selectedStages.map((stageId) => {
                                                        const stage = pipelineStages.find(s => s.id === stageId)
                                                        return stage ? (
                                                            <Badge key={stageId} variant="secondary" className="text-xs">
                                                                <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ backgroundColor: stage.color }} />
                                                                {stage.label}
                                                            </Badge>
                                                        ) : null
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>

                                <Card className="bg-blue-50 dark:bg-blue-950/20 border-blue-200">
                                    <CardContent className="py-4 flex items-center gap-3">
                                        <UsersIcon className="size-5 text-blue-600" />
                                        <span className="text-sm text-blue-700 dark:text-blue-400">
                                            Recipient count will be calculated when the campaign is created.
                                            Each recipient receives an individual email (no CC list exposure).
                                        </span>
                                    </CardContent>
                                </Card>

                                <div className="space-y-2">
                                    <Label>When to send?</Label>
                                    <div className="flex gap-4">
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="schedule"
                                                checked={scheduleFor === "now"}
                                                onChange={() => setScheduleFor("now")}
                                                className="accent-primary"
                                            />
                                            <span>Send now</span>
                                        </label>
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input
                                                type="radio"
                                                name="schedule"
                                                checked={scheduleFor === "later"}
                                                onChange={() => setScheduleFor("later")}
                                                className="accent-primary"
                                            />
                                            <span>Schedule for later</span>
                                        </label>
                                    </div>
                                </div>

                                {scheduleFor === "later" && (
                                    <div className="space-y-2">
                                        <Label htmlFor="scheduled-date">Scheduled Date & Time</Label>
                                        <Input
                                            id="scheduled-date"
                                            type="datetime-local"
                                            value={scheduledDate}
                                            onChange={(e) => setScheduledDate(e.target.value)}
                                        />
                                    </div>
                                )}

                                <Card className="bg-green-50 dark:bg-green-950/20 border-green-200">
                                    <CardContent className="py-4 flex items-center gap-3">
                                        <CheckCircle2Icon className="size-5 text-green-600" />
                                        <span className="text-sm text-green-700 dark:text-green-400">
                                            Campaign is ready to {scheduleFor === "now" ? "send" : "schedule"}
                                        </span>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="gap-2">
                        <Button variant="outline" onClick={resetWizard}>
                            Cancel
                        </Button>
                        {wizardStep > 1 && (
                            <Button variant="outline" onClick={() => setWizardStep(wizardStep - 1)}>
                                Back
                            </Button>
                        )}
                        {wizardStep < 4 ? (
                            <Button
                                onClick={() => setWizardStep(wizardStep + 1)}
                                disabled={
                                    (wizardStep === 1 && !campaignName) ||
                                    (wizardStep === 2 && !selectedTemplateId)
                                }
                            >
                                Next
                            </Button>
                        ) : (
                            <Button
                                onClick={handleCreateCampaign}
                                disabled={createCampaign.isPending || sendCampaign.isPending}
                            >
                                {createCampaign.isPending || sendCampaign.isPending ? (
                                    <LoaderIcon className="size-4 animate-spin" />
                                ) : scheduleFor === "now" ? (
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
                </DialogContent>
            </Dialog>
        </div>
    )
}
