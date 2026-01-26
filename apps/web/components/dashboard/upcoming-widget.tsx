"use client"

import { type ReactNode } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
    CheckSquareIcon,
    VideoIcon,
    CalendarIcon,
    ArrowRightIcon,
    ChevronRightIcon,
    Loader2Icon,
    AlertTriangleIcon,
} from "lucide-react"
import Link from "@/components/app-link"
import { useUpcoming, type UpcomingTask, type UpcomingMeeting } from "@/lib/hooks/use-dashboard"
import { formatLocalDate } from "@/lib/utils/date"

type UpcomingItem = (UpcomingTask & { type: 'task' }) | (UpcomingMeeting & { type: 'meeting' })

const MAX_UPCOMING_ITEMS = 5
const OVERDUE_COLLAPSE_THRESHOLD = 3
const MY_TASKS_HREF = "/tasks?filter=my_tasks"
const COUNT_BADGE_CLASS = "h-5 min-w-5 rounded-full px-2 text-[10px] font-medium"

function groupItemsByDate(tasks: UpcomingTask[], meetings: UpcomingMeeting[]) {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayStr = formatLocalDate(today)

    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const tomorrowStr = formatLocalDate(tomorrow)

    // Combine and mark with type
    const allItems: UpcomingItem[] = [
        ...tasks.map(t => ({ ...t, type: 'task' as const })),
        ...meetings.map(m => ({ ...m, type: 'meeting' as const })),
    ]

    const overdueItems = allItems.filter((item) =>
        item.type === 'task' && item.is_overdue
    )

    const todayItems = allItems.filter((item) =>
        item.date === todayStr && !item.is_overdue
    )

    const tomorrowItems = allItems.filter((item) =>
        item.date === tomorrowStr
    )

    const thisWeekItems = allItems.filter((item) =>
        item.date > tomorrowStr && !item.is_overdue
    )

    return { todayItems, tomorrowItems, thisWeekItems, overdueItems }
}

export function UpcomingThisWeekWidget({
    assigneeId,
}: {
    assigneeId?: string
}) {
    const upcomingParams = {
        days: 7,
        include_overdue: true,
        ...(assigneeId ? { assignee_id: assigneeId } : {}),
    }
    const { data, isLoading, isError } = useUpcoming(upcomingParams)

    if (isLoading) {
        return (
            <Card className="flex flex-col gap-0 p-0">
                <CardHeader className="p-6 pb-0 gap-0">
                    <div className="flex items-center justify-between mb-1">
                        <CardTitle className="text-base font-semibold">Upcoming This Week</CardTitle>
                    </div>
                    <div className="text-sm text-muted-foreground mb-4">Next 7 days</div>
                </CardHeader>
                <CardContent className="p-6 pt-0 flex-1">
                    <div className="flex items-center justify-center py-12">
                        <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (isError || !data) {
        return (
            <Card className="flex flex-col gap-0 p-0">
                <CardHeader className="p-6 pb-0 gap-0">
                    <div className="flex items-center justify-between mb-1">
                        <CardTitle className="text-base font-semibold">Upcoming This Week</CardTitle>
                    </div>
                    <div className="text-sm text-muted-foreground mb-4">Next 7 days</div>
                </CardHeader>
                <CardContent className="p-6 pt-0 flex-1">
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                        <p className="text-sm text-muted-foreground">Unable to load upcoming items</p>
                    </div>
                </CardContent>
            </Card>
        )
    }

    const { todayItems, tomorrowItems, thisWeekItems, overdueItems } = groupItemsByDate(
        data.tasks,
        data.meetings
    )

    const hasItems = overdueItems.length > 0 || todayItems.length > 0 || tomorrowItems.length > 0 || thisWeekItems.length > 0
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
                    {...(assigneeId ? { assigneeId } : {})}
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
                        {...(assigneeId ? { assigneeId } : {})}
                    />
                )],
            })
            remaining -= 1
        }
    }

    addSection("Today", todayItems)
    addSection("Tomorrow", tomorrowItems)
    addSection("This Week", thisWeekItems)

    return (
        <Card className="flex flex-col gap-0 p-0">
            <CardHeader className="p-6 pb-0 gap-0">
                <div className="flex items-center justify-between mb-1">
                    <CardTitle className="text-base font-semibold">Upcoming This Week</CardTitle>
                    <Link
                        href={buildTaskHref({
                            ...(assigneeId ? { assigneeId } : {}),
                        })}
                        className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700 transition-colors h-8"
                    >
                        View all
                        <ArrowRightIcon className="h-3 w-3" />
                    </Link>
                </div>
                <div className="text-sm text-muted-foreground mb-4">Next 7 days</div>
            </CardHeader>
            <CardContent className="p-6 pt-0 flex-1">
                {!hasItems ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                        <p className="text-sm font-medium text-muted-foreground">No tasks with due dates this week</p>
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
                                    className={`text-xs font-semibold mb-2 ${section.title === "Overdue" ? "text-red-600" : "text-muted-foreground"
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
            </CardContent>
        </Card>
    )
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

    // Format time for display
    const formatTime = (time: string | null) => {
        if (!time) return "All Day"
        const [hours = "0", minutes = "00"] = time.split(':')
        const hour = parseInt(hours, 10)
        const ampm = hour >= 12 ? 'PM' : 'AM'
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
