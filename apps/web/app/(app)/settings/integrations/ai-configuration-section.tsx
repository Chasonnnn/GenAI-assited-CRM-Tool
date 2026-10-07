import { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DialogBody, DialogFooter, DialogClose } from "@/components/ui/dialog"
import { ConfirmDialog } from "@/components/ui/confirm-dialog"
import { getActionErrorMessage } from "@/lib/forms/api-field-errors"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import { Loader2Icon, CheckIcon, XCircleIcon } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { useUserIntegrations, useConnectGcp, useDisconnectIntegration } from "@/lib/hooks/use-user-integrations"
import { useAISettings, useAIConsent, useAcceptConsent, useUpdateAISettings, useTestAPIKey } from "@/lib/hooks/use-ai"
import { toast } from "@/components/ui/toast"
import type { IntegrationStatus } from "@/lib/api/integrations"
import { IntegrationDialogLoadingState, getSelectOptionLabel } from "./integration-shared"

// AI provider options
export const AI_PROVIDERS = [
    {
        value: "gemini",
        label: "Google Gemini",
        models: ["gemini-3.8-flash"],
    },
    {
        value: "vertex_api_key",
        label: "Vertex AI (API Key)",
        models: ["gemini-3.8-flash"],
    },
    {
        value: "vertex_wif",
        label: "Vertex AI (WIF)",
        models: ["gemini-3.8-flash"],
    },
] as const

const VERTEX_LOCATIONS = [
    { value: "global", label: "Global" },
    { value: "us", label: "United States" },
    { value: "eu", label: "European Union" },
] as const

type AiProvider = (typeof AI_PROVIDERS)[number]["value"]

const isAiProvider = (value: string | null | undefined): value is AiProvider =>
    AI_PROVIDERS.some((providerOption) => providerOption.value === value)

type AiConfigurationFormState = {
    isEnabled: boolean
    provider: AiProvider
    apiKey: string
    model: string
    vertexProjectId: string
    vertexLocation: string
    vertexAudience: string
    vertexServiceAccount: string
    vertexUseExpress: boolean
}

type AiConfigurationUiState = {
    keyTested: boolean | null
    saved: boolean
    editingKey: boolean
}

/** DialogBody and DialogFooter of the AI Configuration dialog. */
export function AIConfigurationSection() {
    const { data: aiSettings, isLoading } = useAISettings()

    return (
        <AIConfigurationSectionContent
            key={aiSettings ? "loaded" : "loading"}
            aiSettings={aiSettings}
            isLoading={isLoading}
        />
    )
}

function AIConfigurationSectionContent({
    aiSettings,
    isLoading,
}: {
    aiSettings: ReturnType<typeof useAISettings>["data"]
    isLoading: boolean
}) {
    const { data: consentInfo } = useAIConsent()
    const acceptConsent = useAcceptConsent()
    const updateSettings = useUpdateAISettings()
    const testKey = useTestAPIKey()
    const { data: userIntegrations } = useUserIntegrations()
    const connectGcp = useConnectGcp()
    const disconnectIntegration = useDisconnectIntegration()
    const { refresh: refreshAuth } = useAuth()

    const [aiForm, setAiForm] = useState<AiConfigurationFormState>(() => ({
        isEnabled: aiSettings?.is_enabled ?? false,
        provider: aiSettings && isAiProvider(aiSettings.provider) ? aiSettings.provider : "gemini",
        apiKey: "",
        model: aiSettings?.model || "",
        vertexProjectId:
            aiSettings?.vertex_wif?.project_id ||
            aiSettings?.vertex_api_key?.project_id ||
            "",
        vertexLocation:
            aiSettings?.vertex_wif?.location ||
            aiSettings?.vertex_api_key?.location ||
            "us",
        vertexAudience: aiSettings?.vertex_wif?.audience || "",
        vertexServiceAccount: aiSettings?.vertex_wif?.service_account_email || "",
        vertexUseExpress:
            aiSettings?.provider === "vertex_api_key"
            && !aiSettings.vertex_api_key?.project_id
            && !aiSettings.vertex_api_key?.location,
    }))
    const [aiUi, setAiUi] = useState<AiConfigurationUiState>({
        keyTested: null,
        saved: false,
        editingKey: false,
    })

    const updateAiForm = <K extends keyof AiConfigurationFormState>(field: K, value: AiConfigurationFormState[K]) => {
        setAiForm((current) => ({ ...current, [field]: value }))
    }

    const selectedProviderModels =
        AI_PROVIDERS.find((providerOption) => providerOption.value === aiForm.provider)?.models ??
        []
    const consentAccepted = Boolean(aiSettings?.consent_accepted_at)
    const gcpIntegration = userIntegrations?.find((integration) => integration.integration_type === "gcp")
    const vertexReady = aiForm.provider !== "vertex_wif"
        || Boolean(
            aiForm.vertexProjectId.trim()
            && aiForm.vertexLocation.trim()
            && aiForm.vertexServiceAccount.trim()
            && aiForm.vertexAudience.trim()
        )

    const handleTestKey = async () => {
        if (aiForm.provider === "vertex_wif" || !aiForm.apiKey.trim()) return
        setAiUi((current) => ({ ...current, keyTested: null }))
        try {
            const payload: {
                provider: "gemini" | "vertex_api_key";
                api_key: string;
                vertex_api_key?: { project_id: string | null; location: string | null };
            } = {
                provider: aiForm.provider,
                api_key: aiForm.apiKey,
            }
            if (aiForm.provider === "vertex_api_key") {
                payload.vertex_api_key = {
                    project_id: aiForm.vertexUseExpress ? null : aiForm.vertexProjectId.trim() || null,
                    location: aiForm.vertexUseExpress ? null : aiForm.vertexLocation.trim() || null,
                }
            }
            const result = await testKey.mutateAsync(payload)
            setAiUi((current) => ({ ...current, keyTested: result.valid }))
        } catch {
            setAiUi((current) => ({ ...current, keyTested: false }))
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
            is_enabled: aiForm.isEnabled,
            provider: aiForm.provider,
        }
        if (aiForm.apiKey.trim()) {
            update.api_key = aiForm.apiKey
        }
        if (aiForm.model) {
            update.model = aiForm.model
        }
        if (aiForm.provider === "vertex_wif") {
            update.vertex_wif = {
                project_id: aiForm.vertexProjectId.trim() || null,
                location: aiForm.vertexLocation.trim() || null,
                audience: aiForm.vertexAudience.trim() || null,
                service_account_email: aiForm.vertexServiceAccount.trim() || null,
            }
        }
        if (aiForm.provider === "vertex_api_key") {
            update.vertex_api_key = {
                project_id: aiForm.vertexUseExpress ? null : aiForm.vertexProjectId.trim() || null,
                location: aiForm.vertexUseExpress ? null : aiForm.vertexLocation.trim() || null,
            }
        }
        try {
            await updateSettings.mutateAsync(update)
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't save AI configuration")
            if (message) toast.error(message)
            return
        }
        setAiForm((current) => ({ ...current, apiKey: "" }))
        setAiUi((current) => ({
            ...current,
            keyTested: null,
            saved: true,
            editingKey: false,
        }))
        void refreshAuth()
        setTimeout(() => {
            setAiUi((current) => ({ ...current, saved: false }))
        }, 2000)
    }

    const handleAcceptConsent = async () => {
        try {
            await acceptConsent.mutateAsync()
            toast.success("AI consent accepted")
        } catch (error) {
            const message = getActionErrorMessage(error, "Couldn't accept AI consent")
            if (message) toast.error(message)
        }
    }

    if (isLoading) {
        return <IntegrationDialogLoadingState />
    }

    return (
        <>
            <DialogBody>
                {!consentAccepted && consentInfo ? (
                    <AIConsentCard
                        consentText={consentInfo.consent_text}
                        pending={acceptConsent.isPending}
                        onAccept={handleAcceptConsent}
                    />
                ) : null}

                <AISettingsFields
                    aiForm={aiForm}
                    aiUi={aiUi}
                    apiKeyMasked={aiSettings?.api_key_masked ?? null}
                    consentAccepted={consentAccepted}
                    selectedProviderModels={selectedProviderModels}
                    gcpIntegration={gcpIntegration}
                    pendingState={{
                        keyTest: testKey.isPending,
                        gcpConnect: connectGcp.isPending,
                        gcpDisconnect: disconnectIntegration.isPending,
                    }}
                    updateAiForm={updateAiForm}
                    onProviderChange={(provider) => {
                        setAiForm((current) => ({
                            ...current,
                            provider,
                            model: "",
                        }))
                        setAiUi((current) => ({
                            ...current,
                            keyTested: null,
                            editingKey: false,
                        }))
                    }}
                    onApiKeyChange={(apiKey) => {
                        updateAiForm("apiKey", apiKey)
                        setAiUi((current) => ({ ...current, keyTested: null }))
                    }}
                    onEditKey={() => {
                        updateAiForm("apiKey", "")
                        setAiUi((current) => ({ ...current, editingKey: true }))
                    }}
                    onTestKey={handleTestKey}
                    onConnectGcp={() => connectGcp.mutate()}
                    onDisconnectGcp={async () => {
                        await disconnectIntegration.mutateAsync("gcp")
                        toast.success("Google Cloud disconnected")
                    }}
                />
            </DialogBody>
            <DialogFooter>
                <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                <AISaveButton
                    pending={updateSettings.isPending}
                    saved={aiUi.saved}
                    disabled={!vertexReady}
                    onSave={() => {
                        void handleSave()
                    }}
                />
            </DialogFooter>
        </>
    )
}

type UpdateAiConfigurationForm = <K extends keyof AiConfigurationFormState>(
    field: K,
    value: AiConfigurationFormState[K],
) => void

function AIConsentCard({
    consentText,
    pending,
    onAccept,
}: {
    consentText: string
    pending: boolean
    onAccept: () => void
}) {
    return (
        <Card className="mb-4 border-yellow-200 bg-yellow-50/60">
            <CardHeader className="pb-2">
                <CardTitle className="text-base">AI Consent Required</CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                    An admin must accept the AI data processing consent before enabling AI features.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="max-h-40 overflow-auto rounded-md border border-yellow-200 bg-white p-3 text-xs leading-relaxed text-muted-foreground">
                    {consentText}
                </div>
                <Button onClick={onAccept} disabled={pending}>
                    {pending ? (
                        <>
                            <Loader2Icon
                                className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                            Accepting…
                        </>
                    ) : (
                        "Accept Consent"
                    )}
                </Button>
            </CardContent>
        </Card>
    )
}

function AISettingsFields({
    aiForm,
    aiUi,
    apiKeyMasked,
    consentAccepted,
    selectedProviderModels,
    gcpIntegration,
    pendingState,
    updateAiForm,
    onProviderChange,
    onApiKeyChange,
    onEditKey,
    onTestKey,
    onConnectGcp,
    onDisconnectGcp,
}: {
    aiForm: AiConfigurationFormState
    aiUi: AiConfigurationUiState
    apiKeyMasked: string | null
    consentAccepted: boolean
    selectedProviderModels: ReadonlyArray<string>
    gcpIntegration: IntegrationStatus | undefined
    pendingState: {
        keyTest: boolean
        gcpConnect: boolean
        gcpDisconnect: boolean
    }
    updateAiForm: UpdateAiConfigurationForm
    onProviderChange: (provider: AiProvider) => void
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onTestKey: () => void
    onConnectGcp: () => void
    onDisconnectGcp: () => Promise<unknown>
}) {
    return (
        <>
            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                <Label htmlFor="ai-enabled">Enable AI assistant</Label>
                <Switch
                    id="ai-enabled"
                    checked={aiForm.isEnabled}
                    onCheckedChange={(checked) => updateAiForm("isEnabled", checked)}
                    disabled={!consentAccepted && !aiForm.isEnabled}
                />
            </div>

            <div className="space-y-4">
                <AIProviderField
                    provider={aiForm.provider}
                    onProviderChange={onProviderChange}
                />

                {aiForm.provider !== "vertex_wif" ? (
                    <AIApiKeyField
                        provider={aiForm.provider}
                        apiKey={aiForm.apiKey}
                        apiKeyMasked={apiKeyMasked}
                        editingKey={aiUi.editingKey}
                        keyTested={aiUi.keyTested}
                        pending={pendingState.keyTest}
                        onApiKeyChange={onApiKeyChange}
                        onEditKey={onEditKey}
                        onTestKey={onTestKey}
                    />
                ) : null}

                {aiForm.provider === "vertex_api_key" ? (
                    <VertexApiKeySettings
                        form={aiForm}
                        updateAiForm={updateAiForm}
                    />
                ) : null}

                {aiForm.provider === "vertex_wif" ? (
                    <VertexWifSettings
                        form={aiForm}
                        gcpIntegration={gcpIntegration}
                        pendingState={pendingState}
                        updateAiForm={updateAiForm}
                        onConnectGcp={onConnectGcp}
                        onDisconnectGcp={onDisconnectGcp}
                    />
                ) : null}

                <AIModelField
                    model={aiForm.model}
                    selectedProviderModels={selectedProviderModels}
                    onModelChange={(model) => updateAiForm("model", model)}
                />
            </div>
        </>
    )
}

function AIProviderField({
    provider,
    onProviderChange,
}: {
    provider: AiProvider
    onProviderChange: (provider: AiProvider) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-provider">AI Provider</Label>
            <Select
                value={provider}
                onValueChange={(value) => {
                    if (!value || !isAiProvider(value)) return
                    onProviderChange(value)
                }}
            >
                <SelectTrigger id="ai-provider">
                    <SelectValue placeholder="Select provider">
                        {(value: string | null) => getSelectOptionLabel(AI_PROVIDERS, value)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {AI_PROVIDERS.map((providerOption) => (
                        <SelectItem key={providerOption.value} value={providerOption.value}>
                            {providerOption.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    )
}

function AIApiKeyField({
    provider,
    apiKey,
    apiKeyMasked,
    editingKey,
    keyTested,
    pending,
    onApiKeyChange,
    onEditKey,
    onTestKey,
}: {
    provider: AiProvider
    apiKey: string
    apiKeyMasked: string | null
    editingKey: boolean
    keyTested: boolean | null
    pending: boolean
    onApiKeyChange: (apiKey: string) => void
    onEditKey: () => void
    onTestKey: () => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-key">API Key</Label>
            <div className="flex gap-2">
                <Input
                    id="ai-key"
                    type="password"
                    value={editingKey ? apiKey : apiKey || (apiKeyMasked ?? "")}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder="Enter API key"
                    disabled={!editingKey && !apiKey && !!apiKeyMasked}
                    className="flex-1"
                    name="ai-api-key"
                    autoComplete="off"
                />
                {apiKeyMasked && !apiKey && !editingKey ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onEditKey}
                        className="shrink-0"
                    >
                        Change Key
                    </Button>
                ) : (
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
            {keyTested === true ? (
                <p className="text-xs text-green-600">API key is valid!</p>
            ) : null}
            {keyTested === false ? (
                <p className="text-xs text-red-600">API key is invalid. Please check and try again.</p>
            ) : null}
            <p className="text-xs text-muted-foreground">
                {provider === "gemini"
                    ? "Get your key from aistudio.google.com"
                    : "Create a Vertex AI API key in Google Cloud"}
            </p>
        </div>
    )
}

function VertexApiKeySettings({
    form,
    updateAiForm,
}: {
    form: AiConfigurationFormState
    updateAiForm: UpdateAiConfigurationForm
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <div>
                <h3 className="text-sm font-medium">Vertex AI (API Key)</h3>
                <p className="text-xs text-muted-foreground">
                    Express mode works without project or location. Add them to use project-scoped endpoints.
                </p>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
                <div className="text-sm">
                    {form.vertexUseExpress ? "Express mode active" : "Project-scoped mode"}
                </div>
                <div className="flex items-center gap-2">
                    <Label htmlFor="vertex-express" className="text-xs text-muted-foreground">
                        Use express mode
                    </Label>
                    <Switch
                        id="vertex-express"
                        checked={form.vertexUseExpress}
                        onCheckedChange={(checked) => updateAiForm("vertexUseExpress", checked)}
                    />
                </div>
            </div>
            {!form.vertexUseExpress ? (
                <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="vertex-project-key">Project ID (optional)</Label>
                        <Input
                            id="vertex-project-key"
                            value={form.vertexProjectId}
                            onChange={(event) => updateAiForm("vertexProjectId", event.target.value)}
                            placeholder="your-gcp-project-id"
                            name="vertex-project-key"
                            autoComplete="off"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="vertex-location-key">Location (optional)</Label>
                        <Select
                            value={form.vertexLocation}
                            onValueChange={(value) => updateAiForm("vertexLocation", value || "us")}
                        >
                            <SelectTrigger id="vertex-location-key">
                                <SelectValue>
                                    {(value: string | null) => getSelectOptionLabel(VERTEX_LOCATIONS, value)}
                                </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                                {VERTEX_LOCATIONS.map((location) => (
                                    <SelectItem key={location.value} value={location.value}>
                                        {location.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            ) : null}
        </div>
    )
}

function VertexWifSettings({
    form,
    gcpIntegration,
    pendingState,
    updateAiForm,
    onConnectGcp,
    onDisconnectGcp,
}: {
    form: AiConfigurationFormState
    gcpIntegration: IntegrationStatus | undefined
    pendingState: {
        gcpConnect: boolean
        gcpDisconnect: boolean
    }
    updateAiForm: UpdateAiConfigurationForm
    onConnectGcp: () => void
    onDisconnectGcp: () => Promise<unknown>
}) {
    return (
        <div className="space-y-4 rounded-lg border p-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-medium">Vertex AI (WIF)</h3>
                    <p className="text-xs text-muted-foreground">
                        Uses Workload Identity Federation, no long-lived keys stored.
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
                    <ConfirmDialog
                        trigger={(
                            <Button variant="outline" size="sm" disabled={pendingState.gcpDisconnect}>
                                Disconnect…
                            </Button>
                        )}
                        title="Disconnect Google Cloud?"
                        description="Vertex AI (WIF) requests stop until an account is connected again."
                        confirmLabel="Disconnect"
                        errorFallback="Couldn't disconnect Google Cloud. Try again."
                        onConfirm={onDisconnectGcp}
                    />
                ) : (
                    <Button size="sm" onClick={onConnectGcp} disabled={pendingState.gcpConnect}>
                        {pendingState.gcpConnect ? (
                            <Loader2Icon
                                className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                aria-hidden="true"
                            />
                        ) : null}
                        Connect GCP
                    </Button>
                )}
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-project">Project ID</Label>
                <Input
                    id="vertex-project"
                    value={form.vertexProjectId}
                    onChange={(event) => updateAiForm("vertexProjectId", event.target.value)}
                    placeholder="your-gcp-project-id"
                    name="vertex-project"
                    autoComplete="off"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-location">Location</Label>
                <Select
                    value={form.vertexLocation}
                    onValueChange={(value) => updateAiForm("vertexLocation", value || "us")}
                >
                    <SelectTrigger id="vertex-location">
                        <SelectValue>
                            {(value: string | null) => getSelectOptionLabel(VERTEX_LOCATIONS, value)}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        {VERTEX_LOCATIONS.map((location) => (
                            <SelectItem key={location.value} value={location.value}>
                                {location.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-service-account">Service Account Email</Label>
                <Input
                    id="vertex-service-account"
                    value={form.vertexServiceAccount}
                    onChange={(event) => updateAiForm("vertexServiceAccount", event.target.value)}
                    placeholder="vertex-sa@project.iam.gserviceaccount.com"
                    name="vertex-service-account"
                    autoComplete="off"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="vertex-audience">Workload Identity Audience</Label>
                <Input
                    id="vertex-audience"
                    value={form.vertexAudience}
                    onChange={(event) => updateAiForm("vertexAudience", event.target.value)}
                    placeholder="//iam.googleapis.com/projects/123/locations/global/workloadIdentityPools/pool/providers/provider"
                    name="vertex-audience"
                    autoComplete="off"
                />
                <p className="text-xs text-muted-foreground">
                    Use the provider resource name or full audience from the Workload Identity Provider.
                </p>
            </div>
        </div>
    )
}

function AIModelField({
    model,
    selectedProviderModels,
    onModelChange,
}: {
    model: string
    selectedProviderModels: ReadonlyArray<string>
    onModelChange: (model: string) => void
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor="ai-model">Model</Label>
            <Select value={model} onValueChange={(value) => onModelChange(value || "")}>
                <SelectTrigger id="ai-model">
                    <SelectValue placeholder="Select model (optional)">
                        {(value: string | null) =>
                            value
                                ? getSelectOptionLabel(
                                    selectedProviderModels.map((selectedModel) => ({
                                        value: selectedModel,
                                        label: selectedModel,
                                    })),
                                    value,
                                )
                                : ""
                        }
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {selectedProviderModels.map((selectedModel) => (
                        <SelectItem key={selectedModel} value={selectedModel}>
                            {selectedModel}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
                Leave empty to use the default model
            </p>
        </div>
    )
}

function AISaveButton({
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
                "Save AI Configuration"
            )}
        </Button>
    )
}
