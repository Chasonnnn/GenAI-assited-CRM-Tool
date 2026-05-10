"use client"

import { useEffect, useMemo, useState } from "react"
import {
    AlertCircleIcon,
    CheckIcon,
    ImageIcon,
    RefreshCwIcon,
    SaveIcon,
    Settings2Icon,
    SparklesIcon,
} from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    Card,
    CardAction,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import {
    Empty,
    EmptyContent,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "@/components/ui/empty"
import {
    Field,
    FieldDescription,
    FieldError,
    FieldGroup,
    FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth-context"
import type {
    AIStudioDraft,
    AIStudioFormat,
    AIStudioGenerateRequest,
    AIStudioImageQuality,
    AIStudioImageSize,
    AIStudioPlatform,
    AIStudioSettingsUpdate,
    AIStudioTone,
} from "@/lib/api/ai-studio"
import {
    useAIStudioDrafts,
    useAIStudioSettings,
    useGenerateAIStudioDraft,
    useSaveAIStudioDraft,
    useUpdateAIStudioSettings,
} from "@/lib/hooks/use-ai-studio"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { cn } from "@/lib/utils"

const platformOptions: Array<{ value: AIStudioPlatform; label: string }> = [
    { value: "instagram", label: "Instagram" },
    { value: "facebook", label: "Facebook" },
    { value: "linkedin", label: "LinkedIn" },
    { value: "x", label: "X" },
    { value: "tiktok", label: "TikTok" },
]

const formatOptions: Array<{ value: AIStudioFormat; label: string }> = [
    { value: "feed", label: "Feed" },
    { value: "story", label: "Story" },
    { value: "reel", label: "Reel" },
    { value: "carousel", label: "Carousel" },
    { value: "ad", label: "Ad" },
]

const toneOptions: Array<{ value: AIStudioTone; label: string }> = [
    { value: "warm", label: "Warm" },
    { value: "professional", label: "Professional" },
    { value: "bold", label: "Bold" },
    { value: "calm", label: "Calm" },
    { value: "educational", label: "Educational" },
]

const imageSizeOptions: Array<{ value: AIStudioImageSize; label: string }> = [
    { value: "auto", label: "Auto" },
    { value: "1024x1024", label: "Square (1024x1024)" },
    { value: "1024x1536", label: "Portrait (1024x1536)" },
    { value: "1536x1024", label: "Landscape (1536x1024)" },
    { value: "2560x1440", label: "2K (2560x1440)" },
    { value: "3840x2160", label: "4K (3840x2160)" },
]

const imageQualityOptions: Array<{ value: AIStudioImageQuality; label: string }> = [
    { value: "auto", label: "Auto" },
    { value: "high", label: "High" },
    { value: "medium", label: "Medium" },
    { value: "low", label: "Low" },
]

const platformLabels = Object.fromEntries(
    platformOptions.map((option) => [option.value, option.label])
) as Record<AIStudioPlatform, string>

const formatLabels = Object.fromEntries(
    formatOptions.map((option) => [option.value, option.label])
) as Record<AIStudioFormat, string>

const toneLabels = Object.fromEntries(
    toneOptions.map((option) => [option.value, option.label])
) as Record<AIStudioTone, string>

const imageSizeLabels = Object.fromEntries(
    imageSizeOptions.map((option) => [option.value, option.label])
) as Record<AIStudioImageSize, string>

const imageQualityLabels = Object.fromEntries(
    imageQualityOptions.map((option) => [option.value, option.label])
) as Record<AIStudioImageQuality, string>

function getErrorMessage(error: unknown): string {
    return error instanceof Error ? error.message : "Something went wrong."
}

function formatDraftDate(value: string) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    }).format(date)
}

function DraftPreview({
    draft,
    isSaving,
    onSave,
    onRegenerate,
}: {
    draft: AIStudioDraft | null
    isSaving: boolean
    onSave: () => void
    onRegenerate: () => void
}) {
    if (!draft) {
        return (
            <Empty className="min-h-[520px] border bg-card">
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <ImageIcon />
                    </EmptyMedia>
                    <EmptyTitle>Draft preview</EmptyTitle>
                    <EmptyDescription>
                        Generated caption, hashtags, and image will appear here for review.
                    </EmptyDescription>
                </EmptyHeader>
            </Empty>
        )
    }

    return (
        <Card className="min-h-[520px]">
            <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={draft.status === "saved" ? "default" : "secondary"}>
                        {draft.status === "saved" ? "Saved" : "Preview"}
                    </Badge>
                    <Badge variant="outline">{platformLabels[draft.platform]}</Badge>
                    <Badge variant="outline">{formatLabels[draft.format]}</Badge>
                    <Badge variant="outline">{imageSizeLabels[draft.image_size]}</Badge>
                    <Badge variant="outline">{imageQualityLabels[draft.image_quality]}</Badge>
                    <Badge variant="outline">Draft only</Badge>
                </div>
                <CardTitle>Generated draft</CardTitle>
                <CardDescription>
                    {draft.reasoning_model} copy with {draft.image_model} image generation.
                </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
                {draft.image_url ? (
                    <div className="overflow-hidden rounded-lg border bg-muted">
                        <img
                            alt="Generated social media visual"
                            src={draft.image_url}
                            className="aspect-square w-full object-cover"
                        />
                    </div>
                ) : (
                    <div className="flex aspect-square items-center justify-center rounded-lg border bg-muted text-muted-foreground">
                        <ImageIcon />
                    </div>
                )}

                <div className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-4">
                    <p className="whitespace-pre-wrap text-sm leading-6">{draft.caption}</p>
                    {draft.hashtags.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {draft.hashtags.map((tag) => (
                                <Badge key={tag} variant="secondary">
                                    {tag}
                                </Badge>
                            ))}
                        </div>
                    )}
                </div>

                <div className="rounded-lg border bg-background p-4">
                    <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                        Image prompt
                    </div>
                    <p className="text-sm leading-6 text-muted-foreground">{draft.image_prompt}</p>
                </div>
            </CardContent>
            <CardFooter className="flex-wrap gap-2">
                <Button
                    type="button"
                    onClick={onSave}
                    disabled={draft.status === "saved" || isSaving}
                >
                    {isSaving ? <Spinner data-icon="inline-start" /> : <SaveIcon data-icon="inline-start" />}
                    Save draft
                </Button>
                <Button type="button" variant="outline" onClick={onRegenerate}>
                    <RefreshCwIcon data-icon="inline-start" />
                    Regenerate
                </Button>
            </CardFooter>
        </Card>
    )
}

function SavedDraftsPanel({
    drafts,
    isLoading,
    onSelect,
}: {
    drafts: AIStudioDraft[]
    isLoading: boolean
    onSelect: (draft: AIStudioDraft) => void
}) {
    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>Saved drafts</CardTitle>
                    <CardDescription>Recently saved AI Studio work.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Saved drafts</CardTitle>
                <CardDescription>Recently saved AI Studio work.</CardDescription>
            </CardHeader>
            <CardContent>
                {drafts.length === 0 ? (
                    <Empty className="border bg-muted/20 p-6">
                        <EmptyContent>
                            <EmptyTitle>No saved drafts</EmptyTitle>
                            <EmptyDescription>Saved drafts appear here after review.</EmptyDescription>
                        </EmptyContent>
                    </Empty>
                ) : (
                    <div className="flex flex-col gap-2">
                        {drafts.map((draft) => (
                            <button
                                type="button"
                                key={draft.id}
                                onClick={() => onSelect(draft)}
                                className="rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                                <div className="flex items-center justify-between gap-3">
                                    <span className="truncate text-sm font-medium">
                                        {draft.brief}
                                    </span>
                                    <span className="shrink-0 text-xs text-muted-foreground">
                                        {formatDraftDate(draft.created_at)}
                                    </span>
                                </div>
                                <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                                    {draft.caption}
                                </p>
                            </button>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default function AIStudioPage() {
    const { user } = useAuth()
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const settingsQuery = useAIStudioSettings()
    const draftsQuery = useAIStudioDrafts()
    const updateSettings = useUpdateAIStudioSettings()
    const generateDraft = useGenerateAIStudioDraft()
    const saveDraft = useSaveAIStudioDraft()

    const [brief, setBrief] = useState("")
    const [platform, setPlatform] = useState<AIStudioPlatform>("instagram")
    const [format, setFormat] = useState<AIStudioFormat>("feed")
    const [tone, setTone] = useState<AIStudioTone>("warm")
    const [audience, setAudience] = useState("")
    const [imageSize, setImageSize] = useState<AIStudioImageSize>("auto")
    const [imageQuality, setImageQuality] = useState<AIStudioImageQuality>("auto")
    const [previewDraft, setPreviewDraft] = useState<AIStudioDraft | null>(null)
    const [errorMessage, setErrorMessage] = useState("")
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [settingsApiKey, setSettingsApiKey] = useState("")
    const [agentsMd, setAgentsMd] = useState("")
    const [skillsMd, setSkillsMd] = useState("")
    const [settingsSaved, setSettingsSaved] = useState(false)

    const permissionSet = useMemo(
        () => new Set(permissionsQuery.data?.permissions ?? []),
        [permissionsQuery.data?.permissions]
    )
    const isDeveloper = user?.role === "developer"
    const canUseAI = isDeveloper || permissionSet.has("use_ai_assistant")
    const canManageSettings = isDeveloper || permissionSet.has("manage_ai_settings")
    const aiAvailable = Boolean(user?.ai_enabled && canUseAI)
    const settings = settingsQuery.data

    useEffect(() => {
        if (!settingsOpen || !settings) return
        setSettingsApiKey("")
        setAgentsMd(settings.agents_md)
        setSkillsMd(settings.skills_md)
        setSettingsSaved(false)
    }, [settingsOpen, settings])

    const canGenerate = Boolean(
        aiAvailable &&
            settings?.has_api_key &&
            brief.trim().length >= 8 &&
            !generateDraft.isPending
    )

    const generatePayload = (): AIStudioGenerateRequest => ({
        brief: brief.trim(),
        platform,
        format,
        tone,
        audience: audience.trim(),
        image_size: imageSize,
        image_quality: imageQuality,
    })

    const handleGenerate = async () => {
        if (!canGenerate) return
        setErrorMessage("")
        try {
            const draft = await generateDraft.mutateAsync(generatePayload())
            setPreviewDraft(draft)
        } catch (error) {
            setErrorMessage(getErrorMessage(error))
        }
    }

    const handleSaveDraft = async () => {
        if (!previewDraft) return
        setErrorMessage("")
        try {
            const saved = await saveDraft.mutateAsync(previewDraft.id)
            setPreviewDraft(saved)
        } catch (error) {
            setErrorMessage(getErrorMessage(error))
        }
    }

    const handleSaveSettings = async () => {
        const payload: AIStudioSettingsUpdate = {
            agents_md: agentsMd,
            skills_md: skillsMd,
        }
        if (settingsApiKey.trim()) {
            payload.api_key = settingsApiKey.trim()
        }
        try {
            await updateSettings.mutateAsync(payload)
            setSettingsSaved(true)
            setSettingsApiKey("")
            setSettingsOpen(false)
        } catch (error) {
            setErrorMessage(getErrorMessage(error))
        }
    }

    const savedDrafts = draftsQuery.data?.items ?? []

    return (
        <div className="h-full overflow-y-auto bg-muted/20">
            <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex max-w-3xl flex-col gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                            <h1 className="text-2xl font-semibold tracking-tight">
                                AI Studio Preview
                            </h1>
                            <Badge variant="outline">Balanced</Badge>
                        </div>
                        <p className="text-sm leading-6 text-muted-foreground">
                            Create review-ready social copy and visuals. Nothing posts directly.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">Copy: gpt-5.5</Badge>
                        <Badge variant="outline">Image: gpt-image-2</Badge>
                        {canManageSettings && (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setSettingsOpen(true)}
                            >
                                <Settings2Icon data-icon="inline-start" />
                                Studio settings
                            </Button>
                        )}
                    </div>
                </div>

                {!aiAvailable && (
                    <Alert variant="destructive">
                        <AlertCircleIcon />
                        <AlertTitle>AI Studio is unavailable</AlertTitle>
                        <AlertDescription>
                            Your organization or role does not currently have AI access.
                        </AlertDescription>
                    </Alert>
                )}

                {settingsQuery.isError && (
                    <Alert variant="destructive">
                        <AlertCircleIcon />
                        <AlertTitle>Settings could not load</AlertTitle>
                        <AlertDescription>{getErrorMessage(settingsQuery.error)}</AlertDescription>
                    </Alert>
                )}

                {errorMessage && (
                    <Alert variant="destructive">
                        <AlertCircleIcon />
                        <AlertTitle>AI Studio needs attention</AlertTitle>
                        <AlertDescription>{errorMessage}</AlertDescription>
                    </Alert>
                )}

                {settingsQuery.isLoading ? (
                    <div className="grid gap-6 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
                        <Skeleton className="h-[620px] w-full" />
                        <Skeleton className="h-[620px] w-full" />
                    </div>
                ) : (
                    <div className="grid gap-6 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
                        <div className="flex flex-col gap-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Draft generator</CardTitle>
                                    <CardDescription>
                                        Start with a brief. AI Studio returns one caption and one
                                        image for review.
                                    </CardDescription>
                                    {!settings?.has_api_key && (
                                        <CardAction>
                                            <Badge variant="destructive">Key required</Badge>
                                        </CardAction>
                                    )}
                                </CardHeader>
                                <CardContent>
                                    <FieldGroup>
                                        <Field>
                                            <FieldLabel htmlFor="ai-studio-brief">Brief</FieldLabel>
                                            <Textarea
                                                id="ai-studio-brief"
                                                value={brief}
                                                onChange={(event) => setBrief(event.target.value)}
                                                placeholder="Launch announcement, patient education topic, campaign hook..."
                                                className="min-h-32 resize-none"
                                            />
                                            <FieldDescription>
                                                Include the goal, audience, offer, and any wording
                                                constraints.
                                            </FieldDescription>
                                        </Field>

                                        <div className="grid gap-4 sm:grid-cols-2">
                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-platform">
                                                    Platform
                                                </FieldLabel>
                                                <Select
                                                    value={platform}
                                                    onValueChange={(value) => {
                                                        if (value) setPlatform(value as AIStudioPlatform)
                                                    }}
                                                >
                                                    <SelectTrigger id="ai-studio-platform">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                platformLabels[
                                                                    (value || platform) as AIStudioPlatform
                                                                ]
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectGroup>
                                                            {platformOptions.map((option) => (
                                                                <SelectItem
                                                                    key={option.value}
                                                                    value={option.value}
                                                                >
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectGroup>
                                                    </SelectContent>
                                                </Select>
                                            </Field>

                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-format">
                                                    Format
                                                </FieldLabel>
                                                <Select
                                                    value={format}
                                                    onValueChange={(value) => {
                                                        if (value) setFormat(value as AIStudioFormat)
                                                    }}
                                                >
                                                    <SelectTrigger id="ai-studio-format">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                formatLabels[
                                                                    (value || format) as AIStudioFormat
                                                                ]
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectGroup>
                                                            {formatOptions.map((option) => (
                                                                <SelectItem
                                                                    key={option.value}
                                                                    value={option.value}
                                                                >
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectGroup>
                                                    </SelectContent>
                                                </Select>
                                            </Field>
                                        </div>

                                        <div className="grid gap-4 sm:grid-cols-2">
                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-tone">Tone</FieldLabel>
                                                <Select
                                                    value={tone}
                                                    onValueChange={(value) => {
                                                        if (value) setTone(value as AIStudioTone)
                                                    }}
                                                >
                                                    <SelectTrigger id="ai-studio-tone">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                toneLabels[(value || tone) as AIStudioTone]
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectGroup>
                                                            {toneOptions.map((option) => (
                                                                <SelectItem
                                                                    key={option.value}
                                                                    value={option.value}
                                                                >
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectGroup>
                                                    </SelectContent>
                                                </Select>
                                            </Field>

                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-audience">
                                                    Audience
                                                </FieldLabel>
                                                <Input
                                                    id="ai-studio-audience"
                                                    value={audience}
                                                    onChange={(event) =>
                                                        setAudience(event.target.value)
                                                    }
                                                    placeholder="Optional"
                                                />
                                            </Field>
                                        </div>

                                        <div className="grid gap-4 sm:grid-cols-2">
                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-image-size">
                                                    Size
                                                </FieldLabel>
                                                <Select
                                                    value={imageSize}
                                                    onValueChange={(value) => {
                                                        if (value) {
                                                            setImageSize(value as AIStudioImageSize)
                                                        }
                                                    }}
                                                >
                                                    <SelectTrigger id="ai-studio-image-size">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                imageSizeLabels[
                                                                    (value || imageSize) as AIStudioImageSize
                                                                ]
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectGroup>
                                                            {imageSizeOptions.map((option) => (
                                                                <SelectItem
                                                                    key={option.value}
                                                                    value={option.value}
                                                                >
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectGroup>
                                                    </SelectContent>
                                                </Select>
                                            </Field>

                                            <Field>
                                                <FieldLabel htmlFor="ai-studio-image-quality">
                                                    Quality
                                                </FieldLabel>
                                                <Select
                                                    value={imageQuality}
                                                    onValueChange={(value) => {
                                                        if (value) {
                                                            setImageQuality(
                                                                value as AIStudioImageQuality
                                                            )
                                                        }
                                                    }}
                                                >
                                                    <SelectTrigger id="ai-studio-image-quality">
                                                        <SelectValue>
                                                            {(value: string | null) =>
                                                                imageQualityLabels[
                                                                    (value ||
                                                                        imageQuality) as AIStudioImageQuality
                                                                ]
                                                            }
                                                        </SelectValue>
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectGroup>
                                                            {imageQualityOptions.map((option) => (
                                                                <SelectItem
                                                                    key={option.value}
                                                                    value={option.value}
                                                                >
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectGroup>
                                                    </SelectContent>
                                                </Select>
                                            </Field>
                                        </div>

                                        {!settings?.has_api_key && (
                                            <Alert>
                                                <AlertCircleIcon />
                                                <AlertTitle>Connect OpenAI</AlertTitle>
                                                <AlertDescription>
                                                    Admins can add an organization API key in Studio
                                                    settings. Keys are stored server-side only.
                                                </AlertDescription>
                                            </Alert>
                                        )}

                                        <Button
                                            type="button"
                                            onClick={handleGenerate}
                                            disabled={!canGenerate}
                                            className="w-full"
                                        >
                                            {generateDraft.isPending ? (
                                                <Spinner data-icon="inline-start" />
                                            ) : (
                                                <SparklesIcon data-icon="inline-start" />
                                            )}
                                            Generate draft
                                        </Button>
                                        {brief.trim().length > 0 && brief.trim().length < 8 && (
                                            <FieldError>Brief must be at least 8 characters.</FieldError>
                                        )}
                                    </FieldGroup>
                                </CardContent>
                            </Card>

                            <SavedDraftsPanel
                                drafts={savedDrafts}
                                isLoading={draftsQuery.isLoading}
                                onSelect={setPreviewDraft}
                            />
                        </div>

                        <DraftPreview
                            draft={previewDraft}
                            isSaving={saveDraft.isPending}
                            onSave={handleSaveDraft}
                            onRegenerate={handleGenerate}
                        />
                    </div>
                )}
            </div>

            <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
                <DialogContent className="sm:max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>Studio settings</DialogTitle>
                        <DialogDescription>
                            OpenAI BYOK and guidance are scoped to AI Studio only.
                        </DialogDescription>
                    </DialogHeader>
                    <FieldGroup>
                        <Field>
                            <FieldLabel htmlFor="ai-studio-api-key">OpenAI API key</FieldLabel>
                            <Input
                                id="ai-studio-api-key"
                                value={settingsApiKey}
                                onChange={(event) => setSettingsApiKey(event.target.value)}
                                placeholder={settings?.api_key_masked ?? "sk-..."}
                                type="password"
                                autoComplete="off"
                            />
                            <FieldDescription>
                                Leave blank to keep the remembered key unchanged.
                            </FieldDescription>
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="ai-studio-agents-md">Agents.md</FieldLabel>
                            <Textarea
                                id="ai-studio-agents-md"
                                value={agentsMd}
                                onChange={(event) => setAgentsMd(event.target.value)}
                                className="min-h-32 resize-y"
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="ai-studio-skills-md">Skills.md</FieldLabel>
                            <Textarea
                                id="ai-studio-skills-md"
                                value={skillsMd}
                                onChange={(event) => setSkillsMd(event.target.value)}
                                className="min-h-32 resize-y"
                            />
                        </Field>
                        {settingsSaved && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <CheckIcon className="size-4" />
                                Saved
                            </div>
                        )}
                    </FieldGroup>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setSettingsOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            onClick={handleSaveSettings}
                            disabled={updateSettings.isPending}
                            className={cn(updateSettings.isPending && "cursor-wait")}
                        >
                            {updateSettings.isPending && <Spinner data-icon="inline-start" />}
                            Save settings
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
