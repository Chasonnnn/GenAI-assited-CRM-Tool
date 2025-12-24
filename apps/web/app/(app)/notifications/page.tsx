"use client"

import { useState } from "react"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Skeleton } from "@/components/ui/skeleton"
import {
    BellIcon,
    CheckSquareIcon,
    AlertCircleIcon,
    FileTextIcon,
    CalendarIcon,
    ChevronDownIcon,
    ChevronUpIcon,
} from "lucide-react"
import { useNotifications, useMarkRead, useMarkAllRead } from "@/lib/hooks/use-notifications"
import { useTasks } from "@/lib/hooks/use-tasks"
import type { Notification } from "@/lib/api/notifications"

// Map notification types to UI groups
const TYPE_GROUPS: Record<string, string[]> = {
    all: [],
    case: ["case_assigned", "case_status_changed", "case_handoff_ready", "case_handoff_accepted", "case_handoff_denied"],
    task: ["task_assigned", "task_due_soon", "task_overdue"],
    appointment: ["appointment_requested", "appointment_confirmed", "appointment_cancelled", "appointment_reminder"],
}

const typeIcons: Record<string, typeof FileTextIcon> = {
    case: FileTextIcon,
    task: CheckSquareIcon,
    appointment: CalendarIcon,
}

function getNotificationIcon(type: string) {
    if (type.startsWith("case")) return FileTextIcon
    if (type.startsWith("task")) return CheckSquareIcon
    if (type.startsWith("appointment")) return CalendarIcon
    return BellIcon
}

export default function NotificationsPage() {
    const router = useRouter()
    const [typeFilter, setTypeFilter] = useState("all")
    const [isOverdueOpen, setIsOverdueOpen] = useState(true)

    // Get notification types for filter
    const notificationTypes = typeFilter !== "all" ? TYPE_GROUPS[typeFilter] : undefined

    const { data: notificationsData, isLoading } = useNotifications({
        limit: 50,
        notification_types: notificationTypes,
    })
    const markRead = useMarkRead()
    const markAllRead = useMarkAllRead()

    // Fetch overdue tasks (incomplete with due_date in the past)
    const { data: overdueTasksData } = useTasks({
        is_completed: false,
        my_tasks: true,
        per_page: 10,
    })

    const notifications = notificationsData?.items ?? []
    const unreadCount = notificationsData?.unread_count ?? 0

    // Filter overdue tasks client-side (due_date < today)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const overdueTasks = (overdueTasksData?.items ?? []).filter((task) => {
        if (!task.due_date) return false
        const dueDate = new Date(task.due_date)
        return dueDate < today
    })

    const handleNotificationClick = (notification: Notification) => {
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }
        if (notification.entity_type === "case" && notification.entity_id) {
            router.push(`/cases/${notification.entity_id}`)
        } else if (notification.entity_type === "task" && notification.entity_id) {
            router.push(`/tasks`)
        } else if (notification.entity_type === "appointment" && notification.entity_id) {
            router.push(`/appointments/${notification.entity_id}`)
        }
    }

    const handleMarkAllRead = () => {
        markAllRead.mutate()
    }

    const getDaysOverdue = (dueDate: string) => {
        const due = new Date(dueDate)
        const diffTime = today.getTime() - due.getTime()
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    }

    if (isLoading) {
        return (
            <div className="flex min-h-screen flex-col">
                <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                    <div className="flex h-16 items-center justify-between px-6">
                        <Skeleton className="h-8 w-48" />
                        <Skeleton className="h-9 w-28" />
                    </div>
                </div>
                <div className="flex-1 space-y-6 p-6">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full" />
                    ))}
                </div>
            </div>
        )
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <div className="flex items-center gap-3">
                        <BellIcon className="size-6" />
                        <h1 className="text-2xl font-semibold">Notifications</h1>
                        {unreadCount > 0 && (
                            <Badge variant="secondary" className="bg-teal-500/10 text-teal-500 border-teal-500/20">
                                {unreadCount} unread
                            </Badge>
                        )}
                    </div>
                    {unreadCount > 0 && (
                        <Button variant="outline" onClick={handleMarkAllRead} disabled={markAllRead.isPending}>
                            Mark all read
                        </Button>
                    )}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-6 p-6">
                {/* Filter Bar */}
                <div className="flex items-center gap-3">
                    <Select value={typeFilter} onValueChange={(v) => { if (v) setTypeFilter(v) }}>
                        <SelectTrigger className="w-[200px]">
                            <SelectValue placeholder="Filter by type">
                                {(value: string | null) => {
                                    const labels: Record<string, string> = {
                                        all: "All",
                                        case: "Case Updates",
                                        task: "Task Updates",
                                        appointment: "Appointments",
                                    }
                                    return labels[value ?? "all"] ?? "All"
                                }}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All</SelectItem>
                            <SelectItem value="case">Case Updates</SelectItem>
                            <SelectItem value="task">Task Updates</SelectItem>
                            <SelectItem value="appointment">Appointments</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Overdue Tasks Section */}
                {overdueTasks.length > 0 && (
                    <Collapsible open={isOverdueOpen} onOpenChange={setIsOverdueOpen}>
                        <Card className="border-red-500/20 bg-red-500/5">
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className="flex size-10 items-center justify-center rounded-lg bg-red-500/10">
                                            <AlertCircleIcon className="size-5 text-red-500" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-red-500">Overdue Tasks</CardTitle>
                                            <CardDescription className="text-red-400/80">
                                                {overdueTasks.length} task{overdueTasks.length > 1 ? "s" : ""} need immediate attention
                                            </CardDescription>
                                        </div>
                                    </div>
                                    <CollapsibleTrigger>
                                        <span className="inline-flex items-center justify-center h-9 w-9 rounded-md hover:bg-accent hover:text-accent-foreground cursor-pointer">
                                            {isOverdueOpen ? <ChevronUpIcon className="size-4" /> : <ChevronDownIcon className="size-4" />}
                                        </span>
                                    </CollapsibleTrigger>
                                </div>
                            </CardHeader>
                            <CollapsibleContent>
                                <CardContent className="space-y-3">
                                    {overdueTasks.map((task) => (
                                        <Link
                                            key={task.id}
                                            href="/tasks"
                                            className="flex items-start justify-between rounded-lg border border-red-500/10 bg-background p-4 transition-colors hover:bg-red-500/5"
                                        >
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <CheckSquareIcon className="size-4 text-red-500" />
                                                    <span className="font-medium">{task.title}</span>
                                                </div>
                                                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                                                    <span className="text-red-500">
                                                        {getDaysOverdue(task.due_date!)} day{getDaysOverdue(task.due_date!) > 1 ? "s" : ""} overdue
                                                    </span>
                                                    {task.owner_name && (
                                                        <>
                                                            <span>•</span>
                                                            <span>Assigned to {task.owner_name}</span>
                                                        </>
                                                    )}
                                                    {task.case_number && (
                                                        <>
                                                            <span>•</span>
                                                            <span className="text-teal-500">
                                                                Case #{task.case_number}
                                                            </span>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </Link>
                                    ))}
                                    <Link href="/tasks" className="block pt-2 text-center text-sm text-teal-500 hover:underline">
                                        View all tasks →
                                    </Link>
                                </CardContent>
                            </CollapsibleContent>
                        </Card>
                    </Collapsible>
                )}

                {/* Recent Notifications Section */}
                <Card>
                    <CardHeader>
                        <CardTitle>Recent Notifications</CardTitle>
                        <CardDescription>Stay updated with your latest activity</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {notifications.length > 0 ? (
                            <ScrollArea className="h-[600px] pr-4">
                                <div className="space-y-3">
                                    {notifications.map((notification) => {
                                        const Icon = getNotificationIcon(notification.type)
                                        return (
                                            <div
                                                key={notification.id}
                                                onClick={() => handleNotificationClick(notification)}
                                                className={`block rounded-lg border p-4 transition-colors hover:bg-accent cursor-pointer ${!notification.read_at ? "border-l-4 border-l-blue-500 bg-blue-500/5" : "border-border"
                                                    }`}
                                            >
                                                <div className="flex items-start gap-3">
                                                    {!notification.read_at && (
                                                        <div className="mt-1.5 size-2 rounded-full bg-blue-500 flex-shrink-0" />
                                                    )}
                                                    <div className="flex size-10 items-center justify-center rounded-lg bg-muted flex-shrink-0">
                                                        <Icon className="size-5" />
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className={`font-medium ${!notification.read_at ? "font-bold" : ""}`}>
                                                            {notification.title}
                                                        </div>
                                                        {notification.body && (
                                                            <p className="mt-1 text-sm text-muted-foreground">{notification.body}</p>
                                                        )}
                                                        <div className="mt-2 text-xs text-muted-foreground">
                                                            {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </ScrollArea>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-12 text-center">
                                <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
                                    <BellIcon className="size-8 text-muted-foreground" />
                                </div>
                                <h3 className="text-lg font-semibold">You're all caught up!</h3>
                                <p className="mt-1 text-sm text-muted-foreground">No notifications to display</p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
