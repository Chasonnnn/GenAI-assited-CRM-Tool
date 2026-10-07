import { useState } from "react"
import Link from "@/components/app-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DialogBody, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { CopyField } from "@/components/ui/copy-field"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog"
import { ActivityIcon, AlertTriangleIcon, Loader2Icon, CheckIcon, XCircleIcon, CheckCircleIcon, RotateCwIcon } from "lucide-react"
import { useResendSettings, useUpdateResendSettings, useTestResendKey, useRotateWebhook, useEligibleSenders } from "@/lib/hooks/use-resend"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "@/components/ui/toast"
import type { TestKeyResponse, ResendSettings, ResendSettingsUpdate, EligibleSender } from "@/lib/api/resend"
import { IntegrationDialogLoadingState } from "./integration-shared"

function getEligibleSenderLabel(
    senders:
        | Array<{
            user_id: string
            display_name: string
            gmail_email: string
        }>
        | null
        | undefined,
    value: string | null | undefined,
): string {
    if (!value) return ""
    const sender = senders?.find((item) => item.user_id === value)
    if (!sender) return ""
    return `${sender.display_name} (${sender.gmail_email})`
}

type EmailConfigurationFormState = {
    provider: "resend" | "gmail" | ""
    apiKey: string
    rateLimitGroupConfigured: boolean
    rateLimitGroupEnabled: boolean
    rateLimitGroupToken: string
    replaceRateLimitGroupToken: boolean
    clearRateLimitGroup: boolean
    verifiedDomain: string
    fromEmail: string
    fromName: string
    replyTo: string
    webhookTrackingEnabled: boolean
    clearWebhookTracking: boolean
    replaceWebhookSigningSecret: boolean
    webhookSigningSecret: string
    defaultSender: string
}

type EmailConfigurationUiState = {
    keyTested: TestKeyResponse | null
    saved: boolean
    isEditingKey: boolean
    hasUserEdited: boolean
}

const createEmailConfigurationFormState = (
    settings: ResendSettings | undefined,
): EmailConfigurationFormState => ({
    provider: settings?.email_provider || "resend",
    apiKey: "",
    rateLimitGroupConfigured: settings?.rate_limit_group_configured ?? false,
    rateLimitGroupEnabled: settings?.rate_limit_group_configured ?? false,
    rateLimitGroupToken: "",
    replaceRateLimitGroupToken: false,
    clearRateLimitGroup: false,
    verifiedDomain: settings?.verified_domain || "",
    fromEmail: settings?.from_email || "",
    fromName: settings?.from_name || "",
    replyTo: settings?.reply_to_email || "",
    webhookTrackingEnabled:
        settings?.webhook_signing_secret_configured ?? false,
    clearWebhookTracking: false,
    replaceWebhookSigningSecret: false,
    webhookSigningSecret: "",
    defaultSender: settings?.default_sender_user_id || "",
})

const changeEmailConfigurationProvider = (
    current: EmailConfigurationFormState,
    provider: EmailConfigurationFormState["provider"],
): EmailConfigurationFormState => ({
    ...current,
    provider,
    apiKey: provider !== "resend" ? "" : current.apiKey,
    rateLimitGroupEnabled:
        provider === "resend"
            ? current.rateLimitGroupConfigured
            : current.rateLimitGroupEnabled,
    rateLimitGroupToken:
        provider !== "resend" ? "" : current.rateLimitGroupToken,
    replaceRateLimitGroupToken:
        provider !== "resend" ? false : current.replaceRateLimitGroupToken,
    clearRateLimitGroup:
        provider !== "resend" ? false : current.clearRateLimitGroup,
    clearWebhookTracking:
        provider !== "resend" ? false : current.clearWebhookTracking,
    replaceWebhookSigningSecret:
        provider !== "resend" ? false : current.replaceWebhookSigningSecret,
    webhookSigningSecret:
        provider !== "resend" ? "" : current.webhookSigningSecret,
})

/** DialogBody and DialogFooter of the Email Configuration dialog. */
export function EmailConfigurationSection() {
    const { data: settings, isLoading } = useResendSettings()

    return (
        <EmailConfigurationSectionContent
            key={settings ? "loaded" : "loading"}
            settings={settings}
            isLoading={isLoading}
        />
    )
}

function EmailConfigurationSectionContent({
    settings,
    isLoading,
}: {
    settings: ReturnType<typeof useResendSettings>["data"]
    isLoading: boolean
}) {
    const updateSettings = useUpdateResendSettings()
    const testKey = useTestResendKey()
    const rotateWebhook = useRotateWebhook()
    const [emailForm, setEmailForm] = useState<EmailConfigurationFormState>(
        () => createEmailConfigurationFormState(settings),
    )
    const [emailUi, setEmailUi] = useState<EmailConfigurationUiState>({
        keyTested: null,
        saved: false,
        isEditingKey: false,
        hasUserEdited: false,
    })
    const { data: eligibleSenders, isLoading: eligibleSendersLoading } = useEligibleSenders(emailForm.provider === "gmail")

    const updateEmailForm = <K extends keyof EmailConfigurationFormState>(
        field: K,
        value: EmailConfigurationFormState[K],
        markEdited = false,
    ) => {
        setEmailForm((current) => ({ ...current, [field]: value }))
        if (markEdited) {
            setEmailUi((current) => ({ ...current, hasUserEdited: true }))
        }
    }

    const handleProviderChange = (value: "resend" | "gmail" | "") => {
        setEmailForm((current) =>
            changeEmailConfigurationProvider(current, value),
        )
        setEmailUi((current) => ({
            ...current,
            hasUserEdited: true,
            saved: false,
            keyTested: null,
            isEditingKey: value !== "resend" ? false : current.isEditingKey,
        }))
    }

    const handleTestKey = async () => {
        if (!emailForm.apiKey.trim()) return
        setEmailUi((current) => ({ ...current, keyTested: null }))
        try {
            const result = await testKey.mutateAsync(emailForm.apiKey)
            setEmailUi((current) => ({ ...current, keyTested: result }))
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't test the API key") ?? "Couldn't test the API key"
            setEmailUi((current) => ({
                ...current,
                keyTested: {
                    valid: false,
                    error: message,
                    verified_domains: [],
                    permission_limited: false,
                    warning: null,
                },
            }))
            toast.error(message)
        }
    }

    const handleSave = async () => {
        const update: ResendSettingsUpdate = {
            email_provider: emailForm.provider,
        }

        if (settings?.current_version !== undefined) {
            update.expected_version = settings.current_version
        }

        if (emailForm.provider === "resend") {
            if (emailForm.apiKey.trim()) {
                update.api_key = emailForm.apiKey
            }
            if (emailForm.clearRateLimitGroup) {
                update.rate_limit_group_token = ""
            } else if (
                emailForm.rateLimitGroupEnabled &&
                (!emailForm.rateLimitGroupConfigured ||
                    emailForm.replaceRateLimitGroupToken) &&
                emailForm.rateLimitGroupToken.trim()
            ) {
                update.rate_limit_group_token = emailForm.rateLimitGroupToken.trim()
            }
            update.verified_domain = emailForm.verifiedDomain.trim()
            update.from_email = emailForm.fromEmail
            update.from_name = emailForm.fromName
            update.reply_to_email = emailForm.replyTo
            if (emailForm.clearWebhookTracking) {
                update.webhook_signing_secret = ""
            } else if (emailForm.webhookSigningSecret.trim()) {
                update.webhook_signing_secret = emailForm.webhookSigningSecret.trim()
            }
        } else if (emailForm.provider === "gmail") {
            update.default_sender_user_id = emailForm.defaultSender || null
        }

        try {
            const savedSettings = await updateSettings.mutateAsync(update)
            setEmailForm((current) => ({
                ...current,
                apiKey: "",
                rateLimitGroupConfigured:
                    savedSettings?.rate_limit_group_configured ??
                    current.rateLimitGroupConfigured,
                rateLimitGroupEnabled:
                    savedSettings?.rate_limit_group_configured ??
                    current.rateLimitGroupEnabled,
                rateLimitGroupToken: "",
                replaceRateLimitGroupToken: false,
                clearRateLimitGroup: false,
                webhookTrackingEnabled:
                    savedSettings?.webhook_signing_secret_configured ??
                    current.webhookTrackingEnabled,
                clearWebhookTracking: false,
                replaceWebhookSigningSecret: false,
                webhookSigningSecret: "",
            }))
            setEmailUi((current) => ({
                ...current,
                keyTested: null,
                isEditingKey: false,
                hasUserEdited: false,
                saved: true,
            }))
            toast.success("Email configuration saved")
            setTimeout(() => {
                setEmailUi((current) => ({ ...current, saved: false }))
            }, 2000)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save email configuration")
            if (message) toast.error(message)
        }
    }

    // Runs from the rotate confirmation, which shows a failure inline and stays open.
    const handleRotateWebhook = async () => {
        await rotateWebhook.mutateAsync()
        toast.success("Webhook URL rotated. Update Resend to use the new URL.")
    }

    const hasResendKey = Boolean(emailForm.apiKey.trim() || settings?.api_key_masked)
    const newResendKeyValidated = Boolean(
        !emailForm.apiKey.trim() || emailUi.keyTested?.valid,
    )
    const hasVerifiedDomain = Boolean(emailForm.verifiedDomain.trim())
    const hasFromEmail = Boolean(emailForm.fromEmail.trim())
    const hasGmailSender = Boolean(emailForm.defaultSender)
    const normalizedRateLimitGroupToken = emailForm.rateLimitGroupToken.trim()
    const rateLimitGroupTokenInvalid = Boolean(
        normalizedRateLimitGroupToken &&
        (normalizedRateLimitGroupToken.length < 32 ||
            normalizedRateLimitGroupToken.length > 256),
    )
    const rateLimitGroupReady = Boolean(
        emailForm.provider !== "resend" ||
        !emailForm.rateLimitGroupEnabled ||
        (emailForm.rateLimitGroupConfigured &&
            !emailForm.replaceRateLimitGroupToken &&
            !emailForm.clearRateLimitGroup) ||
        normalizedRateLimitGroupToken,
    )
    const normalizedVerifiedDomain = emailForm.verifiedDomain.trim().toLowerCase()
    const normalizedFromEmail = emailForm.fromEmail.trim().toLowerCase()
    const senderIdentityChanged = Boolean(
        emailForm.provider === "resend" &&
        (normalizedVerifiedDomain !==
            (settings?.verified_domain?.trim().toLowerCase() ?? "") ||
            normalizedFromEmail !==
            (settings?.from_email?.trim().toLowerCase() ?? "")),
    )
    const storedCredentialRetestRequired = Boolean(
        settings?.api_key_masked &&
        senderIdentityChanged &&
        !emailUi.keyTested?.valid,
    )
    const testedDomains = emailUi.keyTested?.verified_domains ?? []
    const testedDomainMismatch = Boolean(
        emailUi.keyTested?.valid &&
        !emailUi.keyTested.permission_limited &&
        !testedDomains.includes(normalizedVerifiedDomain),
    )
    const webhookTrackingReady = Boolean(
        emailForm.provider !== "resend" ||
        !emailForm.webhookTrackingEnabled ||
        (settings?.webhook_signing_secret_configured &&
            !emailForm.replaceWebhookSigningSecret) ||
        emailForm.webhookSigningSecret.trim(),
    )
    const resendReady =
        emailForm.provider !== "resend" ||
        (hasResendKey &&
            newResendKeyValidated &&
            hasVerifiedDomain &&
            hasFromEmail &&
            !storedCredentialRetestRequired &&
            !testedDomainMismatch)
    const gmailReady = emailForm.provider !== "gmail" || hasGmailSender
    const canSave =
        Boolean(emailForm.provider) &&
        resendReady &&
        gmailReady &&
        rateLimitGroupReady &&
        !rateLimitGroupTokenInvalid &&
        webhookTrackingReady
    const showMaskedKey = Boolean(settings?.api_key_masked) && !emailUi.isEditingKey && !emailForm.apiKey

    if (isLoading) {
        return <IntegrationDialogLoadingState />
    }

    return (
        <>
            <DialogBody>
                <EmailSettingsFields
                    form={emailForm}
                    ui={emailUi}
                    settings={settings}
                    eligibleSenders={eligibleSenders ?? []}
                    eligibleSendersLoading={eligibleSendersLoading}
                    showMaskedKey={showMaskedKey}
                    storedCredentialRetestRequired={storedCredentialRetestRequired}
                    rateLimitGroupTokenInvalid={rateLimitGroupTokenInvalid}
                    pendingState={{
                        keyTest: testKey.isPending,
                        webhookRotate: rotateWebhook.isPending,
                    }}
                    onProviderChange={handleProviderChange}
                    updateEmailForm={updateEmailForm}
                    onApiKeyChange={(apiKey) => {
                        updateEmailForm("apiKey", apiKey, true)
                        setEmailUi((current) => ({
                            ...current,
                            keyTested: null,
                            isEditingKey: true,
                        }))
                    }}
                    onEditKey={() => {
                        updateEmailForm("apiKey", "", true)
                        setEmailUi((current) => ({
                            ...current,
                            isEditingKey: true,
                            keyTested: null,
                        }))
                    }}
                    onCancelKeyEdit={() => {
                        updateEmailForm("apiKey", "")
                        setEmailUi((current) => ({
                            ...current,
                            isEditingKey: false,
                            keyTested: null,
                        }))
                    }}
                    onTestKey={handleTestKey}
                    onRotateWebhook={handleRotateWebhook}
                />
            </DialogBody>
            <DialogFooter
                start={(
                    <Button variant="ghost" render={<Link href="/settings/integrations/email" />}>
                        <ActivityIcon aria-hidden="true" />
                        View email operations
                    </Button>
                )}
            >
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <EmailSaveButton
                    pending={updateSettings.isPending}
                    saved={emailUi.saved}
                    disabled={!canSave}
                    onSave={() => {
                        void handleSave()
                    }}
                />
            </DialogFooter>
        </>
    )
}

type UpdateEmailConfigurationForm = <K extends keyof EmailConfigurationFormState>(
    field: K,
    value: EmailConfigurationFormState[K],
    markEdited?: boolean,
) => void

function EmailSettingsFields({
    form,
    ui,
    settings,
    eligibleSenders,
    eligibleSendersLoading,
    showMaskedKey,
    storedCredentialRetestRequired,
    rateLimitGroupTokenInvalid,
    pendingState,
    onProviderChange,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    eligibleSenders: EligibleSender[]
    eligibleSendersLoading: boolean
    showMaskedKey: boolean
    storedCredentialRetestRequired: boolean
    rateLimitGroupTokenInvalid: boolean
    pendingState: {
        keyTest: boolean
        webhookRotate: boolean
    }
    onProviderChange: (provider: "resend" | "gmail" | "") => void
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-6">
            <EmailProviderField
                provider={form.provider}
                onProviderChange={onProviderChange}
            />

            {form.provider === "resend" ? (
                <ResendConfigurationFields
                    form={form}
                    ui={ui}
                    settings={settings}
                    showMaskedKey={showMaskedKey}
                    storedCredentialRetestRequired={storedCredentialRetestRequired}
                    rateLimitGroupTokenInvalid={rateLimitGroupTokenInvalid}
                    pendingState={pendingState}
                    updateEmailForm={updateEmailForm}
                    onApiKeyChange={onApiKeyChange}
                    onEditKey={onEditKey}
                    onCancelKeyEdit={onCancelKeyEdit}
                    onTestKey={onTestKey}
                    onRotateWebhook={onRotateWebhook}
                />
            ) : null}

            {form.provider === "gmail" ? (
                <GmailConfigurationFields
                    defaultSender={form.defaultSender}
                    eligibleSenders={eligibleSenders}
                    eligibleSendersLoading={eligibleSendersLoading}
                    settings={settings}
                    onDefaultSenderChange={(defaultSender) =>
                        updateEmailForm("defaultSender", defaultSender, true)
                    }
                />
            ) : null}
        </div>
    )
}

function EmailProviderField({
    provider,
    onProviderChange,
}: {
    provider: EmailConfigurationFormState["provider"]
    onProviderChange: (provider: "resend" | "gmail" | "") => void
}) {
    return (
        <div className="space-y-3">
            <Label htmlFor="email-provider">Email Provider</Label>
            <RadioGroup
                value={provider}
                onValueChange={(value) => onProviderChange(value as "resend" | "gmail" | "")}
                className="flex flex-col gap-3"
                id="email-provider"
                aria-label="Email provider"
            >
                <div className="flex items-center gap-2">
                    <RadioGroupItem value="resend" id="provider-resend" />
                    <Label htmlFor="provider-resend" className="cursor-pointer">
                        <span className="font-medium">Resend</span>
                        <span className="ml-2 text-xs text-muted-foreground">(Recommended)</span>
                    </Label>
                </div>
                <div className="flex items-center gap-2">
                    <RadioGroupItem value="gmail" id="provider-gmail" />
                    <Label htmlFor="provider-gmail" className="cursor-pointer">
                        <span className="font-medium">Gmail</span>
                        <span className="ml-2 text-xs text-muted-foreground">(Org admin account)</span>
                    </Label>
                </div>
            </RadioGroup>
        </div>
    )
}

function ResendConfigurationFields({
    form,
    ui,
    settings,
    showMaskedKey,
    storedCredentialRetestRequired,
    rateLimitGroupTokenInvalid,
    pendingState,
    updateEmailForm,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    ui: EmailConfigurationUiState
    settings: ResendSettings | undefined
    showMaskedKey: boolean
    storedCredentialRetestRequired: boolean
    rateLimitGroupTokenInvalid: boolean
    pendingState: {
        keyTest: boolean
        webhookRotate: boolean
    }
    updateEmailForm: UpdateEmailConfigurationForm
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <h3 className="text-sm font-medium">Resend Configuration</h3>

            <ResendApiKeyField
                apiKey={form.apiKey}
                apiKeyMasked={settings?.api_key_masked ?? null}
                keyTested={ui.keyTested}
                editingKey={ui.isEditingKey}
                showMaskedKey={showMaskedKey}
                pending={pendingState.keyTest}
                onApiKeyChange={onApiKeyChange}
                onEditKey={onEditKey}
                onCancelKeyEdit={onCancelKeyEdit}
                onTestKey={onTestKey}
            />

            {storedCredentialRetestRequired ? (
                <Alert
                    id="resend-sender-retest-alert"
                    variant="destructive"
                >
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Re-test sender access</AlertTitle>
                    <AlertDescription>
                        These sender changes are not verified. Re-enter the
                        stored Resend credential with Change Key, then test it
                        before saving.
                    </AlertDescription>
                </Alert>
            ) : null}

            <ResendVerifiedDomainField
                value={form.verifiedDomain}
                keyTested={ui.keyTested}
                storedCredentialRetestRequired={storedCredentialRetestRequired}
                onChange={(verifiedDomain) =>
                    updateEmailForm("verifiedDomain", verifiedDomain, true)
                }
            />

            <div className="space-y-2">
                <Label htmlFor="from-email">From Email</Label>
                <Input
                    id="from-email"
                    type="email"
                    value={form.fromEmail}
                    onChange={(event) => updateEmailForm("fromEmail", event.target.value, true)}
                    aria-invalid={storedCredentialRetestRequired}
                    aria-describedby={
                        storedCredentialRetestRequired
                            ? "resend-sender-retest-alert"
                            : undefined
                    }
                    placeholder={
                        form.verifiedDomain
                            ? `no-reply@${form.verifiedDomain}`
                            : "no-reply@yourdomain.com"
                    }
                    name="from-email"
                    autoComplete="email"
                />
                <p className="text-xs text-muted-foreground">
                    Enter the complete sender address. Its domain must match the
                    verified domain above.
                </p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="from-name">From Name (optional)</Label>
                <Input
                    id="from-name"
                    value={form.fromName}
                    onChange={(event) => updateEmailForm("fromName", event.target.value, true)}
                    placeholder="Your Company Name"
                    name="from-name"
                    autoComplete="organization"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="reply-to">Reply-To Email (optional)</Label>
                <Input
                    id="reply-to"
                    type="email"
                    value={form.replyTo}
                    onChange={(event) => updateEmailForm("replyTo", event.target.value, true)}
                    placeholder="support@yourdomain.com"
                    name="reply-to"
                    autoComplete="email"
                />
            </div>

            <ResendWebhookTrackingField
                form={form}
                settings={settings}
                pending={pendingState.webhookRotate}
                updateEmailForm={updateEmailForm}
                onRotateWebhook={onRotateWebhook}
            />

            <ResendRateLimitGroupField
                form={form}
                invalid={rateLimitGroupTokenInvalid}
                updateEmailForm={updateEmailForm}
            />
        </div>
    )
}

function ResendWebhookTrackingField({
    form,
    settings,
    pending,
    updateEmailForm,
    onRotateWebhook,
}: {
    form: EmailConfigurationFormState
    settings: ResendSettings | undefined
    pending: boolean
    updateEmailForm: UpdateEmailConfigurationForm
    onRotateWebhook: () => Promise<void>
}) {
    const [disableTrackingDialogOpen, setDisableTrackingDialogOpen] =
        useState(false)
    const webhookTrackingConfigured =
        settings?.webhook_signing_secret_configured ?? false
    const status = form.clearWebhookTracking
        ? { label: "Pending disable", variant: "secondary" as const }
        : form.webhookTrackingEnabled && webhookTrackingConfigured
          ? { label: "Tracking enabled", variant: "default" as const }
          : form.webhookTrackingEnabled
            ? { label: "Setup required", variant: "secondary" as const }
            : { label: "Optional", variant: "outline" as const }

    const handleTrackingChange = (checked: boolean) => {
        if (!checked && webhookTrackingConfigured && !form.clearWebhookTracking) {
            setDisableTrackingDialogOpen(true)
            return
        }

        updateEmailForm("webhookTrackingEnabled", checked, true)
        if (checked) {
            updateEmailForm("clearWebhookTracking", false)
        } else {
            updateEmailForm("replaceWebhookSigningSecret", false)
            updateEmailForm("webhookSigningSecret", "")
        }
    }

    const confirmDisableTracking = () => {
        updateEmailForm("webhookTrackingEnabled", false, true)
        updateEmailForm("clearWebhookTracking", true)
        updateEmailForm("replaceWebhookSigningSecret", false)
        updateEmailForm("webhookSigningSecret", "")
        setDisableTrackingDialogOpen(false)
    }

    return (
        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id="resend-webhook-tracking"
                        checked={form.webhookTrackingEnabled}
                        onCheckedChange={(checked) =>
                            handleTrackingChange(checked === true)
                        }
                    />
                    <div className="space-y-1">
                        <Label
                            htmlFor="resend-webhook-tracking"
                            className="cursor-pointer"
                        >
                            Enable Resend webhook tracking (optional)
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            Track delivery, opens, and clicks with verified Resend events.
                        </p>
                    </div>
                </div>
                <Badge variant={status.variant}>{status.label}</Badge>
            </div>

            {form.webhookTrackingEnabled ? (
                <div className="space-y-3">
                    {settings?.webhook_url ? (
                        <ResendWebhookUrlField
                            webhookUrl={settings.webhook_url}
                            pending={pending}
                            onRotateWebhook={onRotateWebhook}
                        />
                    ) : null}

                    {webhookTrackingConfigured &&
                    !form.replaceWebhookSigningSecret ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
                            <p className="text-sm text-muted-foreground">
                                Signing secret is stored securely.
                            </p>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                    updateEmailForm(
                                        "replaceWebhookSigningSecret",
                                        true,
                                        true,
                                    )
                                }
                            >
                                Replace secret
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label htmlFor="resend-webhook-secret">
                                Webhook Signing Secret
                            </Label>
                            <Input
                                id="resend-webhook-secret"
                                type="password"
                                value={form.webhookSigningSecret}
                                onChange={(event) =>
                                    updateEmailForm(
                                        "webhookSigningSecret",
                                        event.target.value,
                                        true,
                                    )
                                }
                                placeholder="whsec_…"
                                name="resend-webhook-signing-secret"
                                autoComplete="off"
                            />
                            <p className="text-xs text-muted-foreground">
                                Paste the signing secret from Resend. It is encrypted
                                and never shown again.
                            </p>
                            {webhookTrackingConfigured ? (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                        updateEmailForm("webhookSigningSecret", "")
                                        updateEmailForm(
                                            "replaceWebhookSigningSecret",
                                            false,
                                            true,
                                        )
                                    }}
                                >
                                    Cancel replacement
                                </Button>
                            ) : null}
                        </div>
                    )}
                </div>
            ) : form.clearWebhookTracking ? (
                <Alert>
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Tracking pending disable</AlertTitle>
                    <AlertDescription>
                        Tracking will be disabled when you save. Sending email is
                        unaffected.
                    </AlertDescription>
                </Alert>
            ) : null}

            <AlertDialog
                open={disableTrackingDialogOpen}
                onOpenChange={setDisableTrackingDialogOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Disable webhook tracking?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Delivery, open, and click events will stop being verified
                            after you save. Sending email through Resend will continue.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep tracking</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            onClick={confirmDisableTracking}
                        >
                            Disable tracking
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

function ResendRateLimitGroupField({
    form,
    invalid,
    updateEmailForm,
}: {
    form: EmailConfigurationFormState
    invalid: boolean
    updateEmailForm: UpdateEmailConfigurationForm
}) {
    const [disableDialogOpen, setDisableDialogOpen] = useState(false)
    const status = form.clearRateLimitGroup
        ? { label: "Pending disable", variant: "secondary" as const }
        : form.rateLimitGroupEnabled && form.rateLimitGroupConfigured
          ? { label: "Group configured", variant: "default" as const }
          : form.rateLimitGroupEnabled
            ? { label: "Setup required", variant: "secondary" as const }
            : { label: "Optional", variant: "outline" as const }

    const handleEnabledChange = (checked: boolean) => {
        if (
            !checked &&
            form.rateLimitGroupConfigured &&
            !form.clearRateLimitGroup
        ) {
            setDisableDialogOpen(true)
            return
        }

        updateEmailForm("rateLimitGroupEnabled", checked, true)
        if (checked) {
            updateEmailForm("clearRateLimitGroup", false)
            return
        }

        updateEmailForm("replaceRateLimitGroupToken", false)
        updateEmailForm("rateLimitGroupToken", "")
    }

    const confirmDisable = () => {
        updateEmailForm("rateLimitGroupEnabled", false, true)
        updateEmailForm("clearRateLimitGroup", true)
        updateEmailForm("replaceRateLimitGroupToken", false)
        updateEmailForm("rateLimitGroupToken", "")
        setDisableDialogOpen(false)
    }

    return (
        <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                    <Checkbox
                        id="resend-rate-limit-group-enabled"
                        checked={form.rateLimitGroupEnabled}
                        onCheckedChange={(checked) =>
                            handleEnabledChange(checked === true)
                        }
                    />
                    <div className="space-y-1">
                        <Label
                            htmlFor="resend-rate-limit-group-enabled"
                            className="cursor-pointer"
                        >
                            Use shared Resend team rate-limit group (optional)
                        </Label>
                        <p className="text-xs text-muted-foreground">
                            Coordinate rate limiting across API keys in the same
                            Resend team.
                        </p>
                    </div>
                </div>
                <Badge variant={status.variant}>{status.label}</Badge>
            </div>

            {form.rateLimitGroupEnabled ? (
                <div className="space-y-3">
                    {form.rateLimitGroupConfigured &&
                    !form.replaceRateLimitGroupToken ? (
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border bg-background p-3">
                            <p className="text-sm text-muted-foreground">
                                Shared group token is stored securely.
                            </p>
                            <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                    updateEmailForm(
                                        "replaceRateLimitGroupToken",
                                        true,
                                        true,
                                    )
                                }
                            >
                                Replace token
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label htmlFor="resend-rate-limit-group">
                                Resend team rate-limit group token
                            </Label>
                            <Input
                                id="resend-rate-limit-group"
                                name="resend-rate-limit-group"
                                type="password"
                                autoComplete="off"
                                value={form.rateLimitGroupToken}
                                onChange={(event) =>
                                    updateEmailForm(
                                        "rateLimitGroupToken",
                                        event.target.value,
                                        true,
                                    )
                                }
                                placeholder="Enter a shared token with at least 32 characters"
                                aria-invalid={invalid}
                                aria-describedby="resend-rate-limit-group-help"
                            />
                            {form.rateLimitGroupConfigured ? (
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => {
                                        updateEmailForm("rateLimitGroupToken", "")
                                        updateEmailForm(
                                            "replaceRateLimitGroupToken",
                                            false,
                                            true,
                                        )
                                    }}
                                >
                                    Cancel replacement
                                </Button>
                            ) : null}
                        </div>
                    )}

                    <div
                        id="resend-rate-limit-group-help"
                        className="space-y-1 text-xs"
                    >
                        <p className="text-muted-foreground">
                            Use the same token for every API key in the same Resend
                            team. The default limit is 5 requests per second shared
                            across the team.
                        </p>
                        {invalid ? (
                            <p className="text-destructive">
                                Token must be between 32 and 256 characters.
                            </p>
                        ) : null}
                    </div>
                </div>
            ) : null}

            {form.clearRateLimitGroup ? (
                <Alert>
                    <AlertTriangleIcon aria-hidden="true" />
                    <AlertTitle>Shared group pending disable</AlertTitle>
                    <AlertDescription>
                        The saved rate-limit group will be removed when you save.
                    </AlertDescription>
                </Alert>
            ) : null}

            <AlertDialog
                open={disableDialogOpen}
                onOpenChange={setDisableDialogOpen}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            Disable the shared rate-limit group?
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            After you save, this organization will no longer share
                            one admission limit with other API keys in the same
                            Resend team. Email sending will remain available.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Keep shared group</AlertDialogCancel>
                        <AlertDialogAction
                            variant="destructive"
                            onClick={confirmDisable}
                        >
                            Disable shared group
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    )
}

function ResendApiKeyField({
    apiKey,
    apiKeyMasked,
    keyTested,
    editingKey,
    showMaskedKey,
    pending,
    onApiKeyChange,
    onEditKey,
    onCancelKeyEdit,
    onTestKey,
}: {
    apiKey: string
    apiKeyMasked: string | null
    keyTested: EmailConfigurationUiState["keyTested"]
    editingKey: boolean
    showMaskedKey: boolean
    pending: boolean
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onCancelKeyEdit: () => void
    onTestKey: () => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="resend-key">API Key</Label>
            <div className="flex gap-2">
                <Input
                    id="resend-key"
                    type="password"
                    value={showMaskedKey ? apiKeyMasked ?? "" : apiKey}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder="re_…"
                    disabled={showMaskedKey}
                    className="flex-1"
                    name="resend-api-key"
                    autoComplete="off"
                />
                {showMaskedKey ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onEditKey}
                        className="shrink-0"
                    >
                        Change Key
                    </Button>
                ) : (
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onTestKey}
                            disabled={!apiKey.trim() || pending}
                        >
                            {pending ? (
                                <Loader2Icon
                                    className="size-4 animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                            ) : keyTested?.valid ? (
                                <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                            ) : keyTested !== null ? (
                                <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                            ) : (
                                "Test"
                            )}
                        </Button>
                        {apiKeyMasked && editingKey ? (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={onCancelKeyEdit}
                            >
                                Cancel
                            </Button>
                        ) : null}
                    </div>
                )}
            </div>
            <ResendVerifiedDomainBanner keyTested={keyTested} />
            <p className="text-xs text-muted-foreground">
                Testing checks Resend domain access only and never sends an
                email. Full access keys can list verified domains; Sending
                access keys may require manual domain entry. Test a new key
                before saving. Get your key from{" "}
                <a
                    href="https://resend.com/api-keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                >
                    resend.com/api-keys
                </a>
                , or{" "}
                <a
                    href="https://resend.com/docs/dashboard/api-keys/introduction"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                >
                    review Resend key permissions
                </a>
                .
            </p>
        </div>
    )
}

function ResendVerifiedDomainBanner({
    keyTested,
}: {
    keyTested: EmailConfigurationUiState["keyTested"]
}) {
    if (keyTested?.valid && keyTested.permission_limited) {
        return (
            <Alert>
                <AlertTriangleIcon aria-hidden="true" />
                <AlertTitle>Domain access is permission-limited</AlertTitle>
                <AlertDescription className="space-y-1">
                    <p>{keyTested.warning}</p>
                    <p>
                        Enter a domain you have already verified in Resend. This
                        app cannot confirm domain verification with this key.
                    </p>
                </AlertDescription>
            </Alert>
        )
    }

    if (keyTested?.valid) {
        return (
            <Alert>
                <CheckCircleIcon aria-hidden="true" />
                <AlertTitle>API key accepted</AlertTitle>
                <AlertDescription className="space-y-1">
                    <p>
                        No domain was selected automatically. Enter one of the
                        verified domains in the field below.
                    </p>
                    <p>
                        {keyTested.verified_domains.length > 0
                            ? `Available verified domains: ${keyTested.verified_domains.join(", ")}`
                            : "No verified domains were returned for this account."}
                    </p>
                </AlertDescription>
            </Alert>
        )
    }

    if (keyTested && !keyTested.valid) {
        return (
            <Alert variant="destructive">
                <XCircleIcon aria-hidden="true" />
                <AlertTitle>API key is invalid</AlertTitle>
                <AlertDescription>
                    {keyTested.error || "Resend rejected this API key."}
                </AlertDescription>
            </Alert>
        )
    }

    return null
}

function ResendVerifiedDomainField({
    value,
    keyTested,
    storedCredentialRetestRequired,
    onChange,
}: {
    value: string
    keyTested: EmailConfigurationUiState["keyTested"]
    storedCredentialRetestRequired: boolean
    onChange: (verifiedDomain: string) => void
}) {
    const normalizedValue = value.trim().toLowerCase()
    const domainRejectedByFullAccessKey = Boolean(
        normalizedValue &&
        keyTested?.valid &&
        !keyTested.permission_limited &&
        !keyTested.verified_domains.includes(normalizedValue),
    )

    return (
        <div className="space-y-2">
            <Label htmlFor="resend-verified-domain">Verified domain</Label>
            <Input
                id="resend-verified-domain"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                placeholder="example.com"
                name="resend-verified-domain"
                autoComplete="off"
                aria-invalid={
                    storedCredentialRetestRequired ||
                    domainRejectedByFullAccessKey
                }
                aria-describedby={
                    storedCredentialRetestRequired
                        ? "resend-verified-domain-help resend-sender-retest-alert"
                        : "resend-verified-domain-help"
                }
            />
            <p
                id="resend-verified-domain-help"
                className="text-xs text-muted-foreground"
            >
                Enter the domain exactly as it appears in Resend. This value is
                never selected automatically.
            </p>
            {domainRejectedByFullAccessKey ? (
                <p className="text-xs font-medium text-destructive" role="alert">
                    This domain is not in the verified domains returned for this
                    API key.
                </p>
            ) : null}
        </div>
    )
}

function ResendWebhookUrlField({
    webhookUrl,
    pending,
    onRotateWebhook,
}: {
    webhookUrl: string
    pending: boolean
    onRotateWebhook: () => Promise<void>
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="resend-webhook-url">Webhook URL</Label>
            <div className="flex min-w-0 gap-2">
                <CopyField
                    id="resend-webhook-url"
                    value={webhookUrl}
                    copyLabel="Copy webhook URL"
                    className="flex-1"
                />
                <ConfirmDialog
                    trigger={(
                        <Button
                            variant="outline"
                            size="icon"
                            disabled={pending}
                            aria-label="Rotate webhook URL"
                        >
                            {pending ? (
                                <Loader2Icon
                                    className="animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                            ) : (
                                <RotateCwIcon aria-hidden="true" />
                            )}
                        </Button>
                    )}
                    title="Rotate webhook URL?"
                    description="The current URL stops accepting Resend events. Update the endpoint in Resend after rotating."
                    confirmLabel="Rotate URL"
                    errorFallback="Couldn't rotate the webhook URL. Try again."
                    onConfirm={onRotateWebhook}
                />
            </div>
            <p className="text-xs text-muted-foreground">
                Create a webhook endpoint in Resend pointing to this URL and subscribe to: email.delivered, email.bounced, email.complained, email.opened, email.clicked.
            </p>
        </div>
    )
}

function GmailConfigurationFields({
    defaultSender,
    eligibleSenders,
    eligibleSendersLoading,
    settings,
    onDefaultSenderChange,
}: {
    defaultSender: string
    eligibleSenders: EligibleSender[]
    eligibleSendersLoading: boolean
    settings: ResendSettings | undefined
    onDefaultSenderChange: (defaultSender: string) => void
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <h3 className="text-sm font-medium">Gmail Configuration</h3>

            <div className="space-y-2">
                <Label htmlFor="gmail-sender">Default Sender</Label>
                <Select
                    value={defaultSender}
                    onValueChange={(value) => onDefaultSenderChange(value ?? "")}
                >
                    <SelectTrigger id="gmail-sender">
                        <SelectValue placeholder={eligibleSendersLoading ? "Loading senders…" : "Select admin with Gmail connected"}>
                            {(value: string | null) => getEligibleSenderLabel(eligibleSenders, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {eligibleSenders.map((sender) => (
                            <SelectItem key={sender.user_id} value={sender.user_id}>
                                {sender.display_name} ({sender.gmail_email})
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {!eligibleSendersLoading && !eligibleSenders.length ? (
                    <p className="text-xs text-yellow-600">
                        No eligible senders found. Admin users must connect Gmail first.
                    </p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                    Only admin users with Gmail connected can be selected as the default sender.
                </p>
            </div>

            {settings?.default_sender_name ? (
                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                    <span>
                        Current sender: <strong>{settings.default_sender_name}</strong> ({settings.default_sender_email})
                    </span>
                </div>
            ) : null}
        </div>
    )
}

function EmailSaveButton({
    pending,
    saved,
    disabled,
    onSave,
}: {
    pending: boolean
    saved: boolean
    disabled: boolean
    onSave: () => void
}) {
    return (
        <Button onClick={onSave} disabled={pending || disabled}>
            {pending ? (
                <>
                    <Loader2Icon
                        className="animate-spin motion-reduce:animate-none"
                        aria-hidden="true"
                    />
                    Saving…
                </>
            ) : saved ? (
                <>
                    <CheckIcon aria-hidden="true" />
                    Saved
                </>
            ) : (
                "Save Email Configuration"
            )}
        </Button>
    )
}
