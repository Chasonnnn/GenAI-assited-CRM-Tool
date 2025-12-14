"use client"

import { useState } from "react"
import Link from "next/link"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { PlusIcon, SearchIcon } from "lucide-react"

// Sample data - TODO: Replace with API data
const tasks = [
    // Overdue
    {
        id: "1",
        title: "Follow up with Case #00042",
        caseId: "00042",
        status: "overdue",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        completed: false,
    },
    {
        id: "2",
        title: "Review questionnaire for Case #00038",
        caseId: "00038",
        status: "overdue",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        completed: false,
    },
    // Today
    {
        id: "3",
        title: "Schedule medical consultation",
        caseId: "00042",
        status: "today",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        completed: false,
    },
    {
        id: "4",
        title: "Update contact information",
        caseId: "00039",
        status: "today",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        completed: false,
    },
    {
        id: "5",
        title: "Send welcome packet",
        caseId: "00041",
        status: "today",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        completed: false,
    },
    // Tomorrow
    {
        id: "6",
        title: "Prepare contract documents",
        caseId: "00045",
        status: "tomorrow",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        completed: false,
    },
    {
        id: "7",
        title: "Schedule follow-up call",
        caseId: "00038",
        status: "tomorrow",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        completed: false,
    },
    // Next Week
    {
        id: "8",
        title: "Review application documents",
        caseId: "00040",
        status: "next-week",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        completed: false,
    },
    {
        id: "9",
        title: "Coordinate with legal team",
        caseId: "00042",
        status: "next-week",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        completed: false,
    },
    {
        id: "10",
        title: "Submit background check",
        caseId: "00039",
        status: "next-week",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        completed: false,
    },
]

const completedTasks = [
    {
        id: "c1",
        title: "Complete initial screening",
        caseId: "00042",
        status: "completed",
        assignee: { name: "Emily Chen", avatar: "/avatars/emily.jpg", initials: "EC" },
        completed: true,
    },
    {
        id: "c2",
        title: "Send confirmation email",
        caseId: "00041",
        status: "completed",
        assignee: { name: "John Smith", avatar: "/avatars/john.jpg", initials: "JS" },
        completed: true,
    },
    {
        id: "c3",
        title: "Review medical records",
        caseId: "00039",
        status: "completed",
        assignee: { name: "Sarah Davis", avatar: "/avatars/sarah.jpg", initials: "SD" },
        completed: true,
    },
]

const statusBadgeColors: Record<string, string> = {
    overdue: "bg-destructive/10 text-destructive border-destructive/20",
    today: "bg-amber-500/10 text-amber-500 border-amber-500/20",
    tomorrow: "bg-blue-500/10 text-blue-500 border-blue-500/20",
    "next-week": "bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20",
}

const statusLabels: Record<string, string> = {
    overdue: "Overdue",
    today: "Today",
    tomorrow: "Tomorrow",
    "next-week": "Next Week",
}

export default function TasksPage() {
    const [filter, setFilter] = useState<"all" | "assigned" | "unassigned">("all")
    const [searchQuery, setSearchQuery] = useState("")
    const [showCompleted, setShowCompleted] = useState(false)

    // Group tasks by status
    const overdueItems = tasks.filter((t) => t.status === "overdue")
    const todayItems = tasks.filter((t) => t.status === "today")
    const tomorrowItems = tasks.filter((t) => t.status === "tomorrow")
    const nextWeekItems = tasks.filter((t) => t.status === "next-week")

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Tasks</h1>
                    <Button>
                        <PlusIcon className="mr-2 size-4" />
                        Add Task
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 space-y-4 p-6">
                {/* Filters Row */}
                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex gap-2">
                        <Button variant={filter === "all" ? "secondary" : "ghost"} size="sm" onClick={() => setFilter("all")}>
                            All
                        </Button>
                        <Button
                            variant={filter === "assigned" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setFilter("assigned")}
                        >
                            Assigned to Me
                        </Button>
                        <Button
                            variant={filter === "unassigned" ? "secondary" : "ghost"}
                            size="sm"
                            onClick={() => setFilter("unassigned")}
                        >
                            Unassigned
                        </Button>
                    </div>

                    <div className="relative ml-auto w-full max-w-sm">
                        <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            placeholder="Search tasks..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-9"
                        />
                    </div>
                </div>

                {/* Tasks Card */}
                <Card className="p-6">
                    <div className="space-y-6">
                        {/* Overdue Section */}
                        {overdueItems.length > 0 && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    <div className="h-px flex-1 bg-destructive" />
                                    <h3 className="text-sm font-medium text-destructive">Overdue</h3>
                                    <div className="h-px flex-1 bg-destructive" />
                                </div>
                                <div className="space-y-2">
                                    {overdueItems.map((task) => (
                                        <div
                                            key={task.id}
                                            className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                                        >
                                            <Checkbox className="mt-0.5" />
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{task.title}</span>
                                                    <Badge variant="secondary" className={statusBadgeColors[task.status]}>
                                                        {statusLabels[task.status]}
                                                    </Badge>
                                                </div>
                                                <Link href={`/cases/${task.caseId}`} className="text-sm text-muted-foreground hover:underline">
                                                    Case #{task.caseId}
                                                </Link>
                                            </div>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={task.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{task.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{task.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Today Section */}
                        {todayItems.length > 0 && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    <div className="h-px flex-1 bg-border" />
                                    <h3 className="text-sm font-medium text-amber-500">Today</h3>
                                    <div className="h-px flex-1 bg-border" />
                                </div>
                                <div className="space-y-2">
                                    {todayItems.map((task) => (
                                        <div
                                            key={task.id}
                                            className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                                        >
                                            <Checkbox className="mt-0.5" />
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{task.title}</span>
                                                    <Badge variant="secondary" className={statusBadgeColors[task.status]}>
                                                        {statusLabels[task.status]}
                                                    </Badge>
                                                </div>
                                                <Link href={`/cases/${task.caseId}`} className="text-sm text-muted-foreground hover:underline">
                                                    Case #{task.caseId}
                                                </Link>
                                            </div>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={task.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{task.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{task.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Tomorrow Section */}
                        {tomorrowItems.length > 0 && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    <div className="h-px flex-1 bg-border" />
                                    <h3 className="text-sm font-medium text-muted-foreground">Tomorrow</h3>
                                    <div className="h-px flex-1 bg-border" />
                                </div>
                                <div className="space-y-2">
                                    {tomorrowItems.map((task) => (
                                        <div
                                            key={task.id}
                                            className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                                        >
                                            <Checkbox className="mt-0.5" />
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{task.title}</span>
                                                    <Badge variant="secondary" className={statusBadgeColors[task.status]}>
                                                        {statusLabels[task.status]}
                                                    </Badge>
                                                </div>
                                                <Link href={`/cases/${task.caseId}`} className="text-sm text-muted-foreground hover:underline">
                                                    Case #{task.caseId}
                                                </Link>
                                            </div>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={task.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{task.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{task.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Next Week Section */}
                        {nextWeekItems.length > 0 && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                    <div className="h-px flex-1 bg-border" />
                                    <h3 className="text-sm font-medium text-muted-foreground">Next Week</h3>
                                    <div className="h-px flex-1 bg-border" />
                                </div>
                                <div className="space-y-2">
                                    {nextWeekItems.map((task) => (
                                        <div
                                            key={task.id}
                                            className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                                        >
                                            <Checkbox className="mt-0.5" />
                                            <div className="flex-1 space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium">{task.title}</span>
                                                    <Badge variant="secondary" className={statusBadgeColors[task.status]}>
                                                        {statusLabels[task.status]}
                                                    </Badge>
                                                </div>
                                                <Link href={`/cases/${task.caseId}`} className="text-sm text-muted-foreground hover:underline">
                                                    Case #{task.caseId}
                                                </Link>
                                            </div>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={task.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{task.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{task.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Completed Tasks Section */}
                        <div className="border-t border-border pt-4">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowCompleted(!showCompleted)}
                                className="w-full justify-center"
                            >
                                {showCompleted ? "Hide" : "Show"} completed tasks ({completedTasks.length})
                            </Button>

                            {showCompleted && (
                                <div className="mt-4 space-y-2">
                                    {completedTasks.map((task) => (
                                        <div
                                            key={task.id}
                                            className="flex items-start gap-3 rounded-lg border border-border p-3 opacity-60"
                                        >
                                            <Checkbox checked className="mt-0.5" />
                                            <div className="flex-1 space-y-1">
                                                <span className="font-medium line-through">{task.title}</span>
                                                <Link
                                                    href={`/cases/${task.caseId}`}
                                                    className="block text-sm text-muted-foreground hover:underline"
                                                >
                                                    Case #{task.caseId}
                                                </Link>
                                            </div>
                                            <TooltipProvider>
                                                <Tooltip>
                                                    <TooltipTrigger>
                                                        <Avatar className="size-8">
                                                            <AvatarImage src={task.assignee.avatar || "/placeholder.svg"} />
                                                            <AvatarFallback>{task.assignee.initials}</AvatarFallback>
                                                        </Avatar>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>{task.assignee.name}</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </TooltipProvider>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    )
}
