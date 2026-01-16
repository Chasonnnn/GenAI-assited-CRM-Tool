"use client"

import { useState, useMemo } from "react"
import { HeartPulseIcon } from "lucide-react"
import { parseISO, differenceInDays, addDays, format, isValid } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { InlineDateField } from "@/components/inline-date-field"
import { SurrogateRead } from "@/lib/types/surrogate"
import { SurrogateUpdatePayload } from "@/lib/api/surrogates"

interface PregnancyData {
    gestationalDays: number           // Can be negative if start date is in future
    gestationalWeeks: number          // Clamped to 0 minimum
    dueDate: Date                     // The effective due date (manual or calculated)
    calculatedDueDate: Date           // Always the calculated date (280 days from start)
    trimester: 'First' | 'Second' | 'Third'
    daysRemaining: number
    progress: number                  // Clamped to 0-100
}

function usePregnancyTracker(
    startDate: string | null | undefined,
    dueDateOverride: string | null | undefined
): PregnancyData | null {
    return useMemo(() => {
        if (!startDate) return null

        const start = parseISO(startDate)
        if (!isValid(start)) return null

        const today = new Date()

        // Start date = LMP-equivalent = gestational day 0
        // Allow negative values so UI can show "future date" warning
        const gestationalDays = differenceInDays(today, start)

        // Clamp weeks to 0 minimum (don't show negative weeks)
        const gestationalWeeks = Math.max(0, Math.floor(gestationalDays / 7))

        // Always calculate what due date would be (for "Reset to calculated")
        const calculatedDueDate = addDays(start, 280)

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
            gestationalDays,
            gestationalWeeks,
            dueDate,
            calculatedDueDate,
            trimester,
            daysRemaining,
            progress,
        }
    }, [startDate, dueDateOverride])
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
        surrogateData.pregnancy_due_date
    )

    const hasManualDueDate = !!surrogateData.pregnancy_due_date
    const [isEditingDueDate, setIsEditingDueDate] = useState(false)

    const handleClearDueDateOverride = async () => {
        await onUpdate({ pregnancy_due_date: null })
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    <HeartPulseIcon className="size-4 text-pink-500" />
                    Pregnancy Tracker
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Week/Day Display - only show if start date is set and not future */}
                {pregnancy && pregnancy.gestationalDays >= 0 && (
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
                {pregnancy && pregnancy.gestationalDays < 0 && (
                    <div className="text-sm text-amber-600 bg-amber-50 dark:bg-amber-950/20 p-2 rounded">
                        Start date is in the future ({Math.abs(pregnancy.gestationalDays)} days from now)
                    </div>
                )}

                {/* Date inputs */}
                <div className="space-y-3 pt-2 border-t">
                    {/* Start Date (LMP-equivalent = day 0) */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground w-24 shrink-0">Start Date:</span>
                        <InlineDateField
                            value={surrogateData.pregnancy_start_date}
                            onSave={async (v) => {
                                await onUpdate({ pregnancy_start_date: v })
                            }}
                            label="Pregnancy start date (LMP-equivalent)"
                            placeholder="Set start date"
                        />
                    </div>

                    {/* Due Date with edit/clear controls (only show if start date is set) */}
                    {surrogateData.pregnancy_start_date && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-muted-foreground w-24 shrink-0">Due Date:</span>

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

                                    {hasManualDueDate ? (
                                        <>
                                            <Badge variant="outline" className="text-xs">manual</Badge>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 px-2 text-xs"
                                                onClick={() => setIsEditingDueDate(true)}
                                            >
                                                Edit
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 px-2 text-xs text-muted-foreground"
                                                onClick={handleClearDueDateOverride}
                                            >
                                                Reset to calculated
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            {pregnancy?.calculatedDueDate && (
                                                <Badge variant="secondary" className="text-xs">calculated</Badge>
                                            )}
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 px-2 text-xs"
                                                onClick={() => setIsEditingDueDate(true)}
                                            >
                                                Override
                                            </Button>
                                        </>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>

                {/* Trimester Badge */}
                {pregnancy && pregnancy.gestationalDays >= 0 && (
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

