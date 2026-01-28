"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { BrainIcon, CopyIcon, Loader2Icon, MailIcon, SparklesIcon } from "lucide-react"
import type { DraftEmailResponse, EmailType, SummarizeSurrogateResponse } from "@/lib/api/ai"

const DEFAULT_EMAIL_TYPES: EmailType[] = [
    "follow_up",
    "status_update",
    "meeting_request",
    "document_request",
    "introduction",
]

type SurrogateAiTabProps = {
    aiSettings: { is_enabled?: boolean } | null | undefined
    aiSummary: SummarizeSurrogateResponse | null
    aiDraftEmail: DraftEmailResponse | null
    selectedEmailType: EmailType | null
    onSelectEmailType: (value: EmailType) => void
    onGenerateSummary: () => void
    onDraftEmail: () => void
    isGeneratingSummary: boolean
    isDraftingEmail: boolean
    emailTypes?: EmailType[]
}

export function SurrogateAiTab({
    aiSettings,
    aiSummary,
    aiDraftEmail,
    selectedEmailType,
    onSelectEmailType,
    onGenerateSummary,
    onDraftEmail,
    isGeneratingSummary,
    isDraftingEmail,
    emailTypes = DEFAULT_EMAIL_TYPES,
}: SurrogateAiTabProps) {
    if (aiSettings && !aiSettings.is_enabled) {
        return (
            <Card>
                <CardContent className="pt-6">
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                        <BrainIcon className="mb-4 h-12 w-12 text-muted-foreground" />
                        <h3 className="text-lg font-medium">AI Assistant Not Enabled</h3>
                        <p className="mt-2 max-w-md text-sm text-muted-foreground">
                            Contact your admin to enable AI features and configure an API key in
                            Settings.
                        </p>
                    </div>
                </CardContent>
            </Card>
        )
    }

    return (
        <div className="grid gap-4 md:grid-cols-2">
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <SparklesIcon className="h-4 w-4" />
                        Surrogate Summary
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Button
                        onClick={onGenerateSummary}
                        disabled={isGeneratingSummary}
                        className="w-full"
                    >
                        {isGeneratingSummary ? (
                            <>
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" /> Generating...
                            </>
                        ) : (
                            <>
                                <SparklesIcon className="mr-2 h-4 w-4" /> Generate Summary
                            </>
                        )}
                    </Button>

                    {aiSummary && (
                        <div className="space-y-4 border-t pt-4">
                            <div>
                                <h4 className="mb-1 text-sm font-medium">Summary</h4>
                                <p className="text-sm text-muted-foreground">{aiSummary.summary}</p>
                            </div>
                            <div>
                                <h4 className="mb-1 text-sm font-medium">Recent Activity</h4>
                                <p className="text-sm text-muted-foreground">
                                    {aiSummary.recent_activity}
                                </p>
                            </div>
                            {aiSummary.suggested_next_steps.length > 0 && (
                                <div>
                                    <h4 className="mb-1 text-sm font-medium">
                                        Suggested Next Steps
                                    </h4>
                                    <ul className="space-y-1 text-sm text-muted-foreground">
                                        {aiSummary.suggested_next_steps.map((step, i) => (
                                            <li key={i} className="flex items-start gap-2">
                                                <span className="text-primary">•</span>
                                                {step}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {aiSummary.pending_tasks.length > 0 && (
                                <div>
                                    <h4 className="mb-1 text-sm font-medium">Pending Tasks</h4>
                                    <ul className="space-y-1 text-sm text-muted-foreground">
                                        {aiSummary.pending_tasks.map((task) => (
                                            <li key={task.id} className="flex items-center gap-2">
                                                <Badge variant="secondary" className="text-xs">
                                                    {task.due_date || "No due date"}
                                                </Badge>
                                                {task.title}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <MailIcon className="h-4 w-4" />
                        Draft Email
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                        {emailTypes.map((emailType) => {
                            const label =
                                emailType === "meeting_request"
                                    ? "appointment request"
                                    : emailType.replace(/_/g, " ")
                            return (
                                <Button
                                    key={emailType}
                                    variant={selectedEmailType === emailType ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => onSelectEmailType(emailType)}
                                    className="text-xs capitalize"
                                >
                                    {label}
                                </Button>
                            )
                        })}
                    </div>

                    <Button
                        onClick={onDraftEmail}
                        disabled={!selectedEmailType || isDraftingEmail}
                        className="w-full"
                    >
                        {isDraftingEmail ? (
                            <>
                                <Loader2Icon className="mr-2 h-4 w-4 animate-spin" /> Drafting...
                            </>
                        ) : (
                            <>
                                <MailIcon className="mr-2 h-4 w-4" /> Draft Email
                            </>
                        )}
                    </Button>

                    {aiDraftEmail && (
                        <div className="space-y-3 border-t pt-4">
                            <div>
                                <h4 className="mb-1 text-sm font-medium">To</h4>
                                <p className="text-sm text-muted-foreground">
                                    {aiDraftEmail.recipient_name} &lt;
                                    {aiDraftEmail.recipient_email}&gt;
                                </p>
                            </div>
                            <div>
                                <h4 className="mb-1 text-sm font-medium">Subject</h4>
                                <p className="text-sm text-muted-foreground">
                                    {aiDraftEmail.subject}
                                </p>
                            </div>
                            <div>
                                <h4 className="mb-1 text-sm font-medium">Body</h4>
                                <div className="max-h-64 whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
                                    {aiDraftEmail.body}
                                </div>
                            </div>
                            <div className="flex gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                        navigator.clipboard.writeText(
                                            `Subject: ${aiDraftEmail.subject}\n\n${aiDraftEmail.body}`
                                        )
                                    }}
                                >
                                    <CopyIcon className="mr-1 h-3 w-3" /> Copy
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={() => {
                                        window.open(
                                            `mailto:${aiDraftEmail.recipient_email}?subject=${encodeURIComponent(
                                                aiDraftEmail.subject
                                            )}&body=${encodeURIComponent(aiDraftEmail.body)}`
                                        )
                                    }}
                                >
                                    <MailIcon className="mr-1 h-3 w-3" /> Open in Email
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
