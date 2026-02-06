"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import DOMPurify from "dompurify"
import {
    WandIcon,
    ZapIcon,
    Loader2Icon,
    CheckCircleIcon,
    AlertTriangleIcon,
    XCircleIcon,
    ArrowLeftIcon,
    SparklesIcon,
    MailIcon,
} from "lucide-react"
import { toast } from "sonner"
import {
    generateWorkflow,
    saveAIWorkflow,
    generateEmailTemplate,
    type GeneratedWorkflow,
    type GeneratedEmailTemplate,
} from "@/lib/api/ai"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useCreateEmailTemplate, useEmailTemplateVariables } from "@/lib/hooks/use-email-templates"
import Link from "@/components/app-link"

// Trigger display labels
const TRIGGER_LABELS: Record<string, string> = {
    surrogate_created: "When a new case is created",
    status_changed: "When case stage changes",
    inactivity: "When case is inactive",
    scheduled: "On a schedule",
    match_proposed: "When a match is proposed",
    match_accepted: "When a match is accepted",
    match_rejected: "When a match is rejected",
    document_uploaded: "When a document is uploaded",
    note_added: "When a note is added",
    appointment_scheduled: "When an appointment is scheduled",
    appointment_completed: "When an appointment is completed",
}

// Action display labels
const ACTION_LABELS: Record<string, string> = {
    send_email: "Send Email",
    create_task: "Create Task",
    assign_surrogate: "Assign Surrogate",
    update_field: "Update Field",
    add_note: "Add Note",
    send_notification: "Send Notification",
}

// Suggested prompts
const SUGGESTED_PROMPTS = [
    "When a new lead comes in from California, assign to Maria and send welcome email",
    "If a case has no activity for 7 days, send a follow-up email and create a task for the case manager",
    "When an appointment is scheduled, send a confirmation email to the applicant",
    "When a match is proposed, notify the case manager and send the match proposal email",
    "Weekly on Monday, send a nurture email to all leads in the inquiry stage",
]

const EMAIL_SUGGESTED_PROMPTS = [
    "Welcome email for new applicants who just submitted a form",
    "Follow-up email after 7 days of inactivity",
    "Appointment confirmation email with date/time and location",
    "Status update email when a case moves to approved",
]

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

export default function AIWorkflowBuilderPage() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const { user } = useAuth()
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissions = effectivePermissions?.permissions || []
    const isAIEnabled = user?.ai_enabled ?? false
    const canUseAI = isAIEnabled && permissions.includes("use_ai_assistant")
    const canManageAutomation = permissions.includes("manage_automation")

    const initialMode =
        searchParams.get("mode") === "email_template" ? "email_template" : "workflow"
    const initialScope = searchParams.get("scope") === "org" ? "org" : "personal"

    const [mode, setMode] = useState<"workflow" | "email_template">(initialMode)
    const [workflowScope, setWorkflowScope] = useState<"personal" | "org">(initialScope)

    const [isGenerating, setIsGenerating] = useState(false)
    const [isSavingWorkflow, setIsSavingWorkflow] = useState(false)
    const [workflowPrompt, setWorkflowPrompt] = useState("")
    const [generatedWorkflow, setGeneratedWorkflow] = useState<GeneratedWorkflow | null>(null)
    const [workflowExplanation, setWorkflowExplanation] = useState<string | null>(null)
    const [workflowErrors, setWorkflowErrors] = useState<string[]>([])
    const [workflowWarnings, setWorkflowWarnings] = useState<string[]>([])

    const [emailPrompt, setEmailPrompt] = useState("")
    const [generatedTemplate, setGeneratedTemplate] = useState<GeneratedEmailTemplate | null>(null)
    const [templateName, setTemplateName] = useState("")
    const [templateSubject, setTemplateSubject] = useState("")
    const [templateBody, setTemplateBody] = useState("")
    const [templateExplanation, setTemplateExplanation] = useState<string | null>(null)
    const [templateErrors, setTemplateErrors] = useState<string[]>([])
    const [templateWarnings, setTemplateWarnings] = useState<string[]>([])

    const sanitizedTemplateBody = useMemo(
        () => DOMPurify.sanitize(templateBody),
        [templateBody]
    )

    const createEmailTemplate = useCreateEmailTemplate()
    const {
        data: templateVariableCatalog = [],
        isLoading: templateVariableCatalogLoading,
        error: templateVariableCatalogError,
    } = useEmailTemplateVariables()

    useEffect(() => {
        if (workflowScope === "org" && !canManageAutomation) {
            setWorkflowScope("personal")
        }
    }, [workflowScope, canManageAutomation])

    useEffect(() => {
        setGeneratedWorkflow(null)
        setWorkflowExplanation(null)
        setWorkflowErrors([])
        setWorkflowWarnings([])
        setGeneratedTemplate(null)
        setTemplateExplanation(null)
        setTemplateErrors([])
        setTemplateWarnings([])
    }, [mode])

    const templateVariables = useMemo(
        () => extractTemplateVariables(`${templateSubject}\n${templateBody}`),
        [templateSubject, templateBody]
    )
    const canValidateTemplateVariables =
        !templateVariableCatalogLoading &&
        !templateVariableCatalogError &&
        templateVariableCatalog.length > 0
    const allowedTemplateVariableNames = useMemo(
        () => new Set(templateVariableCatalog.map((variable) => variable.name)),
        [templateVariableCatalog]
    )
    const requiredTemplateVariableNames = useMemo(
        () => templateVariableCatalog.filter((variable) => variable.required).map((variable) => variable.name),
        [templateVariableCatalog]
    )
    const missingRequiredVariable =
        Boolean(generatedTemplate) &&
        canValidateTemplateVariables &&
        requiredTemplateVariableNames.some((required) => !templateVariables.includes(required))
    const unknownTemplateVariables = useMemo(() => {
        if (!canValidateTemplateVariables) return []
        return templateVariables.filter((variable) => !allowedTemplateVariableNames.has(variable))
    }, [allowedTemplateVariableNames, canValidateTemplateVariables, templateVariables])
    const hasUnknownTemplateVariables = unknownTemplateVariables.length > 0

    const disableReason = !isAIEnabled
        ? "AI is disabled for your organization."
        : !canUseAI
            ? "You don't have permission to use AI."
            : null

    const activePrompt = mode === "workflow" ? workflowPrompt : emailPrompt
    const promptPlaceholder =
        mode === "workflow"
            ? "Example: When a new lead comes in from Texas, send them a welcome email and create a follow-up task for next week..."
            : "Example: Create a warm welcome email for new applicants who just submitted their form..."
    const promptTitle = mode === "workflow" ? "Describe Your Workflow" : "Describe Your Email Template"
    const promptDescription =
        mode === "workflow"
            ? "Tell us what should happen and when. Be specific about triggers, conditions, and actions."
            : "Describe the email you want to send, including tone, purpose, and any details to include."
    const suggestionList = mode === "workflow" ? SUGGESTED_PROMPTS : EMAIL_SUGGESTED_PROMPTS
    const generateLabel = mode === "workflow" ? "Generate Workflow" : "Generate Template"

    const handleGenerate = async () => {
        if (!activePrompt.trim() || activePrompt.length < 10) {
            toast.error("Please provide a more detailed description (at least 10 characters)")
            return
        }

        setIsGenerating(true)

        if (mode === "workflow") {
            setGeneratedWorkflow(null)
            setWorkflowExplanation(null)
            setWorkflowErrors([])
            setWorkflowWarnings([])
            try {
                const result = await generateWorkflow(activePrompt, workflowScope)

                if (result.success && result.workflow) {
                    setGeneratedWorkflow(result.workflow)
                    setWorkflowExplanation(result.explanation)
                    setWorkflowWarnings(result.warnings || [])
                    toast.success("Workflow generated! Review below before saving.")
                } else {
                    setWorkflowExplanation(result.explanation)
                    setWorkflowErrors(result.validation_errors || [])
                    if (result.workflow) {
                        setGeneratedWorkflow(result.workflow)
                    }
                    toast.error("Could not generate a valid workflow. See details below.")
                }
            } catch {
                toast.error("Failed to generate workflow. Please try again.")
            } finally {
                setIsGenerating(false)
            }
            return
        }

        setGeneratedTemplate(null)
        setTemplateExplanation(null)
        setTemplateErrors([])
        setTemplateWarnings([])

        try {
            const result = await generateEmailTemplate(activePrompt)

            if (result.success && result.template) {
                setGeneratedTemplate(result.template)
                setTemplateName(result.template.name)
                setTemplateSubject(result.template.subject)
                setTemplateBody(result.template.body_html)
                setTemplateExplanation(result.explanation)
                setTemplateWarnings(result.warnings || [])
                toast.success("Template generated! Review below before saving.")
            } else {
                setTemplateExplanation(result.explanation)
                setTemplateErrors(result.validation_errors || [])
                if (result.template) {
                    setGeneratedTemplate(result.template)
                    setTemplateName(result.template.name)
                    setTemplateSubject(result.template.subject)
                    setTemplateBody(result.template.body_html)
                }
                toast.error("Could not generate a valid template. See details below.")
            }
        } catch {
            toast.error("Failed to generate template. Please try again.")
        } finally {
            setIsGenerating(false)
        }
    }

    const handleSaveWorkflow = async () => {
        if (!generatedWorkflow) return

        setIsSavingWorkflow(true)
        try {
            const result = await saveAIWorkflow(generatedWorkflow, workflowScope)

            if (result.success && result.workflow_id) {
                toast.success("Workflow saved! It's currently disabled for your review.")
                router.push(`/automation?tab=workflows&scope=${workflowScope}`)
            } else {
                toast.error(result.error || "Failed to save workflow")
            }
        } catch {
            toast.error("Failed to save workflow. Please try again.")
        } finally {
            setIsSavingWorkflow(false)
        }
    }

    const handleSaveEmailTemplate = async () => {
        if (!generatedTemplate) return
        if (!templateName.trim() || !templateSubject.trim()) {
            toast.error("Template name and subject are required.")
            return
        }
        if (missingRequiredVariable) {
            toast.error("Template must include {{unsubscribe_url}}.")
            return
        }

        try {
            await createEmailTemplate.mutateAsync({
                name: templateName.trim(),
                subject: templateSubject.trim(),
                body: templateBody,
                scope: "personal",
            })
            toast.success("Template saved to My Email Templates.")
            router.push("/automation/email-templates")
        } catch (error) {
            const message = error instanceof Error ? error.message : "Failed to save template"
            toast.error(message)
        }
    }

    const handleSuggestionClick = (suggestion: string) => {
        if (mode === "workflow") {
            setWorkflowPrompt(suggestion)
        } else {
            setEmailPrompt(suggestion)
        }
    }

    const backHref =
        mode === "email_template" ? "/automation/email-templates" : "/automation?tab=workflows"

    return (
        <div className="flex min-h-screen flex-col bg-background">
            {/* Header */}
            <div className="border-b bg-card">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-4">
                        <Button
                            variant="ghost"
                            size="icon-sm"
                            render={<Link href={backHref} />}
                        >
                            <ArrowLeftIcon className="size-4" />
                        </Button>
                        <div>
                            <div className="flex items-center gap-3">
                                {mode === "workflow" ? (
                                    <SparklesIcon className="size-6 text-teal-500" />
                                ) : (
                                    <MailIcon className="size-6 text-indigo-500" />
                                )}
                                <h1 className="text-2xl font-semibold">
                                    {mode === "workflow" ? "AI Workflow Builder" : "AI Email Template Builder"}
                                </h1>
                                <Badge variant="secondary" className="bg-teal-500/10 text-teal-500 border-teal-500/20">
                                    Beta
                                </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                                {mode === "workflow"
                                    ? "Describe what you want in plain English, and AI will create the workflow for you."
                                    : "Describe the email template you need, and AI will draft it for you."}
                            </p>
                        </div>
                    </div>
                    <Tabs value={mode} onValueChange={(value) => setMode(value as "workflow" | "email_template")}>
                        <TabsList>
                            <TabsTrigger value="workflow" className="gap-2">
                                <ZapIcon className="size-4" />
                                Workflow
                            </TabsTrigger>
                            <TabsTrigger value="email_template" className="gap-2">
                                <MailIcon className="size-4" />
                                Email Template
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
                {!canUseAI && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>AI Builder is disabled</AlertTitle>
                        <AlertDescription>
                            {disableReason || "AI is currently unavailable."}
                        </AlertDescription>
                    </Alert>
                )}

                {/* Prompt Input */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <WandIcon className="size-5" />
                            {promptTitle}
                        </CardTitle>
                        <CardDescription>
                            {promptDescription}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Textarea
                            placeholder={promptPlaceholder}
                            value={activePrompt}
                            onChange={(e) =>
                                mode === "workflow"
                                    ? setWorkflowPrompt(e.target.value)
                                    : setEmailPrompt(e.target.value)
                            }
                            rows={4}
                            className="resize-none"
                        />

                        {/* Suggestions */}
                        <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">Try these examples:</p>
                            <div className="flex flex-wrap gap-2">
                                {suggestionList.slice(0, 3).map((suggestion, i) => (
                                    <button
                                        key={i}
                                        onClick={() => handleSuggestionClick(suggestion)}
                                        className="text-xs px-3 py-1.5 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                        {suggestion.length > 50 ? suggestion.slice(0, 50) + "..." : suggestion}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {mode === "workflow" && (
                            <div className="flex items-center gap-3 text-sm text-muted-foreground">
                                <span>Scope:</span>
                                <Tabs
                                    value={workflowScope}
                                    onValueChange={(value) =>
                                        setWorkflowScope(value as "personal" | "org")
                                    }
                                >
                                    <TabsList>
                                        <TabsTrigger value="personal">Personal</TabsTrigger>
                                        <TabsTrigger value="org" disabled={!canManageAutomation}>
                                            Org
                                        </TabsTrigger>
                                    </TabsList>
                                </Tabs>
                                {!canManageAutomation && (
                                    <span className="text-xs">Org scope requires manage automation</span>
                                )}
                            </div>
                        )}

                        <div className="flex justify-end">
                            <Button
                                onClick={handleGenerate}
                                disabled={isGenerating || !activePrompt.trim() || !canUseAI}
                                className="gap-2"
                            >
                                {isGenerating ? (
                                    <>
                                        <Loader2Icon className="size-4 animate-spin" />
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <SparklesIcon className="size-4" />
                                        {generateLabel}
                                    </>
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Validation Errors */}
                {mode === "workflow" && workflowErrors.length > 0 && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>Validation Errors</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {workflowErrors.map((error, i) => (
                                    <li key={i}>{error}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Warnings */}
                {mode === "workflow" && workflowWarnings.length > 0 && (
                    <Alert>
                        <AlertTriangleIcon className="size-4" />
                        <AlertTitle>Warnings</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {workflowWarnings.map((warning, i) => (
                                    <li key={i}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Generated Workflow Preview */}
                {mode === "workflow" && generatedWorkflow && (
                    <Card className="border-teal-500/30">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="flex items-center gap-2">
                                        <ZapIcon className="size-5 text-teal-500" />
                                        {generatedWorkflow.name}
                                    </CardTitle>
                                    {generatedWorkflow.description && (
                                        <CardDescription className="mt-1">
                                            {generatedWorkflow.description}
                                        </CardDescription>
                                    )}
                                </div>
                                {workflowErrors.length === 0 && (
                                    <Badge variant="outline" className="border-green-500 text-green-600">
                                        <CheckCircleIcon className="size-3 mr-1" />
                                        Valid
                                    </Badge>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Trigger */}
                            <div className="bg-muted/50 rounded-lg p-4">
                                <p className="text-sm font-medium text-muted-foreground mb-1">Trigger</p>
                                <p className="font-medium">
                                    {TRIGGER_LABELS[generatedWorkflow.trigger_type] || generatedWorkflow.trigger_type}
                                </p>
                                {Object.keys(generatedWorkflow.trigger_config).length > 0 && (
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Config: {JSON.stringify(generatedWorkflow.trigger_config)}
                                    </p>
                                )}
                            </div>

                            {/* Conditions */}
                            {generatedWorkflow.conditions.length > 0 && (
                                <div className="bg-muted/50 rounded-lg p-4">
                                    <p className="text-sm font-medium text-muted-foreground mb-2">
                                        Conditions ({generatedWorkflow.condition_logic})
                                    </p>
                                    <ul className="space-y-1">
                                        {generatedWorkflow.conditions.map((cond, i) => (
                                            <li key={i} className="text-sm">
                                                <span className="font-mono bg-background px-1 rounded">{cond.field}</span>
                                                {" "}{cond.operator}{" "}
                                                <span className="font-mono bg-background px-1 rounded">
                                                    {String(cond.value)}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Actions */}
                            <div className="bg-muted/50 rounded-lg p-4">
                                <p className="text-sm font-medium text-muted-foreground mb-2">Actions</p>
                                <ul className="space-y-2">
                                    {generatedWorkflow.actions.map((action, i) => (
                                        <li key={i} className="flex items-start gap-2">
                                            <Badge variant="secondary" className="shrink-0">
                                                {i + 1}
                                            </Badge>
                                            <div>
                                                <p className="font-medium">
                                                    {ACTION_LABELS[action.action_type] || action.action_type}
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {Object.entries(action)
                                                        .filter(([k]) => k !== "action_type")
                                                        .map(([k, v]) => `${k}: ${v}`)
                                                        .join(", ")}
                                                </p>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Explanation */}
                            {workflowExplanation && (
                                <p className="text-sm text-muted-foreground italic">{workflowExplanation}</p>
                            )}

                            {/* Save Button */}
                            {workflowErrors.length === 0 && (
                                <div className="flex justify-end gap-3 pt-4 border-t">
                                    <Button
                                        variant="outline"
                                        onClick={() => {
                                            setGeneratedWorkflow(null)
                                            setWorkflowExplanation(null)
                                        }}
                                    >
                                        Discard
                                    </Button>
                                    <Button onClick={handleSaveWorkflow} disabled={isSavingWorkflow}>
                                        {isSavingWorkflow ? (
                                            <>
                                                <Loader2Icon className="size-4 animate-spin mr-2" />
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <CheckCircleIcon className="size-4 mr-2" />
                                                Save Workflow
                                            </>
                                        )}
                                    </Button>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                )}

                {mode === "email_template" && templateErrors.length > 0 && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>Validation Errors</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {templateErrors.map((error, i) => (
                                    <li key={i}>{error}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {mode === "email_template" && templateWarnings.length > 0 && (
                    <Alert>
                        <AlertTriangleIcon className="size-4" />
                        <AlertTitle>Warnings</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {templateWarnings.map((warning, i) => (
                                    <li key={i}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {mode === "email_template" && generatedTemplate && (
                    <Card className="border-indigo-500/30">
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="flex items-center gap-2">
                                        <MailIcon className="size-5 text-indigo-500" />
                                        {templateName || generatedTemplate.name}
                                    </CardTitle>
                                    {templateExplanation && (
                                        <CardDescription className="mt-1">
                                            {templateExplanation}
                                        </CardDescription>
                                    )}
                                </div>
                                {templateErrors.length === 0 && !missingRequiredVariable && (
                                    <Badge variant="outline" className="border-green-500 text-green-600">
                                        <CheckCircleIcon className="size-3 mr-1" />
                                        Valid
                                    </Badge>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-3">
                                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                                    <p className="text-sm font-medium text-muted-foreground">Template Name</p>
                                    <Input
                                        value={templateName}
                                        onChange={(e) => setTemplateName(e.target.value)}
                                        placeholder="Template name"
                                    />
                                </div>
                                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                                    <p className="text-sm font-medium text-muted-foreground">Subject</p>
                                    <Input
                                        value={templateSubject}
                                        onChange={(e) => setTemplateSubject(e.target.value)}
                                        placeholder="Subject line"
                                    />
                                </div>
                                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                                    <p className="text-sm font-medium text-muted-foreground">Body (HTML)</p>
                                    <Textarea
                                        value={templateBody}
                                        onChange={(e) => setTemplateBody(e.target.value)}
                                        rows={6}
                                        className="font-mono text-xs"
                                    />
                                </div>
                                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                                    <p className="text-sm font-medium text-muted-foreground">Preview</p>
                                    <div
                                        className="prose prose-sm max-w-none"
                                        dangerouslySetInnerHTML={{ __html: sanitizedTemplateBody }}
                                    />
                                </div>
                                <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                                    <p className="text-sm font-medium text-muted-foreground">
                                        Variables detected
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                        {templateVariables.length === 0 ? (
                                            <span className="text-xs text-muted-foreground">None</span>
                                        ) : (
                                            templateVariables.map((variable) => (
                                                <Badge key={variable} variant="secondary">
                                                    {variable}
                                                </Badge>
                                            ))
                                        )}
                                    </div>
                                </div>
                            </div>

                            {missingRequiredVariable && (
                                <Alert variant="destructive">
                                    <XCircleIcon className="size-4" />
                                    <AlertTitle>Missing required variable</AlertTitle>
                                    <AlertDescription>
                                        Add <code>{"{{unsubscribe_url}}"}</code> to the body before saving.
                                    </AlertDescription>
                                </Alert>
                            )}

                            {hasUnknownTemplateVariables && (
                                <Alert variant="destructive">
                                    <XCircleIcon className="size-4" />
                                    <AlertTitle>Unknown variables</AlertTitle>
                                    <AlertDescription>
                                        {unknownTemplateVariables.join(", ")}
                                    </AlertDescription>
                                </Alert>
                            )}

                            <div className="flex justify-end gap-3 pt-4 border-t">
                                <Button
                                    variant="outline"
                                    onClick={() => {
                                        setGeneratedTemplate(null)
                                        setTemplateExplanation(null)
                                    }}
                                >
                                    Discard
                                </Button>
                                <Button
                                    onClick={handleSaveEmailTemplate}
                                    disabled={
                                        createEmailTemplate.isPending ||
                                        missingRequiredVariable ||
                                        hasUnknownTemplateVariables ||
                                        templateErrors.length > 0
                                    }
                                >
                                    {createEmailTemplate.isPending ? (
                                        <>
                                            <Loader2Icon className="size-4 animate-spin mr-2" />
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            <CheckCircleIcon className="size-4 mr-2" />
                                            Save Template
                                        </>
                                    )}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Info Card */}
                {mode === "workflow" && !generatedWorkflow && !isGenerating && (
                    <Card className="bg-muted/30 border-dashed">
                        <CardContent className="py-8">
                            <div className="flex flex-col items-center text-center space-y-4">
                                <div className="size-16 rounded-full bg-teal-500/10 flex items-center justify-center">
                                    <SparklesIcon className="size-8 text-teal-500" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg">How It Works</h3>
                                    <p className="text-sm text-muted-foreground max-w-md mt-2">
                                        Describe your automation in plain English. Our AI will understand your intent
                                        and create a workflow with the right triggers, conditions, and actions.
                                        You can review and modify before saving.
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2 justify-center">
                                    <Badge variant="outline">Natural Language</Badge>
                                    <Badge variant="outline">Safe by Default</Badge>
                                    <Badge variant="outline">Review Before Saving</Badge>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {mode === "email_template" && !generatedTemplate && !isGenerating && (
                    <Card className="bg-muted/30 border-dashed">
                        <CardContent className="py-8">
                            <div className="flex flex-col items-center text-center space-y-4">
                                <div className="size-16 rounded-full bg-indigo-500/10 flex items-center justify-center">
                                    <MailIcon className="size-8 text-indigo-500" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg">How It Works</h3>
                                    <p className="text-sm text-muted-foreground max-w-md mt-2">
                                        Describe the email you want to send. AI will draft an HTML template using
                                        approved variables so you can reuse it across workflows and campaigns.
                                    </p>
                                </div>
                                <div className="flex flex-wrap gap-2 justify-center">
                                    {templateVariableCatalogLoading && (
                                        <Badge variant="outline">Loading variables...</Badge>
                                    )}
                                    {!templateVariableCatalogLoading &&
                                        templateVariableCatalog.length > 0 && (
                                            <>
                                                {templateVariableCatalog.slice(0, 6).map((variable) => (
                                                    <Badge key={variable.name} variant="outline">
                                                        {variable.name}
                                                    </Badge>
                                                ))}
                                                {templateVariableCatalog.length > 6 && (
                                                    <Badge variant="outline">
                                                        +{templateVariableCatalog.length - 6} more
                                                    </Badge>
                                                )}
                                            </>
                                        )}
                                    {!templateVariableCatalogLoading &&
                                        templateVariableCatalog.length === 0 && (
                                            <Badge variant="outline">Variables unavailable</Badge>
                                        )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    )
}
