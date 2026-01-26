"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    WandIcon,
    ZapIcon,
    Loader2Icon,
    CheckCircleIcon,
    AlertTriangleIcon,
    XCircleIcon,
    ArrowLeftIcon,
    SparklesIcon,
} from "lucide-react"
import { toast } from "sonner"
import { generateWorkflow, saveAIWorkflow, type GeneratedWorkflow } from "@/lib/api/ai"
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
    update_status: "Update Stage",
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

export default function AIWorkflowBuilderPage() {
    const router = useRouter()
    const [prompt, setPrompt] = useState("")
    const [isGenerating, setIsGenerating] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [generatedWorkflow, setGeneratedWorkflow] = useState<GeneratedWorkflow | null>(null)
    const [explanation, setExplanation] = useState<string | null>(null)
    const [validationErrors, setValidationErrors] = useState<string[]>([])
    const [warnings, setWarnings] = useState<string[]>([])

    const handleGenerate = async () => {
        if (!prompt.trim() || prompt.length < 10) {
            toast.error("Please provide a more detailed description (at least 10 characters)")
            return
        }

        setIsGenerating(true)
        setGeneratedWorkflow(null)
        setExplanation(null)
        setValidationErrors([])
        setWarnings([])

        try {
            const result = await generateWorkflow(prompt)

            if (result.success && result.workflow) {
                setGeneratedWorkflow(result.workflow)
                setExplanation(result.explanation)
                setWarnings(result.warnings || [])
                toast.success("Workflow generated! Review below before saving.")
            } else {
                setExplanation(result.explanation)
                setValidationErrors(result.validation_errors || [])
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
    }

    const handleSave = async () => {
        if (!generatedWorkflow) return

        setIsSaving(true)
        try {
            const result = await saveAIWorkflow(generatedWorkflow)

            if (result.success && result.workflow_id) {
                toast.success("Workflow saved! It's currently disabled for your review.")
                router.push("/automation?tab=workflows")
            } else {
                toast.error(result.error || "Failed to save workflow")
            }
        } catch {
            toast.error("Failed to save workflow. Please try again.")
        } finally {
            setIsSaving(false)
        }
    }

    const handleSuggestionClick = (suggestion: string) => {
        setPrompt(suggestion)
    }

    return (
        <div className="flex min-h-screen flex-col bg-background">
            {/* Header */}
            <div className="border-b bg-card">
                <div className="flex items-center justify-between p-6">
                    <div className="flex items-center gap-4">
                        <Button
                            variant="ghost"
                            size="icon-sm"
                            render={<Link href="/automation?tab=workflows" />}
                        >
                            <ArrowLeftIcon className="size-4" />
                        </Button>
                        <div>
                            <div className="flex items-center gap-3">
                                <SparklesIcon className="size-6 text-teal-500" />
                                <h1 className="text-2xl font-semibold">AI Workflow Builder</h1>
                                <Badge variant="secondary" className="bg-teal-500/10 text-teal-500 border-teal-500/20">
                                    Beta
                                </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                                Describe what you want in plain English, and AI will create the workflow for you.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
                {/* Prompt Input */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <WandIcon className="size-5" />
                            Describe Your Workflow
                        </CardTitle>
                        <CardDescription>
                            Tell us what should happen and when. Be specific about triggers, conditions, and actions.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Textarea
                            placeholder="Example: When a new lead comes in from Texas, send them a welcome email and create a follow-up task for next week..."
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            rows={4}
                            className="resize-none"
                        />

                        {/* Suggestions */}
                        <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">Try these examples:</p>
                            <div className="flex flex-wrap gap-2">
                                {SUGGESTED_PROMPTS.slice(0, 3).map((suggestion, i) => (
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

                        <div className="flex justify-end">
                            <Button
                                onClick={handleGenerate}
                                disabled={isGenerating || !prompt.trim()}
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
                                        Generate Workflow
                                    </>
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Validation Errors */}
                {validationErrors.length > 0 && (
                    <Alert variant="destructive">
                        <XCircleIcon className="size-4" />
                        <AlertTitle>Validation Errors</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {validationErrors.map((error, i) => (
                                    <li key={i}>{error}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Warnings */}
                {warnings.length > 0 && (
                    <Alert>
                        <AlertTriangleIcon className="size-4" />
                        <AlertTitle>Warnings</AlertTitle>
                        <AlertDescription>
                            <ul className="list-disc list-inside space-y-1 mt-2">
                                {warnings.map((warning, i) => (
                                    <li key={i}>{warning}</li>
                                ))}
                            </ul>
                        </AlertDescription>
                    </Alert>
                )}

                {/* Generated Workflow Preview */}
                {generatedWorkflow && (
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
                                {validationErrors.length === 0 && (
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
                            {explanation && (
                                <p className="text-sm text-muted-foreground italic">{explanation}</p>
                            )}

                            {/* Save Button */}
                            {validationErrors.length === 0 && (
                                <div className="flex justify-end gap-3 pt-4 border-t">
                                    <Button
                                        variant="outline"
                                        onClick={() => {
                                            setGeneratedWorkflow(null)
                                            setExplanation(null)
                                        }}
                                    >
                                        Discard
                                    </Button>
                                    <Button onClick={handleSave} disabled={isSaving}>
                                        {isSaving ? (
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

                {/* Info Card */}
                {!generatedWorkflow && !isGenerating && (
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
            </div>
        </div>
    )
}
