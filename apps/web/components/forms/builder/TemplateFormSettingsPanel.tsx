"use client"

import NextImage from "next/image"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

type TemplateFormSettingsPanelProps = {
    formName: string
    formDescription: string
    publicEyebrow: string
    publicTitle: string
    publicSubtitle: string
    logoUrl: string
    resolvedLogoUrl: string
    privacyNotice: string
    maxFileSizeMb: number
    maxFileCount: number
    allowedMimeTypesText: string
    onFormNameChange: (value: string) => void
    onFormDescriptionChange: (value: string) => void
    onPublicEyebrowChange: (value: string) => void
    onPublicTitleChange: (value: string) => void
    onPublicSubtitleChange: (value: string) => void
    onLogoUrlChange: (value: string) => void
    onPrivacyNoticeChange: (value: string) => void
    onMaxFileSizeMbChange: (value: number) => void
    onMaxFileCountChange: (value: number) => void
    onAllowedMimeTypesTextChange: (value: string) => void
}

export function TemplateFormSettingsPanel({
    formName,
    formDescription,
    publicEyebrow,
    publicTitle,
    publicSubtitle,
    logoUrl,
    resolvedLogoUrl,
    privacyNotice,
    maxFileSizeMb,
    maxFileCount,
    allowedMimeTypesText,
    onFormNameChange,
    onFormDescriptionChange,
    onPublicEyebrowChange,
    onPublicTitleChange,
    onPublicSubtitleChange,
    onLogoUrlChange,
    onPrivacyNoticeChange,
    onMaxFileSizeMbChange,
    onMaxFileCountChange,
    onAllowedMimeTypesTextChange,
}: TemplateFormSettingsPanelProps) {
    return (
        <div className="mx-auto max-w-5xl">
            <div className="rounded-[28px] border border-border/80 bg-card p-6 shadow-sm sm:p-8">
                <div className="mb-8 flex flex-wrap items-start justify-between gap-3 border-b border-border/70 pb-6">
                    <div className="space-y-1">
                        <h2 className="text-xl font-semibold tracking-tight">Form Settings</h2>
                        <p className="max-w-2xl text-sm text-muted-foreground">
                            Configure the shared template identity, privacy copy, and upload defaults outside the field editor.
                        </p>
                    </div>
                    <Badge variant="outline">Template-level</Badge>
                </div>

                <div className="space-y-6">
                    <div className="space-y-2">
                        <Label htmlFor="settings-form-name">Internal template name</Label>
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
                            placeholder="Describe the purpose of this template for your team"
                        />
                    </div>

                    <div className="space-y-4 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <h4 className="text-sm font-semibold">Public Header</h4>
                                <p className="text-xs text-stone-500">
                                    These lines appear at the top of forms created from this template.
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

                    <div className="space-y-2">
                        <Label htmlFor="settings-logo-url">Logo URL</Label>
                        <Input
                            id="settings-logo-url"
                            value={logoUrl}
                            onChange={(e) => onLogoUrlChange(e.target.value)}
                            placeholder="https://example.com/logo.png"
                        />
                        {logoUrl && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => onLogoUrlChange("")}
                            >
                                Remove
                            </Button>
                        )}
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
                                        onMaxFileSizeMbChange(
                                            Number.parseFloat(e.target.value || "0") || 1,
                                        )
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
                                        onMaxFileCountChange(
                                            Number.parseInt(e.target.value || "0", 10) || 0,
                                        )
                                    }
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="settings-allowed-mime-types">
                                Allowed MIME types (comma separated)
                            </Label>
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
                </div>
            </div>
        </div>
    )
}
