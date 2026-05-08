"use client"

import * as React from "react"
import { Code2Icon, CopyIcon, DownloadIcon, LinkIcon, QrCodeIcon } from "lucide-react"
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
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import type { FormIntakeLinkRead, TrackingMode } from "@/lib/api/forms"

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
}: ShareApplicationDialogProps) {
    const [embedEnabled, setEmbedEnabled] = React.useState(false)
    const [originText, setOriginText] = React.useState("")
    const [trackingMode, setTrackingMode] = React.useState<TrackingMode>("privacy_safe_lead")
    const [consentText, setConsentText] = React.useState("")

    React.useEffect(() => {
        if (!selectedQrLink) return
        setEmbedEnabled(selectedQrLink.embed_enabled)
        setOriginText((selectedQrLink.allowed_embed_origins || []).join("\n"))
        setTrackingMode(selectedQrLink.tracking_mode || "privacy_safe_lead")
        setConsentText(selectedQrLink.consent_text || "")
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
        const allowedOrigins = originText
            .split(/[\n,]+/)
            .map((value) => value.trim())
            .filter(Boolean)
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
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Share Application Intake</AlertDialogTitle>
                    <AlertDialogDescription>
                        Choose how you want to distribute this published application form.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <Tabs defaultValue="hosted" className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="hosted">Hosted Link</TabsTrigger>
                        <TabsTrigger value="qr">QR Code</TabsTrigger>
                        <TabsTrigger value="embed">Embed</TabsTrigger>
                    </TabsList>
                    <TabsContent value="hosted" className="mt-4">
                        {selectedQrLink?.intake_url ? (
                            <div className="space-y-2 rounded-md border border-stone-200 bg-stone-50 p-3 text-xs text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                                <div className="font-medium text-stone-900 dark:text-stone-100">
                                    {selectedQrLink.event_name || selectedQrLink.campaign_name || "Shared intake link"}
                                </div>
                                <div className="break-all">{selectedQrLink.intake_url}</div>
                            </div>
                        ) : (
                            <p className="text-sm text-stone-500">No shared intake link is available yet.</p>
                        )}
                    </TabsContent>
                    <TabsContent value="qr" className="mt-4">
                        <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-sm text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                            Use the QR download actions below for the selected hosted link.
                        </div>
                    </TabsContent>
                    <TabsContent value="embed" className="mt-4 space-y-3">
                        {selectedQrLink ? (
                            <>
                                <div className="space-y-4 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                                    <div className="flex items-center justify-between gap-3">
                                        <Label htmlFor="sf-embed-enabled" className="text-sm font-medium">
                                            Enable iframe embed
                                        </Label>
                                        <Switch
                                            id="sf-embed-enabled"
                                            checked={embedEnabled}
                                            onCheckedChange={setEmbedEnabled}
                                            disabled={isEmbedSettingsPending}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="sf-embed-origins">Allowed origins</Label>
                                        <Textarea
                                            id="sf-embed-origins"
                                            value={originText}
                                            onChange={(event) => setOriginText(event.target.value)}
                                            placeholder="https://www.clientsite.com"
                                            rows={3}
                                            disabled={isEmbedSettingsPending}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="sf-embed-tracking">Tracking mode</Label>
                                        <Select
                                            value={trackingMode}
                                            onValueChange={(value) => setTrackingMode(value as TrackingMode)}
                                            disabled={isEmbedSettingsPending}
                                        >
                                            <SelectTrigger id="sf-embed-tracking">
                                                <SelectValue>
                                                    {(value: string | null) =>
                                                        getTrackingModeLabel((value as TrackingMode | null) ?? "privacy_safe_lead")
                                                    }
                                                </SelectValue>
                                            </SelectTrigger>
                                            <SelectContent>
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
                                            onChange={(event) => setConsentText(event.target.value)}
                                            placeholder="I agree to be contacted about my inquiry."
                                            rows={3}
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
                                <div className="rounded-md border border-stone-200 bg-stone-50 p-3 text-xs text-stone-600 dark:border-stone-800 dark:bg-stone-900/40">
                                    <div className="mb-2 flex items-center gap-2 font-medium text-stone-900 dark:text-stone-100">
                                        <Code2Icon className="size-4" />
                                        Website embed
                                    </div>
                                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all rounded border border-stone-200 bg-white p-3 font-mono text-[11px] leading-5 dark:border-stone-800 dark:bg-stone-950">
                                        {embedSnippet}
                                    </pre>
                                </div>
                                {!selectedQrLink.embed_enabled ? (
                                    <p className="text-xs text-amber-700">
                                        Embedding is disabled for this link until allowed origins are configured.
                                    </p>
                                ) : selectedQrLink.allowed_embed_origins.length > 0 ? (
                                    <p className="text-xs text-stone-500">
                                        Allowed origins: {selectedQrLink.allowed_embed_origins.join(", ")}
                                    </p>
                                ) : null}
                                <Button type="button" variant="outline" onClick={copyEmbedSnippet}>
                                    <CopyIcon className="mr-2 size-4" />
                                    Copy Embed
                                </Button>
                            </>
                        ) : (
                            <p className="text-sm text-stone-500">No shared intake link is available yet.</p>
                        )}
                    </TabsContent>
                </Tabs>
                <AlertDialogFooter>
                    <AlertDialogCancel>Close</AlertDialogCancel>
                    <Button
                        type="button"
                        variant="outline"
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
        internal_only: "Internal Only",
        disabled: "Disabled",
        advanced: "Advanced",
    }
    return labels[value]
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
