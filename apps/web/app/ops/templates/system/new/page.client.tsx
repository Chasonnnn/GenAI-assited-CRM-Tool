"use client"

import { useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useRouter } from "next/navigation"
import { toast } from "@/components/ui/toast"
import { ImageIcon, Loader2Icon, PlusIcon } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Field, FieldError, FieldLabel, ValidatedField } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/page-header"
import { ApiError } from "@/lib/api"
import { useFormValidation, type FormFieldErrors } from "@/lib/forms/use-form-validation"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EmailDesignEditor, type EmailDesignEditorHandle } from "@/components/email/design/email-design-editor"
import { EmailHtmlSource } from "@/components/email/design/email-html-source"
import { EmailPreviewPane } from "@/components/email/design/email-preview-pane"
import { previewPlatformSystemEmailTemplate } from "@/lib/api/platform"
import type { EmailBodyDesign } from "@/lib/api/email-templates"
import type { EmailBodyValue } from "@/lib/email-design"
import { insertAtCursor } from "@/lib/insert-at-cursor"
import {
    useCreatePlatformSystemEmailTemplate,
    usePlatformSystemEmailTemplateVariables,
} from "@/lib/hooks/use-platform-templates"

type ActiveInsertionTarget = "subject" | "body" | null
type EditorView = "edit" | "preview" | "html"
type TextSelectionRef = MutableRefObject<{ start: number; end: number } | null>

function extractTemplateVariables(text: string): string[] {
    if (!text) return []
    const matches = text.match(/{{\s*([a-zA-Z0-9_]+)\s*}}/g) ?? []
    const variables = matches.map((match) => match.replace(/{{\s*|\s*}}/g, ""))
    return Array.from(new Set(variables))
}

function buildSystemKeyFromName(name: string): string {
    const key = name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .replace(/_{2,}/g, "_")
    return key.slice(0, 100)
}

function getFromEmailError(fromEmail: string): string | null {
    const value = fromEmail.trim()
    if (!value) return null
    const basicEmail = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/
    const namedEmail = /^.+<\s*[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+\s*>$/
    if (basicEmail.test(value) || namedEmail.test(value)) return null
    return "Use a valid email or name <email@domain> format."
}

function getSystemKeyError(systemKey: string): string | null {
    const value = systemKey.trim()
    if (!value) return "System key is required."
    if (!/^[a-z0-9_]+$/.test(value)) {
        return "Use only lowercase letters, numbers, and underscores."
    }
    if (value.length < 2 || value.length > 100) {
        return "System key must be between 2 and 100 characters."
    }
    if (value === "new") return "System key cannot be 'new'."
    return null
}

function getNameError(name: string): string | null {
    if (!name.trim()) return "Name is required."
    if (name.trim().length > 120) return "Name must be 120 characters or less."
    return null
}

function getSubjectError(subject: string): string | null {
    if (!subject.trim()) return "Subject is required."
    if (subject.trim().length > 200) return "Subject must be 200 characters or less."
    return null
}

function getBodyError(body: string): string | null {
    if (!body.trim()) return "Body is required."
    return null
}

type NewSystemTemplateValues = {
    system_key: string
    name: string
    subject: string
    from_email: string
    body: string
}

function validateNewSystemTemplate(values: NewSystemTemplateValues): FormFieldErrors<NewSystemTemplateValues> {
    return {
        system_key: getSystemKeyError(values.system_key) ?? undefined,
        name: getNameError(values.name) ?? undefined,
        subject: getSubjectError(values.subject) ?? undefined,
        from_email: getFromEmailError(values.from_email) ?? undefined,
        body: getBodyError(values.body) ?? undefined,
    }
}

type NewSystemTemplateField = keyof NewSystemTemplateValues

function recordSelection(
    el: HTMLInputElement | HTMLTextAreaElement,
    ref: MutableRefObject<{ start: number; end: number } | null>
) {
    ref.current = {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
}

function insertIntoTextControl(
    el: HTMLInputElement | HTMLTextAreaElement | null,
    selectionRef: MutableRefObject<{ start: number; end: number } | null>,
    setValue: Dispatch<SetStateAction<string>>,
    token: string
) {
    if (!el) {
        setValue((prev) => `${prev}${token}`)
        return
    }
    const selection = selectionRef.current ?? {
        start: el.selectionStart ?? el.value.length,
        end: el.selectionEnd ?? el.value.length,
    }
    const result = insertAtCursor(el.value, token, selection.start, selection.end)
    setValue(result.nextValue)
    requestAnimationFrame(() => {
        el.focus()
        el.setSelectionRange(result.nextSelectionStart, result.nextSelectionEnd)
        selectionRef.current = { start: result.nextSelectionStart, end: result.nextSelectionEnd }
    })
}

export default function PlatformSystemEmailTemplateNewPage() {
    const { push } = useRouter()
    const createTemplate = useCreatePlatformSystemEmailTemplate()
    const { data: templateVariables = [], isLoading: variablesLoading } =
        usePlatformSystemEmailTemplateVariables("org_invite")

    const [manualSystemKey, setManualSystemKey] = useState<string | null>(null)
    const [name, setName] = useState("")
    const [subject, setSubject] = useState("")
    const [fromEmail, setFromEmail] = useState("")
    const [bodyValue, setBodyValue] = useState<{ body: string; bodyDesign: EmailBodyDesign | null }>({
        body: "",
        bodyDesign: null,
    })
    const body = bodyValue.body
    const [isActive, setIsActive] = useState(true)
    const [saving, setSaving] = useState(false)
    const [view, setView] = useState<EditorView>("edit")

    const subjectRef = useRef<HTMLInputElement | null>(null)
    const subjectSelectionRef = useRef<{ start: number; end: number } | null>(null)
    const designRef = useRef<EmailDesignEditorHandle | null>(null)
    const activeInsertionTargetRef = useRef<ActiveInsertionTarget>(null)

    const setActiveInsertionTarget = (target: ActiveInsertionTarget) => {
        activeInsertionTargetRef.current = target
    }

    const setBody = (value: EmailBodyValue) => {
        setBodyValue((current) =>
            current.body === value.body && current.bodyDesign === value.bodyDesign ? current : value,
        )
    }

    const systemKey = manualSystemKey ?? buildSystemKeyFromName(name)

    const validation = useFormValidation({
        values: { system_key: systemKey, name, subject, from_email: fromEmail, body },
        validate: validateNewSystemTemplate,
    })

    const canValidateVariables = !variablesLoading && templateVariables.length > 0
    const allowedVariableNames = new Set(templateVariables.map((variable) => variable.name))
    const requiredVariableNames: string[] = []
    for (const variable of templateVariables) {
        if (variable.required) {
            requiredVariableNames.push(variable.name)
        }
    }
    const usedVariableNames = extractTemplateVariables(`${subject}\n${body}`)
    const unknownVariables = canValidateVariables
        ? usedVariableNames.filter((variable) => !allowedVariableNames.has(variable))
        : []
    const usedVariableNamesSet = new Set(usedVariableNames)
    const missingRequiredVariables = canValidateVariables
        ? requiredVariableNames.filter((variable) => !usedVariableNamesSet.has(variable))
        : []

    const insertToken = (token: string) => {
        if (activeInsertionTargetRef.current === "subject") {
            insertIntoTextControl(subjectRef.current, subjectSelectionRef, setSubject, token)
            return
        }
        designRef.current?.insertText(token)
    }

    // The server expands {{platform_logo_block}} to the branding logo image.
    const insertPlatformLogo = () => {
        if (body.includes("{{platform_logo_block}}")) return
        designRef.current?.insertText("{{platform_logo_block}}")
        setActiveInsertionTarget("body")
    }

    const handleCreate = async (values: NewSystemTemplateValues) => {
        if (saving) return
        setSaving(true)
        const finishSaving = () => setSaving(false)
        try {
            const created = await createTemplate.mutateAsync({
                system_key: values.system_key.trim(),
                name: values.name.trim(),
                subject: values.subject.trim(),
                from_email: values.from_email.trim() ? values.from_email.trim() : null,
                body: values.body,
                ...(bodyValue.bodyDesign ? { body_design: bodyValue.bodyDesign } : {}),
                is_active: isActive,
            })
            toast.success("System email template created")
            push(`/ops/templates/system/${created.system_key}`)
            finishSaving()
        } catch (error) {
            finishSaving()
            if (error instanceof ApiError && error.status === 409) {
                validation.setServerErrors({ system_key: "A template with this system key already exists." })
                return
            }
            const message = validation.applyApiError(error, {
                fields: ["system_key", "name", "subject", "from_email", "body"],
                fallback: "Couldn't create system email.",
            })
            if (message) toast.error(message)
        }
    }

    const bodyError = validation.errorFor("body")

    return (
        <Tabs value={view} onValueChange={(value) => setView(value as EditorView)} className="gap-0">
            <PageHeader
                title="New System Email"
                back={{ href: "/ops/templates?tab=system", label: "Back to templates" }}
                sticky
                className="top-14"
                actions={
                    <>
                        <TabsList aria-label="Editor view">
                            <TabsTrigger value="edit">Edit</TabsTrigger>
                            <TabsTrigger value="preview">Preview</TabsTrigger>
                            <TabsTrigger value="html">HTML</TabsTrigger>
                        </TabsList>
                        <Button
                            onClick={(event) => {
                                setView("edit")
                                void validation.handleSubmit(handleCreate)(event)
                            }}
                            disabled={saving}
                        >
                            {saving ? (
                                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                            ) : (
                                <PlusIcon className="size-4" aria-hidden="true" />
                            )}
                            Create
                        </Button>
                    </>
                }
            />

            <TabsContent value="edit" keepMounted className="mt-0 flex min-h-[calc(100dvh-8rem)] flex-col data-hidden:hidden">
                <EmailDesignEditor
                    ref={designRef}
                    initialValue={bodyValue}
                    onChange={setBody}
                    variables={templateVariables}
                    onSelectVariable={(variable) => insertToken(`{{${variable.name}}}`)}
                    onFocus={() => setActiveInsertionTarget("body")}
                    invalid={Boolean(bodyError)}
                    error={bodyError ? <FieldError id="body-error">{bodyError}</FieldError> : null}
                    fields={
                        <div className="grid gap-4">
                            <TemplateSettingsFields
                                systemKey={systemKey}
                                systemKeyError={validation.errorFor("system_key")}
                                name={name}
                                nameError={validation.errorFor("name")}
                                subject={subject}
                                subjectError={validation.errorFor("subject")}
                                fromEmail={fromEmail}
                                fromEmailError={validation.errorFor("from_email")}
                                onFieldBlur={validation.touch}
                                subjectRef={subjectRef}
                                subjectSelectionRef={subjectSelectionRef}
                                onSystemKeyChange={setManualSystemKey}
                                onNameChange={setName}
                                onSubjectChange={setSubject}
                                onFromEmailChange={setFromEmail}
                                onActiveInsertionTargetChange={setActiveInsertionTarget}
                            />
                            <TemplateVariableWarnings
                                unknownVariables={unknownVariables}
                                missingRequiredVariables={missingRequiredVariables}
                                show={Boolean(subject.trim() || body.trim())}
                            />
                        </div>
                    }
                    settings={
                        <div className="grid gap-4">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <Label htmlFor="template-active">Active</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Inactive templates cannot be used for campaigns or transactional sends.
                                    </p>
                                </div>
                                <Switch id="template-active" checked={isActive} onCheckedChange={setIsActive} />
                            </div>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={body.includes("{{platform_logo_block}}")}
                                onClick={insertPlatformLogo}
                            >
                                <ImageIcon aria-hidden="true" />
                                Insert logo
                            </Button>
                        </div>
                    }
                />
            </TabsContent>
            <TabsContent value="preview" className="mt-0 flex min-h-[calc(100dvh-8rem)] flex-col">
                <EmailPreviewPane
                    subject={subject}
                    body={body}
                    queryKey={["platform-system", "new"]}
                    modes={["sample", "names"]}
                    load={(request) =>
                        previewPlatformSystemEmailTemplate({
                            subject: request.subject,
                            body: request.body,
                            variable_mode: request.variableMode === "names" ? "names" : "sample",
                            org_id: null,
                        })
                    }
                />
            </TabsContent>
            <TabsContent value="html" className="mt-0 min-h-[calc(100dvh-8rem)] bg-muted/40 p-4 sm:p-6">
                <EmailHtmlSource html={body} />
            </TabsContent>
        </Tabs>
    )
}

function TemplateSettingsFields({
    systemKey,
    systemKeyError,
    name,
    nameError,
    subject,
    subjectError,
    fromEmail,
    fromEmailError,
    subjectRef,
    subjectSelectionRef,
    onFieldBlur,
    onSystemKeyChange,
    onNameChange,
    onSubjectChange,
    onFromEmailChange,
    onActiveInsertionTargetChange,
}: {
    systemKey: string
    systemKeyError: string | undefined
    name: string
    nameError: string | undefined
    subject: string
    subjectError: string | undefined
    fromEmail: string
    fromEmailError: string | undefined
    onFieldBlur: (field: NewSystemTemplateField) => void
    subjectRef: MutableRefObject<HTMLInputElement | null>
    subjectSelectionRef: TextSelectionRef
    onSystemKeyChange: Dispatch<SetStateAction<string | null>>
    onNameChange: Dispatch<SetStateAction<string>>
    onSubjectChange: Dispatch<SetStateAction<string>>
    onFromEmailChange: Dispatch<SetStateAction<string>>
    onActiveInsertionTargetChange: (target: ActiveInsertionTarget) => void
}) {
    return (
        <div className="grid gap-4 sm:grid-cols-2">
            <ValidatedField
                id="system-key"
                label="System key"
                description="Lowercase letters, numbers, and underscores. Cannot be changed later."
                error={systemKeyError}
            >
                {(control) => (
                    <Input
                        {...control}
                        value={systemKey}
                        onChange={(event) => {
                            onSystemKeyChange(event.target.value)
                        }}
                        onBlur={() => onFieldBlur("system_key")}
                        placeholder="e.g. password_reset"
                    />
                )}
            </ValidatedField>
            <ValidatedField id="name" label="Name" error={nameError}>
                {(control) => (
                    <Input
                        {...control}
                        value={name}
                        onChange={(event) => onNameChange(event.target.value)}
                        onBlur={() => onFieldBlur("name")}
                        placeholder="Human-friendly label"
                    />
                )}
            </ValidatedField>
            <Field data-invalid={subjectError ? true : undefined} className="sm:col-span-2">
                <FieldLabel htmlFor="subject">Subject</FieldLabel>
                <Input
                    ref={subjectRef}
                    id="subject"
                    value={subject}
                    aria-invalid={subjectError ? true : undefined}
                    aria-describedby={subjectError ? "subject-error" : undefined}
                    onChange={(event) => onSubjectChange(event.target.value)}
                    onFocus={(event) => {
                        onActiveInsertionTargetChange("subject")
                        recordSelection(event.currentTarget, subjectSelectionRef)
                    }}
                    onBlur={() => onFieldBlur("subject")}
                    onKeyUp={(event) =>
                        recordSelection(event.currentTarget, subjectSelectionRef)
                    }
                    onMouseUp={(event) =>
                        recordSelection(event.currentTarget, subjectSelectionRef)
                    }
                    onSelect={(event) =>
                        recordSelection(event.currentTarget, subjectSelectionRef)
                    }
                    placeholder="Email subject..."
                />
                {subjectError ? <FieldError id="subject-error">{subjectError}</FieldError> : null}
            </Field>
            <ValidatedField
                id="from-email"
                label="From email (optional)"
                error={fromEmailError}
                className="sm:col-span-2"
            >
                {(control) => (
                    <Input
                        {...control}
                        value={fromEmail}
                        onChange={(event) => onFromEmailChange(event.target.value)}
                        onBlur={() => onFieldBlur("from_email")}
                        placeholder="e.g. Surrogacy Force <no-reply@surrogacyforce.com>"
                    />
                )}
            </ValidatedField>
        </div>
    )
}

function TemplateVariableWarnings({
    unknownVariables,
    missingRequiredVariables,
    show,
}: {
    unknownVariables: string[]
    missingRequiredVariables: string[]
    show: boolean
}) {
    if (!show || (unknownVariables.length === 0 && missingRequiredVariables.length === 0)) {
        return null
    }

    return (
        <Alert className="border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
            <AlertTitle>Template variables</AlertTitle>
            <AlertDescription className="text-amber-800 dark:text-amber-100">
                {unknownVariables.length > 0 && (
                    <p>
                        Unknown:{" "}
                        <span className="font-mono">
                            {unknownVariables.map((v) => `{{${v}}}`).join(", ")}
                        </span>
                    </p>
                )}
                {missingRequiredVariables.length > 0 && (
                    <p>
                        Missing required:{" "}
                        <span className="font-mono">
                            {missingRequiredVariables.map((v) => `{{${v}}}`).join(", ")}
                        </span>
                    </p>
                )}
            </AlertDescription>
        </Alert>
    )
}
