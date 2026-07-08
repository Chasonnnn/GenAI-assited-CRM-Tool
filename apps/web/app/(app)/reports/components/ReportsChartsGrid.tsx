"use client"

import dynamic from "next/dynamic"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import {
    AlertCircleIcon,
    Loader2Icon,
    MegaphoneIcon,
    SparklesIcon,
    TrendingDownIcon,
    TrendingUpIcon,
} from "lucide-react"

const surrogatesOverviewConfig = {
    count: { label: "Surrogates" },
}

const monthlyTrendsConfig = {
    count: { label: "Surrogates", color: "#3b82f6" },
}

const surrogatesByAssigneeConfig = {
    count: { label: "Surrogates" },
}

type StatusChartDatum = {
    status: string
    count: number
    fill: string
}

type TrendChartDatum = {
    date: string
    count: number
}

type AssigneeChartDatum = {
    member: string
    count: number
    fill?: string
}

type MetaPerformance = {
    leads_received?: number | null
    leads_qualified?: number | null
    leads_converted?: number | null
    avg_time_to_convert_hours?: number | null
    conversion_rate?: number | null
}

type ReportsChartsGridProps = {
    aiEnabled: boolean
    statusChartData: StatusChartDatum[]
    trendChartData: TrendChartDatum[]
    assigneeChartData: AssigneeChartDatum[]
    topStatus: StatusChartDatum | null
    topPerformer: AssigneeChartDatum | null
    totalSurrogatesInPeriod: number
    computeTrendPercentage: number | null
    metaPerf?: MetaPerformance | null
    byStatusLoading: boolean
    byStatusError: boolean
    trendLoading: boolean
    trendError: boolean
    byAssigneeLoading: boolean
    byAssigneeError: boolean
    metaLoading: boolean
    metaError: boolean
}

type ReportsChartCanvasProps =
    | {
          kind: "status"
          data: StatusChartDatum[]
      }
    | {
          kind: "trend"
          data: TrendChartDatum[]
      }
    | {
          kind: "assignee"
          data: AssigneeChartDatum[]
      }
    | {
          kind: "meta"
          metaPerf?: MetaPerformance | null | undefined
      }

const ReportsChartCanvas = dynamic<ReportsChartCanvasProps>(
    () =>
        Promise.all([
            import("recharts"),
            import("@/components/ui/chart"),
        ]).then(([{
            Bar,
            BarChart,
            CartesianGrid,
            Cell,
            Line,
            LineChart,
            Pie,
            PieChart,
            Legend,
            Tooltip,
            XAxis,
            YAxis,
        }, {
            ChartContainer,
            ChartTooltipContent,
            ChartLegendContent,
        }]) => {
            function ReportsChartCanvasComponent(props: ReportsChartCanvasProps) {
                if (props.kind === "status") {
                    return (
                        <ChartContainer config={surrogatesOverviewConfig} className="h-[300px] w-full">
                            <BarChart data={props.data}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="status" tickLine={false} axisLine={false} fontSize={12} />
                                <YAxis tickLine={false} axisLine={false} />
                                <Tooltip content={<ChartTooltipContent />} />
                                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                                    {props.data.map((item) => (
                                        <Cell key={`${item.status}-${item.fill}`} fill={item.fill ?? "#94a3b8"} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ChartContainer>
                    )
                }

                if (props.kind === "trend") {
                    return (
                        <ChartContainer config={monthlyTrendsConfig} className="h-[300px] w-full">
                            <LineChart data={props.data}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={12} />
                                <YAxis tickLine={false} axisLine={false} />
                                <Tooltip content={<ChartTooltipContent />} />
                                <Line
                                    type="monotone"
                                    dataKey="count"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    dot={{ r: 4 }}
                                />
                            </LineChart>
                        </ChartContainer>
                    )
                }

                if (props.kind === "assignee") {
                    return (
                        <ChartContainer config={surrogatesByAssigneeConfig} className="h-[300px] w-full">
                            <BarChart data={props.data} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                <XAxis type="number" tickLine={false} axisLine={false} />
                                <YAxis
                                    dataKey="member"
                                    type="category"
                                    tickLine={false}
                                    axisLine={false}
                                    width={100}
                                    fontSize={12}
                                />
                                <Tooltip content={<ChartTooltipContent />} />
                                <Bar dataKey="count" radius={[0, 8, 8, 0]}>
                                    {props.data.map((item) => {
                                        const fill = item.fill || "#3b82f6"
                                        return <Cell key={`${item.member}-${fill}`} fill={fill} />
                                    })}
                                </Bar>
                            </BarChart>
                        </ChartContainer>
                    )
                }

                const metaPerf = props.metaPerf
                return (
                    <ChartContainer
                        config={{
                            notPreQualified: { label: "Not Pre-Qualified", color: "#94a3b8" },
                            preQualified: { label: "Pre-Qualified Only", color: "#3b82f6" },
                            converted: { label: "Converted", color: "#22c55e" },
                        }}
                        className="h-[300px] w-full"
                    >
                        <PieChart>
                            <Tooltip content={<ChartTooltipContent />} />
                            <Pie
                                data={[
                                    {
                                        name: "Not Qualified",
                                        value: Math.max(
                                            0,
                                            (metaPerf?.leads_received ?? 0) -
                                                (metaPerf?.leads_qualified ?? 0)
                                        ),
                                        fill: "#94a3b8",
                                    },
                                    {
                                        name: "Qualified Only",
                                        value: Math.max(
                                            0,
                                            (metaPerf?.leads_qualified ?? 0) -
                                                (metaPerf?.leads_converted ?? 0)
                                        ),
                                        fill: "#3b82f6",
                                    },
                                    {
                                        name: "Converted",
                                        value: metaPerf?.leads_converted ?? 0,
                                        fill: "#22c55e",
                                    },
                                ]}
                                dataKey="value"
                                nameKey="name"
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={100}
                                label={({ name, value }) => {
                                    const labelName = typeof name === "string" ? name : ""
                                    const numericValue =
                                        typeof value === "number" ? value : Number(value ?? 0)
                                    return numericValue > 0 ? `${labelName}: ${numericValue}` : ""
                                }}
                            />
                            <Legend content={<ChartLegendContent />} />
                        </PieChart>
                    </ChartContainer>
                )
            }

            return ReportsChartCanvasComponent
        }),
    {
        ssr: false,
        loading: () => (
            <div className="flex h-[300px] items-center justify-center">
                <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
            </div>
        ),
    },
)

export function ReportsChartsGrid({
    aiEnabled,
    statusChartData,
    trendChartData,
    assigneeChartData,
    topStatus,
    topPerformer,
    totalSurrogatesInPeriod,
    computeTrendPercentage,
    metaPerf,
    byStatusLoading,
    byStatusError,
    trendLoading,
    trendError,
    byAssigneeLoading,
    byAssigneeError,
    metaLoading,
    metaError,
}: ReportsChartsGridProps) {
    return (
        <div className="grid gap-6 md:grid-cols-2">
            {/* Surrogates by Stage */}
            <Card className="animate-in fade-in-50 duration-500 delay-400">
                <CardHeader>
                    <CardTitle>Surrogates by Stage</CardTitle>
                </CardHeader>
                <CardContent>
                    {byStatusLoading ? (
                        <div className="flex h-[300px] items-center justify-center">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : byStatusError ? (
                        <div className="flex h-[300px] items-center justify-center text-destructive">
                            <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                        </div>
                    ) : statusChartData.length > 0 ? (
                        <ReportsChartCanvas kind="status" data={statusChartData} />
                    ) : (
                        <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                            <AlertCircleIcon className="mr-2 size-4" /> No data available
                        </div>
                    )}
                </CardContent>
                <CardFooter className="flex-col items-start gap-2">
                    <div className="flex gap-2 leading-none font-medium">
                        {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                        {byStatusError
                            ? "Unable to load status data"
                            : topStatus
                              ? `${topStatus.status}: ${topStatus.count} surrogates`
                              : "No data yet"}
                    </div>
                    <div className="text-muted-foreground leading-none">
                        {byStatusError ? "Please try again later" : "Current distribution by stage"}
                    </div>
                </CardFooter>
            </Card>

            {/* Surrogates Trend */}
            <Card className="animate-in fade-in-50 duration-500 delay-500">
                <CardHeader>
                    <CardTitle>Surrogates Trend</CardTitle>
                </CardHeader>
                <CardContent>
                    {trendLoading ? (
                        <div className="flex h-[300px] items-center justify-center">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : trendError ? (
                        <div className="flex h-[300px] items-center justify-center text-destructive">
                            <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                        </div>
                    ) : trendChartData.length > 0 ? (
                        <ReportsChartCanvas kind="trend" data={trendChartData} />
                    ) : (
                        <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                            <AlertCircleIcon className="mr-2 size-4" /> No data available
                        </div>
                    )}
                </CardContent>
                <CardFooter className="flex-col items-start gap-2">
                    <div className="flex gap-2 leading-none font-medium">
                        {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                        {trendError ? (
                            "Unable to load trend data"
                        ) : computeTrendPercentage !== null ? (
                            <>
                                {computeTrendPercentage >= 0 ? "Trending up" : "Trending down"} by{" "}
                                {Math.abs(computeTrendPercentage)}%
                                {computeTrendPercentage >= 0 ? (
                                    <TrendingUpIcon className="size-4" />
                                ) : (
                                    <TrendingDownIcon className="size-4" />
                                )}
                            </>
                        ) : (
                            `${totalSurrogatesInPeriod} surrogates in period`
                        )}
                    </div>
                    <div className="text-muted-foreground leading-none">
                        {trendError ? "Please try again later" : `${trendChartData.length} data points`}
                    </div>
                </CardFooter>
            </Card>

            {/* Team Performance */}
            <Card className="animate-in fade-in-50 duration-500 delay-[600ms]">
                <CardHeader>
                    <CardTitle>Team Performance</CardTitle>
                </CardHeader>
                <CardContent>
                    {byAssigneeLoading ? (
                        <div className="flex h-[300px] items-center justify-center">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : byAssigneeError ? (
                        <div className="flex h-[300px] items-center justify-center text-destructive">
                            <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                        </div>
                    ) : assigneeChartData.length > 0 ? (
                        <ReportsChartCanvas kind="assignee" data={assigneeChartData} />
                    ) : (
                        <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                            <AlertCircleIcon className="mr-2 size-4" /> No assigned surrogates
                        </div>
                    )}
                </CardContent>
                <CardFooter className="flex-col items-start gap-2">
                    <div className="flex gap-2 leading-none font-medium">
                        {aiEnabled && <SparklesIcon className="size-4 text-primary" />}
                        {byAssigneeError
                            ? "Unable to load team data"
                            : topPerformer
                              ? `Top: ${topPerformer.member} (${topPerformer.count} surrogates)`
                              : "No assignments yet"}
                        {!byAssigneeError && topPerformer && <TrendingUpIcon className="size-4" />}
                    </div>
                    <div className="text-muted-foreground leading-none">
                        {byAssigneeError ? "Please try again later" : `${assigneeChartData.length} team members`}
                    </div>
                </CardFooter>
            </Card>

            {/* Meta Performance */}
            <Card className="animate-in fade-in-50 duration-500 delay-700">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <MegaphoneIcon className="size-5 text-blue-600" />
                        Meta Lead Ads Performance
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {metaLoading ? (
                        <div className="flex h-[300px] items-center justify-center">
                            <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                        </div>
                    ) : metaError ? (
                        <div className="flex h-[300px] items-center justify-center text-destructive">
                            <AlertCircleIcon className="mr-2 size-4" /> Unable to load data
                        </div>
                    ) : (
                        <ReportsChartCanvas kind="meta" metaPerf={metaPerf ?? null} />
                    )}
                </CardContent>
                <CardFooter className="flex-col items-start gap-2">
                    <div className="flex gap-2 leading-none font-medium">
                        {metaError
                            ? "Unable to load performance data"
                            : metaPerf?.avg_time_to_convert_hours
                              ? `Avg ${Math.round(metaPerf.avg_time_to_convert_hours / 24)} days to convert`
                              : "No conversion data yet"}
                    </div>
                    <div className="text-muted-foreground leading-none">
                        {metaError
                            ? "Please try again later"
                            : `${metaPerf?.leads_received ?? 0} leads received • ${metaPerf?.conversion_rate ?? 0}% conversion rate`}
                    </div>
                </CardFooter>
            </Card>
        </div>
    )
}
