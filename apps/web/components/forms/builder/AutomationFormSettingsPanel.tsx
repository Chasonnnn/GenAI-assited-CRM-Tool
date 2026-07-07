"use client"

import type { ChangeEvent, RefObject } from "react"
import NextImage from "next/image"
import { QRCodeSVG } from "qrcode.react"
import { CopyIcon, DownloadIcon, LinkIcon, Loader2Icon, QrCodeIcon } from "lucide-react"

import type { EmailTemplateListItem } from "@/lib/api/email-templates"
import type { FormIntakeLinkRead, FormPurpose } from "@/lib/api/forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"

const FORM_PURPOSE_LABELS: Record<FormPurpose, string> = {
    surrogate_application: "Surrogate Application",
    lead_capture: "Lead Capture",
    event_intake: "Event Intake",
    other: "Other",
}

type AutomationFormSettingsPanelProps = {
    formName: string
    formDescription: string
    formPurpose: FormPurpose
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
    logoUrl: string
    resolvedLogoUrl: string
    privacyNotice: string
    defaultTemplateId: string
    emailTemplates: EmailTemplateListItem[]
    maxFileSizeMb: number
    maxFileCount: number
    allowedMimeTypesText: string
    useOrgLogo: boolean
    orgLogoAvailable: boolean
    logoInputRef: RefObject<HTMLInputElement | null>
    uploadLogoPending: boolean
    isDefaultSurrogateApplication: boolean
    setDefaultSurrogateApplicationPending: boolean
    isPublished: boolean
    selectedQrLink: FormIntakeLinkRead | null
    onFormNameChange: (value: string) => void
    onFormDescriptionChange: (value: string) => void
    onFormPurposeChange: (value: FormPurpose) => void
    onPublicEyebrowChange: (value: string) => void
    onPublicTitleChange: (value: string) => void
    onPublicSubtitleChange: (value: string) => void
    onLogoUrlChange: (value: string) => void
    onPrivacyNoticeChange: (value: string) => void
    onDefaultTemplateChange: (value: string | null) => void
    onUseOrgLogoChange: (checked: boolean) => void
    onLogoUploadClick: () => void
    onLogoFileChange: (event: ChangeEvent<HTMLInputElement>) => Promise<void> | void
    onSetDefaultSurrogateApplication: () => Promise<void> | void
    onOpenSharePrompt: () => void
    onCopySharedLink: (link: FormIntakeLinkRead) => Promise<void> | void
    onDownloadQrSvg: () => void
    onDownloadQrPng: () => Promise<void> | void
    onMaxFileSizeMbChange: (value: number) => void
    onMaxFileCountChange: (value: number) => void
    onAllowedMimeTypesTextChange: (value: string) => void
}

function SettingsPanelHeader() {
    return (
        <div className="mb-8 flex flex-wrap items-start justify-between gap-3 border-b border-border/70 pb-6">
            <div className="space-y-1">
                <h2 className="text-xl font-semibold tracking-tight">Form Settings</h2>
                <p className="max-w-2xl text-sm text-muted-foreground">
                    Manage your form identity, delivery defaults, sharing, and upload rules in one place.
                </p>
            </div>
            <Badge variant="outline">Form-level</Badge>
        </div>
    )
}

function FormIdentitySection({ settings }: { settings: AutomationFormSettingsPanelProps }) {
    const {
        formName,
        formDescription,
        formPurpose,
        privacyNotice,
        onFormNameChange,
        onFormDescriptionChange,
        onFormPurposeChange,
        onPrivacyNoticeChange,
    } = settings

    return (
        <>
            <div className="space-y-2">
                <Label htmlFor="settings-form-name">Internal form name</Label>
                <Input
                    id="settings-form-name"
                    value={formName}
                    onChange={(e) => onFormNameChange(e.target.value)}
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="settings-form-description">Internal description</Label>
                <Textarea
                    id="settings-form-description"
                    value={formDescription}
                    onChange={(e) => onFormDescriptionChange(e.target.value)}
                    rows={3}
                    placeholder="Describe the purpose of this form for your team"
                />
            </div>

            <div className="space-y-2">
                <Label htmlFor="settings-form-purpose">Form Purpose</Label>
                <Select
                    value={formPurpose}
                    onValueChange={(value) => onFormPurposeChange(value as FormPurpose)}
                >
                    <SelectTrigger id="settings-form-purpose">
                        <SelectValue placeholder="Select purpose">
                            {(value: string | null) =>
                                FORM_PURPOSE_LABELS[(value as FormPurpose | null) ?? "surrogate_application"] ??
                                value ??
                                "Select purpose"
                            }
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="surrogate_application">Surrogate Application</SelectItem>
                        <SelectItem value="lead_capture">Lead Capture</SelectItem>
                        <SelectItem value="event_intake">Event Intake</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                </Select>
                <p className="text-xs text-stone-500">
                    Use lead capture for embeddable contact forms and surrogate application for full intake.
                </p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="settings-privacy-notice">Privacy Notice</Label>
                <Textarea
                    id="settings-privacy-notice"
                    value={privacyNotice}
                    onChange={(e) => onPrivacyNoticeChange(e.target.value)}
                    rows={4}
                    placeholder="Describe how applicant data is protected or paste a privacy policy URL"
                />
            </div>
        </>
    )
}

function LogoSettingsSection({ settings }: { settings: AutomationFormSettingsPanelProps }) {
    const {
        logoUrl,
        resolvedLogoUrl,
        useOrgLogo,
        orgLogoAvailable,
        logoInputRef,
        uploadLogoPending,
        onLogoUrlChange,
        onUseOrgLogoChange,
        onLogoUploadClick,
        onLogoFileChange,
    } = settings

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <Label htmlFor="settings-logo-url">Logo URL</Label>
                <div className="flex items-center gap-2 text-xs text-stone-500">
                    <Switch
                        checked={useOrgLogo}
                        onCheckedChange={onUseOrgLogoChange}
                        disabled={!orgLogoAvailable}
                    />
                    <span>Use org logo</span>
                </div>
            </div>
            <Input
                id="settings-logo-url"
                value={logoUrl}
                onChange={(e) => onLogoUrlChange(e.target.value)}
                placeholder="https://example.com/logo.png"
                disabled={useOrgLogo}
            />
            {!orgLogoAvailable && (
                <p className="text-xs text-stone-500">
                    Add an organization logo in Settings to enable this option.
                </p>
            )}
            <div className="flex items-center gap-2">
                <input
                    id="form-logo-upload"
                    name="form_logo_upload"
                    ref={logoInputRef}
                    type="file"
                    accept="image/png,image/jpeg"
                    aria-label="Upload form logo"
                    className="hidden"
                    onChange={onLogoFileChange}
                />
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onLogoUploadClick}
                    disabled={uploadLogoPending || useOrgLogo}
                >
                    {uploadLogoPending && <Loader2Icon className="mr-2 size-4 animate-spin" />}
                    Upload Logo
                </Button>
                {logoUrl && !useOrgLogo && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onLogoUrlChange("")}
                    >
                        Remove
                    </Button>
                )}
            </div>
            {logoUrl && (
                <div className="rounded-lg border border-stone-200 bg-stone-50 p-3">
                    <NextImage
                        src={resolvedLogoUrl}
                        alt="Form logo preview"
                        width={224}
                        height={56}
                        unoptimized
                        className="h-14 w-auto rounded-md object-contain"
                    />
                </div>
            )}
        </div>
    )
}

function SharedDeliverySection({
    settings,
    templateNameById,
}: {
    settings: AutomationFormSettingsPanelProps
    templateNameById: Map<string, string>
}) {
    const {
        defaultTemplateId,
        emailTemplates,
        formPurpose,
        isDefaultSurrogateApplication,
        isPublished,
        setDefaultSurrogateApplicationPending,
        onDefaultTemplateChange,
        onSetDefaultSurrogateApplication,
    } = settings

    return (
        <div className="space-y-4 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
            <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Shared Delivery</h4>
                <div className="flex items-center gap-2">
                    {isDefaultSurrogateApplication && <Badge variant="secondary">Default</Badge>}
                    <Badge variant="outline">Reusable Link</Badge>
                </div>
            </div>
            <div className="space-y-2">
                <Label htmlFor="settings-default-template">Default application email template</Label>
                <Select
                    value={defaultTemplateId || "none"}
                    onValueChange={(value) => onDefaultTemplateChange(value === "none" ? "" : value)}
                >
                    <SelectTrigger id="settings-default-template">
                        <SelectValue placeholder="Select template">
                            {(value: string | null) =>
                                value === "none"
                                    ? "No default template"
                                    : templateNameById.get(value ?? "") ?? value ?? "Select template"
                            }
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="none">No default template</SelectItem>
                        {emailTemplates.map((template) => (
                            <SelectItem key={template.id} value={template.id}>
                                {template.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p className="text-xs text-stone-500">
                    Shared intake email sends use this template by default.
                </p>
            </div>
            <div className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <p className="text-sm font-medium">Default shared-send form</p>
                        {isDefaultSurrogateApplication && (
                            <Badge variant="secondary" className="text-[11px]">
                                Active
                            </Badge>
                        )}
                    </div>
                    <p className="text-xs text-stone-500">
                        Exactly one published surrogate application form can be the default for shared intake sends.
                    </p>
                </div>
                <Button
                    type="button"
                    variant={isDefaultSurrogateApplication ? "secondary" : "outline"}
                    size="sm"
                    className="w-full justify-center sm:w-auto"
                    onClick={onSetDefaultSurrogateApplication}
                    disabled={
                        isDefaultSurrogateApplication ||
                        setDefaultSurrogateApplicationPending ||
                        !isPublished ||
                        formPurpose !== "surrogate_application"
                    }
                >
                    {setDefaultSurrogateApplicationPending && (
                        <Loader2Icon className="mr-2 size-3 animate-spin" />
                    )}
                    {isDefaultSurrogateApplication ? "Default Active" : "Set as Default"}
                </Button>
                {formPurpose !== "surrogate_application" && (
                    <p className="text-xs text-amber-600">
                        Change purpose to <code>surrogate_application</code> to set as default.
                    </p>
                )}
                {!isPublished && (
                    <p className="text-xs text-amber-600">
                        Publish this form before setting it as default.
                    </p>
                )}
            </div>
        </div>
    )
}

function PublicHeaderSection({ settings }: { settings: AutomationFormSettingsPanelProps }) {
    const {
        publicEyebrow,
        publicTitle,
        publicSubtitle,
        onPublicEyebrowChange,
        onPublicTitleChange,
        onPublicSubtitleChange,
    } = settings

    return (
        <div className="space-y-4 rounded-lg border border-stone-200 bg-stone-50/70 p-4 dark:border-stone-800 dark:bg-stone-950/40">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h4 className="text-sm font-semibold">Public Form Title & Subtitle</h4>
                    <p className="text-xs text-stone-500">
                        Edit the header shown on the shared link, QR page, and website embed.
                    </p>
                </div>
                <Badge variant="outline">Applicant-facing</Badge>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                    <Label htmlFor="settings-public-eyebrow">Eyebrow</Label>
                    <Input
                        id="settings-public-eyebrow"
                        value={publicEyebrow}
                        onChange={(e) => onPublicEyebrowChange(e.target.value)}
                        placeholder="PRE-QUESTIONNAIRE"
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="settings-public-title">Title</Label>
                    <Input
                        id="settings-public-title"
                        value={publicTitle}
                        onChange={(e) => onPublicTitleChange(e.target.value)}
                        placeholder="EWI pre-questionnaire"
                    />
                </div>
            </div>
            <div className="space-y-2">
                <Label htmlFor="settings-public-subtitle">Subtitle</Label>
                <Textarea
                    id="settings-public-subtitle"
                    value={publicSubtitle}
                    onChange={(e) => onPublicSubtitleChange(e.target.value)}
                    rows={3}
                    placeholder="Answer a few quick questions so our team can review basic eligibility and follow up."
                />
            </div>
        </div>
    )
}

function ShareQrSection({ settings }: { settings: AutomationFormSettingsPanelProps }) {
    const {
        isPublished,
        selectedQrLink,
        onOpenSharePrompt,
        onCopySharedLink,
        onDownloadQrSvg,
        onDownloadQrPng,
    } = settings

    return (
        <div className="space-y-3 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold">
                    <QrCodeIcon className="size-4" />
                    Share & QR
                </div>
                <Badge variant="outline">Auto-generated</Badge>
            </div>
            <p className="text-xs text-stone-500">
                Publishing creates a primary shared application link automatically. Share it directly or download QR for events.
            </p>

            {!isPublished ? (
                <p className="text-xs text-amber-600">
                    Publish this form to generate the share link and QR code.
                </p>
            ) : !selectedQrLink?.intake_url ? (
                <p className="text-xs text-stone-500">Preparing shared link…</p>
            ) : (
                <div className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                    <div className="break-all text-xs text-stone-600">{selectedQrLink.intake_url}</div>
                    <div className="flex flex-wrap gap-2">
                        <Button type="button" size="sm" variant="outline" onClick={onOpenSharePrompt}>
                            <LinkIcon className="mr-2 size-3" />
                            Share
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => onCopySharedLink(selectedQrLink)}
                        >
                            <CopyIcon className="mr-2 size-3" />
                            Copy URL
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={onDownloadQrSvg}>
                            <DownloadIcon className="mr-2 size-3" />
                            Download SVG
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => void onDownloadQrPng()}>
                            <DownloadIcon className="mr-2 size-3" />
                            Download PNG
                        </Button>
                    </div>
                    <div className="inline-flex rounded-md border border-stone-200 bg-white p-2">
                        <div id="shared-intake-qr">
                            <QRCodeSVG value={selectedQrLink.intake_url} size={120} includeMargin />
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

function UploadRulesSection({ settings }: { settings: AutomationFormSettingsPanelProps }) {
    const {
        maxFileSizeMb,
        maxFileCount,
        allowedMimeTypesText,
        onMaxFileSizeMbChange,
        onMaxFileCountChange,
        onAllowedMimeTypesTextChange,
    } = settings

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold">Upload Rules</h4>
                <Badge variant="outline">Files</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2">
                <div className="space-y-2">
                    <Label htmlFor="settings-max-file-size">Max file size (MB)</Label>
                    <Input
                        id="settings-max-file-size"
                        inputMode="numeric"
                        value={maxFileSizeMb}
                        onChange={(e) =>
                            onMaxFileSizeMbChange(Number.parseFloat(e.target.value || "0") || 1)
                        }
                    />
                </div>
                <div className="space-y-2">
                    <Label htmlFor="settings-max-file-count">Max files total</Label>
                    <Input
                        id="settings-max-file-count"
                        inputMode="numeric"
                        value={maxFileCount}
                        onChange={(e) =>
                            onMaxFileCountChange(Number.parseInt(e.target.value || "0", 10) || 0)
                        }
                    />
                </div>
            </div>
            <div className="space-y-2">
                <Label htmlFor="settings-allowed-mime-types">Allowed MIME types (comma separated)</Label>
                <Input
                    id="settings-allowed-mime-types"
                    value={allowedMimeTypesText}
                    onChange={(e) => onAllowedMimeTypesTextChange(e.target.value)}
                    placeholder="image/*,application/pdf"
                />
                <p className="text-xs text-stone-500">
                    Leave blank to use the platform safe file allowlist. Per-field uploads are still capped at 5 files.
                </p>
            </div>
        </div>
    )
}

export function AutomationFormSettingsPanel(settings: AutomationFormSettingsPanelProps) {
    const templateNameById = new Map(settings.emailTemplates.map((template) => [template.id, template.name] as const))

    return (
        <div className="mx-auto max-w-5xl">
            <div className="rounded-[28px] border border-border/80 bg-card p-6 shadow-sm sm:p-8">
                <SettingsPanelHeader />
                <div className="space-y-6">
                    <FormIdentitySection settings={settings} />
                    <LogoSettingsSection settings={settings} />
                    <SharedDeliverySection settings={settings} templateNameById={templateNameById} />
                    <PublicHeaderSection settings={settings} />
                    <ShareQrSection settings={settings} />
                    <UploadRulesSection settings={settings} />
                </div>
            </div>
        </div>
    )
}
