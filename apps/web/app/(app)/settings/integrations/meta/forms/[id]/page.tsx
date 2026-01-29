"use client"

import { useEffect, useMemo, useState } from "react"
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
import { useMetaFormMapping, useUpdateMetaFormMapping } from "@/lib/hooks/use-meta-forms"
import { useAiMapImport } from "@/lib/hooks/use-import"
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
    { value: "height_flexible", label: "Height (flexible)" },
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

export default function MetaFormMappingPage() {
    const params = useParams()
    const router = useRouter()
    const formId = params?.id as string

    const { data, isLoading } = useMetaFormMapping(formId)
    const updateMutation = useUpdateMetaFormMapping(formId)
    const aiMapMutation = useAiMapImport()

    const [mappings, setMappings] = useState<ColumnMappingDraft[]>([])
    const [unknownColumnBehavior, setUnknownColumnBehavior] = useState<UnknownColumnBehavior>("metadata")
    const [touchedColumns, setTouchedColumns] = useState<Set<string>>(new Set())
    const [error, setError] = useState<string>("")

    const columnLabels = useMemo(() => {
        const map = new Map<string, string>()
        data?.columns.forEach((col) => {
            map.set(col.key, col.label || col.key)
        })
        return map
    }, [data])

    useEffect(() => {
        if (!data) return
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

        const touched = new Set<string>(rules.map((rule) => rule.csv_column))
        setTouchedColumns(touched)
        const behavior = data.unknown_column_behavior || "metadata"
        setUnknownColumnBehavior(behavior)
        setMappings(applyUnknownColumnBehavior(merged, behavior, touched))
    }, [data])

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
        if (!data) return
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
            setError(err instanceof Error ? err.message : "AI mapping failed")
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

    if (isLoading || !data) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div>
                        <h1 className="text-2xl font-semibold">{data.form.form_name}</h1>
                        <p className="text-sm text-muted-foreground">{data.form.form_external_id}</p>
                    </div>
                    <Button variant="ghost" onClick={() => router.push("/settings/integrations/meta/forms")}>
                        <ArrowLeftIcon className="mr-2 size-4" />
                        Back to forms
                    </Button>
                </div>
            </div>

            <div className="flex-1 space-y-6 p-6">
                {data.form.mapping_status === "outdated" && (
                    <Alert variant="destructive">
                        <AlertTitle>Mapping outdated</AlertTitle>
                        <AlertDescription>
                            This form changed in Meta. Update mappings before leads can convert.
                        </AlertDescription>
                    </Alert>
                )}

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
                                {data.ai_available && (
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
                                        <TableHead>Field</TableHead>
                                        <TableHead>Samples</TableHead>
                                        <TableHead>Action</TableHead>
                                        <TableHead>Map To</TableHead>
                                        <TableHead>Transform</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {mappings.map((mapping) => (
                                        <TableRow key={mapping.csv_column}>
                                            <TableCell className="font-medium">
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2">
                                                        <span>{columnLabels.get(mapping.csv_column) || mapping.csv_column}</span>
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
                                                            updateMapping(mapping.csv_column, { action: "map" })
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
                                                            {data.available_fields.map((field) => (
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
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>

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
                                                    {row[col.key] || <span className="text-muted-foreground">—</span>}
                                                </TableCell>
                                            ))}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>

                {error && (
                    <Alert variant="destructive">
                        <AlertTitle>Unable to save</AlertTitle>
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}

                <div className="flex items-center justify-end gap-3">
                    <Button variant="outline" onClick={() => router.push("/settings/integrations/meta/forms")}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={updateMutation.isPending}>
                        {updateMutation.isPending ? (
                            <>
                                <Loader2Icon className="mr-2 size-4 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            "Save mapping"
                        )}
                    </Button>
                </div>

                {data.form.unconverted_leads > 0 && (
                    <Alert>
                        <AlertTitle>Reprocess queued</AlertTitle>
                        <AlertDescription>
                            Saving will reprocess {data.form.unconverted_leads} unconverted lead(s).
                        </AlertDescription>
                    </Alert>
                )}
            </div>
        </div>
    )
}
