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
    event_intake: "Event Intake",
    other: "Other",
}

type AutomationFormSettingsPanelProps = {
    formName: string
    formDescription: string
    formPurpose: FormPurpose
    publicTitle: string
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
    onPublicTitleChange: (value: string) => void
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

export function AutomationFormSettingsPanel({
    formName,
    formDescription,
    formPurpose,
    publicTitle,
    logoUrl,
    resolvedLogoUrl,
    privacyNotice,
    defaultTemplateId,
    emailTemplates,
    maxFileSizeMb,
    maxFileCount,
    allowedMimeTypesText,
    useOrgLogo,
    orgLogoAvailable,
    logoInputRef,
    uploadLogoPending,
    isDefaultSurrogateApplication,
    setDefaultSurrogateApplicationPending,
    isPublished,
    selectedQrLink,
    onFormNameChange,
    onFormDescriptionChange,
    onFormPurposeChange,
    onPublicTitleChange,
    onLogoUrlChange,
    onPrivacyNoticeChange,
    onDefaultTemplateChange,
    onUseOrgLogoChange,
    onLogoUploadClick,
    onLogoFileChange,
    onSetDefaultSurrogateApplication,
    onOpenSharePrompt,
    onCopySharedLink,
    onDownloadQrSvg,
    onDownloadQrPng,
    onMaxFileSizeMbChange,
    onMaxFileCountChange,
    onAllowedMimeTypesTextChange,
}: AutomationFormSettingsPanelProps) {
    const templateNameById = new Map(emailTemplates.map((template) => [template.id, template.name] as const))

    return (
        <div className="mx-auto max-w-5xl">
            <div className="rounded-[28px] border border-border/80 bg-card p-6 shadow-sm sm:p-8">
                <div className="mb-8 flex flex-wrap items-start justify-between gap-3 border-b border-border/70 pb-6">
                    <div className="space-y-1">
                        <h2 className="text-xl font-semibold tracking-tight">Form Settings</h2>
                        <p className="max-w-2xl text-sm text-muted-foreground">
                            Manage your form identity, delivery defaults, sharing, and upload rules in one place.
                        </p>
                    </div>
                    <Badge variant="outline">Form-level</Badge>
                </div>

                <div className="space-y-6">
                    <div className="space-y-2">
                        <Label htmlFor="settings-form-name">Form Name</Label>
                        <Input
                            id="settings-form-name"
                            value={formName}
                            onChange={(e) => onFormNameChange(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="settings-form-description">Description</Label>
                        <Textarea
                            id="settings-form-description"
                            value={formDescription}
                            onChange={(e) => onFormDescriptionChange(e.target.value)}
                            rows={3}
                            placeholder="Describe the purpose of this form"
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
                                <SelectItem value="event_intake">Event Intake</SelectItem>
                                <SelectItem value="other">Other</SelectItem>
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-stone-500">
                            Dedicated case sends default to forms with purpose
                            <code className="ml-1">surrogate_application</code>.
                        </p>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="settings-public-title">Public Title</Label>
                        <Input
                            id="settings-public-title"
                            value={publicTitle}
                            onChange={(e) => onPublicTitleChange(e.target.value)}
                            placeholder="Business or program title shown to applicants"
                        />
                    </div>

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

                    <div className="space-y-4 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
                        <div className="flex items-center justify-between">
                            <h4 className="text-sm font-semibold">Dedicated Delivery</h4>
                            <div className="flex items-center gap-2">
                                {isDefaultSurrogateApplication && <Badge variant="secondary">Default</Badge>}
                                <Badge variant="outline">Per-surrogate</Badge>
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
                                One-click surrogate sends use this template by default.
                            </p>
                        </div>
                        <div className="space-y-2 rounded-md border border-stone-200 p-3 dark:border-stone-800">
                            <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                    <p className="text-sm font-medium">Default case-send form</p>
                                    {isDefaultSurrogateApplication && (
                                        <Badge variant="secondary" className="text-[11px]">
                                            Active
                                        </Badge>
                                    )}
                                </div>
                                <p className="text-xs text-stone-500">
                                    Exactly one published surrogate application form can be the default for case sends.
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
                            <p className="text-xs text-stone-500">Preparing shared link...</p>
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
                                Leave blank to allow any file types. Per-field uploads are still capped at 5 files.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
