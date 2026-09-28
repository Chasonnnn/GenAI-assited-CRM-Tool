"use client"

import type { ReactNode } from "react"
import { Loader2Icon, SendIcon } from "lucide-react"

import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { ValidatedField } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useFormValidation } from "@/lib/forms/use-form-validation"
import { validateEmail } from "@/lib/forms/validators"

const VARIABLE_LABEL_OVERRIDES: Record<string, string> = {
    org_name: "Organization name",
    org_logo_url: "Organization logo URL",
    owner_name: "Owner name",
    status_label: "Status",
}

const UPPERCASE_WORDS = new Set(["id", "url", "ip", "sms"])

/** "first_name" → "First name"; "form_link" → "Form link"; "unsubscribe_url" → "Unsubscribe URL". */
export function formatTemplateVariableLabel(name: string): string {
    const override = VARIABLE_LABEL_OVERRIDES[name]
    if (override) return override
    const words = name
        .split(/[_\s]+/)
        .filter(Boolean)
        .map((word) => (UPPERCASE_WORDS.has(word.toLowerCase()) ? word.toUpperCase() : word.toLowerCase()))
    if (words.length === 0) return name
    const [first = "", ...rest] = words
    const capitalized = UPPERCASE_WORDS.has(first.toLowerCase())
        ? first
        : `${first.charAt(0).toUpperCase()}${first.slice(1)}`
    return [capitalized, ...rest].join(" ")
}

type SendTestEmailDialogProps = {
    open: boolean
    onOpenChange: (open: boolean) => void
    /** One line naming what is sent, for example the template name or "the saved draft". */
    description?: ReactNode
    toEmail: string
    onToEmailChange: (value: string) => void
    ignoreOptOut: boolean
    onIgnoreOptOutChange: (value: boolean) => void
    /** Variables the recipient can override, without unsubscribe_url. */
    variableNames: readonly string[]
    variables: Record<string, string>
    onVariableChange: (name: string, value: string) => void
    variablesLoading?: boolean
    /** The template uses {{unsubscribe_url}}, which is generated per recipient. */
    hasUnsubscribeUrl?: boolean
    /** Sanitized failure message from the last send. */
    error?: string | null
    isSending: boolean
    /** Called only when the recipient is a valid email address. */
    onSend: () => void
}

export function SendTestEmailDialog({
    open,
    onOpenChange,
    description,
    ...formProps
}: SendTestEmailDialogProps) {
    return (
        <Dialog
            open={open}
            onOpenChange={(nextOpen) => {
                if (!nextOpen && formProps.isSending) return
                onOpenChange(nextOpen)
            }}
        >
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Send test email</DialogTitle>
                    {description ? <DialogDescription>{description}</DialogDescription> : null}
                </DialogHeader>
                {/* Mounted only while open, so validation state resets each time the dialog opens. */}
                <SendTestEmailForm {...formProps} onCancel={() => onOpenChange(false)} />
            </DialogContent>
        </Dialog>
    )
}

function SendTestEmailForm({
    toEmail,
    onToEmailChange,
    ignoreOptOut,
    onIgnoreOptOutChange,
    variableNames,
    variables,
    onVariableChange,
    variablesLoading = false,
    hasUnsubscribeUrl = false,
    error,
    isSending,
    onSend,
    onCancel,
}: Omit<SendTestEmailDialogProps, "open" | "onOpenChange" | "description"> & {
    onCancel: () => void
}) {
    const form = useFormValidation({
        values: { toEmail },
        validate: (values) => ({
            toEmail: validateEmail(values.toEmail, {
                requiredMessage: "Enter a recipient email address.",
            }),
        }),
    })

    return (
        <>
            <div className="space-y-4">
                <ValidatedField label="To email" error={form.errorFor("toEmail")}>
                    {(control) => (
                        <Input
                            {...control}
                            type="email"
                            value={toEmail}
                            onChange={(event) => onToEmailChange(event.target.value)}
                            onBlur={() => form.touch("toEmail")}
                            placeholder="test@example.com"
                        />
                    )}
                </ValidatedField>

                <div className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3">
                    <Checkbox
                        id="send-test-ignore-opt-out"
                        checked={ignoreOptOut}
                        onCheckedChange={(checked) => onIgnoreOptOutChange(checked === true)}
                        aria-describedby="send-test-ignore-opt-out-hint"
                    />
                    <div className="space-y-1">
                        <Label htmlFor="send-test-ignore-opt-out" className="cursor-pointer">
                            Send even if unsubscribed
                        </Label>
                        <p
                            id="send-test-ignore-opt-out-hint"
                            className="text-xs text-muted-foreground"
                        >
                            Test-only override for marketing opt-outs. Hard bounces and complaints
                            remain suppressed.
                        </p>
                    </div>
                </div>

                <Accordion defaultValue={[]} className="rounded-lg">
                    <AccordionItem value="variables">
                        <AccordionTrigger>Variables (optional)</AccordionTrigger>
                        <AccordionContent>
                            <div className="space-y-3">
                                {variablesLoading ? (
                                    <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                                        Loading variables…
                                    </div>
                                ) : (
                                    <>
                                        {hasUnsubscribeUrl ? (
                                            <p className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                                                The unsubscribe link is generated for the recipient.
                                            </p>
                                        ) : null}
                                        {variableNames.length === 0 ? (
                                            <p className="text-sm text-muted-foreground">
                                                No variables in this template.
                                            </p>
                                        ) : (
                                            variableNames.map((name) => (
                                                <div key={name} className="space-y-1">
                                                    <Label htmlFor={`send-test-variable-${name}`}>
                                                        {formatTemplateVariableLabel(name)}
                                                    </Label>
                                                    <Input
                                                        id={`send-test-variable-${name}`}
                                                        value={variables[name] ?? ""}
                                                        onChange={(event) =>
                                                            onVariableChange(name, event.target.value)
                                                        }
                                                    />
                                                </div>
                                            ))
                                        )}
                                    </>
                                )}
                            </div>
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>

                {error ? (
                    <p role="alert" className="text-sm text-destructive">
                        {error}
                    </p>
                ) : null}
            </div>

            <DialogFooter>
                <Button variant="outline" onClick={onCancel} disabled={isSending}>
                    Cancel
                </Button>
                <Button onClick={form.handleSubmit(() => onSend())} disabled={isSending}>
                    {isSending ? (
                        <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                        <SendIcon className="size-4" aria-hidden="true" />
                    )}
                    Send test email
                </Button>
            </DialogFooter>
        </>
    )
}
