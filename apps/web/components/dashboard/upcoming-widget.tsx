"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CheckSquareIcon, VideoIcon, CalendarIcon, ArrowRightIcon } from "lucide-react"
import Link from "next/link"

interface UpcomingItem {
    id: string
    type: "task" | "meeting"
    title: string
    time?: string // undefined means "All Day"
    caseId: string
    caseName: string
    date: Date
    isOverdue?: boolean
}

// Sample data - replace with real data in production
const upcomingItems: UpcomingItem[] = [
    {
        id: "1",
        type: "task",
        title: "Submit medical records",
        time: "09:00 AM",
        caseId: "C-2024-001",
        caseName: "Sarah & Michael Johnson",
        date: new Date(),
        isOverdue: false,
    },
    {
        id: "2",
        type: "meeting",
        title: "Initial consultation call",
        time: "02:00 PM",
        caseId: "C-2024-003",
        caseName: "Emily Rodriguez",
        date: new Date(),
        isOverdue: false,
    },
    {
        id: "3",
        type: "task",
        title: "Review contract amendments",
        caseId: "C-2024-002",
        caseName: "David & Laura Chen",
        date: new Date(Date.now() + 86400000), // Tomorrow
        isOverdue: false,
    },
    {
        id: "4",
        type: "meeting",
        title: "Agency coordination meeting",
        time: "10:00 AM",
        caseId: "C-2024-005",
        caseName: "Robert Smith",
        date: new Date(Date.now() + 86400000), // Tomorrow
        isOverdue: false,
    },
    {
        id: "5",
        type: "task",
        title: "Background check follow-up",
        time: "11:30 AM",
        caseId: "C-2024-004",
        caseName: "Jessica Williams",
        date: new Date(Date.now() + 172800000), // 2 days from now
        isOverdue: false,
    },
    {
        id: "6",
        type: "task",
        title: "Insurance verification",
        caseId: "C-2024-006",
        caseName: "Marcus & Lisa Taylor",
        date: new Date(Date.now() - 86400000), // Yesterday (overdue)
        isOverdue: true,
    },
]

function groupItemsByDate(items: UpcomingItem[]) {
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)

    const endOfWeek = new Date(today)
    endOfWeek.setDate(endOfWeek.getDate() + 7)

    const todayItems = items.filter((item) => {
        const itemDate = new Date(item.date)
        itemDate.setHours(0, 0, 0, 0)
        return itemDate.getTime() === today.getTime() && !item.isOverdue
    })

    const tomorrowItems = items.filter((item) => {
        const itemDate = new Date(item.date)
        itemDate.setHours(0, 0, 0, 0)
        return itemDate.getTime() === tomorrow.getTime()
    })

    const thisWeekItems = items.filter((item) => {
        const itemDate = new Date(item.date)
        itemDate.setHours(0, 0, 0, 0)
        return itemDate > tomorrow && itemDate < endOfWeek
    })

    const overdueItems = items.filter((item) => item.isOverdue)

    return { todayItems, tomorrowItems, thisWeekItems, overdueItems }
}

export function UpcomingThisWeekWidget() {
    const { todayItems, tomorrowItems, thisWeekItems, overdueItems } = groupItemsByDate(upcomingItems)
    const allItems = [...overdueItems, ...todayItems, ...tomorrowItems, ...thisWeekItems].slice(0, 10)

    const hasItems = allItems.length > 0

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

    return (
        <div className="flex items-start gap-3 rounded-lg border border-border bg-card/50 p-3 hover:bg-accent/50 transition-colors">
            <div className="flex-shrink-0 mt-0.5">
                <Icon className={`h-4 w-4 ${item.type === "meeting" ? "text-blue-500" : "text-muted-foreground"}`} />
            </div>

            <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium leading-tight">{item.title}</p>
                    {item.isOverdue && (
                        <Badge variant="destructive" className="flex-shrink-0 text-[10px] h-4 px-1.5">
                            Overdue
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {item.time ? <span className="font-medium">{item.time}</span> : <span className="font-medium">All Day</span>}
                    <span className="text-muted-foreground/60">•</span>
                    <Link
                        href={`/cases/${item.caseId}`}
                        className="text-teal-600 hover:text-teal-700 hover:underline transition-colors"
                    >
                        {item.caseId}
                    </Link>
                </div>
            </div>
        </div>
    )
}
