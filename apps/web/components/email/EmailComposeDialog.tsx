"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { EyeIcon, EyeOffIcon, SendIcon, Loader2Icon } from "lucide-react"
import { useEmailTemplates, useEmailTemplate, useSendEmail } from "@/lib/hooks/use-email-templates"

interface EmailComposeDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    caseData: {
        id: string
        email: string
        full_name: string
        case_number: string
        status: string
        state?: string
    }
    onSuccess?: () => void
}

export function EmailComposeDialog({
    open,
    onOpenChange,
    caseData,
    onSuccess,
}: EmailComposeDialogProps) {
    const [selectedTemplate, setSelectedTemplate] = React.useState<string>("")
    const [subject, setSubject] = React.useState("")
    const [body, setBody] = React.useState("")
    const [isPreview, setIsPreview] = React.useState(false)

    // Fetch email templates list
    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates(true)
    // Fetch full template when one is selected
    const { data: fullTemplate } = useEmailTemplate(selectedTemplate || null)
    const sendEmailMutation = useSendEmail()

    // Update subject and body when full template loads
    React.useEffect(() => {
        if (fullTemplate) {
            setSubject(fullTemplate.subject)
            setBody(fullTemplate.body)
        }
    }, [fullTemplate])

    // Reset form when dialog closes
    React.useEffect(() => {
        if (!open) {
            setSelectedTemplate("")
            setSubject("")
            setBody("")
            setIsPreview(false)
        }
    }, [open])

    const handleSend = async () => {
        try {
            await sendEmailMutation.mutateAsync({
                template_id: selectedTemplate,
                recipient_email: caseData.email,
                case_id: caseData.id,
                variables: {
                    "case.full_name": caseData.full_name,
                    "case.case_number": caseData.case_number,
                    "case.status": caseData.status,
                    "case.state": caseData.state || "",
                },
            })
            onSuccess?.()
            onOpenChange(false)
        } catch (error) {
            console.error("Failed to send email:", error)
        }
    }

    const handleCancel = () => {
        onOpenChange(false)
    }

    // Replace variables with case data for preview
    const renderPreview = (text: string) => {
        return text
            .replace(/\{\{case\.full_name\}\}/g, caseData.full_name)
            .replace(/\{\{case\.case_number\}\}/g, caseData.case_number)
            .replace(/\{\{case\.status\}\}/g, caseData.status)
            .replace(/\{\{case\.state\}\}/g, caseData.state || "")
    }

    // Highlight variables in edit mode
    const renderWithHighlights = (text: string) => {
        const parts = text.split(/(\{\{[^}]+\}\})/g)
        return parts.map((part, index) => {
            if (part.match(/\{\{[^}]+\}\}/)) {
                return (
                    <span key={index} className="bg-teal-500/20 text-teal-400 px-1 py-0.5 rounded font-medium">
                        {part}
                    </span>
                )
            }
            return <span key={index}>{part}</span>
        })
    }

    const availableVariables = [
        "{{case.full_name}}",
        "{{case.case_number}}",
        "{{case.status}}",
        "{{case.state}}",
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Send Email</DialogTitle>
                    <DialogDescription>Compose and send an email to {caseData.full_name}</DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    {/* Template Selector */}
                    <div className="grid gap-2">
                        <Label htmlFor="template">Email Template</Label>
                        <Select value={selectedTemplate} onValueChange={setSelectedTemplate} disabled={templatesLoading}>
                            <SelectTrigger id="template">
                                <SelectValue placeholder={templatesLoading ? "Loading templates..." : "Select a template..."} />
                            </SelectTrigger>
                            <SelectContent>
                                {templates.map((template) => (
                                    <SelectItem key={template.id} value={template.id}>
                                        {template.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Recipient Email (Read-only) */}
                    <div className="grid gap-2">
                        <Label htmlFor="recipient">To</Label>
                        <Input
                            id="recipient"
                            value={caseData.email}
                            readOnly
                            className="bg-muted/50 cursor-not-allowed"
                        />
                    </div>

                    {/* Subject Line */}
                    <div className="grid gap-2">
                        <Label htmlFor="subject">Subject</Label>
                        <Input
                            id="subject"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            placeholder="Enter email subject..."
                        />
                        {!isPreview && subject && (
                            <div className="text-xs text-muted-foreground">{renderWithHighlights(subject)}</div>
                        )}
                    </div>

                    {/* Body with Preview Toggle */}
                    <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                            <Label htmlFor="body">Message</Label>
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => setIsPreview(!isPreview)}
                                className="h-7 gap-2"
                                disabled={!body}
                            >
                                {isPreview ? (
                                    <>
                                        <EyeOffIcon className="size-4" />
                                        Edit
                                    </>
                                ) : (
                                    <>
                                        <EyeIcon className="size-4" />
                                        Preview
                                    </>
                                )}
                            </Button>
                        </div>

                        {isPreview ? (
                            <div className="border-input bg-muted/30 min-h-48 rounded-xl border px-4 py-3 text-sm whitespace-pre-wrap">
                                {renderPreview(subject ? `Subject: ${subject}\n\n` : "")}
                                {renderPreview(body)}
                            </div>
                        ) : (
                            <>
                                <Textarea
                                    id="body"
                                    value={body}
                                    onChange={(e) => setBody(e.target.value)}
                                    placeholder="Enter email message..."
                                    className="min-h-48 font-mono text-sm"
                                />
                                {body && (
                                    <div className="bg-muted/30 rounded-lg px-3 py-2 text-xs">
                                        <div className="font-medium mb-2 text-muted-foreground">Available Variables:</div>
                                        <div className="flex flex-wrap gap-2">
                                            {availableVariables.map((variable) => (
                                                <code key={variable} className="bg-teal-500/20 text-teal-400 px-2 py-1 rounded text-xs">
                                                    {variable}
                                                </code>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    {/* Error Message */}
                    {sendEmailMutation.isError && (
                        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg text-sm">
                            Failed to send email. Please try again.
                        </div>
                    )}

                    {/* Success Message */}
                    {sendEmailMutation.isSuccess && (
                        <div className="bg-green-500/10 text-green-600 dark:text-green-400 px-4 py-3 rounded-lg text-sm">
                            Email sent successfully!
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        type="button"
                        variant="outline"
                        onClick={handleCancel}
                        disabled={sendEmailMutation.isPending}
                    >
                        Cancel
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSend}
                        disabled={!selectedTemplate || !subject || !body || sendEmailMutation.isPending}
                        className="gap-2"
                    >
                        {sendEmailMutation.isPending ? (
                            <>
                                <Loader2Icon className="size-4 animate-spin" />
                                Sending...
                            </>
                        ) : (
                            <>
                                <SendIcon className="size-4" />
                                Send Email
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
