"use client"

import Image from "next/image"
import { type ClipboardEvent, useReducer, useRef, useState } from "react"
import {
    AlertCircleIcon,
    CheckIcon,
    ImageIcon,
    PaperclipIcon,
    RefreshCwIcon,
    SaveIcon,
    Settings2Icon,
    SparklesIcon,
    XIcon,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth-context"
import type {
    AIStudioDraft,
    AIStudioFormat,
    AIStudioGenerateRequest,
    AIStudioImageQuality,
    AIStudioImageSize,
    AIStudioPlatform,
    AIStudioReferenceImageInput,
    AIStudioSettings,
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

const maxReferenceImages = 4
const maxReferenceImageBytes = 8 * 1024 * 1024
const allowedReferenceMimeTypes = ["image/png", "image/jpeg", "image/webp"] as const

type ReferenceImageDraft = AIStudioReferenceImageInput & {
    id: string
    dataUrl: string
    size_bytes: number
}

type SettingsFormState = {
    apiKey: string
    agentsMd: string
    skillsMd: string
    saved: boolean
}

type AIStudioSettingsDialogState = SettingsFormState & {
    open: boolean
}

type AIStudioSettingsDialogAction =
    | { type: "open"; settings: AIStudioSettings | undefined }
    | { type: "close" }
    | { type: "setApiKey"; value: string }
    | { type: "setAgentsMd"; value: string }
    | { type: "setSkillsMd"; value: string }
    | { type: "saveSucceeded" }

function getErrorMessage(error: unknown): string {
    return error instanceof Error ? error.message : "Something went wrong."
}

function buildSettingsFormState(settings: AIStudioSettings | undefined): SettingsFormState {
    return {
        apiKey: "",
        agentsMd: settings?.agents_md ?? "",
        skillsMd: settings?.skills_md ?? "",
        saved: false,
    }
}

const initialAIStudioSettingsDialogState: AIStudioSettingsDialogState = {
    open: false,
    ...buildSettingsFormState(undefined),
}

function aiStudioSettingsDialogReducer(
    state: AIStudioSettingsDialogState,
    action: AIStudioSettingsDialogAction,
): AIStudioSettingsDialogState {
    switch (action.type) {
        case "open":
            return {
                open: true,
                ...buildSettingsFormState(action.settings),
            }
        case "close":
            return { ...state, open: false }
        case "setApiKey":
            return { ...state, apiKey: action.value, saved: false }
        case "setAgentsMd":
            return { ...state, agentsMd: action.value, saved: false }
        case "setSkillsMd":
            return { ...state, skillsMd: action.value, saved: false }
        case "saveSucceeded":
            return { ...state, apiKey: "", open: false, saved: true }
        default:
            return state
    }
}

const draftDateFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
})

function formatDraftDate(value: string) {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    return draftDateFormatter.format(date)
}

function isAllowedReferenceMimeType(type: string): type is ReferenceImageDraft["mime_type"] {
    return allowedReferenceMimeTypes.includes(type as ReferenceImageDraft["mime_type"])
}

function fileToReferenceImage(file: File): Promise<ReferenceImageDraft> {
    const mimeType = file.type
    if (!isAllowedReferenceMimeType(mimeType)) {
        return Promise.reject(new Error("Use PNG, JPEG, or WebP sample pictures."))
    }
    if (file.size > maxReferenceImageBytes) {
        return Promise.reject(new Error("Sample pictures must be 8 MB or smaller."))
    }
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
            const dataUrl = String(reader.result ?? "")
            const dataBase64 = dataUrl.includes(",") ? dataUrl.split(",", 2)[1] : dataUrl
            if (!dataBase64) {
                reject(new Error("Sample picture could not be read."))
                return
            }
            resolve({
                id: `${file.name}-${file.size}-${file.lastModified}`,
                filename: file.name || "sample-picture",
                mime_type: mimeType,
                data_base64: dataBase64,
                dataUrl,
                size_bytes: file.size,
            })
        }
        reader.onerror = () => reject(new Error("Sample picture could not be read."))
        reader.readAsDataURL(file)
    })
}

function DraftPreview({
    draft,
    isSaving,
    onSave,
    onRegenerate,
    showActions = true,
}: {
    draft: AIStudioDraft | null
    isSaving: boolean
    onSave: () => void
    onRegenerate: () => void
    showActions?: boolean
}) {
    if (!draft) {
        return (
            <Empty className="min-h-[520px] border bg-card">
                <EmptyHeader>
                    <EmptyMedia variant="icon">
                        <ImageIcon aria-hidden="true" />
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
                    {draft.audience && (
                        <Badge variant="outline">Audience: {draft.audience}</Badge>
                    )}
                    <Badge variant="outline">{imageSizeLabels[draft.image_size]}</Badge>
                    <Badge variant="outline">{imageQualityLabels[draft.image_quality]}</Badge>
                    {draft.reference_images?.length > 0 && (
                        <Badge variant="outline">
                            {draft.reference_images.length} sample
                            {draft.reference_images.length === 1 ? "" : "s"}
                        </Badge>
                    )}
                    <Badge variant="outline">Draft only</Badge>
                </div>
                <CardTitle>Generated draft</CardTitle>
                <CardDescription>
                    {draft.reasoning_model} copy with {draft.image_model} image generation.
                </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
                {draft.image_url ? (
                    <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
                        <Image
                            alt="Generated social media visual"
                            src={draft.image_url}
                            className="size-full object-cover"
                            fill
                            sizes="(min-width: 1024px) 420px, 100vw"
                            unoptimized
                        />
                    </div>
                ) : (
                    <div className="flex aspect-square items-center justify-center rounded-lg border bg-muted text-muted-foreground">
                        <ImageIcon aria-hidden="true" />
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
            {showActions && (
                <CardFooter className="flex-wrap gap-2">
                    <Button
                        type="button"
                        onClick={onSave}
                        disabled={draft.status === "saved" || isSaving}
                    >
                        {isSaving ? (
                            <Spinner data-icon="inline-start" aria-hidden="true" />
                        ) : (
                            <SaveIcon data-icon="inline-start" aria-hidden="true" />
                        )}
                        Save draft
                    </Button>
                    <Button type="button" variant="outline" onClick={onRegenerate}>
                        <RefreshCwIcon data-icon="inline-start" aria-hidden="true" />
                        Regenerate
                    </Button>
                </CardFooter>
            )}
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

function BriefComposer({
    value,
    onChange,
    images,
    isAdding,
    errorMessage,
    onFiles,
    onRemove,
}: {
    value: string
    onChange: (value: string) => void
    images: ReferenceImageDraft[]
    isAdding: boolean
    errorMessage: string
    onFiles: (files: File[]) => void | Promise<void>
    onRemove: (id: string) => void
}) {
    const inputRef = useRef<HTMLInputElement | null>(null)

    const handleFiles = (files: FileList | File[] | null) => {
        const fileList = files ? Array.from(files) : []
        if (fileList.length === 0) return
        void onFiles(fileList)
    }

    const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
        const pastedFiles = Array.from(event.clipboardData.files).filter((file) =>
            file.type.startsWith("image/")
        )
        if (pastedFiles.length === 0) return
        event.preventDefault()
        handleFiles(pastedFiles)
    }

    return (
        <Field>
            <FieldLabel htmlFor="ai-studio-brief">Brief</FieldLabel>
            <div
                onDrop={(event) => {
                    event.preventDefault()
                    handleFiles(event.dataTransfer.files)
                }}
                onDragOver={(event) => event.preventDefault()}
                className="overflow-hidden rounded-lg border bg-input/30 transition-colors focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50"
            >
                <input
                    ref={inputRef}
                    id="ai-studio-reference-images"
                    type="file"
                    accept={allowedReferenceMimeTypes.join(",")}
                    multiple
                    className="sr-only"
                    aria-label="Upload sample pictures"
                    onChange={(event) => {
                        handleFiles(event.target.files)
                        event.target.value = ""
                    }}
                />
                {images.length > 0 && (
                    <div className="flex gap-2 overflow-x-auto border-b bg-background/60 p-3">
                        {images.map((image) => (
                            <div
                                key={image.id}
                                className="relative size-16 shrink-0 overflow-visible rounded-lg border bg-background shadow-xs"
                            >
                                <Image
                                    alt={image.filename}
                                    src={image.dataUrl}
                                    fill
                                    className="rounded-lg object-cover"
                                    sizes="64px"
                                    unoptimized
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="icon-sm"
                                    aria-label={`Remove ${image.filename}`}
                                    onClick={() => onRemove(image.id)}
                                    className="absolute -right-2 -top-2 size-6 rounded-full bg-background p-0"
                                >
                                    <XIcon aria-hidden="true" />
                                </Button>
                            </div>
                        ))}
                    </div>
                )}
                <Textarea
                    id="ai-studio-brief"
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    onPaste={handlePaste}
                    placeholder="Launch announcement, patient education topic, campaign hook..."
                    className="min-h-32 resize-none rounded-none border-0 bg-transparent shadow-none focus-visible:border-transparent focus-visible:ring-0"
                />
                <div className="flex items-center justify-between gap-3 border-t bg-background/40 px-3 py-2">
                    <div className="flex min-w-0 items-center gap-2">
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            aria-label="Attach sample pictures"
                            onClick={() => inputRef.current?.click()}
                        >
                            <PaperclipIcon aria-hidden="true" />
                        </Button>
                        <span className="truncate text-xs text-muted-foreground">
                            Paste images here or attach up to {maxReferenceImages}
                        </span>
                    </div>
                    <Badge variant="outline">
                        {images.length}/{maxReferenceImages}
                    </Badge>
                </div>
            </div>
            <FieldDescription>
                Include the goal, offer, and any wording constraints. Audience can be detected.
            </FieldDescription>
            {isAdding && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Spinner data-icon="inline-start" aria-hidden="true" />
                    Reading sample picture
                </div>
            )}
            {errorMessage && <FieldError>{errorMessage}</FieldError>}
        </Field>
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
    const [galleryDraft, setGalleryDraft] = useState<AIStudioDraft | null>(null)
    const [activeTab, setActiveTab] = useState<"create" | "gallery">("create")
    const [referenceImages, setReferenceImages] = useState<ReferenceImageDraft[]>([])
    const [referenceImageError, setReferenceImageError] = useState("")
    const [isAddingReferenceImage, setIsAddingReferenceImage] = useState(false)
    const [errorMessage, setErrorMessage] = useState("")
    const [settingsDialog, dispatchSettingsDialog] = useReducer(
        aiStudioSettingsDialogReducer,
        initialAIStudioSettingsDialogState,
    )

    const permissionSet = new Set(permissionsQuery.data?.permissions ?? [])
    const isDeveloper = user?.role === "developer"
    const canUseAI = isDeveloper || permissionSet.has("use_ai_assistant")
    const canManageSettings = isDeveloper || permissionSet.has("manage_ai_settings")
    const aiAvailable = Boolean(user?.ai_enabled && canUseAI)
    const settings = settingsQuery.data
    const {
        agentsMd,
        apiKey: settingsApiKey,
        open: settingsOpen,
        saved: settingsSaved,
        skillsMd,
    } = settingsDialog

    const openSettingsDialog = () => {
        dispatchSettingsDialog({ type: "open", settings })
    }

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
        reference_images: referenceImages.map((image) => ({
            filename: image.filename,
            mime_type: image.mime_type,
            data_base64: image.data_base64,
        })),
    })

    const handleReferenceFiles = async (files: File[]) => {
        setReferenceImageError("")
        const imageFiles = files.filter((file) => file.type.startsWith("image/"))
        if (imageFiles.length === 0) {
            setReferenceImageError("Paste or upload PNG, JPEG, or WebP images.")
            return
        }
        const remainingSlots = maxReferenceImages - referenceImages.length
        if (remainingSlots <= 0) {
            setReferenceImageError("Remove a sample before adding another image.")
            return
        }
        const selectedFiles = imageFiles.slice(0, remainingSlots)
        if (imageFiles.length > remainingSlots) {
            setReferenceImageError(`AI Studio supports up to ${maxReferenceImages} samples.`)
        }
        setIsAddingReferenceImage(true)
        const result = await Promise.all(selectedFiles.map(fileToReferenceImage)).then((nextImages) => ({
            status: "success" as const,
            nextImages,
        })).catch((error: unknown) => ({
            status: "error" as const,
            message: getErrorMessage(error),
        }))

        if (result.status === "success") {
            setReferenceImages((current) => {
                const seen = new Set(current.map((image) => image.id))
                const unique = result.nextImages.filter((image) => !seen.has(image.id))
                return [...current, ...unique].slice(0, maxReferenceImages)
            })
        } else {
            setReferenceImageError(result.message)
        }
        setIsAddingReferenceImage(false)
    }

    const handleRemoveReferenceImage = (id: string) => {
        setReferenceImageError("")
        setReferenceImages((current) => current.filter((image) => image.id !== id))
    }

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
            dispatchSettingsDialog({ type: "saveSucceeded" })
        } catch (error) {
            setErrorMessage(getErrorMessage(error))
        }
    }

    const savedDrafts = draftsQuery.data?.items ?? []
    const selectedGalleryDraft = galleryDraft ?? savedDrafts[0] ?? null

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
                                onClick={openSettingsDialog}
                            >
                                <Settings2Icon data-icon="inline-start" aria-hidden="true" />
                                Studio settings
                            </Button>
                        )}
                    </div>
                </div>

                {!aiAvailable && (
                    <Alert variant="destructive">
                        <AlertCircleIcon aria-hidden="true" />
                        <AlertTitle>AI Studio is unavailable</AlertTitle>
                        <AlertDescription>
                            Your organization or role does not currently have AI access.
                        </AlertDescription>
                    </Alert>
                )}

                {settingsQuery.isError && (
                    <Alert variant="destructive">
                        <AlertCircleIcon aria-hidden="true" />
                        <AlertTitle>Settings could not load</AlertTitle>
                        <AlertDescription>{getErrorMessage(settingsQuery.error)}</AlertDescription>
                    </Alert>
                )}

                {errorMessage && (
                    <Alert variant="destructive">
                        <AlertCircleIcon aria-hidden="true" />
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
                    <Tabs
                        value={activeTab}
                        onValueChange={(value) => setActiveTab(value as "create" | "gallery")}
                        className="gap-6"
                    >
                        <TabsList aria-label="AI Studio sections">
                            <TabsTrigger value="create">Create</TabsTrigger>
                            <TabsTrigger value="gallery">Gallery</TabsTrigger>
                        </TabsList>

                        <TabsContent value="create" className="mt-0">
                            {activeTab === "create" && (
                                <div className="grid gap-6 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
                                    <Card>
                                        <CardHeader>
                                            <CardTitle>Draft generator</CardTitle>
                                            <CardDescription>
                                                Start with a brief. AI Studio returns one caption
                                                and one image for review.
                                            </CardDescription>
                                            {!settings?.has_api_key && (
                                                <CardAction>
                                                    <Badge variant="destructive">Key required</Badge>
                                                </CardAction>
                                            )}
                                        </CardHeader>
                                        <CardContent>
                                            <FieldGroup>
                                                <BriefComposer
                                                    value={brief}
                                                    onChange={setBrief}
                                                    images={referenceImages}
                                                    isAdding={isAddingReferenceImage}
                                                    errorMessage={referenceImageError}
                                                    onFiles={handleReferenceFiles}
                                                    onRemove={handleRemoveReferenceImage}
                                                />

                                                <div className="grid gap-4 sm:grid-cols-2">
                                                    <Field>
                                                        <FieldLabel htmlFor="ai-studio-platform">
                                                            Platform
                                                        </FieldLabel>
                                                        <Select
                                                            value={platform}
                                                            onValueChange={(value) => {
                                                                if (value) {
                                                                    setPlatform(
                                                                        value as AIStudioPlatform
                                                                    )
                                                                }
                                                            }}
                                                        >
                                                            <SelectTrigger id="ai-studio-platform">
                                                                <SelectValue>
                                                                    {(value: string | null) =>
                                                                        platformLabels[
                                                                            (value ||
                                                                                platform) as AIStudioPlatform
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
                                                                if (value) {
                                                                    setFormat(value as AIStudioFormat)
                                                                }
                                                            }}
                                                        >
                                                            <SelectTrigger id="ai-studio-format">
                                                                <SelectValue>
                                                                    {(value: string | null) =>
                                                                        formatLabels[
                                                                            (value ||
                                                                                format) as AIStudioFormat
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
                                                        <FieldLabel htmlFor="ai-studio-tone">
                                                            Tone
                                                        </FieldLabel>
                                                        <Select
                                                            value={tone}
                                                            onValueChange={(value) => {
                                                                if (value) {
                                                                    setTone(value as AIStudioTone)
                                                                }
                                                            }}
                                                        >
                                                            <SelectTrigger id="ai-studio-tone">
                                                                <SelectValue>
                                                                    {(value: string | null) =>
                                                                        toneLabels[
                                                                            (value ||
                                                                                tone) as AIStudioTone
                                                                        ]
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
                                                            placeholder="Auto-detect"
                                                        />
                                                        <FieldDescription>
                                                            Leave blank to detect from the brief and
                                                            samples.
                                                        </FieldDescription>
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
                                                                    setImageSize(
                                                                        value as AIStudioImageSize
                                                                    )
                                                                }
                                                            }}
                                                        >
                                                            <SelectTrigger id="ai-studio-image-size">
                                                                <SelectValue>
                                                                    {(value: string | null) =>
                                                                        imageSizeLabels[
                                                                            (value ||
                                                                                imageSize) as AIStudioImageSize
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
                                                        <AlertCircleIcon aria-hidden="true" />
                                                        <AlertTitle>Connect OpenAI</AlertTitle>
                                                        <AlertDescription>
                                                            Admins can add an organization API key in
                                                            Studio settings. Keys are stored
                                                            server-side only.
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
                                                        <Spinner data-icon="inline-start" aria-hidden="true" />
                                                    ) : (
                                                        <SparklesIcon data-icon="inline-start" aria-hidden="true" />
                                                    )}
                                                    Generate draft
                                                </Button>
                                                {brief.trim().length > 0 &&
                                                    brief.trim().length < 8 && (
                                                        <FieldError>
                                                            Brief must be at least 8 characters.
                                                        </FieldError>
                                                    )}
                                            </FieldGroup>
                                        </CardContent>
                                    </Card>

                                    <DraftPreview
                                        draft={previewDraft}
                                        isSaving={saveDraft.isPending}
                                        onSave={handleSaveDraft}
                                        onRegenerate={handleGenerate}
                                    />
                                </div>
                            )}
                        </TabsContent>

                        <TabsContent value="gallery" className="mt-0">
                            {activeTab === "gallery" && (
                                <div className="grid gap-6 lg:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
                                    <SavedDraftsPanel
                                        drafts={savedDrafts}
                                        isLoading={draftsQuery.isLoading}
                                        onSelect={setGalleryDraft}
                                    />
                                    <DraftPreview
                                        draft={selectedGalleryDraft}
                                        isSaving={false}
                                        onSave={() => undefined}
                                        onRegenerate={() => undefined}
                                        showActions={false}
                                    />
                                </div>
                            )}
                        </TabsContent>
                    </Tabs>
                )}
            </div>

            <Dialog
                open={settingsOpen}
                onOpenChange={(open) => {
                    if (open) {
                        openSettingsDialog()
                        return
                    }
                    dispatchSettingsDialog({ type: "close" })
                }}
            >
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
                                onChange={(event) =>
                                    dispatchSettingsDialog({
                                        type: "setApiKey",
                                        value: event.target.value,
                                    })
                                }
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
                                onChange={(event) =>
                                    dispatchSettingsDialog({
                                        type: "setAgentsMd",
                                        value: event.target.value,
                                    })
                                }
                                className="min-h-32 resize-y"
                            />
                        </Field>
                        <Field>
                            <FieldLabel htmlFor="ai-studio-skills-md">Skills.md</FieldLabel>
                            <Textarea
                                id="ai-studio-skills-md"
                                value={skillsMd}
                                onChange={(event) =>
                                    dispatchSettingsDialog({
                                        type: "setSkillsMd",
                                        value: event.target.value,
                                    })
                                }
                                className="min-h-32 resize-y"
                            />
                        </Field>
                        {settingsSaved && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <CheckIcon className="size-4" aria-hidden="true" />
                                Saved
                            </div>
                        )}
                    </FieldGroup>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => dispatchSettingsDialog({ type: "close" })}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            onClick={handleSaveSettings}
                            disabled={updateSettings.isPending}
                            className={cn(updateSettings.isPending && "cursor-wait")}
                        >
                            {updateSettings.isPending && <Spinner data-icon="inline-start" aria-hidden="true" />}
                            Save settings
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
