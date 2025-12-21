"use client"

import * as React from "react"
import { Bell } from "lucide-react"
import { useRouter } from "next/navigation"
import { formatDistanceToNow } from "date-fns"

import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    useNotifications,
    useUnreadCount,
    useMarkRead,
    useMarkAllRead,
} from "@/lib/hooks/use-notifications"
import { useNotificationSocket } from "@/lib/hooks/use-notification-socket"
import type { Notification } from "@/lib/api/notifications"

export function NotificationBell() {
    const router = useRouter()
    const { data: countData } = useUnreadCount()
    const { data: notificationsData } = useNotifications({ limit: 10 })
    const markRead = useMarkRead()
    const markAllRead = useMarkAllRead()

    // Real-time WebSocket connection
    const { isConnected, unreadCount: wsUnreadCount } = useNotificationSocket()

    // Prefer WebSocket count when connected, fall back to polling
    const unreadCount = wsUnreadCount ?? countData?.count ?? 0
    const notifications = notificationsData?.items ?? []

    const handleNotificationClick = (notification: Notification) => {
        // Mark as read
        if (!notification.read_at) {
            markRead.mutate(notification.id)
        }

        // Navigate to entity
        if (notification.entity_type === "case" && notification.entity_id) {
            router.push(`/cases/${notification.entity_id}`)
        } else if (notification.entity_type === "task" && notification.entity_id) {
            router.push(`/tasks`)
        }
    }

    const handleMarkAllRead = () => {
        markAllRead.mutate()
    }

    const handleViewAll = () => {
        router.push("/notifications")
    }

    return (
        <DropdownMenu>
            <DropdownMenuTrigger>
                <span className="relative inline-flex items-center justify-center rounded-md text-sm font-medium h-9 w-9 hover:bg-accent hover:text-accent-foreground cursor-pointer">
                    <Bell className="h-5 w-5" />
                    {unreadCount > 0 && (
                        <Badge
                            variant="destructive"
                            className="absolute -top-1 -right-1 h-5 min-w-5 px-1 flex items-center justify-center text-xs"
                        >
                            {unreadCount > 99 ? "99+" : unreadCount}
                        </Badge>
                    )}
                </span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
                <div className="flex items-center justify-between px-3 py-2.5 text-xs text-muted-foreground">
                    <span className="font-medium">Notifications</span>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground"
                            onClick={handleMarkAllRead}
                        >
                            Mark all read
                        </Button>
                    )}
                </div>
                <DropdownMenuSeparator />

                {notifications.length === 0 ? (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                        No notifications
                    </div>
                ) : (
                    <ScrollArea className="h-[300px]">
                        {notifications.map((notification) => (
                            <DropdownMenuItem
                                key={notification.id}
                                className={`flex flex-col items-start gap-1 p-3 cursor-pointer ${!notification.read_at ? "bg-muted/50" : ""
                                    }`}
                                onClick={() => handleNotificationClick(notification)}
                            >
                                <div className="flex items-start justify-between w-full gap-2">
                                    <span className="font-medium text-sm line-clamp-1">
                                        {notification.title}
                                    </span>
                                    {!notification.read_at && (
                                        <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0 mt-1" />
                                    )}
                                </div>
                                {notification.body && (
                                    <span className="text-xs text-muted-foreground line-clamp-2">
                                        {notification.body}
                                    </span>
                                )}
                                <span className="text-xs text-muted-foreground">
                                    {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}
                                </span>
                            </DropdownMenuItem>
                        ))}
                    </ScrollArea>
                )}

                <DropdownMenuSeparator />
                <DropdownMenuItem
                    className="justify-center text-sm font-medium"
                    onClick={handleViewAll}
                >
                    View all notifications
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
