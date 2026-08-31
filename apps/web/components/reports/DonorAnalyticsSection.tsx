"use client"

import { useState } from "react"
import { AlertCircleIcon } from "lucide-react"

import { useAuth } from "@/lib/auth-context"
import {
    useDonorAnalyticsSummary,
    useDonorsByStatus,
    useDonorsTrend,
} from "@/lib/hooks/use-analytics"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
import { useDefaultPipeline } from "@/lib/hooks/use-pipelines"
import type { DonorType } from "@/lib/api/analytics"
import { getDonorPipelineEntityType } from "@/lib/types/donor"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

type DonorAnalyticsSectionProps = {
    dateParams: {
        from_date?: string
        to_date?: string
    }
}

const DONOR_TYPE_LABELS: Record<DonorType, string> = {
    egg: "Egg Donors",
    sperm: "Sperm Donors",
}

function SummaryValue({ value, loading }: { value: string | number; loading: boolean }) {
    if (loading) return <Skeleton className="h-8 w-20" />
    return <div className="text-2xl font-bold">{value}</div>
}

export function DonorAnalyticsSection({ dateParams }: DonorAnalyticsSectionProps) {
    const { user } = useAuth()
    const [donorType, setDonorType] = useState<DonorType>("egg")
    const permissionsQuery = useEffectivePermissions(user?.user_id ?? null)
    const isDeveloper = user?.role === "developer"
    const canViewDonors = isDeveloper
        || (permissionsQuery.data?.permissions ?? []).includes("view_donors")
    const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
    const params = {
        donor_type: donorType,
        period: "day" as const,
        timezone: browserTimezone,
        ...dateParams,
    }
    const summaryQuery = useDonorAnalyticsSummary(params, { enabled: canViewDonors })
    const statusQuery = useDonorsByStatus(params, { enabled: canViewDonors })
    const trendQuery = useDonorsTrend(params, { enabled: canViewDonors })
    const pipelineQuery = useDefaultPipeline(getDonorPipelineEntityType(donorType), canViewDonors)

    if (!isDeveloper && (permissionsQuery.isLoading || !canViewDonors)) return null

    const pipeline = pipelineQuery.data
    const colorByStage = new Map(pipeline?.stages.map((stage) => [stage.id, stage.color]) ?? [])
    const statusRows = statusQuery.data ?? []
    const trendRows = trendQuery.data ?? []
    const maxStatusCount = Math.max(1, ...statusRows.map((row) => row.count))
    const maxTrendCount = Math.max(1, ...trendRows.map((row) => row.count))
    const summary = summaryQuery.data
    const isError = summaryQuery.isError || statusQuery.isError || trendQuery.isError

    return (
        <section className="space-y-4" aria-labelledby="donor-analytics-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 id="donor-analytics-title" className="text-xl font-semibold">Donors</h2>
                <ToggleGroup
                    value={[donorType]}
                    aria-label="Donor report type"
                    onValueChange={(value) => {
                        const nextValue = Array.isArray(value) ? value[0] : value
                        if (nextValue === "egg" || nextValue === "sperm") setDonorType(nextValue)
                    }}
                    variant="outline"
                    size="sm"
                    spacing={0}
                >
                    <ToggleGroupItem value="egg">Egg Donors</ToggleGroupItem>
                    <ToggleGroupItem value="sperm">Sperm Donors</ToggleGroupItem>
                </ToggleGroup>
            </div>

            {isError ? (
                <Card>
                    <CardContent className="flex h-32 items-center justify-center text-destructive">
                        <AlertCircleIcon className="mr-2 size-4" /> Unable to load donor analytics
                    </CardContent>
                </Card>
            ) : (
                <>
                    <div className="grid gap-4 md:grid-cols-4">
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Total</CardTitle></CardHeader>
                            <CardContent>
                                <SummaryValue value={summary?.total_donors ?? 0} loading={summaryQuery.isLoading} />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">New This Period</CardTitle></CardHeader>
                            <CardContent>
                                <SummaryValue value={summary?.new_this_period ?? 0} loading={summaryQuery.isLoading} />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Qualification Rate</CardTitle></CardHeader>
                            <CardContent>
                                <SummaryValue value={`${summary?.qualification_rate ?? 0}%`} loading={summaryQuery.isLoading} />
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2"><CardTitle className="text-sm">Average to Qualification</CardTitle></CardHeader>
                            <CardContent>
                                <SummaryValue
                                    value={summary?.avg_time_to_qualification_hours == null
                                        ? "—"
                                        : `${Math.round(summary.avg_time_to_qualification_hours / 24)}d`}
                                    loading={summaryQuery.isLoading}
                                />
                            </CardContent>
                        </Card>
                    </div>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <Card>
                            <CardHeader><CardTitle>{DONOR_TYPE_LABELS[donorType]} by Stage</CardTitle></CardHeader>
                            <CardContent>
                                {statusQuery.isLoading ? (
                                    <Skeleton className="h-72 w-full" />
                                ) : (
                                    <div className="space-y-3" role="img" aria-label={`${DONOR_TYPE_LABELS[donorType]} by stage`}>
                                        {statusRows.map((row) => (
                                            <div key={row.stage_id ?? row.status} className="grid grid-cols-[9rem_1fr_2rem] items-center gap-3">
                                                <span className="truncate text-sm text-muted-foreground">{row.status}</span>
                                                <div className="h-3 overflow-hidden rounded-full bg-muted">
                                                    <div
                                                        className="h-full rounded-full"
                                                        style={{
                                                            width: `${(row.count / maxStatusCount) * 100}%`,
                                                            backgroundColor: row.stage_id
                                                                ? colorByStage.get(row.stage_id) ?? "#6b7280"
                                                                : "#6b7280",
                                                        }}
                                                    />
                                                </div>
                                                <span className="text-right text-sm font-medium">{row.count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader><CardTitle>{DONOR_TYPE_LABELS[donorType]} Creation Trend</CardTitle></CardHeader>
                            <CardContent>
                                {trendQuery.isLoading ? (
                                    <Skeleton className="h-72 w-full" />
                                ) : trendRows.length === 0 ? (
                                    <div className="flex h-72 items-center justify-center text-muted-foreground">No data available</div>
                                ) : (
                                    <div className="flex h-72 items-end gap-2 overflow-x-auto" role="img" aria-label={`${DONOR_TYPE_LABELS[donorType]} creation trend`}>
                                        {trendRows.map((row) => (
                                            <div key={row.date} className="flex min-w-10 flex-1 flex-col items-center justify-end gap-2">
                                                <span className="text-xs font-medium">{row.count}</span>
                                                <div
                                                    className="w-full min-w-6 rounded-t bg-primary"
                                                    style={{ height: `${Math.max(4, (row.count / maxTrendCount) * 220)}px` }}
                                                />
                                                <span className="whitespace-nowrap text-[10px] text-muted-foreground">{row.date}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </>
            )}
        </section>
    )
}
