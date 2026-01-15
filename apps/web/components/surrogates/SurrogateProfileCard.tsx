"use client"

import * as React from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
    ChevronDownIcon,
    ChevronUpIcon,
    RefreshCwIcon,
    SaveIcon,
    EyeIcon,
    EyeOffIcon,
    Loader2Icon,
    FileTextIcon,
    PencilIcon,
    XIcon,
    DownloadIcon,
    EditIcon,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useProfile, useSyncProfile, useSaveProfileOverrides, useToggleProfileHidden } from "@/lib/hooks/use-profile"
import { exportProfilePdf } from "@/lib/api/profile"
import type { FormSchema } from "@/lib/api/forms"
import type { JsonObject, JsonValue } from "@/lib/types/json"
import { formatLocalDate, parseDateInput } from "@/lib/utils/date"

interface SurrogateProfileCardProps {
    surrogateId: string
}

export function SurrogateProfileCard({ surrogateId }: SurrogateProfileCardProps) {
    const { data: profile, isLoading, error } = useProfile(surrogateId)
    const syncMutation = useSyncProfile()
    const saveMutation = useSaveProfileOverrides()
    const toggleHiddenMutation = useToggleProfileHidden()

    // Local edit state
    const [editedFields, setEditedFields] = React.useState<JsonObject>({})
    const [baselineOverrides, setBaselineOverrides] = React.useState<JsonObject>({})
    const [hiddenFields, setHiddenFields] = React.useState<string[]>([])
    const [baselineHidden, setBaselineHidden] = React.useState<string[]>([])
    const [revealedFields, setRevealedFields] = React.useState<Set<string>>(new Set())
    const [stagedChanges, setStagedChanges] = React.useState<Array<{ field_key: string; old_value: unknown; new_value: unknown }>>([])
    const [latestSubmissionId, setLatestSubmissionId] = React.useState<string | null>(null)
    const [isEditMode, setIsEditMode] = React.useState(false)
    const [sectionOpen, setSectionOpen] = React.useState<Record<number, boolean>>({})

    // Track which field is being edited
    const [editingField, setEditingField] = React.useState<string | null>(null)

    // Reset local state when profile changes
    React.useEffect(() => {
        if (profile) {
            const overrides = profile.overrides || {}
            const hidden = profile.hidden_fields || []
            setEditedFields(overrides)
            setBaselineOverrides(overrides)
            setHiddenFields(hidden)
            setBaselineHidden(hidden)
            setStagedChanges([])
            setLatestSubmissionId(null)
            setRevealedFields(new Set())
            setIsEditMode(false)
        }
    }, [profile])

    // Initialize section state
    React.useEffect(() => {
        if (!profile?.schema_snapshot?.pages) return
        const initialState: Record<number, boolean> = {}
        profile.schema_snapshot.pages.forEach((_page, index) => {
            initialState[index] = true
        })
        setSectionOpen(initialState)
    }, [profile?.schema_snapshot])

    const isSameOverrides = (a: JsonObject, b: JsonObject) => {
        const keys = new Set([...Object.keys(a), ...Object.keys(b)])
        for (const key of keys) {
            if (a[key] !== b[key]) return false
        }
        return true
    }

    const isSameHidden = (a: string[], b: string[]) => {
        if (a.length !== b.length) return false
        const setA = new Set(a)
        return b.every((item) => setA.has(item))
    }

    const hasOverrideChanges =
        !isSameOverrides(editedFields, baselineOverrides) || !!latestSubmissionId

    const hasChanges =
        !isSameOverrides(editedFields, baselineOverrides) ||
        !isSameHidden(hiddenFields, baselineHidden) ||
        stagedChanges.length > 0 ||
        !!latestSubmissionId

    const handleSync = async () => {
        try {
            if (!isEditMode) {
                setIsEditMode(true)
            }
            const result = await syncMutation.mutateAsync(surrogateId)
            if (result.staged_changes.length === 0) {
                toast.info("Profile is already up to date")
                return
            }
            setStagedChanges(result.staged_changes)
            setLatestSubmissionId(result.latest_submission_id)
            // Apply staged changes to editedFields
            const newEdits = { ...editedFields }
            result.staged_changes.forEach(change => {
                newEdits[change.field_key] = change.new_value
            })
            setEditedFields(newEdits)
            toast.success(`${result.staged_changes.length} changes staged. Click Save to apply.`)
        } catch {
            toast.error("Failed to sync profile")
        }
    }

    const handleSave = async () => {
        try {
            if (hasOverrideChanges) {
                await saveMutation.mutateAsync({
                    surrogateId,
                    overrides: editedFields,
                    newBaseSubmissionId: latestSubmissionId,
                })
            }
            const previousHidden = new Set(baselineHidden)
            const currentHidden = new Set(hiddenFields)
            const hiddenDiff = new Set<string>([
                ...baselineHidden.filter((field) => !currentHidden.has(field)),
                ...hiddenFields.filter((field) => !previousHidden.has(field)),
            ])

            for (const fieldKey of hiddenDiff) {
                await toggleHiddenMutation.mutateAsync({
                    surrogateId,
                    fieldKey,
                    hidden: currentHidden.has(fieldKey),
                })
            }
            toast.success("Profile saved")
            setStagedChanges([])
            setLatestSubmissionId(null)
            setIsEditMode(false)
            setRevealedFields(new Set())
        } catch {
            toast.error("Failed to save profile")
        }
    }

    const handleFieldChange = (fieldKey: string, value: JsonValue) => {
        setEditedFields(prev => ({ ...prev, [fieldKey]: value }))
    }

    const handleToggleHidden = (fieldKey: string) => {
        setHiddenFields((prev) =>
            prev.includes(fieldKey) ? prev.filter((key) => key !== fieldKey) : [...prev, fieldKey]
        )
        setRevealedFields((prev) => {
            const next = new Set(prev)
            next.delete(fieldKey)
            return next
        })
    }

    const handleReveal = (fieldKey: string) => {
        setRevealedFields((prev) => {
            const next = new Set(prev)
            if (next.has(fieldKey)) {
                next.delete(fieldKey)
            } else {
                next.add(fieldKey)
            }
            return next
        })
    }

    const cancelEditing = (fieldKey?: string) => {
        setEditingField(null)
        if (!fieldKey) return
        setEditedFields((prev) => {
            const next = { ...prev }
            if (baselineOverrides[fieldKey] === undefined) {
                delete next[fieldKey]
            } else {
                next[fieldKey] = baselineOverrides[fieldKey]
            }
            return next
        })
    }

    const handleCancel = () => {
        setEditedFields(baselineOverrides)
        setHiddenFields(baselineHidden)
        setStagedChanges([])
        setLatestSubmissionId(null)
        setEditingField(null)
        setIsEditMode(false)
        setRevealedFields(new Set())
    }

    const [isExporting, setIsExporting] = React.useState(false)

    const handleExport = async () => {
        setIsExporting(true)
        try {
            await exportProfilePdf(surrogateId)
            toast.success("Profile exported as PDF")
        } catch {
            toast.error("Failed to export profile")
        } finally {
            setIsExporting(false)
        }
    }

    // Loading state
    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-12">
                    <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading profile...</span>
                </CardContent>
            </Card>
        )
    }

    // Error state
    if (error) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                    <p className="text-sm text-muted-foreground">Unable to load profile card</p>
                </CardContent>
            </Card>
        )
    }

    // Empty state - no submission
    if (!profile?.base_submission_id) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Profile Card</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col items-center justify-center py-8 text-center">
                    <FileTextIcon className="h-12 w-12 text-muted-foreground/50 mb-4" />
                    <p className="text-sm text-muted-foreground">
                        No application submitted yet
                    </p>
                </CardContent>
            </Card>
        )
    }

    const schema = profile.schema_snapshot as FormSchema | null
    const pages = schema?.pages || []
    const hiddenFieldSet = new Set(hiddenFields)
    const revealedSet = revealedFields

    const renderFieldValue = (
        fieldKey: string,
        field: FormSchema["pages"][number]["fields"][number],
        value: unknown,
        baseValue: unknown,
        isHidden: boolean,
    ) => {
        // Editing mode
        if (isEditMode && editingField === fieldKey) {
            return (
                <div className="flex items-center gap-2">
                    <Input
                        value={String(editedFields[fieldKey] ?? value ?? "")}
                        onChange={(e) => handleFieldChange(fieldKey, e.target.value)}
                        className="h-8 text-sm"
                        autoFocus
                    />
                    <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={() => cancelEditing(fieldKey)}
                    >
                        <XIcon className="h-3.5 w-3.5" />
                    </Button>
                </div>
            )
        }

        // Hidden field
        if (isHidden && !revealedSet.has(fieldKey)) {
            return <span className="text-sm text-muted-foreground font-mono">******</span>
        }

        // Check for override (highlight yellow)
        const displayValue = editedFields[fieldKey] !== undefined ? editedFields[fieldKey] : value
        const isOverridden = baseValue !== displayValue
        const isStaged = stagedChanges.some(c => c.field_key === fieldKey)

        const valueClass = cn(
            "text-sm text-right",
            (isOverridden || isStaged) && "bg-yellow-100 dark:bg-yellow-900/30 px-1.5 py-0.5 rounded",
            isHidden && "text-muted-foreground"
        )

        if (displayValue === null || displayValue === undefined || displayValue === "") {
            return <span className="text-sm text-muted-foreground">—</span>
        }

        if (field.type === "date" && typeof displayValue === "string") {
            return <span className={valueClass}>{formatLocalDate(parseDateInput(displayValue))}</span>
        }

        if (typeof displayValue === "boolean") {
            const badge = displayValue ? (
                <Badge variant="default" className="bg-green-500 hover:bg-green-500/80">Yes</Badge>
            ) : (
                <Badge variant="secondary">No</Badge>
            )
            return <span className={valueClass}>{badge}</span>
        }

        if (Array.isArray(displayValue)) {
            return displayValue.length ? (
                <span className={valueClass}>{displayValue.join(", ")}</span>
            ) : (
                <span className="text-sm text-muted-foreground">—</span>
            )
        }

        return <span className={valueClass}>{String(displayValue)}</span>
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-lg">Profile Card</CardTitle>
                <div className="flex items-center gap-2">
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-7"
                        onClick={handleExport}
                        disabled={isExporting}
                    >
                        {isExporting ? (
                            <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <DownloadIcon className="h-3.5 w-3.5" />
                        )}
                        <span className="ml-1.5">Export</span>
                    </Button>
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-7"
                        onClick={handleSync}
                        disabled={syncMutation.isPending}
                    >
                        {syncMutation.isPending ? (
                            <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <RefreshCwIcon className="h-3.5 w-3.5" />
                        )}
                        <span className="ml-1.5">Sync</span>
                    </Button>
                    {isEditMode ? (
                        <Button
                            size="sm"
                            variant="ghost"
                            className="h-7"
                            onClick={handleCancel}
                        >
                            Cancel
                        </Button>
                    ) : (
                        <Button
                            size="sm"
                            className="h-7"
                            onClick={() => setIsEditMode(true)}
                        >
                            <EditIcon className="h-3.5 w-3.5 mr-1.5" />
                            Edit
                        </Button>
                    )}
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {pages.map((page, pageIndex) => (
                    <Collapsible
                        key={pageIndex}
                        open={sectionOpen[pageIndex] ?? true}
                        onOpenChange={(open) =>
                            setSectionOpen((prev) => ({ ...prev, [pageIndex]: open }))
                        }
                    >
                        <CollapsibleTrigger className="flex w-full items-center justify-between py-2 text-sm font-medium hover:text-primary transition-colors">
                            <span>{page.title || `Section ${pageIndex + 1}`}</span>
                            {(sectionOpen[pageIndex] ?? true) ? (
                                <ChevronUpIcon className="h-4 w-4" />
                            ) : (
                                <ChevronDownIcon className="h-4 w-4" />
                            )}
                        </CollapsibleTrigger>
                        <CollapsibleContent className="space-y-2 pt-2">
                            {page.fields
                                .filter((f) => f.type !== "file")
                                .map((field) => {
                                    const isHidden = hiddenFieldSet.has(field.key)
                                    const mergedValue = profile.merged_view[field.key]
                                    const baseValue = profile.base_answers[field.key]

                                    return (
                                        <div
                                            key={field.key}
                                            className="flex items-center justify-between gap-4 py-1.5 border-b border-border/50 last:border-0 group"
                                        >
                                            <span className="text-sm text-muted-foreground flex-shrink-0">
                                                {field.label}
                                            </span>
                                            <div className="flex items-center gap-2">
                                                {renderFieldValue(field.key, field, mergedValue, baseValue, isHidden)}

                                                {/* Edit button */}
                                                {isEditMode && !isHidden && editingField !== field.key && (
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        onClick={() => setEditingField(field.key)}
                                                    >
                                                        <PencilIcon className="h-3 w-3" />
                                                    </Button>
                                                )}

                                                {/* Temporary reveal for hidden fields */}
                                                {isHidden && (
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        onClick={() => handleReveal(field.key)}
                                                        aria-label={revealedSet.has(field.key) ? "Hide field value" : "Reveal field value"}
                                                        title={revealedSet.has(field.key) ? "Hide field value" : "Reveal field value"}
                                                    >
                                                        {revealedSet.has(field.key) ? (
                                                            <EyeOffIcon className="h-3 w-3" />
                                                        ) : (
                                                            <EyeIcon className="h-3 w-3" />
                                                        )}
                                                    </Button>
                                                )}

                                                {/* Persistent hide/unhide toggle (edit mode only) */}
                                                {isEditMode && (
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        onClick={() => handleToggleHidden(field.key)}
                                                        aria-label={isHidden ? "Unhide field" : "Hide field"}
                                                        title={isHidden ? "Unhide field" : "Hide field"}
                                                    >
                                                        {isHidden ? (
                                                            <EyeIcon className="h-3 w-3" />
                                                        ) : (
                                                            <EyeOffIcon className="h-3 w-3" />
                                                        )}
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })}
                        </CollapsibleContent>
                    </Collapsible>
                ))}

                {/* Floating save button */}
                {isEditMode && hasChanges && (
                    <div className="sticky bottom-0 pt-4 bg-gradient-to-t from-card to-transparent">
                        <Button
                            className="w-full bg-primary hover:bg-primary/90"
                            onClick={handleSave}
                            disabled={saveMutation.isPending || toggleHiddenMutation.isPending}
                        >
                            {saveMutation.isPending ? (
                                <Loader2Icon className="h-4 w-4 animate-spin mr-2" />
                            ) : (
                                <SaveIcon className="h-4 w-4 mr-2" />
                            )}
                            Save Changes
                            {stagedChanges.length > 0 && (
                                <Badge variant="secondary" className="ml-2">
                                    {stagedChanges.length} synced
                                </Badge>
                            )}
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
