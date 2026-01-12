"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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
    ArrowLeftIcon,
    UsersIcon,
    SendIcon,
    CheckCircle2Icon,
    MousePointerClickIcon,
    CopyIcon,
    TrashIcon,
    LoaderIcon,
    ChevronDownIcon,
    ChevronUpIcon,
    MailIcon,
} from "lucide-react"
import { format } from "date-fns"
import { toast } from "sonner"
import {
    useCampaign,
    useCampaignRuns,
    useRunRecipients,
    useDeleteCampaign,
    useDuplicateCampaign,
} from "@/lib/hooks/use-campaigns"
import { useEmailTemplate } from "@/lib/hooks/use-email-templates"

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

    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [showTemplatePreview, setShowTemplatePreview] = useState(true)

    // API hooks
    const { data: campaign, isLoading } = useCampaign(campaignId)
    const { data: runs } = useCampaignRuns(campaignId)
    const latestRun = runs?.[0]
    const { data: recipients } = useRunRecipients(
        campaignId,
        latestRun?.id,
        { limit: 50 }
    )
    const { data: template } = useEmailTemplate(campaign?.email_template_id ?? null)

    const deleteCampaign = useDeleteCampaign()
    const duplicateCampaign = useDuplicateCampaign()

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

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <LoaderIcon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!campaign) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center gap-4">
                <h2 className="text-xl font-semibold">Campaign not found</h2>
                <Link href="/automation/campaigns">
                    <Button variant="outline">Back to Campaigns</Button>
                </Link>
            </div>
        )
    }

    // Calculate percentages
    const totalRecipients = campaign.total_recipients || 0
    const sentPercent = totalRecipients > 0 ? Math.round((campaign.sent_count / totalRecipients) * 100) : 0
    const openedCount = campaign.opened_count || 0
    const clickedCount = campaign.clicked_count || 0
    const openPercent = campaign.sent_count > 0 ? Math.round((openedCount / campaign.sent_count) * 100) : 0
    const clickPercent = campaign.sent_count > 0 ? Math.round((clickedCount / campaign.sent_count) * 100) : 0

    return (
        <div className="flex min-h-screen flex-col bg-background">
            {/* Header */}
            <div className="border-b bg-card">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-4">
                        <Link href="/automation/campaigns">
                            <Button variant="ghost" size="icon-sm">
                                <ArrowLeftIcon className="size-4" />
                            </Button>
                        </Link>
                        <div>
                            <div className="flex items-center gap-3">
                                <h1 className="text-2xl font-bold">{campaign.name}</h1>
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
                            <div className="text-3xl font-bold">{totalRecipients}</div>
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
                            <div className="text-3xl font-bold">{campaign.sent_count}</div>
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
                            <div className="text-3xl font-bold text-green-600">{openedCount}</div>
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
                            <div className="text-3xl font-bold text-blue-600">{clickedCount}</div>
                            <p className="text-sm text-muted-foreground">{clickPercent}% of sent</p>
                        </CardContent>
                    </Card>
                </div>

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
                        <CardTitle>Recipients</CardTitle>
                        <CardDescription>
                            {latestRun
                                ? `Last run: ${format(new Date(latestRun.started_at), "MMM d, yyyy 'at' h:mm a")}`
                                : "No runs yet"}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
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
        </div>
    )
}
