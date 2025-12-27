"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CheckSquareIcon, VideoIcon, CalendarIcon, ArrowRightIcon, Loader2Icon } from "lucide-react"
import Link from "next/link"
import { useUpcoming, type UpcomingTask, type UpcomingMeeting } from "@/lib/hooks/use-dashboard"
import { formatLocalDate } from "@/lib/utils/date"

type UpcomingItem = (UpcomingTask & { type: 'task' }) | (UpcomingMeeting & { type: 'meeting' })

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

export function UpcomingThisWeekWidget() {
    const { data, isLoading, isError } = useUpcoming({ days: 7, include_overdue: true })

    if (isLoading) {
        return (
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Upcoming This Week</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center justify-center py-12">
                        <Loader2Icon className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (isError || !data) {
        return (
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Upcoming This Week</CardTitle>
                </CardHeader>
                <CardContent>
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

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Upcoming This Week</CardTitle>
                    <Link
                        href="/tasks"
                        className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700 transition-colors"
                    >
                        View All
                        <ArrowRightIcon className="h-3 w-3" />
                    </Link>
                </div>
            </CardHeader>
            <CardContent>
                {!hasItems ? (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <CalendarIcon className="h-12 w-12 text-muted-foreground/50 mb-3" />
                        <p className="text-sm font-medium text-muted-foreground">Nothing scheduled</p>
                        <p className="text-xs text-muted-foreground/60 mt-1">Your week is clear</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {overdueItems.length > 0 && (
                            <div>
                                <h3 className="text-xs font-semibold text-red-600 mb-2">Overdue</h3>
                                <div className="space-y-2">
                                    {overdueItems.map((item) => (
                                        <UpcomingItemRow key={item.id} item={item} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {todayItems.length > 0 && (
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground mb-2">Today</h3>
                                <div className="space-y-2">
                                    {todayItems.map((item) => (
                                        <UpcomingItemRow key={item.id} item={item} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {tomorrowItems.length > 0 && (
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground mb-2">Tomorrow</h3>
                                <div className="space-y-2">
                                    {tomorrowItems.map((item) => (
                                        <UpcomingItemRow key={item.id} item={item} />
                                    ))}
                                </div>
                            </div>
                        )}

                        {thisWeekItems.length > 0 && (
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground mb-2">This Week</h3>
                                <div className="space-y-2">
                                    {thisWeekItems.map((item) => (
                                        <UpcomingItemRow key={item.id} item={item} />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function UpcomingItemRow({ item }: { item: UpcomingItem }) {
    const Icon = item.type === "task" ? CheckSquareIcon : VideoIcon

    // Format time for display
    const formatTime = (time: string | null) => {
        if (!time) return "All Day"
        const [hours, minutes] = time.split(':')
        const hour = parseInt(hours, 10)
        const ampm = hour >= 12 ? 'PM' : 'AM'
        const displayHour = hour % 12 || 12
        return `${displayHour}:${minutes} ${ampm}`
    }

    return (
        <div className="flex items-start gap-3 rounded-lg border border-border bg-card/50 p-3 hover:bg-accent/50 transition-colors">
            <div className="flex-shrink-0 mt-0.5">
                <Icon className={`h-4 w-4 ${item.type === "meeting" ? "text-blue-500" : "text-muted-foreground"}`} />
            </div>

            <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-tight">{item.title}</p>
                    {item.is_overdue && (
                        <Badge variant="destructive" className="flex-shrink-0 text-[10px] h-4 px-1.5">
                            Overdue
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium">{formatTime(item.time)}</span>
                    {item.case_id && (
                        <>
                            <span className="text-muted-foreground/60">•</span>
                            <Link
                                href={`/cases/${item.case_id}`}
                                className="text-teal-600 hover:text-teal-700 hover:underline transition-colors"
                            >
                                {item.case_number || 'View Case'}
                            </Link>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
