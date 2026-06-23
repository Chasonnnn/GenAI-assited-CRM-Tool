"use client"

import * as React from "react"
import {
    AlertTriangleIcon,
    CheckCircle2Icon,
    Code2Icon,
    CopyIcon,
    DownloadIcon,
    LinkIcon,
    QrCodeIcon,
    RefreshCwIcon,
    XCircleIcon,
} from "lucide-react"
import { toast } from "sonner"

import {
    AlertDialog,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { formatUtcDateLabel } from "@/components/ui/time-display"
import type { FormEmbedHealthRead, FormIntakeLinkRead, TrackingMode } from "@/lib/api/forms"

type ShareApplicationDialogProps = {
    open: boolean
    selectedQrLink: FormIntakeLinkRead | null
    onOpenChange: (open: boolean) => void
    onCopyLink: (link: FormIntakeLinkRead) => Promise<void>
    onDownloadQrSvg: () => void
    onDownloadQrPng: () => Promise<void>
    onUpdateEmbedSettings: (args: {
        link: FormIntakeLinkRead
        embedEnabled: boolean
        allowedOrigins: string[]
        trackingMode: TrackingMode
        consentText: string | null
    }) => Promise<void>
    isEmbedSettingsPending?: boolean
    embedHealth?: FormEmbedHealthRead | null | undefined
    isEmbedHealthFetching?: boolean
    onRefreshEmbedHealth?: () => void
}

type EmbedSettingsState = {
    embedEnabled: boolean
    originText: string
    trackingMode: TrackingMode
    consentText: string
}

const DEFAULT_EMBED_SETTINGS: EmbedSettingsState = {
    embedEnabled: false,
    originText: "",
    trackingMode: "enhanced_match_lead",
    consentText: "",
}

export function ShareApplicationDialog({
    open,
    selectedQrLink,
    onOpenChange,
    onCopyLink,
    onDownloadQrSvg,
    onDownloadQrPng,
    onUpdateEmbedSettings,
    isEmbedSettingsPending = false,
    embedHealth,
    isEmbedHealthFetching = false,
    onRefreshEmbedHealth,
}: ShareApplicationDialogProps) {
    const [embedSettings, setEmbedSettings] = React.useState<EmbedSettingsState>(DEFAULT_EMBED_SETTINGS)
    const { embedEnabled, originText, trackingMode, consentText } = embedSettings

    React.useEffect(() => {
        if (!selectedQrLink) {
            setEmbedSettings(DEFAULT_EMBED_SETTINGS)
            return
        }
        setEmbedSettings({
            embedEnabled: selectedQrLink.embed_enabled,
            originText: (selectedQrLink.allowed_embed_origins || []).join("\n"),
            trackingMode: selectedQrLink.tracking_mode || "enhanced_match_lead",
            consentText: selectedQrLink.consent_text || "",
        })
    }, [selectedQrLink])

    const embedSnippet = selectedQrLink ? buildEmbedSnippet(selectedQrLink) : ""
    const copyEmbedSnippet = async () => {
        if (!embedSnippet) return
        try {
            await navigator.clipboard.writeText(embedSnippet)
            toast.success("Embed snippet copied")
        } catch {
            toast.error("Failed to copy embed snippet")
        }
    }
    const saveEmbedSettings = async () => {
        if (!selectedQrLink) return
        const allowedOrigins: string[] = []
        for (const value of originText.split(/[\n,]+/)) {
            const origin = value.trim()
            if (origin) allowedOrigins.push(origin)
        }
        if (embedEnabled && allowedOrigins.length === 0) {
            toast.error("Add at least one allowed website origin")
            return
        }
        await onUpdateEmbedSettings({
            link: selectedQrLink,
            embedEnabled,
            allowedOrigins,
            trackingMode,
            consentText: consentText.trim() || null,
        })
    }

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent className="max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-2xl gap-4 overflow-x-hidden overflow-y-auto p-4 data-[size=default]:max-w-2xl data-[size=default]:sm:max-w-2xl sm:p-6">
                <AlertDialogHeader className="min-w-0">
                    <AlertDialogTitle>Share Application Intake</AlertDialogTitle>
                    <AlertDialogDescription className="break-words">
                        Choose how you want to distribute this published application form.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <Tabs defaultValue="hosted" className="min-w-0 w-full overflow-hidden">
                    <TabsList className="grid h-auto w-full min-w-0 grid-cols-3 rounded-2xl sm:h-9">
                        <TabsTrigger value="hosted" className="min-w-0 px-1.5 text-xs sm:px-2 sm:text-sm">
                            <span className="truncate">Hosted Link</span>
                        </TabsTrigger>
                        <TabsTrigger value="qr" className="min-w-0 px-1.5 text-xs sm:px-2 sm:text-sm">
                            <span className="truncate">QR Code</span>
                        </TabsTrigger>
                        <TabsTrigger value="embed" className="min-w-0 px-1.5 text-xs sm:px-2 sm:text-sm">
                            <span className="truncate">Embed</span>
                        </TabsTrigger>
                    </TabsList>
                    <TabsContent value="hosted" className="mt-4 min-w-0">
                        {selectedQrLink?.intake_url ? (
                            <div className="min-w-0 max-w-full space-y-2 overflow-hidden rounded-md border border-stone-200 bg-stone-50 p-3 text-xs text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                    {selectedQrLink.event_name || selectedQrLink.campaign_name || "Shared intake link"}
                                </div>
                                <div className="break-all">{selectedQrLink.intake_url}</div>
                            </div>
                        ) : (
                            <p className="text-sm text-stone-500">No shared intake link is available yet.</p>
                        )}
                    </TabsContent>
                    <TabsContent value="qr" className="mt-4 min-w-0">
                        <div className="min-w-0 max-w-full rounded-md border border-stone-200 bg-stone-50 p-3 text-sm text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                            Use the QR download actions below for the selected hosted link.
                        </div>
                    </TabsContent>
                    <TabsContent
                        value="embed"
                        className="mt-4 max-h-[min(48vh,32rem)] min-w-0 space-y-3 overflow-y-auto overflow-x-hidden pr-1"
                    >
                        {selectedQrLink ? (
                            <>
                                <div className="min-w-0 max-w-full space-y-4 overflow-hidden rounded-md border border-stone-200 p-3 dark:border-stone-800">
                                    <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                                            <EmbedHealthStatusBadge health={embedHealth} />
                                            {embedHealth?.updated_at ? (
                                                <span className="text-xs text-stone-500">
                                                    Checked {formatUtcDateLabel(embedHealth.updated_at, { month: "long" })}
                                                </span>
                                            ) : null}
                                        </div>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            className="shrink-0"
                                            onClick={onRefreshEmbedHealth}
                                            disabled={!selectedQrLink || isEmbedHealthFetching}
                                        >
                                            <RefreshCwIcon
                                                className={`mr-2 size-4 ${isEmbedHealthFetching ? "animate-spin" : ""}`}
                                            />
                                            Check setup
                                        </Button>
                                    </div>
                                    {embedHealth ? (
                                        <div className="min-w-0 max-w-full space-y-2 overflow-hidden rounded-md border border-stone-200 bg-stone-50 p-3 dark:border-stone-800 dark:bg-stone-900/40">
                                            {embedHealth.checks.map((check) => (
                                                <div key={check.key} className="flex min-w-0 gap-2 text-xs">
                                                    <EmbedHealthCheckIcon status={check.status} />
                                                    <div className="min-w-0">
                                                        <div className="font-medium text-stone-900 dark:text-stone-100">
                                                            {check.label}
                                                        </div>
                                                        <div className="break-words text-stone-500">{check.message}</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : null}
                                    <div className="flex items-center justify-between gap-3">
                                        <Label htmlFor="sf-embed-enabled" className="text-sm font-medium">
                                            Enable iframe embed
                                        </Label>
                                        <Switch
                                            id="sf-embed-enabled"
                                            checked={embedEnabled}
                                            onCheckedChange={(checked) =>
                                                setEmbedSettings((current) => ({ ...current, embedEnabled: checked }))
                                            }
                                            disabled={isEmbedSettingsPending}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="sf-embed-origins">Allowed origins</Label>
                                        <Textarea
                                            id="sf-embed-origins"
                                            value={originText}
                                            onChange={(event) =>
                                                setEmbedSettings((current) => ({
                                                    ...current,
                                                    originText: event.target.value,
                                                }))
                                            }
                                            placeholder="https://www.clientsite.com"
                                            rows={3}
                                            className="min-w-0"
                                            disabled={isEmbedSettingsPending}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="sf-embed-tracking">Tracking mode</Label>
                                        <Select
                                            value={trackingMode}
                                            onValueChange={(value) =>
                                                setEmbedSettings((current) => ({
                                                    ...current,
                                                    trackingMode: value as TrackingMode,
                                                }))
                                            }
                                            disabled={isEmbedSettingsPending}
                                        >
                                            <SelectTrigger id="sf-embed-tracking" className="min-w-0">
                                                <SelectValue>
                                                    {(value: string | null) =>
                                                        getTrackingModeLabel((value as TrackingMode | null) ?? "enhanced_match_lead")
                                                    }
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="enhanced_match_lead">Enhanced Match Lead</SelectItem>
                                                <SelectItem value="privacy_safe_lead">Privacy-safe Lead</SelectItem>
                                                <SelectItem value="internal_only">Internal Only</SelectItem>
                                                <SelectItem value="disabled">Disabled</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="sf-embed-consent">Consent text</Label>
                                        <Textarea
                                            id="sf-embed-consent"
                                            value={consentText}
                                            onChange={(event) =>
                                                setEmbedSettings((current) => ({
                                                    ...current,
                                                    consentText: event.target.value,
                                                }))
                                            }
                                            placeholder="I agree to be contacted about my inquiry."
                                            rows={3}
                                            className="min-w-0"
                                            disabled={isEmbedSettingsPending}
                                        />
                                    </div>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => void saveEmbedSettings()}
                                        disabled={!selectedQrLink || isEmbedSettingsPending}
                                    >
                                        Save Embed Settings
                                    </Button>
                                </div>
                                <div className="min-w-0 max-w-full overflow-hidden rounded-md border border-stone-200 bg-stone-50 p-3 text-xs text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                                    <div className="mb-2 flex items-center gap-2 font-medium text-stone-900 dark:text-stone-100">
                                        <Code2Icon className="size-4" />
                                        Website embed
                                    </div>
                                    <pre className="max-h-48 max-w-full overflow-auto whitespace-pre-wrap break-all rounded border border-stone-200 bg-white p-3 font-mono text-[11px] leading-5 dark:border-stone-800 dark:bg-stone-950">
                                        {embedSnippet}
                                    </pre>
                                </div>
                                {!selectedQrLink.embed_enabled ? (
                                    <p className="text-xs text-amber-700">
                                        Embedding is disabled for this link until allowed origins are configured.
                                    </p>
                                ) : selectedQrLink.allowed_embed_origins.length > 0 ? (
                                    <p className="break-words text-xs text-stone-500">
                                        Allowed origins: {selectedQrLink.allowed_embed_origins.join(", ")}
                                    </p>
                                ) : null}
                                <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={copyEmbedSnippet}>
                                    <CopyIcon className="mr-2 size-4" />
                                    Copy Embed
                                </Button>
                            </>
                        ) : (
                            <p className="text-sm text-stone-500">No shared intake link is available yet.</p>
                        )}
                    </TabsContent>
                </Tabs>
                <AlertDialogFooter className="min-w-0 flex-col sm:flex-row sm:flex-wrap">
                    <AlertDialogCancel className="w-full sm:w-auto">Close</AlertDialogCancel>
                    <Button
                        type="button"
                        variant="outline"
                        className="w-full sm:w-auto"
                        disabled={!selectedQrLink}
                        onClick={async () => {
                            if (!selectedQrLink) return
                            await onCopyLink(selectedQrLink)
                            onOpenChange(false)
                        }}
                    >
                        <LinkIcon className="mr-2 size-4" />
                        Copy Link
                    </Button>
                    <Button
                        type="button"
                        variant="outline"
                        className="w-full sm:w-auto"
                        disabled={!selectedQrLink}
                        onClick={() => {
                            if (!selectedQrLink) return
                            onDownloadQrSvg()
                            onOpenChange(false)
                        }}
                    >
                        <DownloadIcon className="mr-2 size-4" />
                        QR (SVG)
                    </Button>
                    <Button
                        type="button"
                        className="w-full sm:w-auto"
                        disabled={!selectedQrLink}
                        onClick={() => {
                            if (!selectedQrLink) return
                            void onDownloadQrPng()
                            onOpenChange(false)
                        }}
                    >
                        <QrCodeIcon className="mr-2 size-4" />
                        QR (PNG)
                    </Button>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    )
}

function getTrackingModeLabel(value: TrackingMode): string {
    const labels: Record<TrackingMode, string> = {
        privacy_safe_lead: "Privacy-safe Lead",
        enhanced_match_lead: "Enhanced Match Lead",
        internal_only: "Internal Only",
        disabled: "Disabled",
        advanced: "Advanced",
    }
    return labels[value]
}

function EmbedHealthStatusBadge({ health }: { health?: FormEmbedHealthRead | null | undefined }) {
    if (!health) {
        return <Badge variant="outline">Setup not checked</Badge>
    }
    if (health.status === "ready") {
        return <Badge className="bg-emerald-600 hover:bg-emerald-600">Ready to embed</Badge>
    }
    if (health.status === "needs_attention") {
        return <Badge variant="secondary">Needs attention</Badge>
    }
    return <Badge variant="destructive">Blocked</Badge>
}

function EmbedHealthCheckIcon({ status }: { status: "pass" | "warning" | "block" }) {
    if (status === "pass") {
        return <CheckCircle2Icon className="mt-0.5 size-4 shrink-0 text-emerald-600" />
    }
    if (status === "warning") {
        return <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-amber-600" />
    }
    return <XCircleIcon className="mt-0.5 size-4 shrink-0 text-red-600" />
}

function buildEmbedSnippet(link: FormIntakeLinkRead): string {
    let origin = "https://app.surrogacyforce.com"
    const fallbackOrigin = typeof window === "undefined" ? origin : window.location.origin
    if (link.intake_url) {
        try {
            origin = new URL(link.intake_url, fallbackOrigin).origin
        } catch {
            origin = fallbackOrigin
        }
    }
    return `<div data-sf-form="${link.slug}"></div>\n<script async src="${origin}/embed/forms.v1.js"></script>`
}
