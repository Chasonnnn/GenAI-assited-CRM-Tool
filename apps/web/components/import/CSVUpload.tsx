"use client"

import { useEffect, useState, useCallback, type DragEvent } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
    UploadIcon,
    XIcon,
    CheckIcon,
    XCircleIcon,
    FileIcon,
    Loader2Icon,
    SparklesIcon,
    BookOpenIcon,
    SearchIcon,
} from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import {
    usePreviewImport,
    useSubmitImport,
    useApproveImport,
    useAiMapImport,
    type EnhancedImportPreview,
} from "@/lib/hooks/use-import"
import type { ValidationMode } from "@/lib/api/import"
import type { SurrogateSource } from "@/lib/types/surrogate"
import {
    applyUnknownColumnBehavior,
    buildColumnMappingsFromSuggestions,
    buildImportSubmitPayload,
    type ColumnMappingDraft,
    type UnknownColumnBehavior,
} from "@/lib/import-utils"

const TRANSFORM_OPTIONS = [
    { value: "", label: "None" },
    { value: "date_flexible", label: "Date (flexible)" },
    { value: "datetime_flexible", label: "Date/Time (flexible)" },
    { value: "height_flexible", label: "Height (flexible)" },
    { value: "int_flexible", label: "Integer (flexible)" },
    { value: "state_normalize", label: "State normalize" },
    { value: "phone_normalize", label: "Phone normalize" },
    { value: "boolean_flexible", label: "Boolean (flexible)" },
    { value: "boolean_inverted", label: "Boolean (inverted)" },
]

const ACTION_OPTIONS = [
    { value: "map", label: "Map" },
    { value: "metadata", label: "Metadata" },
    { value: "ignore", label: "Ignore" },
    { value: "custom", label: "Custom" },
]

const SOURCE_OPTIONS: Array<{ value: SurrogateSource; label: string }> = [
    { value: "manual", label: "Manual" },
    { value: "import", label: "Import" },
    { value: "referral", label: "Referral" },
    { value: "website", label: "Website" },
    { value: "meta", label: "Meta" },
    { value: "agency", label: "Agency" },
]

interface CSVUploadProps {
    onImportComplete?: () => void
}

/** Get badge info based on suggestion reason */
function getReasonBadge(reason: string): {
    icon: React.ReactNode
    label: string
    variant: "secondary" | "outline"
} | null {
    if (reason.startsWith("Learned")) {
        return {
            icon: <BookOpenIcon className="size-3 mr-1" />,
            label: "Learned",
            variant: "secondary",
        }
    }
    if (reason.startsWith("AI:")) {
        return {
            icon: <SparklesIcon className="size-3 mr-1" />,
            label: "AI",
            variant: "outline",
        }
    }
    if (reason.includes("Matched from saved template")) {
        return {
            icon: <FileIcon className="size-3 mr-1" />,
            label: "Template",
            variant: "outline",
        }
    }
    if (reason.includes("similarity")) {
        return {
            icon: <SearchIcon className="size-3 mr-1" />,
            label: "Similar",
            variant: "outline",
        }
    }
    return null
}

export function CSVUpload({ onImportComplete }: CSVUploadProps) {
    const { user } = useAuth()
    const [file, setFile] = useState<File | null>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [preview, setPreview] = useState<EnhancedImportPreview | null>(null)
    const [mappings, setMappings] = useState<ColumnMappingDraft[]>([])
    const [unknownColumnBehavior, setUnknownColumnBehavior] = useState<UnknownColumnBehavior>("ignore")
    const [touchedColumns, setTouchedColumns] = useState<Set<string>>(new Set())
    const [backdateCreatedAt, setBackdateCreatedAt] = useState(false)
    const [backdateTouched, setBackdateTouched] = useState(false)
    const [allowAiAssist, setAllowAiAssist] = useState(false)
    const [defaultSource, setDefaultSource] = useState<SurrogateSource>("manual")
    const [error, setError] = useState<string>("")
    const [submitMessage, setSubmitMessage] = useState<string | null>(null)
    const [approveMessage, setApproveMessage] = useState<string | null>(null)
    const [templateCleared, setTemplateCleared] = useState(false)
    const [validationMode, setValidationMode] = useState<ValidationMode>("drop_invalid_fields")
    const [showValidationDialog, setShowValidationDialog] = useState(false)

    const previewMutation = usePreviewImport()
    const submitMutation = useSubmitImport()
    const approveMutation = useApproveImport()
    const aiMapMutation = useAiMapImport()

    const canApprove = user?.role === "admin" || user?.role === "developer"
    const hasCreatedAtMapping = mappings.some(
        (mapping) => mapping.action === "map" && mapping.surrogate_field === "created_at"
    )

    useEffect(() => {
        if (!hasCreatedAtMapping) {
            if (backdateCreatedAt) {
                setBackdateCreatedAt(false)
            }
            if (backdateTouched) {
                setBackdateTouched(false)
            }
            return
        }

        if (!backdateTouched && !backdateCreatedAt) {
            setBackdateCreatedAt(true)
        }
    }, [hasCreatedAtMapping, backdateCreatedAt, backdateTouched])

    const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(false)
    }, [])

    const resolveErrorDetail = (error: unknown, fallback: string) => {
        if (
            typeof error === "object" &&
            error !== null &&
            "response" in error &&
            typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
        ) {
            return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || fallback
        }
        if (error instanceof Error && error.message) return error.message
        return fallback
    }

    const handleFileSelect = useCallback(async (selectedFile: File) => {
        if (!selectedFile.name.endsWith(".csv") && !selectedFile.name.endsWith(".tsv")) {
            setError("Please upload a CSV or TSV file")
            return
        }

        setError("")
        setSubmitMessage(null)
        setApproveMessage(null)
        setBackdateCreatedAt(false)
        setBackdateTouched(false)
        setDefaultSource("manual")
        setTemplateCleared(false)
        setValidationMode("drop_invalid_fields")
        setFile(selectedFile)

        try {
            const previewData = await previewMutation.mutateAsync({
                file: selectedFile,
                applyTemplate: true,
                enableAi: allowAiAssist,
            })
            setPreview(previewData)
            const baseMappings = buildColumnMappingsFromSuggestions(previewData.column_suggestions)
            const nextTouched = new Set<string>()
            setTouchedColumns(nextTouched)

            // Use template's unknown_column_behavior if auto-applied, otherwise default
            const effectiveBehavior = previewData.template_unknown_column_behavior as UnknownColumnBehavior | null
            const behavior = effectiveBehavior || unknownColumnBehavior
            if (effectiveBehavior) {
                setUnknownColumnBehavior(effectiveBehavior)
            }

            setMappings(applyUnknownColumnBehavior(baseMappings, behavior, nextTouched))
        } catch (err: unknown) {
            setError(resolveErrorDetail(err, "Failed to preview CSV"))
            setFile(null)
        }
    }, [previewMutation, unknownColumnBehavior, allowAiAssist])

    const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        setIsDragging(false)

        const droppedFile = e.dataTransfer.files[0]
        if (droppedFile) {
            handleFileSelect(droppedFile)
        }
    }, [handleFileSelect])

    const handleRemoveFile = () => {
        setFile(null)
        setPreview(null)
        setMappings([])
        setTouchedColumns(new Set())
        setBackdateCreatedAt(false)
        setBackdateTouched(false)
        setError("")
        setSubmitMessage(null)
        setApproveMessage(null)
        setValidationMode("drop_invalid_fields")
        setShowValidationDialog(false)
    }

    const handleBackdateToggle = (checked: boolean) => {
        setBackdateTouched(true)
        setBackdateCreatedAt(checked)
    }

    const updateMapping = (csvColumn: string, patch: Partial<ColumnMappingDraft>) => {
        setMappings((prev) =>
            prev.map((mapping) =>
                mapping.csv_column === csvColumn ? { ...mapping, ...patch } : mapping
            )
        )
        setTouchedColumns((prev) => {
            const next = new Set(prev)
            next.add(csvColumn)
            return next
        })
    }

    const handleUnknownBehaviorChange = (value: UnknownColumnBehavior) => {
        setUnknownColumnBehavior(value)
        setMappings((prev) => applyUnknownColumnBehavior(prev, value, touchedColumns))
    }

    const handleAiHelp = async () => {
        if (!preview) return

        const unmatched = mappings
            .filter((mapping) => !mapping.surrogate_field && mapping.action !== "custom")
            .map((mapping) => mapping.csv_column)

        if (unmatched.length === 0) return

        const sampleValues = Object.fromEntries(
            mappings.map((mapping) => [mapping.csv_column, mapping.sample_values || []])
        )

        try {
            const result = await aiMapMutation.mutateAsync({
                unmatched_columns: unmatched,
                sample_values: sampleValues,
            })

            setMappings((prev) =>
                prev.map((mapping) => {
                    const suggestion = result.suggestions.find(
                        (item) => item.csv_column === mapping.csv_column
                    )
                    if (!suggestion) return mapping

                    const derived = buildColumnMappingsFromSuggestions([suggestion])[0]
                    if (!derived) return mapping
                    const shouldAdopt =
                        (!mapping.surrogate_field &&
                            (mapping.action === "ignore" || mapping.action === "metadata")) ||
                        mapping.action === "custom"

                    return {
                        ...mapping,
                        ...derived,
                        action: shouldAdopt ? derived.action : mapping.action,
                        surrogate_field: shouldAdopt ? derived.surrogate_field : mapping.surrogate_field,
                        transformation: shouldAdopt ? derived.transformation : mapping.transformation,
                        custom_field_key: shouldAdopt ? derived.custom_field_key : mapping.custom_field_key,
                        sample_values: mapping.sample_values.length ? mapping.sample_values : derived.sample_values,
                    }
                })
            )
        } catch (err: unknown) {
            setError(resolveErrorDetail(err, "AI mapping failed"))
        }
    }

    const ensureRequiredMappings = () => {
        const mappedFields = new Set(
            mappings
                .filter((mapping) => mapping.action === "map" && mapping.surrogate_field)
                .map((mapping) => mapping.surrogate_field)
        )

        if (!mappedFields.has("full_name") || !mappedFields.has("email")) {
            setError("Please map required fields: full_name and email")
            return false
        }

        const hasUnselectedMaps = mappings.some(
            (mapping) => mapping.action === "map" && !mapping.surrogate_field
        )
        if (hasUnselectedMaps) {
            setError("Please select a field for every mapped column")
            return false
        }

        return true
    }

    const submitImportWithMode = async (mode: ValidationMode) => {
        if (!preview) return
        setError("")
        setSubmitMessage(null)
        setApproveMessage(null)

        const payload = buildImportSubmitPayload(
            mappings,
            unknownColumnBehavior,
            touchedColumns,
            backdateCreatedAt,
            defaultSource,
            mode
        )

        try {
            const response = await submitMutation.mutateAsync({
                importId: preview.import_id,
                payload: {
                    column_mappings: payload.column_mappings,
                    unknown_column_behavior: payload.unknown_column_behavior,
                    backdate_created_at: payload.backdate_created_at,
                    default_source: payload.default_source,
                    validation_mode: payload.validation_mode,
                },
            })

            setValidationMode(mode)
            setSubmitMessage(
                response.status === "awaiting_approval"
                    ? "Import submitted for approval."
                    : "Import submitted."
            )
            onImportComplete?.()
        } catch (err: unknown) {
            setError(resolveErrorDetail(err, "Failed to submit import"))
        }
    }

    const handleSubmit = async () => {
        if (!preview) return
        setError("")
        setSubmitMessage(null)
        setApproveMessage(null)

        if (!ensureRequiredMappings()) return

        setShowValidationDialog(true)
    }

    const handleApprove = async () => {
        if (!preview) return
        setError("")
        setApproveMessage(null)

        try {
            const response = await approveMutation.mutateAsync(preview.import_id)
            setApproveMessage(response.message || "Import approved and queued for processing")
            onImportComplete?.()
        } catch (err: unknown) {
            setError(resolveErrorDetail(err, "Failed to approve import"))
        }
    }

    return (
        <div className="space-y-6">
            {!preview && (
                <Card>
                    <div
                        className={cn(
                            "relative flex min-h-[300px] cursor-pointer flex-col items-center justify-center border-2 border-dashed p-12 transition-colors",
                            isDragging && "border-primary bg-primary/5",
                            !isDragging && "border-border hover:border-primary/50 hover:bg-muted/50",
                            error && "border-destructive",
                        )}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        onClick={() => document.getElementById("file-upload")?.click()}
                    >
                        <input
                            id="file-upload"
                            type="file"
                            accept=".csv,.tsv"
                            className="hidden"
                            onChange={(e) => {
                                const selectedFile = e.target.files?.[0]
                                if (selectedFile) handleFileSelect(selectedFile)
                            }}
                        />

                        {previewMutation.isPending ? (
                            <>
                                <Loader2Icon className="mb-4 size-12 animate-spin text-muted-foreground" />
                                <h3 className="mb-2 text-lg font-semibold">Processing CSV...</h3>
                                <p className="text-sm text-muted-foreground">Analyzing rows and detecting duplicates</p>
                            </>
                        ) : (
                            <>
                                <UploadIcon className="mb-4 size-12 text-muted-foreground" />
                                <h3 className="mb-2 text-lg font-semibold">
                                    {isDragging ? "Drop CSV file here" : "Drag CSV here or click to browse"}
                                </h3>
                        <p className="text-sm text-muted-foreground">Upload a CSV file to import surrogates</p>
                    </>
                )}

                {error && (
                            <div className="mt-4 flex items-center gap-2 text-sm text-destructive">
                                <XCircleIcon className="size-4" />
                                {error}
                        </div>
                    )}

                    <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
                        <Switch
                            id="ai-auto-map"
                            checked={allowAiAssist}
                            onCheckedChange={setAllowAiAssist}
                        />
                        <Label htmlFor="ai-auto-map">Allow AI to auto-suggest mappings</Label>
                    </div>
                </div>
            </Card>
        )}

            {preview && (
                <>
                    <Card className="p-4">
                        <div className="flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">Total Rows:</span>
                                <Badge variant="secondary">{preview.total_rows}</Badge>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">Matched Columns:</span>
                                <Badge className="bg-green-500/10 text-green-600 border-green-500/20">
                                    {preview.matched_count}
                                </Badge>
                            </div>

                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground">Unmatched Columns:</span>
                                <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">
                                    {preview.unmatched_count}
                                </Badge>
                            </div>

                            {preview.duplicate_emails_db > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Duplicates in DB:</span>
                                    <Badge className="bg-destructive/10 text-destructive border-destructive/20">
                                        {preview.duplicate_emails_db}
                                    </Badge>
                                </div>
                            )}

                            {preview.duplicate_emails_csv > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Duplicates in CSV:</span>
                                    <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20">
                                        {preview.duplicate_emails_csv}
                                    </Badge>
                                </div>
                            )}

                            {preview.validation_errors > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">Validation Errors:</span>
                                    <Badge className="bg-destructive/10 text-destructive border-destructive/20">
                                        {preview.validation_errors}
                                    </Badge>
                                </div>
                            )}

                            <div className="ml-auto flex items-center gap-2">
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <FileIcon className="size-4" />
                                    {file?.name}
                                </div>
                                <Button variant="ghost" size="sm" onClick={handleRemoveFile}>
                                    <XIcon className="size-4" />
                                </Button>
                            </div>
                        </div>
                    </Card>

                    {/* Auto-applied template banner */}
                    {preview.auto_applied_template && !templateCleared && (
                        <Alert>
                            <CheckIcon className="size-4" />
                            <AlertTitle>Template auto-applied</AlertTitle>
                            <AlertDescription className="flex items-center justify-between">
                                <span>
                                    &ldquo;{preview.auto_applied_template.name}&rdquo; matched{" "}
                                    {Math.round(preview.auto_applied_template.match_score * 100)}% of columns.
                                    {preview.template_unknown_column_behavior && (
                                        <span className="text-muted-foreground ml-2">
                                            Unknown columns: {preview.template_unknown_column_behavior}
                                        </span>
                                    )}
                                </span>
                                <Button
                                    variant="link"
                                    size="sm"
                                    className="h-auto p-0"
                                    onClick={async () => {
                                        if (!file) return
                                        setTemplateCleared(true)
                                        try {
                                            const previewData = await previewMutation.mutateAsync({
                                                file,
                                                applyTemplate: false,
                                                enableAi: allowAiAssist,
                                            })
                                            setPreview(previewData)
                                            const baseMappings = buildColumnMappingsFromSuggestions(
                                                previewData.column_suggestions
                                            )
                                            const nextTouched = new Set<string>()
                                            setTouchedColumns(nextTouched)
                                            setMappings(
                                                applyUnknownColumnBehavior(baseMappings, "ignore", nextTouched)
                                            )
                                            setUnknownColumnBehavior("ignore")
                                        } catch (err: unknown) {
                                            setError(
                                                resolveErrorDetail(err, "Failed to clear template mappings")
                                            )
                                        }
                                    }}
                                >
                                    Clear and map manually
                                </Button>
                            </AlertDescription>
                        </Alert>
                    )}

                    {/* AI auto-trigger indicator */}
                    {preview.ai_auto_triggered && preview.ai_mapped_columns.length > 0 && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <SparklesIcon className="size-4" />
                            AI suggested mappings for {preview.ai_mapped_columns.length} unmatched column(s)
                        </div>
                    )}

                    <Card className="overflow-hidden">
                        <CardHeader>
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <CardTitle>Column Mapping</CardTitle>
                                    <CardDescription>
                                        Review column mappings before submitting the import.
                                    </CardDescription>
                                    {hasCreatedAtMapping && (
                                        <p
                                            className={cn(
                                                "mt-2 text-xs",
                                                backdateCreatedAt ? "text-muted-foreground" : "text-amber-600"
                                            )}
                                        >
                                            {backdateCreatedAt
                                                ? "Created_at will use the CSV timestamp (org timezone fallback if none is provided)."
                                                : "Created_at will use import time; CSV values are stored as metadata unless backdating is enabled."}
                                        </p>
                                    )}
                                </div>
                                <div className="flex flex-wrap items-center gap-3">
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <span>Default source:</span>
                                        <Select
                                            value={defaultSource}
                                            onValueChange={(value) => setDefaultSource(value as SurrogateSource)}
                                        >
                                            <SelectTrigger className="h-8 w-[140px]">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {SOURCE_OPTIONS.map((option) => (
                                                    <SelectItem key={option.value} value={option.value}>
                                                        {option.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                        <span>Unknown columns:</span>
                                        <Select
                                            value={unknownColumnBehavior}
                                            onValueChange={(value) =>
                                                handleUnknownBehaviorChange(value as UnknownColumnBehavior)
                                            }
                                        >
                                            <SelectTrigger className="h-8 w-[140px]">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="ignore">Ignore</SelectItem>
                                                <SelectItem value="metadata">Store metadata</SelectItem>
                                                <SelectItem value="warn">Warn only</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                <Switch
                                                    id="backdate-created-at"
                                                    checked={backdateCreatedAt}
                                                    onCheckedChange={handleBackdateToggle}
                                                    disabled={!hasCreatedAtMapping}
                                                />
                                                <Label htmlFor="backdate-created-at">
                                            Use CSV created_at values
                                                </Label>
                                            </div>
                                    {preview.ai_available && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={handleAiHelp}
                                            disabled={aiMapMutation.isPending}
                                        >
                                            {aiMapMutation.isPending ? (
                                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            ) : (
                                                <SparklesIcon className="mr-2 size-4" />
                                            )}
                                            Get AI help
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-[520px] overflow-auto">
                                <Table>
                                    <TableHeader className="sticky top-0 z-10 bg-background">
                                        <TableRow>
                                            <TableHead>CSV Column</TableHead>
                                            <TableHead>Samples</TableHead>
                                            <TableHead>Action</TableHead>
                                            <TableHead>Map To</TableHead>
                                            <TableHead>Transform</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {mappings.map((mapping) => {
                                            // Get reason from original suggestion for badge
                                            const originalSuggestion = preview.column_suggestions.find(
                                                (s) => s.csv_column === mapping.csv_column
                                            )
                                            const reasonBadge = originalSuggestion
                                                ? getReasonBadge(originalSuggestion.reason)
                                                : null

                                            return (
                                            <TableRow key={mapping.csv_column}>
                                                <TableCell className="font-medium">
                                                    <div className="space-y-1">
                                                        <div className="flex items-center gap-2">
                                                            <span>{mapping.csv_column}</span>
                                                            {reasonBadge && (
                                                                <Badge
                                                                    variant={reasonBadge.variant}
                                                                    className="text-xs flex items-center"
                                                                >
                                                                    {reasonBadge.icon}
                                                                    {reasonBadge.label}
                                                                </Badge>
                                                            )}
                                                            {!reasonBadge && mapping.confidence_level !== "none" && (
                                                                <Badge
                                                                    variant="secondary"
                                                                    className="text-xs capitalize"
                                                                >
                                                                    {mapping.confidence_level}
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        {mapping.warnings?.length > 0 && (
                                                            <p className="text-xs text-amber-600">
                                                                {mapping.warnings[0]}
                                                            </p>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-xs text-muted-foreground">
                                                    {(mapping.sample_values || []).slice(0, 2).join(", ") || "—"}
                                                </TableCell>
                                                <TableCell>
                                                    <Select
                                                        value={mapping.action}
                                                        onValueChange={(value) => {
                                                            if (value === "map") {
                                                                updateMapping(mapping.csv_column, {
                                                                    action: "map",
                                                                })
                                                            } else if (value === "custom") {
                                                                updateMapping(mapping.csv_column, {
                                                                    action: "custom",
                                                                    surrogate_field: null,
                                                                })
                                                            } else {
                                                                updateMapping(mapping.csv_column, {
                                                                    action: value as ColumnMappingDraft["action"],
                                                                    surrogate_field: null,
                                                                    transformation: null,
                                                                })
                                                            }
                                                        }}
                                                    >
                                                        <SelectTrigger className="w-[130px]">
                                                            <SelectValue placeholder="Action" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {ACTION_OPTIONS.map((option) => (
                                                                <SelectItem key={option.value} value={option.value}>
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                </TableCell>
                                                <TableCell>
                                                    {mapping.action === "map" ? (
                                                        <Select
                                                            value={mapping.surrogate_field || ""}
                                                            onValueChange={(value) =>
                                                                updateMapping(mapping.csv_column, {
                                                                    surrogate_field: value || null,
                                                                    action: "map",
                                                                })
                                                            }
                                                        >
                                                            <SelectTrigger className="w-[180px]">
                                                                <SelectValue placeholder="Select field" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {preview.available_fields.map((field) => (
                                                                    <SelectItem key={field} value={field}>
                                                                        {field}
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    ) : mapping.action === "custom" ? (
                                                        <Input
                                                            value={mapping.custom_field_key || ""}
                                                            onChange={(e) =>
                                                                updateMapping(mapping.csv_column, {
                                                                    custom_field_key: e.target.value,
                                                                })
                                                            }
                                                            placeholder="custom_field_key"
                                                            className="w-[180px]"
                                                        />
                                                    ) : (
                                                        <span className="text-xs text-muted-foreground">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <Select
                                                        value={mapping.transformation || ""}
                                                        onValueChange={(value) =>
                                                            updateMapping(mapping.csv_column, {
                                                                transformation: value || null,
                                                            })
                                                        }
                                                        disabled={mapping.action !== "map"}
                                                    >
                                                        <SelectTrigger className="w-[170px]">
                                                            <SelectValue placeholder="None" />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {TRANSFORM_OPTIONS.map((option) => (
                                                                <SelectItem key={option.value || "none"} value={option.value}>
                                                                    {option.label}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                </TableCell>
                                            </TableRow>
                                        )})}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="overflow-hidden">
                        <CardHeader>
                            <CardTitle>Preview ({preview.sample_rows.length} of {preview.total_rows} rows)</CardTitle>
                            <CardDescription>
                                {validationMode === "drop_invalid_fields"
                                    ? "Rows with invalid values will still be imported; invalid fields are dropped and logged."
                                    : "Rows with validation errors will be skipped and logged."}
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="max-h-[400px] overflow-auto">
                                <Table>
                                    <TableHeader className="sticky top-0 z-10 bg-background">
                                        <TableRow>
                                            {Object.keys(preview.sample_rows[0] || {}).map((header) => (
                                                <TableHead key={header}>{header}</TableHead>
                                            ))}
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {preview.sample_rows.map((row, rowIdx) => (
                                            <TableRow key={rowIdx}>
                                                {Object.keys(preview.sample_rows[0] || {}).map((header) => (
                                                    <TableCell key={header}>
                                                        {row[header] || <span className="text-muted-foreground">—</span>}
                                                    </TableCell>
                                                ))}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="flex items-center justify-end gap-3">
                        <Button variant="outline" onClick={handleRemoveFile} disabled={submitMutation.isPending}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSubmit}
                            disabled={submitMutation.isPending}
                            className="min-w-[160px]"
                        >
                            {submitMutation.isPending ? (
                                <>
                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                    Submitting...
                                </>
                            ) : (
                                "Submit Import"
                            )}
                        </Button>
                    </div>

                    {submitMessage && (
                        <Card className="bg-green-500/10 border-green-500/20">
                            <CardContent className="py-3">
                                <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                                    <CheckIcon className="size-5" />
                                    <p className="font-medium">{submitMessage}</p>
                                </div>
                                {canApprove && (
                                    <div className="mt-3">
                                        <Button
                                            variant="secondary"
                                            onClick={handleApprove}
                                            disabled={approveMutation.isPending}
                                        >
                                            {approveMutation.isPending ? (
                                                <>
                                                    <Loader2Icon className="mr-2 size-4 animate-spin" />
                                                    Approving...
                                                </>
                                            ) : (
                                                "Approve & Run Import"
                                            )}
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {approveMessage && (
                        <Card className="bg-green-500/10 border-green-500/20">
                            <CardContent className="py-3">
                                <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                                    <CheckIcon className="size-5" />
                                    <p className="font-medium">{approveMessage}</p>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {error && (
                        <Card className="bg-destructive/10 border-destructive/20">
                            <CardContent className="py-3">
                                <div className="flex items-center gap-2 text-destructive">
                                    <XCircleIcon className="size-5" />
                                    <p className="font-medium">{error}</p>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    <Dialog open={showValidationDialog} onOpenChange={setShowValidationDialog}>
                        <DialogContent className="sm:max-w-lg">
                            <DialogHeader>
                                <DialogTitle>Handle validation issues</DialogTitle>
                                <DialogDescription>
                                    Choose how to handle invalid values (for example phone, state, or numeric fields)
                                    before submitting this import.
                                </DialogDescription>
                            </DialogHeader>

                            <div className="space-y-3 py-2">
                                <RadioGroup
                                    value={validationMode}
                                    onValueChange={(value) => setValidationMode(value as ValidationMode)}
                                    className="space-y-3"
                                >
                                    <div className="flex items-start space-x-3 rounded-md border border-border p-3">
                                        <RadioGroupItem value="drop_invalid_fields" id="validation-drop-fields" />
                                        <div className="space-y-1">
                                            <Label htmlFor="validation-drop-fields" className="font-medium">
                                                Import anyway (drop invalid fields)
                                            </Label>
                                            <p className="text-xs text-muted-foreground">
                                                Import rows even if optional fields are invalid. Invalid values are
                                                cleared and recorded as warnings.
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-start space-x-3 rounded-md border border-border p-3">
                                        <RadioGroupItem value="skip_invalid_rows" id="validation-skip-rows" />
                                        <div className="space-y-1">
                                            <Label htmlFor="validation-skip-rows" className="font-medium">
                                                Skip invalid rows
                                            </Label>
                                            <p className="text-xs text-muted-foreground">
                                                Rows with any validation errors are skipped and logged.
                                            </p>
                                        </div>
                                    </div>
                                </RadioGroup>
                            </div>

                            <DialogFooter>
                                <Button
                                    variant="outline"
                                    onClick={() => setShowValidationDialog(false)}
                                    disabled={submitMutation.isPending}
                                >
                                    Review mappings
                                </Button>
                                <Button
                                    onClick={async () => {
                                        setShowValidationDialog(false)
                                        await submitImportWithMode(validationMode)
                                    }}
                                    disabled={submitMutation.isPending}
                                >
                                    {submitMutation.isPending ? (
                                        <>
                                            <Loader2Icon className="mr-2 size-4 animate-spin" />
                                            Submitting...
                                        </>
                                    ) : (
                                        "Submit import"
                                    )}
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </>
            )}
        </div>
    )
}
