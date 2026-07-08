"use client"

import { useReducer, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TrustedSanitizedHtmlContent } from "@/components/safe-html-content"
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
import type { TemplateVariableRead } from "@/lib/types/template-variable"
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

function getStableKeyValue(value: unknown): string {
    if (value === null || value === undefined) return String(value)
    if (typeof value !== "object") return String(value)

    try {
        return JSON.stringify(value)
    } catch {
        return String(value)
    }
}

function getWorkflowMessageKey(message: string): string {
    return message
}

function getWorkflowConditionKey(condition: GeneratedWorkflow["conditions"][number]): string {
    return `${condition.field}:${condition.operator}:${getStableKeyValue(condition.value)}`
}

function getWorkflowActionKey(action: GeneratedWorkflow["actions"][number]): string {
    return Object.entries(action)
        .toSorted(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
        .map(([key, value]) => `${key}:${getStableKeyValue(value)}`)
        .join("|")
}

function getStableKeyedItems<T>(
    items: readonly T[],
    getBaseKey: (item: T) => string,
): Array<{ item: T; key: string; position: number }> {
    const seen = new Map<string, number>()

    return items.map((item, position) => {
        const baseKey = getBaseKey(item) || "item"
        const occurrence = seen.get(baseKey) ?? 0
        seen.set(baseKey, occurrence + 1)

        return {
            item,
            key: occurrence === 0 ? baseKey : `${baseKey}#${occurrence + 1}`,
            position,
        }
    })
}

interface WorkflowGenerationState {
    generatedWorkflow: GeneratedWorkflow | null
    explanation: string | null
    errors: string[]
    warnings: string[]
}

type WorkflowGenerationAction =
    | { type: "reset" }
    | {
        type: "success"
        workflow: GeneratedWorkflow
        explanation: string | null
        warnings: string[]
    }
    | {
        type: "invalid"
        workflow: GeneratedWorkflow | null
        explanation: string | null
        errors: string[]
    }
    | { type: "discard" }

const initialWorkflowGenerationState: WorkflowGenerationState = {
    generatedWorkflow: null,
    explanation: null,
    errors: [],
    warnings: [],
}

function workflowGenerationReducer(
    _state: WorkflowGenerationState,
    action: WorkflowGenerationAction
): WorkflowGenerationState {
    if (action.type === "reset" || action.type === "discard") {
        return initialWorkflowGenerationState
    }

    if (action.type === "success") {
        return {
            generatedWorkflow: action.workflow,
            explanation: action.explanation,
            errors: [],
            warnings: action.warnings,
        }
    }

    return {
        generatedWorkflow: action.workflow,
        explanation: action.explanation,
        errors: action.errors,
        warnings: [],
    }
}

interface TemplateGenerationState {
    generatedTemplate: GeneratedEmailTemplate | null
    name: string
    subject: string
    body: string
    explanation: string | null
    errors: string[]
    warnings: string[]
}

type TemplateGenerationAction =
    | { type: "reset" }
    | {
        type: "success"
        template: GeneratedEmailTemplate
        explanation: string | null
        warnings: string[]
    }
    | {
        type: "invalid"
        template: GeneratedEmailTemplate | null
        explanation: string | null
        errors: string[]
    }
    | { type: "setName"; value: string }
    | { type: "setSubject"; value: string }
    | { type: "setBody"; value: string }
    | { type: "discard" }

const initialTemplateGenerationState: TemplateGenerationState = {
    generatedTemplate: null,
    name: "",
    subject: "",
    body: "",
    explanation: null,
    errors: [],
    warnings: [],
}

function templateGenerationReducer(
    state: TemplateGenerationState,
    action: TemplateGenerationAction
): TemplateGenerationState {
    if (action.type === "reset" || action.type === "discard") {
        return initialTemplateGenerationState
    }

    if (action.type === "success") {
        return {
            generatedTemplate: action.template,
            name: action.template.name,
            subject: action.template.subject,
            body: action.template.body_html,
            explanation: action.explanation,
            errors: [],
            warnings: action.warnings,
        }
    }

    if (action.type === "invalid") {
        return {
            generatedTemplate: action.template,
            name: action.template?.name ?? "",
            subject: action.template?.subject ?? "",
            body: action.template?.body_html ?? "",
            explanation: action.explanation,
            errors: action.errors,
            warnings: [],
        }
    }

    if (action.type === "setName") {
        return { ...state, name: action.value }
    }

    if (action.type === "setSubject") {
        return { ...state, subject: action.value }
    }

    return { ...state, body: action.value }
}

function useAIBuilderController() {
    const { push } = useRouter()
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
    const [requestedWorkflowScope, setRequestedWorkflowScope] = useState<"personal" | "org">(initialScope)
    const workflowScope: "personal" | "org" =
        requestedWorkflowScope === "org" && canManageAutomation ? "org" : "personal"

    const [isGenerating, setIsGenerating] = useState(false)
    const [isSavingWorkflow, setIsSavingWorkflow] = useState(false)
    const [workflowPrompt, setWorkflowPrompt] = useState("")
    const [workflowState, dispatchWorkflow] = useReducer(
        workflowGenerationReducer,
        initialWorkflowGenerationState
    )

    const [emailPrompt, setEmailPrompt] = useState("")
    const [templateState, dispatchTemplate] = useReducer(
        templateGenerationReducer,
        initialTemplateGenerationState
    )
    const { generatedWorkflow } = workflowState
    const {
        generatedTemplate,
        name: templateName,
        subject: templateSubject,
        body: templateBody,
    } = templateState

    const sanitizedTemplateBody = DOMPurify.sanitize(templateBody)

    const createEmailTemplate = useCreateEmailTemplate()
    const {
        data: templateVariableCatalog = [],
        isLoading: templateVariableCatalogLoading,
        error: templateVariableCatalogError,
    } = useEmailTemplateVariables()

    const resetGeneratedArtifacts = () => {
        dispatchWorkflow({ type: "reset" })
        dispatchTemplate({ type: "reset" })
    }

    const handleModeChange = (value: string) => {
        const nextMode = value as "workflow" | "email_template"
        if (nextMode === mode) return
        resetGeneratedArtifacts()
        setMode(nextMode)
    }

    const templateVariables = extractTemplateVariables(`${templateSubject}\n${templateBody}`)
    const canValidateTemplateVariables =
        !templateVariableCatalogLoading &&
        !templateVariableCatalogError &&
        templateVariableCatalog.length > 0
    const allowedTemplateVariableNames = new Set(templateVariableCatalog.map((variable) => variable.name))
    const templateVariableNameSet = new Set(templateVariables)
    const requiredTemplateVariableNames: string[] = []
    for (const variable of templateVariableCatalog) {
        if (variable.required) {
            requiredTemplateVariableNames.push(variable.name)
        }
    }
    const missingRequiredVariables =
        generatedTemplate && canValidateTemplateVariables && requiredTemplateVariableNames.length > 0
            ? requiredTemplateVariableNames.filter((required) => !templateVariableNameSet.has(required))
            : []
    const hasMissingRequiredVariables = missingRequiredVariables.length > 0
    const unknownTemplateVariables = canValidateTemplateVariables
        ? templateVariables.filter((variable) => !allowedTemplateVariableNames.has(variable))
        : []
    const hasUnknownTemplateVariables = unknownTemplateVariables.length > 0

    const disableReason = !isAIEnabled
        ? "AI is disabled for your organization."
        : !canUseAI
            ? "You don't have permission to use AI."
            : null

    const activePrompt = mode === "workflow" ? workflowPrompt : emailPrompt

    const handleGenerate = async () => {
        if (!activePrompt.trim() || activePrompt.length < 10) {
            toast.error("Please provide a more detailed description (at least 10 characters)")
            return
        }

        setIsGenerating(true)
        const finishGenerating = () => setIsGenerating(false)

        if (mode === "workflow") {
            dispatchWorkflow({ type: "reset" })
            try {
                const result = await generateWorkflow(activePrompt, workflowScope)

                if (result.success && result.workflow) {
                    dispatchWorkflow({
                        type: "success",
                        workflow: result.workflow,
                        explanation: result.explanation,
                        warnings: result.warnings || [],
                    })
                    toast.success("Workflow generated! Review below before saving.")
                } else {
                    dispatchWorkflow({
                        type: "invalid",
                        workflow: result.workflow ?? null,
                        explanation: result.explanation,
                        errors: result.validation_errors || [],
                    })
                    toast.error("Could not generate a valid workflow. See details below.")
                }
            } catch {
                toast.error("Failed to generate workflow. Please try again.")
            }
            finishGenerating()
            return
        }

        dispatchTemplate({ type: "reset" })

        try {
            const result = await generateEmailTemplate(activePrompt)

            if (result.success && result.template) {
                dispatchTemplate({
                    type: "success",
                    template: result.template,
                    explanation: result.explanation,
                    warnings: result.warnings || [],
                })
                toast.success("Template generated! Review below before saving.")
            } else {
                dispatchTemplate({
                    type: "invalid",
                    template: result.template ?? null,
                    explanation: result.explanation,
                    errors: result.validation_errors || [],
                })
                toast.error("Could not generate a valid template. See details below.")
            }
        } catch {
            toast.error("Failed to generate template. Please try again.")
        }
        finishGenerating()
    }

    const handleSaveWorkflow = async () => {
        if (!generatedWorkflow) return

        setIsSavingWorkflow(true)
        const finishSavingWorkflow = () => setIsSavingWorkflow(false)
        try {
            const result = await saveAIWorkflow(generatedWorkflow, workflowScope)

            if (result.success && result.workflow_id) {
                toast.success("Workflow saved! It's currently disabled for your review.")
                push(`/automation?tab=workflows&scope=${workflowScope}`)
            } else {
                toast.error(result.error || "Failed to save workflow")
            }
        } catch {
            toast.error("Failed to save workflow. Please try again.")
        }
        finishSavingWorkflow()
    }

    const handleSaveEmailTemplate = async () => {
        if (!generatedTemplate) return
        if (!templateName.trim() || !templateSubject.trim()) {
            toast.error("Template name and subject are required.")
            return
        }
        if (hasMissingRequiredVariables) {
            toast.error(
                `Template is missing required variables: ${missingRequiredVariables
                    .map((v) => `{{${v}}}`)
                    .join(", ")}.`
            )
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
            push("/automation/email-templates")
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

    return {
        mode,
        backHref,
        activePrompt,
        workflowScope,
        permissions: { canUseAI, canManageAutomation, disableReason },
        status: {
            isGenerating,
            isSavingWorkflow,
            isSavingTemplate: createEmailTemplate.isPending,
        },
        workflowState,
        templateState,
        templateVariables,
        sanitizedTemplateBody,
        templateValidation: {
            missingRequiredVariables,
            unknownTemplateVariables,
            hasMissingRequiredVariables,
            hasUnknownTemplateVariables,
        },
        templateCatalog: {
            variables: templateVariableCatalog,
            isLoading: templateVariableCatalogLoading,
        },
        onModeChange: handleModeChange,
        onPromptChange: (value: string) =>
            mode === "workflow" ? setWorkflowPrompt(value) : setEmailPrompt(value),
        onSuggestionClick: handleSuggestionClick,
        onWorkflowScopeChange: (value: string) =>
            setRequestedWorkflowScope(value as "personal" | "org"),
        onGenerate: handleGenerate,
        onWorkflowDiscard: () => dispatchWorkflow({ type: "discard" }),
        onWorkflowSave: handleSaveWorkflow,
        onTemplateNameChange: (value: string) => dispatchTemplate({ type: "setName", value }),
        onTemplateSubjectChange: (value: string) => dispatchTemplate({ type: "setSubject", value }),
        onTemplateBodyChange: (value: string) => dispatchTemplate({ type: "setBody", value }),
        onTemplateDiscard: () => dispatchTemplate({ type: "discard" }),
        onTemplateSave: handleSaveEmailTemplate,
    }
}

export default function AIWorkflowBuilderPage() {
    const controller = useAIBuilderController()

    return <AIBuilderPageShell {...controller} />
}

function AIBuilderPageShell({
    mode,
    backHref,
    activePrompt,
    workflowScope,
    permissions,
    status,
    workflowState,
    templateState,
    templateVariables,
    sanitizedTemplateBody,
    templateValidation,
    templateCatalog,
    onModeChange,
    onPromptChange,
    onSuggestionClick,
    onWorkflowScopeChange,
    onGenerate,
    onWorkflowDiscard,
    onWorkflowSave,
    onTemplateNameChange,
    onTemplateSubjectChange,
    onTemplateBodyChange,
    onTemplateDiscard,
    onTemplateSave,
}: {
    mode: "workflow" | "email_template"
    backHref: string
    activePrompt: string
    workflowScope: "personal" | "org"
    permissions: {
        canUseAI: boolean
        canManageAutomation: boolean
        disableReason: string | null
    }
    status: {
        isGenerating: boolean
        isSavingWorkflow: boolean
        isSavingTemplate: boolean
    }
    workflowState: WorkflowGenerationState
    templateState: TemplateGenerationState
    templateVariables: string[]
    sanitizedTemplateBody: string
    templateValidation: {
        missingRequiredVariables: string[]
        unknownTemplateVariables: string[]
        hasMissingRequiredVariables: boolean
        hasUnknownTemplateVariables: boolean
    }
    templateCatalog: {
        variables: TemplateVariableRead[]
        isLoading: boolean
    }
    onModeChange: (value: string) => void
    onPromptChange: (value: string) => void
    onSuggestionClick: (suggestion: string) => void
    onWorkflowScopeChange: (value: string) => void
    onGenerate: () => void
    onWorkflowDiscard: () => void
    onWorkflowSave: () => void
    onTemplateNameChange: (value: string) => void
    onTemplateSubjectChange: (value: string) => void
    onTemplateBodyChange: (value: string) => void
    onTemplateDiscard: () => void
    onTemplateSave: () => void
}) {
    return (
        <div className="flex min-h-screen flex-col bg-background">
            <AIBuilderHeader mode={mode} backHref={backHref} onModeChange={onModeChange} />

            <div className="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
                {!permissions.canUseAI && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>AI Builder is disabled</AlertTitle>
                        <AlertDescription>
                            {permissions.disableReason || "AI is currently unavailable."}
                        </AlertDescription>
                    </Alert>
                )}

                <PromptComposerCard
                    mode={mode}
                    activePrompt={activePrompt}
                    workflowScope={workflowScope}
                    canManageAutomation={permissions.canManageAutomation}
                    isGenerating={status.isGenerating}
                    canUseAI={permissions.canUseAI}
                    onPromptChange={onPromptChange}
                    onSuggestionClick={onSuggestionClick}
                    onWorkflowScopeChange={onWorkflowScopeChange}
                    onGenerate={onGenerate}
                />

                <GenerationAlerts
                    mode={mode}
                    workflowErrors={workflowState.errors}
                    workflowWarnings={workflowState.warnings}
                    templateErrors={templateState.errors}
                    templateWarnings={templateState.warnings}
                />

                {mode === "workflow" && workflowState.generatedWorkflow && (
                    <WorkflowPreviewCard
                        generatedWorkflow={workflowState.generatedWorkflow}
                        workflowErrors={workflowState.errors}
                        workflowExplanation={workflowState.explanation}
                        isSavingWorkflow={status.isSavingWorkflow}
                        onDiscard={onWorkflowDiscard}
                        onSave={onWorkflowSave}
                    />
                )}

                {mode === "email_template" && templateState.generatedTemplate && (
                    <EmailTemplatePreviewCard
                        generatedTemplate={templateState.generatedTemplate}
                        templateName={templateState.name}
                        templateSubject={templateState.subject}
                        templateBody={templateState.body}
                        templateExplanation={templateState.explanation}
                        templateErrors={templateState.errors}
                        templateVariables={templateVariables}
                        sanitizedTemplateBody={sanitizedTemplateBody}
                        missingRequiredVariables={templateValidation.missingRequiredVariables}
                        unknownTemplateVariables={templateValidation.unknownTemplateVariables}
                        hasMissingRequiredVariables={templateValidation.hasMissingRequiredVariables}
                        hasUnknownTemplateVariables={templateValidation.hasUnknownTemplateVariables}
                        isSaving={status.isSavingTemplate}
                        onNameChange={onTemplateNameChange}
                        onSubjectChange={onTemplateSubjectChange}
                        onBodyChange={onTemplateBodyChange}
                        onDiscard={onTemplateDiscard}
                        onSave={onTemplateSave}
                    />
                )}

                {!status.isGenerating && (
                    <>
                        {mode === "workflow" && !workflowState.generatedWorkflow && (
                            <AIBuilderInfoCard
                                mode={mode}
                                templateVariableCatalog={templateCatalog.variables}
                                templateVariableCatalogLoading={templateCatalog.isLoading}
                            />
                        )}
                        {mode === "email_template" && !templateState.generatedTemplate && (
                            <AIBuilderInfoCard
                                mode={mode}
                                templateVariableCatalog={templateCatalog.variables}
                                templateVariableCatalogLoading={templateCatalog.isLoading}
                            />
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

function AIBuilderHeader({
    mode,
    backHref,
    onModeChange,
}: {
    mode: "workflow" | "email_template"
    backHref: string
    onModeChange: (value: string) => void
}) {
    return (
        <div className="border-b bg-card">
            <div className="flex items-center justify-between p-6">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={mode === "email_template" ? "Back to email templates" : "Back to workflows"}
                        render={<Link href={backHref} />}
                    >
                        <ArrowLeftIcon className="size-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-3">
                            {mode === "workflow" ? (
                                <SparklesIcon className="size-6 text-teal-500" />
                            ) : (
                                <MailIcon className="size-6 text-primary" />
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
                <Tabs value={mode} onValueChange={onModeChange}>
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
    )
}

function PromptComposerCard({
    mode,
    activePrompt,
    workflowScope,
    canManageAutomation,
    isGenerating,
    canUseAI,
    onPromptChange,
    onSuggestionClick,
    onWorkflowScopeChange,
    onGenerate,
}: {
    mode: "workflow" | "email_template"
    activePrompt: string
    workflowScope: "personal" | "org"
    canManageAutomation: boolean
    isGenerating: boolean
    canUseAI: boolean
    onPromptChange: (value: string) => void
    onSuggestionClick: (suggestion: string) => void
    onWorkflowScopeChange: (value: string) => void
    onGenerate: () => void
}) {
    const promptPlaceholder =
        mode === "workflow"
            ? "Example: When a new lead comes in from Texas, send them a welcome email and create a follow-up task for next week…"
            : "Example: Create a warm welcome email for new applicants who just submitted their form…"
    const promptTitle = mode === "workflow" ? "Describe Your Workflow" : "Describe Your Email Template"
    const promptDescription =
        mode === "workflow"
            ? "Tell us what should happen and when. Be specific about triggers, conditions, and actions."
            : "Describe the email you want to send, including tone, purpose, and any details to include."
    const suggestionList = mode === "workflow" ? SUGGESTED_PROMPTS : EMAIL_SUGGESTED_PROMPTS
    const generateLabel = mode === "workflow" ? "Generate Workflow" : "Generate Template"

    return (
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
                    onChange={(e) => onPromptChange(e.target.value)}
                    rows={4}
                    className="resize-none"
                />

                <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">Try these examples:</p>
                    <div className="flex flex-wrap gap-2">
                        {suggestionList.slice(0, 3).map((suggestion) => (
                            <button
                                type="button"
                                key={suggestion}
                                onClick={() => onSuggestionClick(suggestion)}
                                className="text-xs px-3 py-1.5 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
                            >
                                {suggestion.length > 50 ? suggestion.slice(0, 50) + "…" : suggestion}
                            </button>
                        ))}
                    </div>
                </div>

                {mode === "workflow" && (
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        <span>Scope:</span>
                        <Tabs value={workflowScope} onValueChange={onWorkflowScopeChange}>
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
                        onClick={onGenerate}
                        disabled={isGenerating || !activePrompt.trim() || !canUseAI}
                        className="gap-2"
                    >
                        {isGenerating ? (
                            <>
                                <Loader2Icon className="size-4 animate-spin" />
                                Generating…
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
    )
}

function GenerationAlerts({
    mode,
    workflowErrors,
    workflowWarnings,
    templateErrors,
    templateWarnings,
}: {
    mode: "workflow" | "email_template"
    workflowErrors: string[]
    workflowWarnings: string[]
    templateErrors: string[]
    templateWarnings: string[]
}) {
    if (mode === "workflow") {
        return (
            <>
                {workflowErrors.length > 0 && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>Validation Errors</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {getStableKeyedItems(workflowErrors, getWorkflowMessageKey).map(({ item: error, key }) => (
                                    <li key={key}>{error}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {workflowWarnings.length > 0 && (
                    <Alert>
                        <AlertTriangleIcon className="size-4" />
                        <AlertTitle>Warnings</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {getStableKeyedItems(workflowWarnings, getWorkflowMessageKey).map(({ item: warning, key }) => (
                                    <li key={key}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}
            </>
        )
    }

    return (
        <>
            {templateErrors.length > 0 && (
                <Alert variant="destructive">
                    <XCircleIcon className="size-4" />
                    <AlertTitle>Validation Errors</AlertTitle>
                    <AlertDescription>
                        <ul className="list-disc list-inside space-y-1 mt-2">
                            {getStableKeyedItems(templateErrors, getWorkflowMessageKey).map(({ item: error, key }) => (
                                <li key={key}>{error}</li>
                            ))}
                        </ul>
                    </AlertDescription>
                </Alert>
            )}

            {templateWarnings.length > 0 && (
                <Alert>
                    <AlertTriangleIcon className="size-4" />
                    <AlertTitle>Warnings</AlertTitle>
                    <AlertDescription>
                        <ul className="list-disc list-inside space-y-1 mt-2">
                            {getStableKeyedItems(templateWarnings, getWorkflowMessageKey).map(({ item: warning, key }) => (
                                <li key={key}>{warning}</li>
                            ))}
                        </ul>
                    </AlertDescription>
                </Alert>
            )}
        </>
    )
}

function WorkflowPreviewCard({
    generatedWorkflow,
    workflowErrors,
    workflowExplanation,
    isSavingWorkflow,
    onDiscard,
    onSave,
}: {
    generatedWorkflow: GeneratedWorkflow
    workflowErrors: string[]
    workflowExplanation: string | null
    isSavingWorkflow: boolean
    onDiscard: () => void
    onSave: () => void
}) {
    return (
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

                {generatedWorkflow.conditions.length > 0 && (
                    <div className="bg-muted/50 rounded-lg p-4">
                        <p className="text-sm font-medium text-muted-foreground mb-2">
                            Conditions ({generatedWorkflow.condition_logic})
                        </p>
                        <ul className="space-y-1">
                            {getStableKeyedItems(generatedWorkflow.conditions, getWorkflowConditionKey).map(({ item: cond, key }) => (
                                <li key={key} className="text-sm">
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

                <div className="bg-muted/50 rounded-lg p-4">
                    <p className="text-sm font-medium text-muted-foreground mb-2">Actions</p>
                    <ul className="space-y-2">
                        {getStableKeyedItems(generatedWorkflow.actions, getWorkflowActionKey).map(({ item: action, key, position }) => {
                            const workflowActionDetails = Object.entries(action).flatMap(([k, v]) =>
                                k === "action_type" ? [] : [`${k}: ${v}`]
                            )
                            return (
                                <li key={key} className="flex items-start gap-2">
                                    <Badge variant="secondary" className="shrink-0">
                                        {position + 1}
                                    </Badge>
                                    <div>
                                        <p className="font-medium">
                                            {ACTION_LABELS[action.action_type] || action.action_type}
                                        </p>
                                        <p className="text-sm text-muted-foreground">
                                            {workflowActionDetails.join(", ")}
                                        </p>
                                    </div>
                                </li>
                            )
                        })}
                    </ul>
                </div>

                {workflowExplanation && (
                    <p className="text-sm text-muted-foreground italic">{workflowExplanation}</p>
                )}

                {workflowErrors.length === 0 && (
                    <div className="flex justify-end gap-3 pt-4 border-t">
                        <Button variant="outline" onClick={onDiscard}>
                            Discard
                        </Button>
                        <Button onClick={onSave} disabled={isSavingWorkflow}>
                            {isSavingWorkflow ? (
                                <>
                                    <Loader2Icon className="size-4 animate-spin mr-2" />
                                    Saving…
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
    )
}

function EmailTemplatePreviewCard({
    generatedTemplate,
    templateName,
    templateSubject,
    templateBody,
    templateExplanation,
    templateErrors,
    templateVariables,
    sanitizedTemplateBody,
    missingRequiredVariables,
    unknownTemplateVariables,
    hasMissingRequiredVariables,
    hasUnknownTemplateVariables,
    isSaving,
    onNameChange,
    onSubjectChange,
    onBodyChange,
    onDiscard,
    onSave,
}: {
    generatedTemplate: GeneratedEmailTemplate
    templateName: string
    templateSubject: string
    templateBody: string
    templateExplanation: string | null
    templateErrors: string[]
    templateVariables: string[]
    sanitizedTemplateBody: string
    missingRequiredVariables: string[]
    unknownTemplateVariables: string[]
    hasMissingRequiredVariables: boolean
    hasUnknownTemplateVariables: boolean
    isSaving: boolean
    onNameChange: (value: string) => void
    onSubjectChange: (value: string) => void
    onBodyChange: (value: string) => void
    onDiscard: () => void
    onSave: () => void
}) {
    return (
        <Card className="border-primary/30">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <MailIcon className="size-5 text-primary" />
                            {templateName || generatedTemplate.name}
                        </CardTitle>
                        {templateExplanation && (
                            <CardDescription className="mt-1">
                                {templateExplanation}
                            </CardDescription>
                        )}
                    </div>
                    {templateErrors.length === 0 && !hasMissingRequiredVariables && (
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
                            onChange={(e) => onNameChange(e.target.value)}
                            placeholder="Template name"
                        />
                    </div>
                    <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                        <p className="text-sm font-medium text-muted-foreground">Subject</p>
                        <Input
                            value={templateSubject}
                            onChange={(e) => onSubjectChange(e.target.value)}
                            placeholder="Subject line"
                        />
                    </div>
                    <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                        <p className="text-sm font-medium text-muted-foreground">Body (HTML)</p>
                        <Textarea
                            value={templateBody}
                            onChange={(e) => onBodyChange(e.target.value)}
                            rows={6}
                            className="font-mono text-xs"
                        />
                    </div>
                    <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                        <p className="text-sm font-medium text-muted-foreground">Preview</p>
                        <TrustedSanitizedHtmlContent
                            html={sanitizedTemplateBody}
                            className="prose prose-sm max-w-none"
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

                {hasMissingRequiredVariables && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>Missing required variables</AlertTitle>
                        <AlertDescription>
                            Add{" "}
                            <span className="font-mono">
                                {missingRequiredVariables.map((v) => `{{${v}}}`).join(", ")}
                            </span>{" "}
                            to the template before saving.
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
                    <Button variant="outline" onClick={onDiscard}>
                        Discard
                    </Button>
                    <Button
                        onClick={onSave}
                        disabled={
                            isSaving ||
                            hasMissingRequiredVariables ||
                            hasUnknownTemplateVariables ||
                            templateErrors.length > 0
                        }
                    >
                        {isSaving ? (
                            <>
                                <Loader2Icon className="size-4 animate-spin mr-2" />
                                Saving…
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
    )
}

function AIBuilderInfoCard({
    mode,
    templateVariableCatalog,
    templateVariableCatalogLoading,
}: {
    mode: "workflow" | "email_template"
    templateVariableCatalog: TemplateVariableRead[]
    templateVariableCatalogLoading: boolean
}) {
    if (mode === "workflow") {
        return (
            <Card className="bg-muted/30 border-dashed">
                <CardContent className="py-8">
                    <div className="flex flex-col items-center text-center gap-y-4">
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
        )
    }

    return (
        <Card className="bg-muted/30 border-dashed">
            <CardContent className="py-8">
                <div className="flex flex-col items-center text-center gap-y-4">
                    <div className="size-16 rounded-full bg-primary/10 flex items-center justify-center">
                        <MailIcon className="size-8 text-primary" />
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
                            <Badge variant="outline">Loading variables…</Badge>
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
    )
}
