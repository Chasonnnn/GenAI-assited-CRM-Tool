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
import { useEmailTemplates, useEmailTemplate } from "@/lib/hooks/use-email-templates"
import { useSendSurrogateEmail } from "@/lib/hooks/use-surrogates"

interface EmailComposeDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    surrogateData: {
        id: string
        email: string
        full_name: string
        surrogate_number: string
        status: string
        state?: string
        phone?: string
    }
    onSuccess?: () => void
}

export function EmailComposeDialog({
    open,
    onOpenChange,
    surrogateData,
    onSuccess,
}: EmailComposeDialogProps) {
    const [selectedTemplate, setSelectedTemplate] = React.useState<string>("")
    const [subject, setSubject] = React.useState("")
    const [body, setBody] = React.useState("")
    const [isPreview, setIsPreview] = React.useState(false)
    const idempotencyKeyRef = React.useRef<string | null>(null)

    // Fetch email templates list
    const { data: templates = [], isLoading: templatesLoading } = useEmailTemplates({ activeOnly: true })
    // Fetch full template when one is selected
    const { data: fullTemplate } = useEmailTemplate(selectedTemplate || null)
    const sendEmailMutation = useSendSurrogateEmail()

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
            idempotencyKeyRef.current = null
        }
    }, [open])

    const handleSend = async () => {
        try {
            if (!idempotencyKeyRef.current) {
                idempotencyKeyRef.current =
                    typeof crypto !== "undefined" && "randomUUID" in crypto
                        ? crypto.randomUUID()
                        : `${Date.now()}-${Math.random().toString(16).slice(2)}`
            }
            await sendEmailMutation.mutateAsync({
                surrogateId: surrogateData.id,
                data: {
                    template_id: selectedTemplate,
                    subject,
                    body,
                    idempotency_key: idempotencyKeyRef.current,
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

    // Replace variables with surrogate data for preview
    const renderPreview = (text: string) => {
        return text
            .replace(/\{\{full_name\}\}/g, surrogateData.full_name)
            .replace(/\{\{surrogate_number\}\}/g, surrogateData.surrogate_number)
            .replace(/\{\{status_label\}\}/g, surrogateData.status)
            .replace(/\{\{state\}\}/g, surrogateData.state || "")
            .replace(/\{\{email\}\}/g, surrogateData.email)
            .replace(/\{\{phone\}\}/g, surrogateData.phone || "")
            .replace(/\{\{owner_name\}\}/g, "")
            .replace(/\{\{org_name\}\}/g, "")
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
        "{{full_name}}",
        "{{email}}",
        "{{phone}}",
        "{{surrogate_number}}",
        "{{status_label}}",
        "{{state}}",
        "{{owner_name}}",
        "{{org_name}}",
    ]

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Send Email</DialogTitle>
                    <DialogDescription>Compose and send an email to {surrogateData.full_name}</DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    {/* Template Selector */}
                    <div className="grid gap-2">
                        <Label htmlFor="template">Email Template</Label>
                        <Select value={selectedTemplate} onValueChange={(value) => setSelectedTemplate(value || "")} disabled={templatesLoading}>
                            <SelectTrigger id="template" className="w-full">
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
                            name="recipient"
                            value={surrogateData.email}
                            readOnly
                            autoComplete="email"
                            spellCheck={false}
                            className="bg-muted/50 cursor-not-allowed"
                        />
                    </div>

                    {/* Subject Line */}
                    <div className="grid gap-2">
                        <Label htmlFor="subject">Subject</Label>
                        <Input
                            id="subject"
                            name="subject"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            placeholder="Enter email subject..."
                            autoComplete="off"
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
                            {sendEmailMutation.error instanceof Error
                                ? sendEmailMutation.error.message
                                : "Failed to send email. Please try again."}
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
