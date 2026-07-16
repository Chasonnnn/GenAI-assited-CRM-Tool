"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Loader2Icon, SparklesIcon, ArrowLeftIcon } from "lucide-react"
import {
    useMetaFormMapping,
    useReconvertMetaFormLeads,
    useMetaFormUnconvertedLeads,
    useUpdateMetaFormMapping,
} from "@/lib/hooks/use-meta-forms"
import { useAiMapImport } from "@/lib/hooks/use-import"
import {
    applyUnknownColumnBehavior,
    buildColumnMappingsFromSuggestions,
    buildImportSubmitPayload,
    type ColumnMappingDraft,
    type UnknownColumnBehavior,
} from "@/lib/import-utils"
import { getSurrogateFieldLabel } from "@/lib/constants/surrogate-field-labels"

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

const UNKNOWN_COLUMN_BEHAVIOR_OPTIONS = [
    { value: "ignore", label: "Ignore" },
    { value: "metadata", label: "Store metadata" },
    { value: "warn", label: "Warn only" },
] satisfies Array<{ value: UnknownColumnBehavior; label: string }>

const ACTION_LABELS = new Map(ACTION_OPTIONS.map((option) => [option.value, option.label]))
const TRANSFORM_LABELS = new Map(TRANSFORM_OPTIONS.map((option) => [option.value, option.label]))
const UNKNOWN_COLUMN_BEHAVIOR_LABELS = new Map(
    UNKNOWN_COLUMN_BEHAVIOR_OPTIONS.map((option) => [option.value, option.label])
)

function getActionLabel(value: string | null) {
    return value ? ACTION_LABELS.get(value) ?? value : "Action"
}

function getTransformationLabel(value: string | null) {
    return value ? TRANSFORM_LABELS.get(value) ?? value : "None"
}

function getUnknownColumnBehaviorLabel(value: UnknownColumnBehavior | null) {
    return value ? UNKNOWN_COLUMN_BEHAVIOR_LABELS.get(value) ?? value : "Store metadata"
}

type MetaFormMappingData = NonNullable<ReturnType<typeof useMetaFormMapping>["data"]>
type MetaFormUnconvertedLeadData = NonNullable<ReturnType<typeof useMetaFormUnconvertedLeads>["data"]>
type UpdateMapping = (csvColumn: string, patch: Partial<ColumnMappingDraft>) => void

function MetaFormMappingHeader({
    formExternalId,
    formName,
    onBack,
}: {
    formExternalId: string
    formName: string
    onBack: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <div>
                    <h1 className="text-2xl font-semibold">{formName}</h1>
                    <p className="text-sm text-muted-foreground">{formExternalId}</p>
                </div>
                <Button variant="ghost" onClick={onBack}>
                    <ArrowLeftIcon className="mr-2 size-4" aria-hidden="true" />
                    Back to forms
                </Button>
            </div>
        </div>
    )
}

function MetaMappingOutdatedAlert() {
    return (
        <Alert variant="destructive">
            <AlertTitle>Mapping outdated</AlertTitle>
            <AlertDescription>
                This form changed in Meta. Update mappings before leads can convert.
            </AlertDescription>
        </Alert>
    )
}

function MetaColumnMappingCard({
    aiMapPending,
    columnLabels,
    data,
    mappings,
    onAiHelp,
    onUnknownBehaviorChange,
    onUpdateMapping,
    unknownColumnBehavior,
}: {
    aiMapPending: boolean
    columnLabels: ReadonlyMap<string, string>
    data: MetaFormMappingData
    mappings: ColumnMappingDraft[]
    onAiHelp: () => Promise<void>
    onUnknownBehaviorChange: (value: UnknownColumnBehavior) => void
    onUpdateMapping: UpdateMapping
    unknownColumnBehavior: UnknownColumnBehavior
}) {
    return (
        <Card className="overflow-hidden">
            <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <CardTitle>Column Mapping</CardTitle>
                        <CardDescription>
                            Map Meta fields to surrogate fields.
                        </CardDescription>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span>Unknown columns:</span>
                            <Select
                                value={unknownColumnBehavior}
                                onValueChange={(value) =>
                                    onUnknownBehaviorChange(value as UnknownColumnBehavior)
                                }
                            >
                                <SelectTrigger
                                    className="h-8 w-[140px]"
                                    aria-label="Unknown columns behavior"
                                >
                                    <SelectValue>
                                        {(value: string | null) =>
                                            getUnknownColumnBehaviorLabel(
                                                value as UnknownColumnBehavior | null
                                            )
                                        }
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent>
                                    {UNKNOWN_COLUMN_BEHAVIOR_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        {data.ai_available && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    void onAiHelp()
                                }}
                                disabled={aiMapPending}
                            >
                                {aiMapPending ? (
                                    <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                                ) : (
                                    <SparklesIcon className="mr-2 size-4" aria-hidden="true" />
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
                                <TableHead>Field</TableHead>
                                <TableHead>Samples</TableHead>
                                <TableHead>Action</TableHead>
                                <TableHead>Map To</TableHead>
                                <TableHead>Transform</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {mappings.map((mapping) => (
                                <MetaColumnMappingRow
                                    key={mapping.csv_column}
                                    availableFields={data.available_fields}
                                    columnLabel={columnLabels.get(mapping.csv_column) || mapping.csv_column}
                                    mapping={mapping}
                                    onUpdateMapping={onUpdateMapping}
                                />
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    )
}

function MetaColumnMappingRow({
    availableFields,
    columnLabel,
    mapping,
    onUpdateMapping,
}: {
    availableFields: string[]
    columnLabel: string
    mapping: ColumnMappingDraft
    onUpdateMapping: UpdateMapping
}) {
    return (
        <TableRow>
            <TableCell className="font-medium">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <span>{columnLabel}</span>
                        <Badge variant="secondary" className="text-xs">
                            {mapping.csv_column}
                        </Badge>
                    </div>
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
                            onUpdateMapping(mapping.csv_column, { action: "map" })
                        } else if (value === "custom") {
                            onUpdateMapping(mapping.csv_column, {
                                action: "custom",
                                surrogate_field: null,
                            })
                        } else {
                            onUpdateMapping(mapping.csv_column, {
                                action: value as ColumnMappingDraft["action"],
                                surrogate_field: null,
                                transformation: null,
                            })
                        }
                    }}
                >
                    <SelectTrigger
                        className="w-[130px]"
                        aria-label={`Action for ${mapping.csv_column}`}
                    >
                        <SelectValue placeholder="Action">
                            {(value: string | null) => getActionLabel(value)}
                        </SelectValue>
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
                            onUpdateMapping(mapping.csv_column, {
                                surrogate_field: value || null,
                                action: "map",
                            })
                        }
                    >
                        <SelectTrigger
                            className="w-[180px]"
                            aria-label={`Map ${mapping.csv_column} to field`}
                        >
                            <SelectValue placeholder="Select field">
                                {(value: string | null) =>
                                    getSurrogateFieldLabel(value) ?? "Select field"
                                }
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            {availableFields.map((field) => (
                                <SelectItem key={field} value={field}>
                                    {getSurrogateFieldLabel(field) ?? "Unknown field"}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                ) : mapping.action === "custom" ? (
                    <Input
                        value={mapping.custom_field_key || ""}
                        onChange={(event) =>
                            onUpdateMapping(mapping.csv_column, {
                                custom_field_key: event.target.value,
                            })
                        }
                        placeholder="custom_field_key"
                        className="w-[180px]"
                        name={`custom-field-${mapping.csv_column}`}
                        autoComplete="off"
                        aria-label={`Custom field key for ${mapping.csv_column}`}
                    />
                ) : (
                    <span className="text-xs text-muted-foreground">No custom field</span>
                )}
            </TableCell>
            <TableCell>
                <Select
                    value={mapping.transformation || ""}
                    onValueChange={(value) =>
                        onUpdateMapping(mapping.csv_column, {
                            transformation: value || null,
                        })
                    }
                    disabled={mapping.action !== "map"}
                >
                    <SelectTrigger
                        className="w-[170px]"
                        aria-label={`Transform ${mapping.csv_column}`}
                    >
                        <SelectValue placeholder="None">
                            {(value: string | null) => getTransformationLabel(value)}
                        </SelectValue>
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
    )
}

function MetaMappingPreviewCard({ data }: { data: MetaFormMappingData }) {
    return (
        <Card className="overflow-hidden">
            <CardHeader>
                <CardTitle>Preview</CardTitle>
                <CardDescription>
                    {data.has_live_leads ? "Live lead samples" : "Sample data (no live leads yet)"}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="max-h-[360px] overflow-auto">
                    <Table>
                        <TableHeader className="sticky top-0 z-10 bg-background">
                            <TableRow>
                                {(data.columns || []).map((col) => (
                                    <TableHead key={col.key}>{col.label || col.key}</TableHead>
                                ))}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.sample_rows.map((row, rowIdx) => (
                                <TableRow key={rowIdx}>
                                    {(data.columns || []).map((col) => (
                                        <TableCell key={col.key}>
                                            {row[col.key] || <span className="text-muted-foreground">Empty</span>}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    )
}

function MetaMappingActions({
    error,
    isSaving,
    onCancel,
    onSave,
}: {
    error: string
    isSaving: boolean
    onCancel: () => void
    onSave: () => Promise<void>
}) {
    return (
        <>
            {error && (
                <Alert variant="destructive">
                    <AlertTitle>Unable to save</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            )}

            <div className="flex items-center justify-end gap-3">
                <Button variant="outline" onClick={onCancel}>
                    Cancel
                </Button>
                <Button
                    onClick={() => {
                        void onSave()
                    }}
                    disabled={isSaving}
                >
                    {isSaving ? (
                        <>
                            <Loader2Icon className="mr-2 size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                            Saving…
                        </>
                    ) : (
                        "Save mapping"
                    )}
                </Button>
            </div>
        </>
    )
}

function MetaUnconvertedLeadsCard({
    leadCount,
    reconvertMessage,
    reconvertPending,
    unconvertedLeadData,
    unconvertedLeadsLoading,
    onReconvert,
}: {
    leadCount: number
    reconvertMessage: string
    reconvertPending: boolean
    unconvertedLeadData: MetaFormUnconvertedLeadData | undefined
    unconvertedLeadsLoading: boolean
    onReconvert: () => Promise<void>
}) {
    return (
        <Card className="overflow-hidden">
            <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <CardTitle>Unconverted Leads</CardTitle>
                        <CardDescription>
                            {unconvertedLeadData
                                ? `${unconvertedLeadData.eligible_count} eligible, ${unconvertedLeadData.blocked_count} blocked.`
                                : `Saving will reprocess ${leadCount} unconverted lead(s).`}
                        </CardDescription>
                    </div>
                    <Button
                        size="sm"
                        onClick={() => {
                            void onReconvert()
                        }}
                        disabled={
                            reconvertPending ||
                            !unconvertedLeadData ||
                            unconvertedLeadData.eligible_count === 0
                        }
                    >
                        {reconvertPending ? (
                            <>
                                <Loader2Icon
                                    className="mr-2 size-4 animate-spin motion-reduce:animate-none"
                                    aria-hidden="true"
                                />
                                Queueing…
                            </>
                        ) : (
                            "Re-convert eligible leads"
                        )}
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                <Alert>
                    <AlertTitle>Reprocess queued</AlertTitle>
                    <AlertDescription>
                        Review the current failure reasons below before saving a new mapping.
                    </AlertDescription>
                </Alert>
                {reconvertMessage && (
                    <Alert>
                        <AlertTitle>Reconversion queued</AlertTitle>
                        <AlertDescription>{reconvertMessage}</AlertDescription>
                    </Alert>
                )}
                {unconvertedLeadsLoading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2Icon
                            className="size-4 animate-spin motion-reduce:animate-none"
                            aria-hidden="true"
                        />
                        Loading unconverted leads…
                    </div>
                ) : unconvertedLeadData?.items.length ? (
                    <MetaUnconvertedLeadsTable items={unconvertedLeadData.items} />
                ) : (
                    <p className="text-sm text-muted-foreground">
                        No unconverted leads are currently queued for this form.
                    </p>
                )}
            </CardContent>
        </Card>
    )
}

function MetaUnconvertedLeadsTable({ items }: { items: MetaFormUnconvertedLeadData["items"] }) {
    return (
        <div className="max-h-[360px] overflow-auto">
            <Table>
                <TableHeader className="sticky top-0 z-10 bg-background">
                    <TableRow>
                        <TableHead>Lead ID</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Retry</TableHead>
                        <TableHead>Reason</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {items.map((lead) => (
                        <TableRow key={lead.id}>
                            <TableCell className="font-mono text-xs">
                                {lead.meta_lead_id}
                            </TableCell>
                            <TableCell>{lead.full_name || "—"}</TableCell>
                            <TableCell>{lead.email || "—"}</TableCell>
                            <TableCell>
                                <Badge variant="secondary">{lead.status}</Badge>
                            </TableCell>
                            <TableCell>
                                {lead.reprocess_eligible ? (
                                    <Badge>Eligible</Badge>
                                ) : (
                                    <Badge variant="outline">Blocked</Badge>
                                )}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                                {lead.reprocess_block_reason
                                    ? lead.reprocess_block_reason.replace(/_/g, " ")
                                    : lead.conversion_error || "Awaiting mapping"}
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    )
}

export default function MetaFormMappingPage() {
    const params = useParams()
    const { push } = useRouter()
    const formId = params?.id as string

    const { data, isLoading } = useMetaFormMapping(formId)
    const { data: unconvertedLeadData, isLoading: unconvertedLeadsLoading } =
        useMetaFormUnconvertedLeads(formId, (data?.form.unconverted_leads || 0) > 0)
    const updateMutation = useUpdateMetaFormMapping(formId)
    const reconvertMutation = useReconvertMetaFormLeads(formId)
    const aiMapMutation = useAiMapImport()

    const [mappingOverrides, setMappingOverrides] = useState<Record<string, ColumnMappingDraft>>({})
    const [unknownColumnBehaviorOverride, setUnknownColumnBehaviorOverride] =
        useState<UnknownColumnBehavior | null>(null)
    const [error, setError] = useState<string>("")
    const [reconvertMessage, setReconvertMessage] = useState<string>("")

    const columnLabels = new Map(
        data?.columns.map((col) => [col.key, col.label || col.key] as const) ?? []
    )

    const serverMappingState = (() => {
        if (!data) {
            return {
                mappings: [] as ColumnMappingDraft[],
                touchedColumns: new Set<string>(),
                unknownColumnBehavior: "metadata" as UnknownColumnBehavior,
            }
        }
        const base = buildColumnMappingsFromSuggestions(data.column_suggestions)
        const rules = data.mapping_rules || []
        const ruleMap = new Map(rules.map((rule) => [rule.csv_column, rule]))

        const merged = base.map((mapping) => {
            const override = ruleMap.get(mapping.csv_column)
            if (!override) return mapping
            return {
                ...mapping,
                action: override.action,
                surrogate_field: override.action === "map" ? override.surrogate_field : null,
                transformation: override.action === "map" ? override.transformation : null,
                custom_field_key: override.action === "custom" ? override.custom_field_key ?? null : null,
            }
        })

        return {
            mappings: merged,
            touchedColumns: new Set<string>(rules.map((rule) => rule.csv_column)),
            unknownColumnBehavior: data.unknown_column_behavior || "metadata",
        }
    })()
    const unknownColumnBehavior =
        unknownColumnBehaviorOverride ?? serverMappingState.unknownColumnBehavior
    const touchedColumns = new Set(serverMappingState.touchedColumns)
    for (const csvColumn of Object.keys(mappingOverrides)) {
        touchedColumns.add(csvColumn)
    }
    const mappings = applyUnknownColumnBehavior(
        serverMappingState.mappings.map(
            (mapping) => mappingOverrides[mapping.csv_column] ?? mapping
        ),
        unknownColumnBehavior,
        touchedColumns
    )

    const updateMapping = (csvColumn: string, patch: Partial<ColumnMappingDraft>) => {
        const currentMapping = mappings.find((mapping) => mapping.csv_column === csvColumn)
        if (!currentMapping) return
        setMappingOverrides((previous) => ({
            ...previous,
            [csvColumn]: { ...currentMapping, ...patch },
        }))
    }

    const handleUnknownBehaviorChange = (value: UnknownColumnBehavior) => {
        setUnknownColumnBehaviorOverride(value)
    }

    const handleAiHelp = async () => {
        if (!data) return
        const unmatched: string[] = []
        const sampleValues: Record<string, string[]> = {}
        for (const mapping of mappings) {
            sampleValues[mapping.csv_column] = mapping.sample_values || []
            if (!mapping.surrogate_field && mapping.action !== "custom") {
                unmatched.push(mapping.csv_column)
            }
        }

        if (unmatched.length === 0) return

        try {
            const result = await aiMapMutation.mutateAsync({
                unmatched_columns: unmatched,
                sample_values: sampleValues,
            })

            setMappingOverrides((previous) => {
                const next = { ...previous }
                for (const mapping of mappings) {
                    const suggestion = result.suggestions.find(
                        (item) => item.csv_column === mapping.csv_column
                    )
                    if (!suggestion) continue

                    const derived = buildColumnMappingsFromSuggestions([suggestion])[0]
                    if (!derived) continue

                    const shouldAdopt =
                        (!mapping.surrogate_field &&
                            (mapping.action === "ignore" || mapping.action === "metadata")) ||
                        mapping.action === "custom"

                    next[mapping.csv_column] = {
                        ...mapping,
                        ...derived,
                        action: shouldAdopt ? derived.action : mapping.action,
                        surrogate_field: shouldAdopt ? derived.surrogate_field : mapping.surrogate_field,
                        transformation: shouldAdopt ? derived.transformation : mapping.transformation,
                        custom_field_key: shouldAdopt ? derived.custom_field_key : mapping.custom_field_key,
                        sample_values: mapping.sample_values.length ? mapping.sample_values : derived.sample_values,
                    }
                }
                return next
            })
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "AI mapping failed")
        }
    }

    const ensureRequiredMappings = () => {
        const mappedFields = new Set<string>()
        for (const mapping of mappings) {
            if (mapping.action === "map" && mapping.surrogate_field) {
                mappedFields.add(mapping.surrogate_field)
            }
        }

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

    const handleSave = async () => {
        if (!data) return
        setError("")
        if (!ensureRequiredMappings()) return

        const payload = buildImportSubmitPayload(mappings, unknownColumnBehavior, touchedColumns)
        try {
            await updateMutation.mutateAsync({
                column_mappings: payload.column_mappings,
                unknown_column_behavior: payload.unknown_column_behavior,
            })
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to save mapping")
        }
    }

    const handleReconvert = async () => {
        setError("")
        setReconvertMessage("")
        try {
            const result = await reconvertMutation.mutateAsync()
            const blockedSummary = Object.entries(result.blocked_reasons || {})
                .map(([reason, count]) => `${count} ${reason.replace(/_/g, " ")}`)
                .join(", ")
            setReconvertMessage(
                [
                    result.message || `Queued ${result.queued_count} lead(s) for reconversion.`,
                    blockedSummary ? `Skipped ${blockedSummary}.` : "",
                ]
                    .filter(Boolean)
                    .join(" ")
            )
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to queue reconversion")
        }
    }

    if (isLoading || !data) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin motion-reduce:animate-none text-muted-foreground" aria-hidden="true" />
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            <MetaFormMappingHeader
                formExternalId={data.form.form_external_id}
                formName={data.form.form_name}
                onBack={() => push("/settings/integrations/meta/forms")}
            />

            <div className="flex-1 space-y-6 p-6">
                {data.form.mapping_status === "outdated" && <MetaMappingOutdatedAlert />}

                <MetaColumnMappingCard
                    aiMapPending={aiMapMutation.isPending}
                    columnLabels={columnLabels}
                    data={data}
                    mappings={mappings}
                    onAiHelp={handleAiHelp}
                    onUnknownBehaviorChange={handleUnknownBehaviorChange}
                    onUpdateMapping={updateMapping}
                    unknownColumnBehavior={unknownColumnBehavior}
                />

                <MetaMappingPreviewCard data={data} />

                <MetaMappingActions
                    error={error}
                    isSaving={updateMutation.isPending}
                    onCancel={() => push("/settings/integrations/meta/forms")}
                    onSave={handleSave}
                />

                {data.form.unconverted_leads > 0 && (
                    <MetaUnconvertedLeadsCard
                        leadCount={data.form.unconverted_leads}
                        reconvertMessage={reconvertMessage}
                        reconvertPending={reconvertMutation.isPending}
                        unconvertedLeadData={unconvertedLeadData}
                        unconvertedLeadsLoading={unconvertedLeadsLoading}
                        onReconvert={handleReconvert}
                    />
                )}
            </div>
        </div>
    )
}
