"use client"

import { type ReactNode, useState } from "react"
import Link from "@/components/app-link"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"
import {
    AlertCircleIcon,
    AlertTriangleIcon,
    ArrowRightIcon,
    CalendarIcon,
    CheckCircle2Icon,
    CheckSquareIcon,
    ChevronRightIcon,
    ChevronDownIcon,
    ClockIcon,
    Loader2Icon,
    PauseCircleIcon,
    PhoneOffIcon,
    VideoIcon,
} from "lucide-react"
import {
    useAttention,
    useUpcoming,
    type UpcomingTask,
    type UpcomingMeeting,
} from "@/lib/hooks/use-dashboard"
import { useDashboardFilters } from "../context/dashboard-filters"
import { formatLocalDate } from "@/lib/utils/date"

type UpcomingItem = (UpcomingTask & { type: "task" }) | (UpcomingMeeting & { type: "meeting" })

const MAX_UPCOMING_ITEMS = 5
const OVERDUE_COLLAPSE_THRESHOLD = 3
const MY_TASKS_HREF = "/tasks?filter=my_tasks"
const COUNT_BADGE_CLASS = "h-5 min-w-5 rounded-full px-2 text-[10px] font-medium"

export function AttentionNeededPanel() {
    const { filters } = useDashboardFilters()
    const { data, isLoading, isError, refetch } = useAttention({
        assignee_id: filters.assigneeId,
        days_unreached: 7,
        days_stuck: 30,
    })
    const { data: upcomingData, isLoading: upcomingLoading, isError: upcomingError } = useUpcoming({
        days: 7,
        include_overdue: true,
        ...(filters.assigneeId ? { assignee_id: filters.assigneeId } : {}),
    })

    const unreachedCount = data?.unreached_count ?? 0
    const overdueCount = data?.overdue_count ?? 0
    const stuckCount = data?.stuck_count ?? 0
    const attentionTotal = unreachedCount + overdueCount + stuckCount
    const hasAttentionItems = attentionTotal > 0

    const { todayItems, tomorrowItems, thisWeekItems, overdueItems } = upcomingData
        ? groupItemsByDate(upcomingData.tasks, upcomingData.meetings)
        : { todayItems: [], tomorrowItems: [], thisWeekItems: [], overdueItems: [] }
    const upcomingTotal =
        overdueItems.length + todayItems.length + tomorrowItems.length + thisWeekItems.length
    const hasUpcomingItems = upcomingTotal > 0

    const buildTasksUrl = (focus?: string) => {
        const params = new URLSearchParams({ filter: "my_tasks" })
        if (filters.assigneeId) params.set("owner_id", filters.assigneeId)
        if (focus) params.set("focus", focus)
        return `/tasks?${params.toString()}`
    }

    const buildSurrogatesUrl = () => {
        const params = new URLSearchParams()
        if (filters.assigneeId) params.set("owner_id", filters.assigneeId)
        return `/surrogates${params.toString() ? `?${params.toString()}` : ""}`
    }

    const [activeSection, setActiveSection] = useState<"attention" | "upcoming">("attention")
    const sections: { title: string; rows: ReactNode[] }[] = []
    let remaining = MAX_UPCOMING_ITEMS

    const addSection = (title: string, items: UpcomingItem[]) => {
        if (!items.length || remaining <= 0) return
        const slice = items.slice(0, remaining)
        remaining -= slice.length
        sections.push({
            title,
            rows: slice.map((item) => (
                <UpcomingItemRow
                    key={item.id}
                    item={item}
                    {...(filters.assigneeId ? { assigneeId: filters.assigneeId } : {})}
                />
            )),
        })
    }

    if (overdueItems.length > 0 && remaining > 0) {
        if (overdueItems.length <= OVERDUE_COLLAPSE_THRESHOLD) {
            addSection("Overdue", overdueItems)
        } else {
            sections.push({
                title: "Overdue",
                rows: [(
                    <OverdueSummaryRow
                        key="overdue-summary"
                        count={overdueItems.length}
                        {...(filters.assigneeId ? { assigneeId: filters.assigneeId } : {})}
                    />
                )],
            })
            remaining -= 1
        }
    }

    addSection("Today", todayItems)
    addSection("Tomorrow", tomorrowItems)
    addSection("This Week", thisWeekItems)

    const attentionOpen = activeSection === "attention"
    const upcomingOpen = activeSection === "upcoming"

    return (
        <Card className="h-full flex flex-col gap-0 p-0">
            <CardContent className="p-6 flex-1 min-h-0">
                <div className="flex h-full min-h-0 flex-col gap-6">
                    <section
                        className={cn("flex min-h-0 flex-col", attentionOpen && "flex-1")}
                    >
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setActiveSection((current) => (
                                            current === "attention" ? "upcoming" : "attention"
                                        ))
                                    }}
                                    className="inline-flex items-center gap-2 text-base font-semibold text-foreground hover:text-foreground/80"
                                    aria-expanded={attentionOpen}
                                >
                                    Attention Needed
                                    <ChevronDownIcon
                                        className={`size-4 transition-transform ${attentionOpen ? "rotate-180" : "rotate-0"}`}
                                    />
                                </button>
                                {!isLoading && !isError && hasAttentionItems && (
                                    <Badge variant="secondary" className={COUNT_BADGE_CLASS}>
                                        {data?.total_count ?? attentionTotal}
                                    </Badge>
                                )}
                            </div>
                            <Popover>
                                <PopoverTrigger
                                    render={
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-8 px-2 text-xs font-medium text-teal-600 hover:text-teal-700"
                                        >
                                            View all
                                        </Button>
                                    }
                                />
                                <PopoverContent align="end" className="w-56 p-2">
                                    <div className="space-y-1">
                                        <Link
                                            href={buildSurrogatesUrl()}
                                            className="flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-muted"
                                        >
                                            <span>Unreached leads</span>
                                            <ChevronRightIcon className="size-4 text-muted-foreground" />
                                        </Link>
                                        <Link
                                            href={buildTasksUrl("overdue")}
                                            className="flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-muted"
                                        >
                                            <span>Overdue tasks</span>
                                            <ChevronRightIcon className="size-4 text-muted-foreground" />
                                        </Link>
                                        <Link
                                            href={buildSurrogatesUrl()}
                                            className="flex items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-muted"
                                        >
                                            <span>Stuck surrogates</span>
                                            <ChevronRightIcon className="size-4 text-muted-foreground" />
                                        </Link>
                                    </div>
                                </PopoverContent>
                            </Popover>
                        </div>
                        {attentionOpen && (
                            <>
                                <div className="text-xs text-muted-foreground mb-3">
                                    Items needing follow-up
                                </div>
                                <div className="flex-1 min-h-0 overflow-auto">
                                    {isLoading ? (
                                        <div className="space-y-3">
                                            {Array.from({ length: 3 }).map((_, i) => (
                                                <div key={i} className="flex items-center gap-3 p-3 rounded-lg border">
                                                    <Skeleton className="size-9 rounded-lg" />
                                                    <div className="flex-1 space-y-2">
                                                        <Skeleton className="h-4 w-32" />
                                                        <Skeleton className="h-3 w-48" />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : isError ? (
                                        <div className="flex flex-col items-center justify-center py-6 gap-3">
                                            <AlertCircleIcon className="size-8 text-destructive" />
                                            <p className="text-sm text-destructive">Unable to load attention items</p>
                                            <Button variant="outline" size="sm" onClick={() => refetch()}>
                                                Retry
                                            </Button>
                                        </div>
                                    ) : !hasAttentionItems || !data ? (
                                        <div className="flex flex-col items-center justify-center py-6 text-center">
                                            <div className="size-12 rounded-full bg-green-500/10 flex items-center justify-center mb-4">
                                                <CheckCircle2Icon className="size-6 text-green-600" />
                                            </div>
                                            <h4 className="font-medium text-foreground">All caught up!</h4>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                No items need your attention right now
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            {unreachedCount > 0 && (
                                                <AttentionItem
                                                    icon={<PhoneOffIcon className="size-4" />}
                                                    iconBg="bg-amber-500/10"
                                                    iconColor="text-amber-600"
                                                    title="Unreached leads (7+ days)"
                                                    description="No contact in 7+ days"
                                                    count={unreachedCount}
                                                    href={buildSurrogatesUrl()}
                                                    countBadgeClass={COUNT_BADGE_CLASS}
                                                />
                                            )}

                                            {overdueCount > 0 && (
                                                <AttentionItem
                                                    icon={<ClockIcon className="size-4" />}
                                                    iconBg="bg-red-500/10"
                                                    iconColor="text-red-600"
                                                    title="Overdue tasks"
                                                    description="Past due date"
                                                    count={overdueCount}
                                                    href={buildTasksUrl("overdue")}
                                                    countBadgeClass={COUNT_BADGE_CLASS}
                                                />
                                            )}

                                            {stuckCount > 0 && (
                                                <AttentionItem
                                                    icon={<PauseCircleIcon className="size-4" />}
                                                    iconBg="bg-orange-500/10"
                                                    iconColor="text-orange-600"
                                                    title="Stuck surrogates (30+ days)"
                                                    description="In stage for 30+ days"
                                                    count={stuckCount}
                                                    href={buildSurrogatesUrl()}
                                                    countBadgeClass={COUNT_BADGE_CLASS}
                                                />
                                            )}
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                    </section>

                    <Separator />

                    <section className={cn("flex min-h-0 flex-col", upcomingOpen && "flex-1")}>
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setActiveSection((current) => (
                                            current === "upcoming" ? "attention" : "upcoming"
                                        ))
                                    }}
                                    className="inline-flex items-center gap-2 text-base font-semibold text-foreground hover:text-foreground/80"
                                    aria-expanded={upcomingOpen}
                                >
                                    Upcoming This Week
                                    <ChevronDownIcon
                                        className={`size-4 transition-transform ${upcomingOpen ? "rotate-180" : "rotate-0"}`}
                                    />
                                </button>
                            </div>
                            <Link
                                href={buildTaskHref({
                                    ...(filters.assigneeId ? { assigneeId: filters.assigneeId } : {}),
                                })}
                                className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700 transition-colors h-8"
                            >
                                View all
                                <ArrowRightIcon className="h-3 w-3" />
                            </Link>
                        </div>
                        {upcomingOpen && (
                            <>
                                <div className="text-xs text-muted-foreground mb-3">Next 7 days</div>
                                <div className="flex-1 min-h-0 overflow-auto">
                                    {upcomingLoading ? (
                                        <div className="flex items-center justify-center py-6">
                                            <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : upcomingError || !upcomingData ? (
                                        <div className="flex flex-col items-center justify-center py-6 text-center">
                                            <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                                            <p className="text-sm text-muted-foreground">Unable to load upcoming items</p>
                                        </div>
                                    ) : !hasUpcomingItems ? (
                                        <div className="flex flex-col items-center justify-center py-6 text-center">
                                            <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                                            <p className="text-sm font-medium text-muted-foreground">
                                                No upcoming tasks or meetings this week
                                            </p>
                                            <Link
                                                href={MY_TASKS_HREF}
                                                className="text-xs text-primary hover:underline mt-2 inline-block"
                                            >
                                                View all tasks →
                                            </Link>
                                        </div>
                                    ) : (
                                        <div className="space-y-4">
                                            {sections.map((section) => (
                                                <div key={section.title}>
                                                    <h3
                                                        className={`text-xs font-semibold mb-2 ${section.title === "Overdue"
                                                            ? "text-red-600"
                                                            : "text-muted-foreground"
                                                            }`}
                                                    >
                                                        {section.title}
                                                    </h3>
                                                    <div className="space-y-2">
                                                        {section.rows}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                    </section>
                </div>
            </CardContent>
        </Card>
    )
}

// =============================================================================
// Attention Item Component
// =============================================================================

interface AttentionItemProps {
    icon: React.ReactNode
    iconBg: string
    iconColor: string
    title: string
    description: string
    count: number
    href: string
    countBadgeClass: string
}

function AttentionItem({
    icon,
    iconBg,
    iconColor,
    title,
    description,
    count,
    href,
    countBadgeClass,
}: AttentionItemProps) {
    return (
        <Link
            href={href}
            className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
        >
            <div className={cn("size-9 rounded-lg flex items-center justify-center", iconBg)}>
                <span className={iconColor}>{icon}</span>
            </div>
            <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
            </div>
            <Badge variant="secondary" className={countBadgeClass}>
                {count}
            </Badge>
            <ChevronRightIcon className="size-4 text-muted-foreground flex-shrink-0" />
        </Link>
    )
}

// =============================================================================
// Upcoming Helpers
// =============================================================================

function groupItemsByDate(tasks: UpcomingTask[], meetings: UpcomingMeeting[]) {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayStr = formatLocalDate(today)

    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const tomorrowStr = formatLocalDate(tomorrow)

    const allItems: UpcomingItem[] = [
        ...tasks.map((task) => ({ ...task, type: "task" as const })),
        ...meetings.map((meeting) => ({ ...meeting, type: "meeting" as const })),
    ]

    const overdueItems = allItems.filter((item) => item.type === "task" && item.is_overdue)
    const todayItems = allItems.filter((item) => item.date === todayStr && !item.is_overdue)
    const tomorrowItems = allItems.filter((item) => item.date === tomorrowStr)
    const thisWeekItems = allItems.filter((item) => item.date > tomorrowStr && !item.is_overdue)

    return { todayItems, tomorrowItems, thisWeekItems, overdueItems }
}

function buildTaskHref({
    assigneeId,
    focus,
}: {
    assigneeId?: string
    focus?: string
}) {
    const params = new URLSearchParams({ filter: "my_tasks" })
    if (assigneeId) params.set("owner_id", assigneeId)
    if (focus) params.set("focus", focus)
    return `/tasks?${params.toString()}`
}

function OverdueSummaryRow({
    count,
    assigneeId,
}: {
    count: number
    assigneeId?: string
}) {
    return (
        <Link
            href={buildTaskHref({
                ...(assigneeId ? { assigneeId } : {}),
                focus: "overdue",
            })}
            className="flex items-center gap-3 rounded-lg border border-border bg-card/50 p-3 hover:bg-accent/50 transition-colors"
        >
            <div className="flex-shrink-0 mt-0.5">
                <AlertTriangleIcon className="h-4 w-4 text-red-600" />
            </div>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight">Overdue tasks</p>
                <p className="text-xs text-muted-foreground">{count} overdue tasks</p>
            </div>
            <Badge variant="secondary" className={`flex-shrink-0 ${COUNT_BADGE_CLASS}`}>
                {count}
            </Badge>
            <ArrowRightIcon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        </Link>
    )
}

function UpcomingItemRow({
    item,
    assigneeId,
}: {
    item: UpcomingItem
    assigneeId?: string
}) {
    const Icon = item.type === "task" ? CheckSquareIcon : VideoIcon
    const isMeeting = item.type === "meeting"

    const formatTime = (time: string | null) => {
        if (!time) return "All Day"
        const [hours = "0", minutes = "00"] = time.split(":")
        const hour = parseInt(hours, 10)
        const ampm = hour >= 12 ? "PM" : "AM"
        const displayHour = hour % 12 || 12
        return `${displayHour}:${minutes} ${ampm}`
    }

    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayStr = formatLocalDate(today)
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const tomorrowStr = formatLocalDate(tomorrow)

    const focus = item.is_overdue
        ? "overdue"
        : item.date === todayStr
            ? "today"
            : item.date === tomorrowStr
                ? "tomorrow"
                : "this-week"

    const href = isMeeting
        ? item.join_url || "/appointments"
        : buildTaskHref({
            ...(assigneeId ? { assigneeId } : {}),
            focus,
        })
    const isExternal = isMeeting && !!item.join_url && item.join_url.startsWith("http")

    const content = (
        <>
            <div className="flex-shrink-0 mt-0.5">
                <Icon className={`h-4 w-4 ${item.type === "meeting" ? "text-blue-500" : "text-muted-foreground"}`} />
            </div>

            <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-tight">{item.title}</p>
                    {item.is_overdue && (
                        <Badge variant="destructive" className="flex-shrink-0 text-[10px] h-4 px-1.5 rounded-full">
                            Overdue
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium">{formatTime(item.time)}</span>
                    {item.surrogate_id && (
                        <>
                            <span className="text-muted-foreground/60">•</span>
                            <span className="text-muted-foreground">
                                {item.surrogate_number || "View Surrogate"}
                            </span>
                        </>
                    )}
                </div>
            </div>
            <ChevronRightIcon className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-1" />
        </>
    )

    if (isExternal) {
        return (
            <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="flex items-start gap-3 rounded-lg border border-border bg-card/50 p-3 hover:bg-accent/50 transition-colors"
            >
                {content}
            </a>
        )
    }

    return (
        <Link
            href={href}
            className="flex items-start gap-3 rounded-lg border border-border bg-card/50 p-3 hover:bg-accent/50 transition-colors"
        >
            {content}
        </Link>
    )
}
