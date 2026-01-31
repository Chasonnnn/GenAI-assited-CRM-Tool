"use client"

import { useState, useEffect } from "react"
import Link from "@/components/app-link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
    CheckCircleIcon,
    AlertTriangleIcon,
    XCircleIcon,
    Loader2Icon,
    RefreshCwIcon,
    KeyIcon,
    FacebookIcon,
    ServerIcon,
    ZapIcon,
    VideoIcon,
    MailIcon,
    CalendarIcon,
    LinkIcon,
    UnlinkIcon,
    SparklesIcon,
    CheckIcon,
} from "lucide-react"
import { useIntegrationHealth } from "@/lib/hooks/use-ops"
import { useAuth } from "@/lib/auth-context"
import { useUserIntegrations, useConnectZoom, useConnectGmail, useConnectGoogleCalendar, useConnectGcp, useDisconnectIntegration } from "@/lib/hooks/use-user-integrations"
import { useAISettings, useUpdateAISettings, useTestAPIKey, useAIConsent, useAcceptConsent } from "@/lib/hooks/use-ai"
import { useResendSettings, useUpdateResendSettings, useTestResendKey, useRotateWebhook, useEligibleSenders } from "@/lib/hooks/use-resend"
import {
    useZapierSettings,
    useZapierTestLead,
    useUpdateZapierOutboundSettings,
    useZapierOutboundTest,
    useCreateZapierInboundWebhook,
    useRotateZapierInboundWebhook,
    useUpdateZapierInboundWebhook,
} from "@/lib/hooks/use-zapier"
import { useMetaForms } from "@/lib/hooks/use-meta-forms"
import { formatRelativeTime } from "@/lib/formatters"
import { CopyIcon, SendIcon, RotateCwIcon, ActivityIcon, PlusIcon } from "lucide-react"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { toast } from "sonner"

const statusConfig = {
    healthy: { icon: CheckCircleIcon, color: "text-green-600", badge: "default" as const, label: "Healthy" },
    degraded: { icon: AlertTriangleIcon, color: "text-yellow-600", badge: "secondary" as const, label: "Degraded" },
    error: { icon: XCircleIcon, color: "text-red-600", badge: "destructive" as const, label: "Error" },
}

const configStatusLabels: Record<string, { label: string; variant: "default" | "destructive" | "secondary" }> = {
    configured: { label: "Configured", variant: "default" },
    missing_token: { label: "Missing Token", variant: "destructive" },
    expired_token: { label: "Token Expired", variant: "destructive" },
}

const integrationTypeConfig: Record<string, { icon: typeof FacebookIcon; label: string; description: string }> = {
    meta_leads: {
        icon: FacebookIcon,
        label: "Meta Lead Ads",
        description: "Automatic lead capture from Facebook/Instagram ads"
    },
    meta_capi: {
        icon: ZapIcon,
        label: "Meta Conversions API",
        description: "Send conversion events back to Meta for ad optimization"
    },
    worker: {
        icon: ServerIcon,
        label: "Background Worker",
        description: "Processes jobs, emails, and scheduled tasks"
    },
    zapier: {
        icon: LinkIcon,
        label: "Zapier",
        description: "Outbound stage events and inbound lead webhooks"
    },
}

// AI provider options
const AI_PROVIDERS = [
    {
        value: "gemini",
        label: "Google Gemini",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
    {
        value: "vertex_api_key",
        label: "Vertex AI (API Key)",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
    {
        value: "vertex_wif",
        label: "Vertex AI (WIF)",
        models: ["gemini-3-flash-preview", "gemini-3-pro-preview"],
    },
] as const

type AiProvider = (typeof AI_PROVIDERS)[number]["value"]

const isAiProvider = (value: string | null | undefined): value is AiProvider =>
    AI_PROVIDERS.some((providerOption) => providerOption.value === value)

function AIConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: aiSettings, isLoading } = useAISettings()
    const { data: consentInfo } = useAIConsent()
    const acceptConsent = useAcceptConsent()
    const updateSettings = useUpdateAISettings()
    const testKey = useTestAPIKey()
    const { data: userIntegrations } = useUserIntegrations()
    const connectGcp = useConnectGcp()
    const disconnectIntegration = useDisconnectIntegration()
    const { refetch: refetchAuth } = useAuth()

    const [isEnabled, setIsEnabled] = useState(false)
    const [provider, setProvider] = useState<AiProvider>("gemini")
    const [apiKey, setApiKey] = useState("")
    const [model, setModel] = useState("")
    const [vertexProjectId, setVertexProjectId] = useState("")
    const [vertexLocation, setVertexLocation] = useState("us-central1")
    const [vertexAudience, setVertexAudience] = useState("")
    const [vertexServiceAccount, setVertexServiceAccount] = useState("")
    const [vertexUseExpress, setVertexUseExpress] = useState(true)
    const [keyTested, setKeyTested] = useState<boolean | null>(null)
    const [saved, setSaved] = useState(false)
    const [editingKey, setEditingKey] = useState(false)

    // Sync state with fetched settings
    useEffect(() => {
        if (aiSettings) {
            setIsEnabled(aiSettings.is_enabled)
            if (isAiProvider(aiSettings.provider)) {
                setProvider(aiSettings.provider)
            } else {
                setProvider("gemini")
            }
            setModel(aiSettings.model || "")
            setEditingKey(false)
            setVertexProjectId(
                aiSettings.vertex_wif?.project_id ||
                aiSettings.vertex_api_key?.project_id ||
                ""
            )
            setVertexLocation(
                aiSettings.vertex_wif?.location ||
                aiSettings.vertex_api_key?.location ||
                "us-central1"
            )
            setVertexAudience(aiSettings.vertex_wif?.audience || "")
            setVertexServiceAccount(aiSettings.vertex_wif?.service_account_email || "")
            setVertexUseExpress(
                aiSettings.provider === "vertex_api_key" &&
                !aiSettings.vertex_api_key?.project_id &&
                !aiSettings.vertex_api_key?.location
            )
        }
    }, [aiSettings])

    const selectedProviderModels =
        AI_PROVIDERS.find((providerOption) => providerOption.value === provider)?.models ??
        []
    const consentAccepted = Boolean(aiSettings?.consent_accepted_at)
    const gcpIntegration = userIntegrations?.find(i => i.integration_type === "gcp")
    const vertexReady = provider !== "vertex_wif"
        || Boolean(
            vertexProjectId.trim() &&
            vertexLocation.trim() &&
            vertexServiceAccount.trim() &&
            vertexAudience.trim()
        )
    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"

    const handleTestKey = async () => {
        if (provider === "vertex_wif") return
        if (!apiKey.trim()) return
        setKeyTested(null)
        try {
            const payload: {
                provider: "gemini" | "vertex_api_key";
                api_key: string;
                vertex_api_key?: { project_id: string | null; location: string | null };
            } = {
                provider,
                api_key: apiKey,
            }
            if (provider === "vertex_api_key") {
                payload.vertex_api_key = {
                    project_id: vertexUseExpress ? null : vertexProjectId.trim() || null,
                    location: vertexUseExpress ? null : vertexLocation.trim() || null,
                }
            }
            const result = await testKey.mutateAsync(payload)
            setKeyTested(result.valid)
        } catch {
            setKeyTested(false)
        }
    }

    const handleSave = async () => {
        const update: {
            is_enabled?: boolean;
            provider?: "gemini" | "vertex_wif" | "vertex_api_key";
            api_key?: string;
            model?: string;
            vertex_wif?: {
                project_id: string | null;
                location: string | null;
                audience: string | null;
                service_account_email: string | null;
            };
            vertex_api_key?: {
                project_id: string | null;
                location: string | null;
            };
        } = {
            is_enabled: isEnabled,
            provider,
        }
        if (apiKey.trim()) {
            update.api_key = apiKey
        }
        if (model) {
            update.model = model
        }
        if (provider === "vertex_wif") {
            update.vertex_wif = {
                project_id: vertexProjectId.trim() || null,
                location: vertexLocation.trim() || null,
                audience: vertexAudience.trim() || null,
                service_account_email: vertexServiceAccount.trim() || null,
            }
        }
        if (provider === "vertex_api_key") {
            update.vertex_api_key = {
                project_id: vertexUseExpress ? null : vertexProjectId.trim() || null,
                location: vertexUseExpress ? null : vertexLocation.trim() || null,
            }
        }
        await updateSettings.mutateAsync(update)
        setApiKey("") // Clear after save
        setKeyTested(null)
        setSaved(true)
        setEditingKey(false)
        refetchAuth()
        setTimeout(() => setSaved(false), 2000)
    }

    const handleAcceptConsent = async () => {
        try {
            await acceptConsent.mutateAsync()
            toast.success("AI consent accepted")
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to accept consent")
        }
    }

    if (isLoading) {
        return (
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">AI Configuration</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Configure AI assistant settings for your organization. Use BYOK (OpenAI/Gemini), Vertex API key (express mode), or Vertex AI via Workload Identity Federation.
                    </p>
                </>
            )}

            {!consentAccepted && consentInfo && (
                <Card className="mb-4 border-yellow-200 bg-yellow-50/60">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base">AI Consent Required</CardTitle>
                        <CardDescription className="text-xs text-muted-foreground">
                            An admin must accept the AI data processing consent before enabling AI features.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="max-h-40 overflow-auto rounded-md border border-yellow-200 bg-white p-3 text-xs leading-relaxed text-muted-foreground">
                            {consentInfo.consent_text}
                        </div>
                        <Button
                            onClick={handleAcceptConsent}
                            disabled={acceptConsent.isPending}
                        >
                            {acceptConsent.isPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Accepting…
                                </>
                            ) : (
                                "Accept Consent"
                            )}
                        </Button>
                    </CardContent>
                </Card>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="flex size-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                                <SparklesIcon className="size-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                            </div>
                            <div>
                                <CardTitle className="text-base">AI Assistant</CardTitle>
                                <CardDescription className="text-xs">
                                    Enable AI-powered features
                                </CardDescription>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Label htmlFor="ai-enabled" className="text-sm">
                                {isEnabled ? "Enabled" : "Disabled"}
                            </Label>
                            <Switch
                                id="ai-enabled"
                                checked={isEnabled}
                                onCheckedChange={setIsEnabled}
                                disabled={!consentAccepted && !isEnabled}
                            />
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-4">
                    {/* Provider Selection */}
                    <div className="space-y-2">
                        <Label htmlFor="ai-provider">AI Provider</Label>
                        <Select value={provider} onValueChange={(v) => {
                            if (v) {
                                if (isAiProvider(v)) {
                                    setProvider(v)
                                }
                                setModel("") // Reset model when provider changes
                                setKeyTested(null)
                                setEditingKey(false)
                            }
                        }}>
                            <SelectTrigger id="ai-provider">
                                <SelectValue placeholder="Select provider" />
                            </SelectTrigger>
                            <SelectContent>
                                {AI_PROVIDERS.map(p => (
                                    <SelectItem key={p.value} value={p.value}>
                                        {p.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* API Key Input (Gemini/Vertex API Key only) */}
                    {provider !== "vertex_wif" && (
                        <div className="space-y-2">
                            <Label htmlFor="ai-key">API Key</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="ai-key"
                                    type="password"
                                    value={editingKey
                                        ? apiKey
                                        : apiKey || (aiSettings?.api_key_masked ? aiSettings.api_key_masked : "")
                                    }
                                    onChange={(e) => {
                                        setApiKey(e.target.value)
                                        setKeyTested(null)
                                    }}
                                    placeholder="Enter API key"
                                    disabled={!editingKey && !apiKey && !!aiSettings?.api_key_masked}
                                    className="flex-1"
                                    name="ai-api-key"
                                    autoComplete="off"
                                />
                                {aiSettings?.api_key_masked && !apiKey && !editingKey ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                            setApiKey("")
                                            setEditingKey(true)
                                        }}
                                        className="shrink-0"
                                    >
                                        Change Key
                                    </Button>
                                ) : (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleTestKey}
                                        disabled={!apiKey.trim() || testKey.isPending}
                                    >
                                        {testKey.isPending ? (
                                            <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : keyTested === true ? (
                                            <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                                        ) : keyTested === false ? (
                                            <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                                        ) : (
                                            "Test"
                                        )}
                                    </Button>
                                )}
                            </div>
                            {keyTested === true && (
                                <p className="text-xs text-green-600">API key is valid!</p>
                            )}
                            {keyTested === false && (
                                <p className="text-xs text-red-600">API key is invalid. Please check and try again.</p>
                            )}
                            <p className="text-xs text-muted-foreground">
                                {provider === "gemini"
                                    ? "Get your key from aistudio.google.com"
                                    : "Create a Vertex AI API key in Google Cloud"}
                            </p>
                        </div>
                    )}

                    {provider === "vertex_api_key" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <div>
                                <h3 className="text-sm font-medium">Vertex AI (API Key)</h3>
                                <p className="text-xs text-muted-foreground">
                                    Express mode works without project or location. Add them to use project-scoped endpoints.
                                </p>
                            </div>
                            <div className="flex items-center justify-between rounded-md border p-3">
                                <div className="text-sm">
                                    {vertexUseExpress ? "Express mode active" : "Project-scoped mode"}
                                </div>
                                <div className="flex items-center gap-2">
                                    <Label htmlFor="vertex-express" className="text-xs text-muted-foreground">
                                        Use express mode
                                    </Label>
                                    <Switch
                                        id="vertex-express"
                                        checked={vertexUseExpress}
                                        onCheckedChange={(checked) => setVertexUseExpress(checked)}
                                    />
                                </div>
                            </div>
                            {!vertexUseExpress && (
                                <div className="grid gap-3 md:grid-cols-2">
                                    <div className="space-y-2">
                                        <Label htmlFor="vertex-project-key">Project ID (optional)</Label>
                                        <Input
                                            id="vertex-project-key"
                                            value={vertexProjectId}
                                            onChange={(e) => setVertexProjectId(e.target.value)}
                                            placeholder="your-gcp-project-id"
                                            name="vertex-project-key"
                                            autoComplete="off"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="vertex-location-key">Location (optional)</Label>
                                        <Input
                                            id="vertex-location-key"
                                            value={vertexLocation}
                                            onChange={(e) => setVertexLocation(e.target.value)}
                                            placeholder="us-central1"
                                            name="vertex-location-key"
                                            autoComplete="off"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {provider === "vertex_wif" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-medium">Vertex AI (WIF)</h3>
                                    <p className="text-xs text-muted-foreground">
                                        Uses Workload Identity Federation—no long-lived keys stored.
                                    </p>
                                </div>
                                {gcpIntegration ? (
                                    <Badge variant="default">GCP Connected</Badge>
                                ) : (
                                    <Badge variant="secondary">GCP Not Connected</Badge>
                                )}
                            </div>

                            <div className="flex items-center justify-between rounded-md border p-3">
                                <div className="text-sm">
                                    {gcpIntegration
                                        ? `Connected as ${gcpIntegration.account_email ?? "Google account"}`
                                        : "Connect a Google Cloud account to verify access."}
                                </div>
                                {gcpIntegration ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => disconnectIntegration.mutate("gcp")}
                                        disabled={disconnectIntegration.isPending}
                                    >
                                        Disconnect
                                    </Button>
                                ) : (
                                    <Button
                                        size="sm"
                                        onClick={() => connectGcp.mutate()}
                                        disabled={connectGcp.isPending}
                                    >
                                        {connectGcp.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : null}
                                        Connect GCP
                                    </Button>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="vertex-project">Project ID</Label>
                                <Input
                                    id="vertex-project"
                                    value={vertexProjectId}
                                    onChange={(e) => setVertexProjectId(e.target.value)}
                                    placeholder="your-gcp-project-id"
                                    name="vertex-project"
                                    autoComplete="off"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="vertex-location">Location</Label>
                                <Input
                                    id="vertex-location"
                                    value={vertexLocation}
                                    onChange={(e) => setVertexLocation(e.target.value)}
                                    placeholder="us-central1"
                                    name="vertex-location"
                                    autoComplete="off"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="vertex-service-account">Service Account Email</Label>
                                <Input
                                    id="vertex-service-account"
                                    value={vertexServiceAccount}
                                    onChange={(e) => setVertexServiceAccount(e.target.value)}
                                    placeholder="vertex-sa@project.iam.gserviceaccount.com"
                                    name="vertex-service-account"
                                    autoComplete="off"
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="vertex-audience">Workload Identity Audience</Label>
                                <Input
                                    id="vertex-audience"
                                    value={vertexAudience}
                                    onChange={(e) => setVertexAudience(e.target.value)}
                                    placeholder="//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
                                    name="vertex-audience"
                                    autoComplete="off"
                                />
                                <p className="text-xs text-muted-foreground">
                                    Use the provider resource name or full audience from the Workload Identity Provider.
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Model Selection */}
                    <div className="space-y-2">
                        <Label htmlFor="ai-model">Model</Label>
                        <Select value={model} onValueChange={(v) => setModel(v || "")}>
                            <SelectTrigger id="ai-model">
                                <SelectValue placeholder="Select model (optional)" />
                            </SelectTrigger>
                            <SelectContent>
                                {selectedProviderModels.map(m => (
                                    <SelectItem key={m} value={m}>
                                        {m}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Leave empty to use the default model
                        </p>
                    </div>

                    {/* Save Button */}
                    <Button onClick={handleSave} disabled={updateSettings.isPending || !vertexReady} className="w-full">
                        {updateSettings.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Saving…
                            </>
                        ) : saved ? (
                            <>
                                <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                                Saved!
                            </>
                        ) : (
                            "Save AI Configuration"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}

function EmailConfigurationSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: settings, isLoading } = useResendSettings()
    const updateSettings = useUpdateResendSettings()
    const testKey = useTestResendKey()
    const rotateWebhook = useRotateWebhook()

    const [provider, setProvider] = useState<"resend" | "gmail" | "">("")
    const [apiKey, setApiKey] = useState("")
    const [fromEmail, setFromEmail] = useState("")
    const [fromName, setFromName] = useState("")
    const [replyTo, setReplyTo] = useState("")
    const [defaultSender, setDefaultSender] = useState("")
    const [keyTested, setKeyTested] = useState<{ valid: boolean; error?: string | null; verified_domains?: string[] } | null>(null)
    const [saved, setSaved] = useState(false)
    const [webhookSecret, setWebhookSecret] = useState<string | null>(null)
    const [isEditingKey, setIsEditingKey] = useState(false)
    const [hasUserEdited, setHasUserEdited] = useState(false)
    const { data: eligibleSenders, isLoading: eligibleSendersLoading } = useEligibleSenders(provider === "gmail")

    // Sync state with fetched settings
    useEffect(() => {
        if (settings && !hasUserEdited) {
            setProvider(settings.email_provider || "resend")
            setFromEmail(settings.from_email || "")
            setFromName(settings.from_name || "")
            setReplyTo(settings.reply_to_email || "")
            setDefaultSender(settings.default_sender_user_id || "")
            setApiKey("")
            setIsEditingKey(false)
            setKeyTested(null)
        }
    }, [settings, hasUserEdited])

    const getErrorMessage = (error: unknown, fallback: string) => {
        if (error instanceof Error && error.message) return error.message
        return fallback
    }

    const handleProviderChange = (value: "resend" | "gmail" | "") => {
        setProvider(value)
        setHasUserEdited(true)
        setSaved(false)
        setKeyTested(null)
        setWebhookSecret(null)
        if (value !== "resend") {
            setApiKey("")
            setIsEditingKey(false)
        }
    }

    const handleTestKey = async () => {
        if (!apiKey.trim()) return
        setKeyTested(null)
        try {
            const result = await testKey.mutateAsync(apiKey)
            setKeyTested(result)
            if (result.valid && result.verified_domains.length > 0) {
                // Auto-suggest from email based on verified domain
                const domain = result.verified_domains[0]
                if (!fromEmail) {
                    setFromEmail(`no-reply@${domain}`)
                    setHasUserEdited(true)
                }
            }
        } catch (error) {
            const message = getErrorMessage(error, "Failed to test key")
            setKeyTested({ valid: false, error: message })
            toast.error(message)
        }
    }

    const handleSave = async () => {
        const update: {
            email_provider?: "resend" | "gmail" | "";
            api_key?: string;
            from_email?: string;
            from_name?: string;
            reply_to_email?: string;
            default_sender_user_id?: string | null;
            expected_version?: number;
        } = {
            email_provider: provider,
        }

        if (settings?.current_version !== undefined) {
            update.expected_version = settings.current_version
        }

        if (provider === "resend") {
            if (apiKey.trim()) {
                update.api_key = apiKey
            }
            update.from_email = fromEmail
            update.from_name = fromName
            update.reply_to_email = replyTo
        } else if (provider === "gmail") {
            update.default_sender_user_id = defaultSender || null
        }

        try {
            await updateSettings.mutateAsync(update)
            setApiKey("") // Clear after save
            setKeyTested(null)
            setIsEditingKey(false)
            setHasUserEdited(false)
            setSaved(true)
            toast.success("Email configuration saved")
            setTimeout(() => setSaved(false), 2000)
        } catch (error) {
            const message = getErrorMessage(error, "Failed to save email configuration")
            toast.error(message)
        }
    }

    const handleRotateWebhook = async () => {
        try {
            const result = await rotateWebhook.mutateAsync()
            setWebhookSecret(result.webhook_secret)
            toast.success("Webhook secret rotated")
        } catch (error) {
            toast.error(getErrorMessage(error, "Failed to rotate webhook secret"))
        }
    }

    const copyToClipboard = (text: string) => {
        navigator.clipboard
            .writeText(text)
            .then(() => toast.success("Copied to clipboard"))
            .catch(() => toast.error("Failed to copy"))
    }

    const hasResendKey = Boolean(apiKey.trim() || settings?.api_key_masked)
    const hasFromEmail = Boolean(fromEmail.trim())
    const hasGmailSender = Boolean(defaultSender)
    const resendReady = provider !== "resend" || (hasResendKey && hasFromEmail)
    const gmailReady = provider !== "gmail" || hasGmailSender
    const canSave = Boolean(provider) && resendReady && gmailReady
    const showMaskedKey = Boolean(settings?.api_key_masked) && !isEditingKey && !apiKey
    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"

    if (isLoading) {
        return (
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">Email Configuration</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Configure the email provider for campaigns. Choose between Resend (recommended for deliverability) or Gmail.
                    </p>
                </>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                            <SendIcon className="size-5 text-teal-600 dark:text-teal-400" aria-hidden="true" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Campaign Email Provider</CardTitle>
                            <CardDescription className="text-xs">
                                {settings?.email_provider === "resend"
                                    ? "Resend"
                                    : settings?.email_provider === "gmail"
                                    ? "Gmail"
                                    : "Not configured"}
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6">
                    {/* Provider Selection */}
                    <div className="space-y-3">
                        <Label htmlFor="email-provider">Email Provider</Label>
                        <RadioGroup
                            value={provider}
                            onValueChange={(v) => handleProviderChange(v as "resend" | "gmail" | "")}
                            className="flex flex-col gap-3"
                            id="email-provider"
                            aria-label="Email provider"
                        >
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="resend" id="provider-resend" />
                                <Label htmlFor="provider-resend" className="cursor-pointer">
                                    <span className="font-medium">Resend</span>
                                    <span className="ml-2 text-xs text-muted-foreground">(Recommended)</span>
                                </Label>
                            </div>
                            <div className="flex items-center space-x-2">
                                <RadioGroupItem value="gmail" id="provider-gmail" />
                                <Label htmlFor="provider-gmail" className="cursor-pointer">
                                    <span className="font-medium">Gmail</span>
                                    <span className="ml-2 text-xs text-muted-foreground">(Org admin account)</span>
                                </Label>
                            </div>
                        </RadioGroup>
                    </div>

                    {/* Resend Configuration */}
                    {provider === "resend" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <h3 className="text-sm font-medium">Resend Configuration</h3>

                            {/* API Key */}
                            <div className="space-y-2">
                                <Label htmlFor="resend-key">API Key</Label>
                                <div className="flex gap-2">
                                    <Input
                                        id="resend-key"
                                        type="password"
                                        value={showMaskedKey ? settings?.api_key_masked ?? "" : apiKey}
                                        onChange={(e) => {
                                            setApiKey(e.target.value)
                                            setKeyTested(null)
                                            setIsEditingKey(true)
                                            setHasUserEdited(true)
                                        }}
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
                                            onClick={() => {
                                                setIsEditingKey(true)
                                                setApiKey("")
                                                setKeyTested(null)
                                                setHasUserEdited(true)
                                            }}
                                            className="shrink-0"
                                        >
                                            Change Key
                                        </Button>
                                    ) : (
                                        <div className="flex gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={handleTestKey}
                                                disabled={!apiKey.trim() || testKey.isPending}
                                            >
                                                {testKey.isPending ? (
                                                    <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                                ) : keyTested?.valid ? (
                                                    <CheckIcon className="size-4 text-green-600" aria-hidden="true" />
                                                ) : keyTested !== null ? (
                                                    <XCircleIcon className="size-4 text-red-600" aria-hidden="true" />
                                                ) : (
                                                    "Test"
                                                )}
                                            </Button>
                                            {settings?.api_key_masked && isEditingKey && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => {
                                                        setIsEditingKey(false)
                                                        setApiKey("")
                                                        setKeyTested(null)
                                                    }}
                                                >
                                                    Cancel
                                                </Button>
                                            )}
                                        </div>
                                    )}
                                </div>
                                {keyTested?.valid && (
                                    <p className="text-xs text-green-600">
                                        API key is valid! Verified domain: {keyTested.verified_domains?.[0] || settings?.verified_domain}
                                    </p>
                                )}
                                {keyTested && !keyTested.valid && (
                                    <p className="text-xs text-red-600">{keyTested.error || "API key is invalid"}</p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Get your key from <a href="https://resend.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">resend.com/api-keys</a>
                                </p>
                            </div>

                            {/* Verified Domain */}
                            {settings?.verified_domain && (
                                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                                    <span>Verified domain: <strong>{settings.verified_domain}</strong></span>
                                </div>
                            )}

                            {/* From Email */}
                            <div className="space-y-2">
                                <Label htmlFor="from-email">From Email</Label>
                                <Input
                                    id="from-email"
                                    type="email"
                                    value={fromEmail}
                                    onChange={(e) => {
                                        setFromEmail(e.target.value)
                                        setHasUserEdited(true)
                                    }}
                                    placeholder={settings?.verified_domain ? `no-reply@${settings.verified_domain}` : "no-reply@yourdomain.com"}
                                    name="from-email"
                                    autoComplete="email"
                                />
                                {settings?.verified_domain && (
                                    <p className="text-xs text-muted-foreground">
                                        Must use your verified domain: @{settings.verified_domain}
                                    </p>
                                )}
                            </div>

                            {/* From Name */}
                            <div className="space-y-2">
                                <Label htmlFor="from-name">From Name (optional)</Label>
                                <Input
                                    id="from-name"
                                    value={fromName}
                                    onChange={(e) => {
                                        setFromName(e.target.value)
                                        setHasUserEdited(true)
                                    }}
                                    placeholder="Your Company Name"
                                    name="from-name"
                                    autoComplete="organization"
                                />
                            </div>

                            {/* Reply-To */}
                            <div className="space-y-2">
                                <Label htmlFor="reply-to">Reply-To Email (optional)</Label>
                                <Input
                                    id="reply-to"
                                    type="email"
                                    value={replyTo}
                                    onChange={(e) => {
                                        setReplyTo(e.target.value)
                                        setHasUserEdited(true)
                                    }}
                                    placeholder="support@yourdomain.com"
                                    name="reply-to"
                                    autoComplete="email"
                                />
                            </div>

                            {/* Webhook URL */}
                            {settings?.webhook_url && (
                                <div className="space-y-2">
                                    <Label>Webhook URL</Label>
                                    <div className="flex gap-2">
                                        <Input
                                            value={settings.webhook_url}
                                            readOnly
                                            className="flex-1 text-xs font-mono"
                                        />
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => copyToClipboard(settings.webhook_url)}
                                            aria-label="Copy webhook URL"
                                        >
                                            <CopyIcon className="size-4" aria-hidden="true" />
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleRotateWebhook}
                                            disabled={rotateWebhook.isPending}
                                            aria-label="Rotate webhook secret"
                                        >
                                            {rotateWebhook.isPending ? (
                                                <Loader2Icon className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                            ) : (
                                                <RotateCwIcon className="size-4" aria-hidden="true" />
                                            )}
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Add this URL to Resend webhook settings for delivery tracking
                                    </p>
                                    {webhookSecret && (
                                        <div className="mt-2 rounded-md bg-yellow-50 p-3 dark:bg-yellow-900/20">
                                            <p className="text-xs font-medium text-yellow-800 dark:text-yellow-200">
                                                New Webhook Secret (copy now - shown only once):
                                            </p>
                                            <div className="mt-1 flex items-center gap-2">
                                                <code className="flex-1 break-all rounded bg-yellow-100 px-2 py-1 text-xs dark:bg-yellow-800/30">
                                                    {webhookSecret}
                                                </code>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => copyToClipboard(webhookSecret)}
                                                    aria-label="Copy webhook secret"
                                                >
                                                    <CopyIcon className="size-4" aria-hidden="true" />
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Gmail Configuration */}
                    {provider === "gmail" && (
                        <div className="space-y-4 rounded-lg border p-4">
                            <h3 className="text-sm font-medium">Gmail Configuration</h3>

                            <div className="space-y-2">
                                <Label htmlFor="gmail-sender">Default Sender</Label>
                                <Select
                                    value={defaultSender}
                                    onValueChange={(v) => {
                                        setDefaultSender(v ?? "")
                                        setHasUserEdited(true)
                                    }}
                                >
                                    <SelectTrigger id="gmail-sender">
                                        <SelectValue placeholder={eligibleSendersLoading ? "Loading senders…" : "Select admin with Gmail connected"} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {eligibleSenders?.map((sender) => (
                                            <SelectItem key={sender.user_id} value={sender.user_id}>
                                                {sender.display_name} ({sender.gmail_email})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {!eligibleSendersLoading && !eligibleSenders?.length && (
                                    <p className="text-xs text-yellow-600">
                                        No eligible senders found. Admin users must connect Gmail first.
                                    </p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    Only admin users with Gmail connected can be selected as the default sender.
                                </p>
                            </div>

                            {settings?.default_sender_name && (
                                <div className="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm dark:bg-green-900/20">
                                    <CheckCircleIcon className="size-4 text-green-600" aria-hidden="true" />
                                    <span>
                                        Current sender: <strong>{settings.default_sender_name}</strong> ({settings.default_sender_email})
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Save Button */}
                    <Button onClick={handleSave} disabled={updateSettings.isPending || !canSave} className="w-full">
                        {updateSettings.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                Saving…
                            </>
                        ) : saved ? (
                            <>
                                <CheckIcon className="mr-2 size-4" aria-hidden="true" />
                                Saved!
                            </>
                        ) : (
                            "Save Email Configuration"
                        )}
                    </Button>
                </CardContent>
            </Card>
        </div>
    )
}

function ZapierWebhookSection({ variant = "page" }: { variant?: "page" | "dialog" }) {
    const { data: settings, isLoading } = useZapierSettings()
    const { data: metaForms = [], isLoading: metaFormsLoading } = useMetaForms()
    const createInboundWebhook = useCreateZapierInboundWebhook()
    const rotateInboundWebhook = useRotateZapierInboundWebhook()
    const updateInboundWebhook = useUpdateZapierInboundWebhook()
    const updateOutbound = useUpdateZapierOutboundSettings()
    const [webhookSecrets, setWebhookSecrets] = useState<Record<string, string>>({})
    const [labelDrafts, setLabelDrafts] = useState<Record<string, string>>({})
    const [rotatingWebhookId, setRotatingWebhookId] = useState<string | null>(null)
    const [testFormId, setTestFormId] = useState('')
    const sendTestLead = useZapierTestLead()
    const sendOutboundTest = useZapierOutboundTest()
    const [outboundUrl, setOutboundUrl] = useState('')
    const [outboundSecret, setOutboundSecret] = useState('')
    const [outboundEnabled, setOutboundEnabled] = useState(false)
    const [sendHashedPii, setSendHashedPii] = useState(false)
    const [eventMapping, setEventMapping] = useState<Array<{ stage_slug: string; event_name: string; enabled: boolean }>>([])
    const [selectedOutboundStage, setSelectedOutboundStage] = useState<string>('')

    useEffect(() => {
        if (!settings?.inbound_webhooks) return
        const drafts: Record<string, string> = {}
        settings.inbound_webhooks.forEach((webhook) => {
            drafts[webhook.webhook_id] = webhook.label || ""
        })
        setLabelDrafts(drafts)
        setWebhookSecrets((prev) => {
            const next: Record<string, string> = {}
            settings.inbound_webhooks.forEach((webhook) => {
                const existing = prev[webhook.webhook_id]
                if (existing) {
                    next[webhook.webhook_id] = existing
                }
            })
            return next
        })
    }, [settings?.inbound_webhooks])

    useEffect(() => {
        if (!settings) return
        setOutboundUrl(settings.outbound_webhook_url || '')
        setOutboundEnabled(Boolean(settings.outbound_enabled))
        setSendHashedPii(Boolean(settings.send_hashed_pii))
        setEventMapping(settings.event_mapping || [])
        const firstStage = settings.event_mapping?.[0]?.stage_slug
        if (firstStage) {
            setSelectedOutboundStage(firstStage)
        }
    }, [settings])

    const copyToClipboard = (text: string) => {
        navigator.clipboard
            .writeText(text)
            .then(() => toast.success("Copied to clipboard"))
            .catch(() => toast.error("Failed to copy"))
    }

    const handleCreateInbound = async () => {
        try {
            const result = await createInboundWebhook.mutateAsync({ label: null })
            setWebhookSecrets((prev) => ({ ...prev, [result.webhook_id]: result.webhook_secret }))
            toast.success("Webhook created")
        } catch {
            toast.error("Failed to create webhook")
        }
    }

    const handleRotateInbound = async (webhookId: string) => {
        try {
            setRotatingWebhookId(webhookId)
            const result = await rotateInboundWebhook.mutateAsync({ webhookId })
            const secretId = result.webhook_id ?? webhookId
            setWebhookSecrets((prev) => ({ ...prev, [secretId]: result.webhook_secret }))
            toast.success("Webhook secret rotated")
        } catch {
            toast.error("Failed to rotate webhook secret")
        } finally {
            setRotatingWebhookId(null)
        }
    }

    const handleLabelBlur = async (webhookId: string) => {
        const draft = (labelDrafts[webhookId] || "").trim()
        const current = settings?.inbound_webhooks?.find((item) => item.webhook_id === webhookId)?.label || ""
        if (draft === (current || "")) {
            return
        }
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { label: draft || null },
            })
            toast.success("Webhook updated")
        } catch {
            toast.error("Failed to update webhook")
        }
    }

    const handleToggleInbound = async (webhookId: string, enabled: boolean) => {
        try {
            await updateInboundWebhook.mutateAsync({
                webhookId,
                payload: { is_active: enabled },
            })
            toast.success(enabled ? "Webhook enabled" : "Webhook disabled")
        } catch {
            toast.error("Failed to update webhook")
        }
    }

    const handleTestLead = async () => {
        try {
            const formId = testFormId.trim()
            const payload = formId ? { form_id: formId } : {}
            const result = await sendTestLead.mutateAsync(payload)
            if (result.status === "converted") {
                toast.success(result.message ?? "Test lead converted successfully")
            } else if (result.status === "awaiting_mapping") {
                toast.message(result.message ?? "Test lead stored. Mapping review required.")
            } else {
                toast.message(result.message ?? `Test lead stored with status: ${result.status}`)
            }
        } catch {
            toast.error("Failed to send test lead")
        }
    }

    const handleSaveOutbound = async () => {
        try {
            const payload: {
                outbound_webhook_url: string | null
                outbound_webhook_secret?: string | null
                outbound_enabled: boolean
                send_hashed_pii: boolean
                event_mapping: Array<{ stage_slug: string; event_name: string; enabled: boolean }>
            } = {
                outbound_webhook_url: outboundUrl.trim() || null,
                outbound_enabled: outboundEnabled,
                send_hashed_pii: sendHashedPii,
                event_mapping: eventMapping,
            }
            const secret = outboundSecret.trim()
            if (secret) {
                payload.outbound_webhook_secret = secret
            }
            await updateOutbound.mutateAsync(payload)
            setOutboundSecret('')
            toast.success("Outbound webhook settings saved")
        } catch {
            toast.error("Failed to save outbound settings")
        }
    }

    const handleOutboundTest = async () => {
        try {
            const payload = selectedOutboundStage ? { stage_slug: selectedOutboundStage } : {}
            const result = await sendOutboundTest.mutateAsync(payload)
            toast.success(`Test event queued: ${result.event_name}`)
        } catch {
            toast.error("Failed to send outbound test event")
        }
    }
    const showHeading = variant === "page"
    const containerClass = showHeading ? "border-t pt-6" : "space-y-4"
    const zapierForms = metaForms.filter(
        (form) => form.page_id === "zapier" || form.form_external_id?.startsWith("zapier-")
    )
    const singleZapierForm = zapierForms.length === 1 ? zapierForms[0] : null
    const mappingHref = singleZapierForm
        ? `/settings/integrations/meta/forms/${singleZapierForm.id}`
        : "/settings/integrations/meta/forms"

    if (isLoading) {
        return (
            <div className={containerClass}>
                {showHeading && (
                    <h2 className="mb-4 text-lg font-semibold">Zapier Webhook</h2>
                )}
                <div className="flex items-center justify-center py-8">
                    <Loader2Icon className="size-6 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                </div>
            </div>
        )
    }

    return (
        <div className={containerClass}>
            {showHeading && (
                <>
                    <h2 className="mb-4 text-lg font-semibold">Zapier Webhook</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Use this webhook to push leads from Zapier into Surrogacy Force.
                    </p>
                </>
            )}

            {!metaFormsLoading && zapierForms.length > 0 && (
                <Alert>
                    <AlertTitle>Zapier form detected</AlertTitle>
                    <AlertDescription>
                        We detected {zapierForms.length} Zapier form
                        {zapierForms.length === 1 ? "" : "s"}. Map fields so inbound Zapier leads can
                        convert automatically.{" "}
                        <Link href={mappingHref} className="text-primary underline">
                            Manage mapping
                        </Link>
                    </AlertDescription>
                </Alert>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900">
                            <LinkIcon className="size-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Lead Intake Webhook</CardTitle>
                            <CardDescription className="text-xs">
                                Send a POST request with lead data when a new lead arrives.
                            </CardDescription>
                        </div>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6">
                    <div className="space-y-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                            <div>
                                <Label>Inbound Webhooks</Label>
                                <p className="text-xs text-muted-foreground">
                                    Create a webhook per Zapier flow or lead source.
                                </p>
                            </div>
                            <Button
                                variant="outline"
                                onClick={handleCreateInbound}
                                disabled={createInboundWebhook.isPending}
                            >
                                {createInboundWebhook.isPending ? (
                                    <>
                                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        Creating…
                                    </>
                                ) : (
                                    <>
                                        <PlusIcon className="mr-2 size-4" aria-hidden="true" />
                                        Add webhook
                                    </>
                                )}
                            </Button>
                        </div>

                        {!settings?.inbound_webhooks?.length ? (
                            <p className="text-xs text-muted-foreground">No inbound webhooks configured yet.</p>
                        ) : (
                            <div className="space-y-4">
                                {settings.inbound_webhooks.map((webhook) => {
                                    const secret = webhookSecrets[webhook.webhook_id]
                                    const labelValue = labelDrafts[webhook.webhook_id] ?? ""
                                    return (
                                    <div key={webhook.webhook_id} className="space-y-3 rounded-md border p-4">
                                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                            <div className="flex-1 space-y-2">
                                                <Label>Label</Label>
                                                <Input
                                                    value={labelValue}
                                                    onChange={(event) =>
                                                        setLabelDrafts((prev) => ({
                                                            ...prev,
                                                            [webhook.webhook_id]: event.target.value,
                                                        }))
                                                    }
                                                    onBlur={() => handleLabelBlur(webhook.webhook_id)}
                                                    placeholder="Optional label"
                                                    name={`zapier-label-${webhook.webhook_id}`}
                                                />
                                                <p className="text-xs text-muted-foreground">
                                                    Created {formatRelativeTime(webhook.created_at)}
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Badge variant={webhook.is_active ? "default" : "secondary"}>
                                                    {webhook.is_active ? "Active" : "Inactive"}
                                                </Badge>
                                                <Switch
                                                    checked={webhook.is_active}
                                                    onCheckedChange={(checked) =>
                                                        handleToggleInbound(webhook.webhook_id, checked)
                                                    }
                                                    aria-label={`Toggle ${webhook.webhook_id}`}
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <Label>Webhook URL</Label>
                                            <div className="flex min-w-0 gap-2">
                                                <Input
                                                    value={webhook.webhook_url}
                                                    readOnly
                                                    className="flex-1 text-xs font-mono"
                                                />
                                                <Button
                                                    variant="outline"
                                                    size="icon"
                                                    onClick={() => copyToClipboard(webhook.webhook_url)}
                                                    aria-label="Copy webhook URL"
                                                >
                                                    <CopyIcon className="size-4" aria-hidden="true" />
                                                </Button>
                                            </div>
                                        </div>

                                        <div className="space-y-2">
                                            <Label>Authentication Header</Label>
                                            <div className="rounded-md border border-dashed bg-muted/50 p-3 text-xs">
                                                <div className="flex items-center justify-between">
                                                    <span>X-Webhook-Token: &lt;your secret&gt;</span>
                                                </div>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                Rotate the secret if you need to reconfigure Zapier.
                                            </p>
                                        </div>

                                        <div className="space-y-3">
                                            <Button
                                                variant="outline"
                                                onClick={() => handleRotateInbound(webhook.webhook_id)}
                                                disabled={
                                                    rotateInboundWebhook.isPending &&
                                                    rotatingWebhookId === webhook.webhook_id
                                                }
                                            >
                                                {rotateInboundWebhook.isPending &&
                                                rotatingWebhookId === webhook.webhook_id ? (
                                                    <>
                                                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                                        Rotating…
                                                    </>
                                                ) : (
                                                    <>
                                                        <RotateCwIcon className="mr-2 size-4" aria-hidden="true" />
                                                        Rotate Webhook Secret
                                                    </>
                                                )}
                                            </Button>

                                            {secret ? (
                                                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-100">
                                                    <p className="mb-2 font-medium">
                                                        New Webhook Secret (copy now — shown once):
                                                    </p>
                                                    <div className="flex items-center gap-2">
                                                        <code className="flex-1 break-all">
                                                            {secret}
                                                        </code>
                                                        <Button
                                                            variant="outline"
                                                            size="icon"
                                                            onClick={() => copyToClipboard(secret)}
                                                            aria-label="Copy webhook secret"
                                                        >
                                                            <CopyIcon className="size-4" aria-hidden="true" />
                                                        </Button>
                                                    </div>
                                                </div>
                                            ) : null}
                                        </div>
                                    </div>
                                    )
                                })}
                            </div>
                        )}
                    </div>

                    <div className="space-y-3 border-t pt-4">
                        <div className="space-y-2">
                            <Label>Test Lead</Label>
                            <Input
                                placeholder="Meta Form ID (optional if only one form)"
                                value={testFormId}
                                onChange={(event) => setTestFormId(event.target.value)}
                                name="zapier-test-form-id"
                                autoComplete="off"
                            />
                            <p className="text-xs text-muted-foreground">
                                Sends a dummy lead through the same mapping pipeline as Meta leads.
                            </p>
                            <p className="text-xs text-muted-foreground">
                                Mapping for Zapier leads is managed in Meta Lead Forms.{" "}
                                <Link href="/settings/integrations/meta/forms" className="text-primary underline">
                                    Manage form mappings
                                </Link>
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            onClick={handleTestLead}
                            disabled={sendTestLead.isPending}
                        >
                            {sendTestLead.isPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                    Sending…
                                </>
                            ) : (
                                <>
                                    <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                                    Send Test Lead
                                </>
                            )}
                        </Button>
                    </div>

                    <div className="space-y-4 border-t pt-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium">Outbound Stage Events</p>
                                <p className="text-xs text-muted-foreground">
                                    Send surrogate stage changes to Zapier for Meta Conversions.
                                </p>
                            </div>
                            <Switch
                                checked={outboundEnabled}
                                onCheckedChange={setOutboundEnabled}
                                aria-label="Enable outbound stage events"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Outbound Webhook URL</Label>
                            <Input
                                value={outboundUrl}
                                onChange={(event) => setOutboundUrl(event.target.value)}
                                placeholder="https://hooks.zapier.com/hooks/catch/…"
                                name="zapier-outbound-url"
                                autoComplete="off"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Webhook Secret (optional)</Label>
                            <Input
                                type="password"
                                value={outboundSecret}
                                onChange={(event) => setOutboundSecret(event.target.value)}
                                placeholder={settings?.outbound_secret_configured ? "•••••••• (set)" : "Enter secret"}
                                name="zapier-outbound-secret"
                                autoComplete="off"
                            />
                            <p className="text-xs text-muted-foreground">
                                If provided, we send it as X-Webhook-Token header.
                            </p>
                        </div>

                        <div className="flex items-center justify-between rounded-md border p-3">
                            <div>
                                <p className="text-sm font-medium">Include hashed PII</p>
                                <p className="text-xs text-muted-foreground">
                                    Optional hashed email/phone for better match rates.
                                </p>
                            </div>
                            <Switch
                                checked={sendHashedPii}
                                onCheckedChange={setSendHashedPii}
                                aria-label="Include hashed PII"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Stage → Event Mapping</Label>
                            <div className="space-y-2">
                                {eventMapping.map((item, index) => (
                                    <div
                                        key={item.stage_slug}
                                        className="flex flex-col gap-2 rounded-md border p-3 md:flex-row md:items-center"
                                    >
                                        <div className="w-32 text-sm font-medium">
                                            {item.stage_slug.replace(/_/g, " ")}
                                        </div>
                                        <Input
                                            value={item.event_name}
                                            onChange={(event) => {
                                                const next = [...eventMapping]
                                                const existing = next[index]
                                                if (!existing) return
                                                next[index] = { ...existing, event_name: event.target.value }
                                                setEventMapping(next)
                                            }}
                                            placeholder="Event name"
                                            name={`zapier-event-${item.stage_slug}`}
                                            autoComplete="off"
                                        />
                                        <div className="flex items-center gap-2">
                                            <Switch
                                                checked={item.enabled}
                                                onCheckedChange={(checked) => {
                                                    const next = [...eventMapping]
                                                    const existing = next[index]
                                                    if (!existing) return
                                                    next[index] = { ...existing, enabled: checked }
                                                    setEventMapping(next)
                                                }}
                                                aria-label={`Enable ${item.stage_slug} event`}
                                            />
                                            <span className="text-xs text-muted-foreground">Enabled</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex flex-col gap-2 md:flex-row md:items-center">
                            <Button onClick={handleSaveOutbound} disabled={updateOutbound.isPending}>
                                {updateOutbound.isPending ? (
                                    <>
                                        <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        Saving…
                                    </>
                                ) : (
                                    "Save Outbound Settings"
                                )}
                            </Button>
                            <div className="flex flex-1 items-center gap-2">
                                <Select
                                    value={selectedOutboundStage}
                                    onValueChange={(value) => setSelectedOutboundStage(value ?? '')}
                                >
                                    <SelectTrigger className="w-full md:w-56" aria-label="Select stage">
                                        <SelectValue placeholder="Select stage" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {eventMapping.map((item) => (
                                            <SelectItem key={item.stage_slug} value={item.stage_slug}>
                                                {item.stage_slug.replace(/_/g, " ")}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Button
                                    variant="outline"
                                    onClick={handleOutboundTest}
                                    disabled={sendOutboundTest.isPending || !outboundEnabled}
                                >
                                    {sendOutboundTest.isPending ? (
                                        <>
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                            Sending…
                                        </>
                                    ) : (
                                        <>
                                            <ActivityIcon className="mr-2 size-4" aria-hidden="true" />
                                            Send Test Event
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

export default function IntegrationsPage() {
    const { data: healthData, isLoading, refetch, isFetching } = useIntegrationHealth()
    const { data: userIntegrations } = useUserIntegrations()
    const { data: aiSettings, isLoading: aiSettingsLoading } = useAISettings()
    const { data: resendSettings, isLoading: resendSettingsLoading } = useResendSettings()
    const { data: zapierSettings, isLoading: zapierSettingsLoading } = useZapierSettings()
    const connectZoom = useConnectZoom()
    const connectGmail = useConnectGmail()
    const connectGoogleCalendar = useConnectGoogleCalendar()
    const disconnectIntegration = useDisconnectIntegration()
    const [aiDialogOpen, setAiDialogOpen] = useState(false)
    const [emailDialogOpen, setEmailDialogOpen] = useState(false)
    const [zapierDialogOpen, setZapierDialogOpen] = useState(false)

    const zoomIntegration = userIntegrations?.find(i => i.integration_type === 'zoom')
    const gmailIntegration = userIntegrations?.find(i => i.integration_type === 'gmail')
    const googleCalendarIntegration = userIntegrations?.find(i => i.integration_type === 'google_calendar')
    const aiProviderLabel = aiSettings?.provider
        ? AI_PROVIDERS.find((providerOption) => providerOption.value === aiSettings.provider)?.label
            ?? aiSettings.provider
        : "Not configured"
    const aiStatusLabel = aiSettings?.is_enabled ? "Enabled" : "Disabled"
    const aiStatusVariant = aiSettings?.is_enabled ? "default" : "secondary"
    const aiStatusIcon = aiSettings?.is_enabled ? CheckCircleIcon : AlertTriangleIcon
    const emailProviderLabel = resendSettings?.email_provider === "resend"
        ? "Resend"
        : resendSettings?.email_provider === "gmail"
            ? "Gmail"
            : "Not configured"
    const emailConfigured = Boolean(resendSettings?.email_provider)
    const emailStatusLabel = emailConfigured ? "Configured" : "Not configured"
    const emailStatusVariant = emailConfigured ? "default" : "secondary"
    const emailStatusIcon = emailConfigured ? CheckCircleIcon : AlertTriangleIcon
    const emailDetail = emailConfigured
        ? resendSettings?.email_provider === "resend"
            ? resendSettings?.from_email ?? "Resend configured"
            : resendSettings?.default_sender_email ?? "Gmail sender selected"
        : "Choose a provider"
    const inboundWebhooks = zapierSettings?.inbound_webhooks ?? []
    const zapierConfigured = inboundWebhooks.some((hook) => hook.secret_configured) || Boolean(zapierSettings?.secret_configured)
    const zapierActive = inboundWebhooks.some((hook) => hook.is_active) || Boolean(zapierSettings?.is_active)
    const zapierStatusLabel = zapierConfigured
        ? (zapierActive ? "Active" : "Configured")
        : "Not configured"
    const zapierStatusVariant = zapierConfigured ? "default" : "secondary"
    const zapierStatusIcon = zapierConfigured
        ? (zapierActive ? CheckCircleIcon : AlertTriangleIcon)
        : XCircleIcon
    const inboundSummary = inboundWebhooks.length
        ? `${inboundWebhooks.length} inbound webhook${inboundWebhooks.length === 1 ? "" : "s"}`
        : "Inbound webhook ready"
    const zapierDetail = zapierConfigured
        ? (zapierSettings?.outbound_enabled ? `${inboundSummary} + outbound enabled` : inboundSummary)
        : "Configure webhook secret"
    const AiStatusIcon = aiStatusIcon
    const EmailStatusIcon = emailStatusIcon
    const ZapierStatusIcon = zapierStatusIcon

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Integrations</h1>
                    <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
                        <RefreshCwIcon className={`mr-2 size-4 ${isFetching ? "animate-spin" : ""} motion-reduce:animate-none`} aria-hidden="true" />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">

                {/* Personal Integrations */}
                <div>
                    <h2 className="mb-4 text-lg font-semibold">Personal Integrations</h2>
                    <p className="mb-4 text-sm text-muted-foreground">Connect your personal accounts to enable features like Zoom appointments and email sending.</p>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {/* Zoom */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                                        <VideoIcon className="size-5 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Zoom</CardTitle>
                                        <CardDescription className="text-xs">Video appointments</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {zoomIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{zoomIntegration.account_email}</p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('zoom')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectZoom.mutate()}
                                        disabled={connectZoom.isPending}
                                    >
                                        {connectZoom.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Zoom
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Gmail */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900">
                                        <MailIcon className="size-5 text-red-600 dark:text-red-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Gmail</CardTitle>
                                        <CardDescription className="text-xs">Email sending</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {gmailIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{gmailIntegration.account_email}</p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('gmail')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectGmail.mutate()}
                                        disabled={connectGmail.isPending}
                                    >
                                        {connectGmail.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Gmail
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Google Calendar + Meeting */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900">
                                        <CalendarIcon className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Google Calendar + Meeting</CardTitle>
                                        <CardDescription className="text-xs">Two-way calendar sync + meeting links</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {googleCalendarIntegration ? (
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="default" className="bg-green-600">
                                                <CheckCircleIcon className="mr-1 size-3" aria-hidden="true" />
                                                Connected
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">{googleCalendarIntegration.account_email}</p>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full"
                                            onClick={() => disconnectIntegration.mutate('google_calendar')}
                                            disabled={disconnectIntegration.isPending}
                                        >
                                            <UnlinkIcon className="mr-2 size-3" aria-hidden="true" />
                                            Disconnect
                                        </Button>
                                    </div>
                                ) : (
                                    <Button
                                        className="w-full"
                                        onClick={() => connectGoogleCalendar.mutate()}
                                        disabled={connectGoogleCalendar.isPending}
                                    >
                                        {connectGoogleCalendar.isPending ? (
                                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                        ) : (
                                            <LinkIcon className="mr-2 size-4" aria-hidden="true" />
                                        )}
                                        Connect Google Calendar
                                    </Button>
                                )}
                            </CardContent>
                        </Card>

                        {/* Meta Leads Admin */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900">
                                        <FacebookIcon className="size-5 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Meta Leads Admin</CardTitle>
                                        <CardDescription className="text-xs">Manage Facebook/Instagram page tokens</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <Button
                                    render={<Link href="/settings/integrations/meta" />}
                                    variant="outline"
                                    className="w-full"
                                >
                                    <KeyIcon className="mr-2 size-4" aria-hidden="true" />
                                    Manage Page Tokens
                                </Button>
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Organization Integrations */}
                <div>
                    <h2 className="mb-4 text-lg font-semibold">Organization Integrations</h2>
                    <p className="mb-4 text-sm text-muted-foreground">
                        Configure shared services like AI, email delivery, and Zapier for the organization.
                    </p>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {/* AI */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900">
                                        <SparklesIcon className="size-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">AI Assistant</CardTitle>
                                        <CardDescription className="text-xs">Copilot, summaries, and AI workflows</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {aiSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={aiStatusVariant} className="w-fit flex items-center gap-1">
                                            <AiStatusIcon className="size-3" aria-hidden="true" />
                                            {aiStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {aiSettings?.provider ? `Provider: ${aiProviderLabel}` : "No provider configured"}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setAiDialogOpen(true)}
                                        >
                                            Configure AI
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Email */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-teal-100 dark:bg-teal-900">
                                        <SendIcon className="size-5 text-teal-600 dark:text-teal-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Email Delivery</CardTitle>
                                        <CardDescription className="text-xs">Campaign + transactional sending</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {resendSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={emailStatusVariant} className="w-fit flex items-center gap-1">
                                            <EmailStatusIcon className="size-3" aria-hidden="true" />
                                            {emailStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {emailConfigured ? `${emailProviderLabel} · ${emailDetail}` : "Choose a provider to start sending"}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setEmailDialogOpen(true)}
                                        >
                                            Configure Email
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Zapier */}
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-100 dark:bg-indigo-900">
                                        <LinkIcon className="size-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                                    </div>
                                    <div>
                                        <CardTitle className="text-base">Zapier</CardTitle>
                                        <CardDescription className="text-xs">Inbound leads + stage event delivery</CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {zapierSettingsLoading ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2Icon className="size-5 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <Badge variant={zapierStatusVariant} className="w-fit flex items-center gap-1">
                                            <ZapierStatusIcon className="size-3" aria-hidden="true" />
                                            {zapierStatusLabel}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground">
                                            {zapierDetail}
                                        </p>
                                        <Button
                                            variant="outline"
                                            className="w-full"
                                            onClick={() => setZapierDialogOpen(true)}
                                        >
                                            Configure Zapier
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>

                <Dialog open={aiDialogOpen} onOpenChange={setAiDialogOpen}>
                    <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <DialogTitle>AI Configuration</DialogTitle>
                                    <DialogDescription>
                                        Configure the AI provider, model, and safety controls for your organization.
                                    </DialogDescription>
                                </div>
                                <Badge variant={aiStatusVariant} className="mt-1 flex items-center gap-1">
                                    <AiStatusIcon className="size-3" aria-hidden="true" />
                                    {aiStatusLabel}
                                </Badge>
                            </div>
                        </DialogHeader>
                        {aiDialogOpen ? <AIConfigurationSection variant="dialog" /> : null}
                    </DialogContent>
                </Dialog>

                <Dialog open={emailDialogOpen} onOpenChange={setEmailDialogOpen}>
                    <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <DialogTitle>Email Configuration</DialogTitle>
                                    <DialogDescription>
                                        Choose a provider and set sender defaults for campaigns and automation.
                                    </DialogDescription>
                                </div>
                                <Badge variant={emailStatusVariant} className="mt-1 flex items-center gap-1">
                                    <EmailStatusIcon className="size-3" aria-hidden="true" />
                                    {emailStatusLabel}
                                </Badge>
                            </div>
                        </DialogHeader>
                        {emailDialogOpen ? <EmailConfigurationSection variant="dialog" /> : null}
                    </DialogContent>
                </Dialog>

                <Dialog open={zapierDialogOpen} onOpenChange={setZapierDialogOpen}>
                    <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
                        <DialogHeader>
                            <div className="flex items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <DialogTitle>Zapier Configuration</DialogTitle>
                                    <DialogDescription>
                                        Manage inbound lead webhooks and outbound stage event delivery.
                                    </DialogDescription>
                                </div>
                                <Badge variant={zapierStatusVariant} className="mt-1 flex items-center gap-1">
                                    <ZapierStatusIcon className="size-3" aria-hidden="true" />
                                    {zapierStatusLabel}
                                </Badge>
                            </div>
                        </DialogHeader>
                        {zapierDialogOpen ? <ZapierWebhookSection variant="dialog" /> : null}
                    </DialogContent>
                </Dialog>

                {/* System Integrations Section */}
                <div className="border-t pt-6">
                    <h2 className="mb-4 text-lg font-semibold">System Integrations</h2>
                    <p className="mb-4 text-sm text-muted-foreground">Organization-level integrations managed by administrators.</p>
                </div>
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
                    </div>
                ) : (healthData?.length ?? 0) === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <ServerIcon className="mb-4 size-12" aria-hidden="true" />
                            <p className="text-lg font-medium">No integrations configured</p>
                            <p className="text-sm">Add integrations to see their health status here</p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {healthData?.map((integration) => {
                            const typeConfig = integrationTypeConfig[integration.integration_type] || {
                                icon: ServerIcon,
                                label: integration.integration_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                                description: "Custom integration",
                            }
                            const status = statusConfig[integration.status] || statusConfig.error
                            const configStatus = configStatusLabels[integration.config_status]
                                ?? configStatusLabels.configured
                                ?? { label: "Configured", variant: "default" as const }
                            const Icon = typeConfig.icon
                            const StatusIcon = status.icon

                            return (
                                <Card key={integration.id} className="relative overflow-hidden">
                                    {/* Status indicator bar */}
                                    <div className={`absolute left-0 top-0 h-full w-1 ${integration.status === 'healthy' ? 'bg-green-500' :
                                        integration.status === 'degraded' ? 'bg-yellow-500' :
                                            'bg-red-500'
                                        }`} />

                                    <CardHeader className="pb-3">
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
                                                    <Icon className="size-5" aria-hidden="true" />
                                                </div>
                                                <div>
                                                    <CardTitle className="text-base">{typeConfig.label}</CardTitle>
                                                    {integration.integration_key && (
                                                        <p className="text-xs text-muted-foreground">
                                                            Page: {integration.integration_key}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            <Badge variant={status.badge} className="flex items-center gap-1">
                                                <StatusIcon className="size-3" aria-hidden="true" />
                                                {status.label}
                                            </Badge>
                                        </div>
                                        <CardDescription className="mt-2 text-xs">
                                            {typeConfig.description}
                                        </CardDescription>
                                    </CardHeader>

                                    <CardContent className="space-y-3">
                                        {/* Config Status */}
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="text-muted-foreground">Configuration</span>
                                            <Badge variant={configStatus.variant} className="text-xs">
                                                <KeyIcon className="mr-1 size-3" aria-hidden="true" />
                                                {configStatus.label}
                                            </Badge>
                                        </div>

                                        {/* Success/Error timestamps */}
                                        <div className="space-y-1 text-xs">
                                            {integration.last_success_at && (
                                                <div className="flex items-center justify-between text-muted-foreground">
                                                    <span>Last success</span>
                                                    <span className="text-green-600">
                                                        {formatRelativeTime(integration.last_success_at, "Never")}
                                                    </span>
                                                </div>
                                            )}
                                            {integration.last_error_at && (
                                                <div className="flex items-center justify-between text-muted-foreground">
                                                    <span>Last error</span>
                                                    <span className="text-red-600">
                                                        {formatRelativeTime(integration.last_error_at, "Never")}
                                                    </span>
                                                </div>
                                            )}
                                        </div>

                                        {/* Error count */}
                                        {integration.error_count_24h > 0 && (
                                            <div className="flex items-center justify-between rounded-md bg-red-100 px-3 py-2 text-sm dark:bg-red-900/30">
                                                <span className="text-red-700 dark:text-red-300">Errors (24h)</span>
                                                <span className="font-semibold text-red-700 dark:text-red-300">
                                                    {integration.error_count_24h}
                                                </span>
                                            </div>
                                        )}

                                        {/* Last error message */}
                                        {integration.last_error && (
                                            <div className="rounded-md bg-muted p-2">
                                                <p className="text-xs text-muted-foreground line-clamp-2">
                                                    {integration.last_error}
                                                </p>
                                            </div>
                                        )}

                                        {/* Action buttons */}
                                        {integration.config_status !== "configured" && (
                                            integration.integration_type === "meta_leads" || integration.integration_type === "meta_capi" ? (
                                                <Button
                                                    render={<Link href="/settings/integrations/meta" />}
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full"
                                                >
                                                    <KeyIcon className="mr-2 size-3" aria-hidden="true" />
                                                    {integration.config_status === "expired_token"
                                                        ? "Refresh Token"
                                                        : "Configure"
                                                    }
                                                </Button>
                                            ) : (
                                                <p className="text-xs text-muted-foreground text-center">
                                                    Configure via CLI
                                                </p>
                                            )
                                        )}
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </div>
                )}

                {/* Help section */}
                <Card className="bg-muted/50">
                    <CardHeader>
                        <CardTitle className="text-base">Need help?</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        <p>
                            Integration tokens are managed via CLI commands. To update a Meta page token:
                        </p>
                        <pre className="mt-2 overflow-x-auto rounded-md bg-muted p-3 text-xs">
                            python -m app.cli update-meta-page-token --page-id YOUR_PAGE_ID
                        </pre>
                        <p className="mt-3">
                            Contact your administrator if you need to add or reconfigure integrations.
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
