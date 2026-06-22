"use client"

import { useState, useMemo, type KeyboardEvent } from "react"
import { HeartPulseIcon, Loader2Icon, PencilIcon, XIcon } from "lucide-react"
import { parseISO, differenceInDays, addDays, format, isValid } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { InlineDateField } from "@/components/inline-date-field"
import { InlineEditField } from "@/components/inline-edit-field"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { SurrogateRead } from "@/lib/types/surrogate"
import { EmbryoStage, SurrogateUpdatePayload } from "@/lib/api/surrogates"

const EMBRYO_STAGE_OPTIONS: { value: EmbryoStage; label: string; embryoAgeDays: number | null }[] = [
    { value: "day_3", label: "Day 3 embryo", embryoAgeDays: 3 },
    { value: "day_5", label: "Day 5 blastocyst", embryoAgeDays: 5 },
    { value: "day_6", label: "Day 6 blastocyst", embryoAgeDays: 6 },
    { value: "unknown", label: "Unknown / not provided", embryoAgeDays: null },
]

function getEmbryoAgeDays(stage: EmbryoStage | null | undefined) {
    return EMBRYO_STAGE_OPTIONS.find((option) => option.value === stage)?.embryoAgeDays ?? null
}

function formatEmbryoStage(stage: EmbryoStage | null | undefined) {
    return EMBRYO_STAGE_OPTIONS.find((option) => option.value === stage)?.label ?? "Unknown / not provided"
}

interface PregnancyData {
    daysSinceTransfer: number         // Can be negative if transfer date is in future
    gestationalDays: number           // IVF gestational age estimate
    gestationalWeeks: number          // Clamped to 0 minimum
    dueDate: Date                     // The effective due date (manual or calculated)
    calculatedDueDate: Date           // Calculated from transfer date and embryo stage when known
    trimester: 'First' | 'Second' | 'Third'
    daysRemaining: number
    progress: number                  // Clamped to 0-100
}

function usePregnancyTracker(
    startDate: string | null | undefined,
    dueDateOverride: string | null | undefined,
    embryoStage: EmbryoStage | null | undefined
): PregnancyData | null {
    return useMemo(() => {
        if (!startDate) return null

        const start = parseISO(startDate)
        if (!isValid(start)) return null

        const today = new Date()
        const embryoAgeDays = getEmbryoAgeDays(embryoStage)
        const daysSinceTransfer = differenceInDays(today, start)
        const gestationalDaysAtTransfer = embryoAgeDays == null ? 0 : 14 + embryoAgeDays
        const calculatedDueDateOffset = embryoAgeDays == null ? 280 : 266 - embryoAgeDays

        // For known IVF embryo stages, transfer date already includes embryo age.
        // Unknown preserves legacy LMP-style tracking until the clinic provides the stage.
        const gestationalDays = daysSinceTransfer + gestationalDaysAtTransfer

        // Clamp weeks to 0 minimum (don't show negative weeks)
        const gestationalWeeks = Math.max(0, Math.floor(gestationalDays / 7))

        // Always calculate what due date would be (for "Reset to calculated")
        const calculatedDueDate = addDays(start, calculatedDueDateOffset)

        // Due date: use override if provided and valid, else use calculated
        let dueDate = calculatedDueDate
        if (dueDateOverride) {
            const parsed = parseISO(dueDateOverride)
            if (isValid(parsed)) {
                dueDate = parsed
            }
        }

        // Trimester calculation (only meaningful for non-negative days)
        let trimester: 'First' | 'Second' | 'Third'
        if (gestationalWeeks < 13) trimester = 'First'
        else if (gestationalWeeks < 27) trimester = 'Second'
        else trimester = 'Third'

        const daysRemaining = Math.max(0, differenceInDays(dueDate, today))

        // Clamp progress to 0-100 (prevent negative progress bar)
        const progress = Math.max(0, Math.min(100, (gestationalDays / 280) * 100))

        return {
            daysSinceTransfer,
            gestationalDays,
            gestationalWeeks,
            dueDate,
            calculatedDueDate,
            trimester,
            daysRemaining,
            progress,
        }
    }, [startDate, dueDateOverride, embryoStage])
}

interface PregnancyTrackerCardProps {
    surrogateData: SurrogateRead
    onUpdate: (data: Partial<SurrogateUpdatePayload>) => Promise<void>
}

export function PregnancyTrackerCard({
    surrogateData,
    onUpdate,
}: PregnancyTrackerCardProps) {
    const pregnancy = usePregnancyTracker(
        surrogateData.pregnancy_start_date,
        surrogateData.pregnancy_due_date,
        surrogateData.embryo_stage
    )

    const hasManualDueDate = !!surrogateData.pregnancy_due_date
    const [isEditingDueDate, setIsEditingDueDate] = useState(false)
    const [isEditingEmbryoStage, setIsEditingEmbryoStage] = useState(false)
    const [isSavingEmbryoStage, setIsSavingEmbryoStage] = useState(false)
    const [embryoStageError, setEmbryoStageError] = useState<string | null>(null)

    const handleEditDueDate = () => {
        setIsEditingDueDate(true)
    }

    const handleEditEmbryoStage = () => {
        setEmbryoStageError(null)
        setIsEditingEmbryoStage(true)
    }

    const handleEmbryoStageDisplayKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
            e.preventDefault()
            handleEditEmbryoStage()
        }
    }

    const handleEmbryoStageChange = async (value: string | null) => {
        const nextValue = (value || "unknown") as EmbryoStage
        if (nextValue === (surrogateData.embryo_stage ?? "unknown")) {
            setIsEditingEmbryoStage(false)
            return
        }

        setIsSavingEmbryoStage(true)
        setEmbryoStageError(null)
        try {
            await onUpdate({ embryo_stage: nextValue })
            setIsEditingEmbryoStage(false)
        } catch (err) {
            setEmbryoStageError(err instanceof Error ? err.message : "Failed to save embryo stage")
        } finally {
            setIsSavingEmbryoStage(false)
        }
    }

    const embryoStageLabel = formatEmbryoStage(surrogateData.embryo_stage)
    const embryoStageIsPlaceholder = !surrogateData.embryo_stage || surrogateData.embryo_stage === "unknown"

    return (
        <Card className="gap-4 py-4">
            <CardHeader className="px-4 pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                    <HeartPulseIcon className="size-4 text-pink-500" />
                    Pregnancy Tracker
                </CardTitle>
            </CardHeader>
            <CardContent className="px-4 space-y-3">
                {/* Week/Day Display - only show if start date is set and not future */}
                {pregnancy && pregnancy.daysSinceTransfer >= 0 && (
                    <div className="flex items-center gap-4">
                        <div className="text-center">
                            <div className="text-3xl font-bold text-primary">
                                {pregnancy.gestationalWeeks}
                            </div>
                            <div className="text-xs text-muted-foreground">weeks</div>
                        </div>
                        <div className="text-center">
                            <div className="text-3xl font-bold">
                                {pregnancy.gestationalDays % 7}
                            </div>
                            <div className="text-xs text-muted-foreground">days</div>
                        </div>
                        <div className="flex-1">
                            {/* Progress bar */}
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-pink-500 rounded-full transition-all"
                                    style={{ width: `${pregnancy.progress}%` }}
                                />
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                                {pregnancy.daysRemaining} days remaining
                            </div>
                        </div>
                    </div>
                )}

                {/* Future date warning */}
                {pregnancy && pregnancy.daysSinceTransfer < 0 && (
                    <div className="text-sm text-amber-600 bg-amber-50 dark:bg-amber-950/20 p-2 rounded">
                        Transferred date is in the future ({Math.abs(pregnancy.daysSinceTransfer)} days from now)
                    </div>
                )}

                {/* Date inputs */}
                <div className="space-y-3 pt-2 border-t">
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground w-28 shrink-0">Embryo Stage:</span>
                        {isEditingEmbryoStage ? (
                            <div className="flex min-w-0 flex-col gap-1">
                                <div className="flex items-center gap-1">
                                    <Select
                                        value={surrogateData.embryo_stage ?? "unknown"}
                                        onValueChange={(value) => void handleEmbryoStageChange(value)}
                                        disabled={isSavingEmbryoStage}
                                    >
                                        <SelectTrigger
                                            aria-label="Embryo Stage"
                                            size="sm"
                                            className="h-8 w-48 rounded-md px-2.5 text-sm"
                                        >
                                            <SelectValue>
                                                {(value: string | null) =>
                                                    formatEmbryoStage(value as EmbryoStage | null)
                                                }
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent className="w-48 min-w-48 rounded-md border border-border shadow-lg">
                                            <SelectGroup>
                                                {EMBRYO_STAGE_OPTIONS.map((option) => (
                                                    <SelectItem key={option.value} value={option.value}>
                                                        {option.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectGroup>
                                        </SelectContent>
                                    </Select>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="icon"
                                        className="size-6"
                                        onClick={() => {
                                            setEmbryoStageError(null)
                                            setIsEditingEmbryoStage(false)
                                        }}
                                        disabled={isSavingEmbryoStage}
                                        aria-label="Cancel Embryo Stage"
                                    >
                                        {isSavingEmbryoStage ? (
                                            <Loader2Icon className="size-3 animate-spin" aria-hidden="true" />
                                        ) : (
                                            <XIcon className="size-3 text-destructive" aria-hidden="true" />
                                        )}
                                    </Button>
                                </div>
                                {embryoStageError && (
                                    <p className="text-xs text-destructive">{embryoStageError}</p>
                                )}
                            </div>
                        ) : (
                            <div
                                className="group -mx-1 flex w-fit cursor-pointer items-center gap-1 rounded px-1 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                onClick={handleEditEmbryoStage}
                                role="button"
                                tabIndex={0}
                                onKeyDown={handleEmbryoStageDisplayKeyDown}
                                aria-label="Edit Embryo Stage"
                            >
                                <span className={embryoStageIsPlaceholder ? "text-sm text-muted-foreground" : "text-sm font-medium"}>
                                    {embryoStageLabel}
                                </span>
                                <PencilIcon
                                    className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                                    aria-hidden="true"
                                />
                            </div>
                        )}
                    </div>

                    {/* Transferred Date */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground w-28 shrink-0">Transferred Date:</span>
                        <InlineDateField
                            value={surrogateData.pregnancy_start_date}
                            onSave={async (v) => {
                                await onUpdate({ pregnancy_start_date: v })
                            }}
                            label="Transferred date"
                            placeholder="Set transferred date"
                        />
                    </div>

                    {/* Due Date with inline editor (only show if start date is set) */}
                    {surrogateData.pregnancy_start_date && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground w-28 shrink-0">Due Date:</span>

                            {isEditingDueDate ? (
                                <InlineDateField
                                    value={surrogateData.pregnancy_due_date || (pregnancy?.calculatedDueDate ? format(pregnancy.calculatedDueDate, 'yyyy-MM-dd') : '')}
                                    onSave={async (v) => {
                                        await onUpdate({ pregnancy_due_date: v })
                                        setIsEditingDueDate(false)
                                    }}
                                    label="Pregnancy due date"
                                    placeholder="Set due date"
                                />
                            ) : (
                                <>
                                    <span className="text-sm font-medium">
                                        {pregnancy?.dueDate ? format(pregnancy.dueDate, 'MMM d, yyyy') : '-'}
                                    </span>

                                    <Badge
                                        variant={hasManualDueDate ? "outline" : "secondary"}
                                        className="text-xs cursor-pointer select-none"
                                        render={
                                            <button
                                                type="button"
                                                className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                            />
                                        }
                                        onClick={handleEditDueDate}
                                        title="Edit due date"
                                    >
                                        {hasManualDueDate ? "manual" : "calculated"}
                                    </Badge>
                                </>
                            )}
                        </div>
                    )}

                    {/* Actual Delivery Date - shown once pregnancy tracking has started */}
                    {surrogateData.pregnancy_start_date && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground w-28 shrink-0">Actual Delivery Date:</span>
                            <InlineDateField
                                value={surrogateData.actual_delivery_date}
                                onSave={async (v) => {
                                    await onUpdate({ actual_delivery_date: v })
                                }}
                                label="Actual delivery date"
                                placeholder="Set when delivered"
                            />
                            {surrogateData.actual_delivery_date && (
                                <Badge variant="default" className="text-xs bg-green-500/10 text-green-600 border-green-500/20">
                                    Delivered
                                </Badge>
                            )}
                        </div>
                    )}

                    {surrogateData.actual_delivery_date && (
                        <>
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground w-28 shrink-0">Gender:</span>
                                <InlineEditField
                                    value={surrogateData.delivery_baby_gender ?? undefined}
                                    onSave={async (v) => {
                                        await onUpdate({ delivery_baby_gender: v || null })
                                    }}
                                    placeholder="Set gender"
                                    label="Delivery gender"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm text-muted-foreground w-28 shrink-0">Weight:</span>
                                <InlineEditField
                                    value={surrogateData.delivery_baby_weight ?? undefined}
                                    onSave={async (v) => {
                                        await onUpdate({ delivery_baby_weight: v || null })
                                    }}
                                    placeholder="Set weight"
                                    label="Delivery weight"
                                />
                            </div>
                        </>
                    )}
                </div>

                {/* Trimester Badge */}
                {pregnancy && pregnancy.daysSinceTransfer >= 0 && (
                    <Badge variant="secondary" className="mt-2">
                        {pregnancy.trimester} Trimester
                    </Badge>
                )}

                {/* Empty state */}
                {!pregnancy && !surrogateData.pregnancy_start_date && (
                    <p className="text-sm text-muted-foreground text-center py-2">
                        Set a start date to track pregnancy progress
                    </p>
                )}
            </CardContent>
        </Card>
    )
}
