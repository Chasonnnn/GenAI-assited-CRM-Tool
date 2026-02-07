"use client"

import * as React from "react"
import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { useSearchHotkey, SearchCommandDialog } from "@/components/search-command"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import {
    Home,
    FolderOpen,
    Inbox,
    Users,
    CheckSquare,
    BarChart3,
    Settings,
    ChevronsUpDown,
    LogOut,
    User,
    Bell,
    Zap,
    Bot,
    ChevronRightIcon,
    HeartHandshake,
    Search,
    PanelLeftIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { getCsrfHeaders } from "@/lib/csrf"
import { NotificationBell } from "@/components/notification-bell"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"
import { useIsMobile } from "@/hooks/use-mobile"

const SIDEBAR_COOKIE_NAME = "sidebar_state"
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7

const navigation = [
    {
        title: "Dashboard",
        url: "/dashboard",
        icon: Home,
    },
    {
        title: "Surrogates",
        url: "/surrogates",
        icon: FolderOpen,
    },
    {
        title: "Intended Parents",
        url: "/intended-parents",
        icon: Users,
    },
    {
        title: "Matches",
        url: "/intended-parents/matches",
        icon: HeartHandshake,
    },
]

const reportsNavigation = {
    title: "Reports",
    url: "/reports",
    icon: BarChart3,
}

const aiNavigation = {
    title: "AI Assistant",
    url: "/ai-assistant",
    icon: Bot,
}

const tasksNavigation = {
    title: "Tasks & Scheduling",
    icon: CheckSquare,
}

const settingsNavigation = {
    title: "Settings",
    url: "/settings",
    icon: Settings,
}

const automationNavigation = {
    title: "Automation",
    url: "/automation",
    icon: Zap,
}

interface AppSidebarProps {
    children: React.ReactNode
}

function readSidebarCookie() {
    if (typeof document === "undefined") return true
    const match = document.cookie
        .split(";")
        .map((c) => c.trim())
        .find((c) => c.startsWith(`${SIDEBAR_COOKIE_NAME}=`))
    if (!match) return true
    return match.split("=")[1] === "true"
}

export function AppSidebar({ children }: AppSidebarProps) {
    const pathname = usePathname()
    const searchParams = useSearchParams()
    const { user } = useAuth()
    const isManager = user?.role && ["admin", "developer"].includes(user.role)
    const isAdmin = user?.role === "admin"
    const isDeveloper = user?.role === "developer"
    const isMobile = useIsMobile()

    const navigationItems = React.useMemo(() => {
        const canViewUnassignedQueue =
            user?.role === "intake_specialist" || user?.role === "developer"
        if (!canViewUnassignedQueue) return navigation

        return [
            ...navigation.slice(0, 2),
            {
                title: "Unassigned Queue",
                url: "/surrogates/unassigned",
                icon: Inbox,
            },
            ...navigation.slice(2),
        ]
    }, [user?.role])

    const activeNavUrl = React.useMemo(() => {
        if (!pathname) return null
        const matches = navigationItems.filter(
            (item) => pathname === item.url || pathname.startsWith(item.url + "/")
        )
        if (matches.length === 0) return null
        matches.sort((a, b) => b.url.length - a.url.length)
        return matches[0]!.url
    }, [pathname, navigationItems])

    const activeSettingsTab = searchParams.get("tab")
    const activeAutomationTab = searchParams.get("tab")

    const [isExpanded, setIsExpanded] = useState(readSidebarCookie)
    const [mobileOpen, setMobileOpen] = useState(false)

    const isCollapsed = !isExpanded && !isMobile

    const setExpanded = useCallback((open: boolean) => {
        setIsExpanded(open)
        document.cookie = `${SIDEBAR_COOKIE_NAME}=${open}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`
    }, [])

    const toggleSidebar = useCallback(() => {
        if (isMobile) {
            setMobileOpen((prev) => !prev)
            return
        }
        setExpanded(!isExpanded)
    }, [isMobile, isExpanded, setExpanded])

    // Sync cookie on mount when switching between mobile/desktop
    useEffect(() => {
        if (!isMobile) {
            setIsExpanded(readSidebarCookie())
        }
    }, [isMobile])

    // Controlled collapsible state
    const [automationOpen, setAutomationOpen] = React.useState(false)
    const [settingsOpen, setSettingsOpen] = React.useState(false)
    const [tasksOpen, setTasksOpen] = React.useState(false)

    React.useEffect(() => {
        if (pathname?.startsWith("/automation")) setAutomationOpen(true)
        if (pathname?.startsWith("/settings") && !pathname?.startsWith("/settings/appointments")) {
            setSettingsOpen(true)
        }
        if (
            pathname?.startsWith("/tasks") ||
            pathname?.startsWith("/appointments") ||
            pathname === "/settings/appointments"
        ) {
            setTasksOpen(true)
        }
    }, [pathname])

    const settingsItems: Array<{ title: string; url: string; tab?: string | null }> = [
        { title: "General", url: "/settings", tab: null },
        { title: "Notification", url: "/settings/notifications" },
        ...(isManager ? [{ title: "Team", url: "/settings/team" }] : []),
        ...((isAdmin || isDeveloper) ? [{ title: "Pipelines", url: "/settings/pipelines" }] : []),
        ...(isManager ? [{ title: "Queue Management", url: "/settings/queues" }] : []),
        { title: "Audit Log", url: "/settings/audit" },
        ...(isManager ? [{ title: "Compliance", url: "/settings/compliance" }] : []),
        { title: "Integrations", url: "/settings/integrations" },
        { title: "System Alerts", url: "/settings/alerts" },
    ]

    const automationItems: Array<{ title: string; url: string; tab?: string | null }> = [
        { title: "Workflows", url: "/automation", tab: null },
        { title: "Campaigns", url: "/automation/campaigns" },
        { title: "Email Templates", url: "/automation/email-templates" },
        { title: "Form Builder", url: "/automation/forms" },
        { title: "AI Builder", url: "/automation/ai-builder" },
        ...(isManager || isDeveloper ? [{ title: "Executions", url: "/automation/executions" }] : []),
    ]

    const tasksItems: Array<{ title: string; url: string }> = [
        { title: "My Tasks", url: "/tasks" },
        { title: "Appointments", url: "/appointments" },
        { title: "Appointment Settings", url: "/settings/appointments" },
    ]

    const isSettingsItemActive = (item: { url: string; tab?: string | null }) => {
        if (item.tab !== undefined) {
            if (pathname !== "/settings") return false
            if (item.tab === null) return activeSettingsTab === null
            return activeSettingsTab === item.tab
        }
        return pathname === item.url
    }

    const isAutomationItemActive = (item: { url: string; tab?: string | null }) => {
        if (item.tab !== undefined) {
            if (pathname !== "/automation") return false
            if (item.tab === null) return activeAutomationTab === null
            return activeAutomationTab === item.tab
        }
        return pathname === item.url
    }

    const initials = user?.display_name
        ?.split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2) || "??"

    const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

    const handleLogout = async () => {
        try {
            await fetch(`${API_BASE}/auth/logout`, {
                method: "POST",
                credentials: "include",
                headers: {
                    ...getCsrfHeaders(),
                },
            })
        } catch {
            // Ignore errors - we'll redirect anyway
        }
        window.location.href = "/login"
    }

    // Search command palette state
    const [searchOpen, setSearchOpen] = useState(false)
    const openSearch = useCallback(() => setSearchOpen(true), [])
    useSearchHotkey(openSearch)

    const navItemClass = useCallback(
        (active: boolean) =>
            cn(
                "ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground gap-2 rounded-lg p-2 text-left text-sm flex w-full items-center transition-colors focus-visible:ring-2 outline-none",
                active && "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
            ),
        []
    )

    const renderNavLink = useCallback(
        (item: { title: string; url: string; icon: React.ComponentType<{ className?: string }> }) => {
            const active = activeNavUrl === item.url
            const Icon = item.icon
            return (
                <Link
                    href={item.url}
                    prefetch={false}
                    className={navItemClass(active)}
                    title={item.title}
                >
                    <Icon className="size-4 shrink-0" />
                    {!isCollapsed && <span className="truncate">{item.title}</span>}
                </Link>
            )
        },
        [activeNavUrl, navItemClass, isCollapsed]
    )

    const sidebarContent = (
        <div className="flex h-full flex-col">
            <div className="p-2">
                <div className={cn("flex items-center gap-2 rounded-lg p-2", isCollapsed && "justify-center")}
                >
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                        <Users className="size-4" />
                    </div>
                    {!isCollapsed && (
                        <div className="grid flex-1 text-left text-sm leading-tight">
                            <span className="truncate font-semibold">Surrogacy Force</span>
                            <span className="truncate text-xs text-muted-foreground">
                                {user?.org_display_name || user?.org_name || "Loading..."}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div className="px-2">
                <Button
                    variant="secondary"
                    className={cn(
                        "w-full justify-start gap-2",
                        isCollapsed && "justify-center"
                    )}
                    onClick={openSearch}
                    title="Search (⌘K)"
                >
                    <Search className="h-4 w-4" />
                    {!isCollapsed && (
                        <span className="flex-1 text-left text-muted-foreground">Search</span>
                    )}
                </Button>
            </div>

            <nav className="flex-1 px-2 pt-3">
                <div className="mb-2 text-xs font-medium text-muted-foreground">Navigation</div>
                <div className="flex flex-col gap-1">
                    {navigationItems.map((item) => (
                        <div key={item.title}>{renderNavLink(item)}</div>
                    ))}

                    <button
                        type="button"
                        onClick={() => setTasksOpen((o) => !o)}
                        className={navItemClass(pathname?.startsWith("/tasks") || pathname?.startsWith("/appointments") || pathname === "/settings/appointments")}
                        title={tasksNavigation.title}
                    >
                        <tasksNavigation.icon className="size-4 shrink-0" />
                        {!isCollapsed && (
                            <>
                                <span className="truncate">{tasksNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        tasksOpen && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </button>
                    {!isCollapsed && tasksOpen && (
                        <div className="ml-6 flex flex-col gap-1">
                            {tasksItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url}
                                    prefetch={false}
                                    className={navItemClass(pathname === subItem.url || pathname?.startsWith(subItem.url + "/"))}
                                >
                                    <span className="truncate text-sm">{subItem.title}</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    <button
                        type="button"
                        onClick={() => setAutomationOpen((o) => !o)}
                        className={navItemClass(pathname?.startsWith("/automation"))}
                        title={automationNavigation.title}
                    >
                        <automationNavigation.icon className="size-4 shrink-0" />
                        {!isCollapsed && (
                            <>
                                <span className="truncate">{automationNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        automationOpen && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </button>
                    {!isCollapsed && automationOpen && (
                        <div className="ml-6 flex flex-col gap-1">
                            {automationItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url}
                                    prefetch={false}
                                    className={navItemClass(isAutomationItemActive(subItem))}
                                >
                                    <span className="truncate text-sm">{subItem.title}</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    <div>{renderNavLink(reportsNavigation)}</div>

                    {user?.ai_enabled && (
                        <div>{renderNavLink(aiNavigation)}</div>
                    )}

                    <button
                        type="button"
                        onClick={() => setSettingsOpen((o) => !o)}
                        className={navItemClass(pathname?.startsWith("/settings") && !pathname?.startsWith("/settings/appointments"))}
                        title={settingsNavigation.title}
                    >
                        <settingsNavigation.icon className="size-4 shrink-0" />
                        {!isCollapsed && (
                            <>
                                <span className="truncate">{settingsNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        settingsOpen && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </button>
                    {!isCollapsed && settingsOpen && (
                        <div className="ml-6 flex flex-col gap-1">
                            {settingsItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url}
                                    prefetch={false}
                                    className={navItemClass(isSettingsItemActive(subItem))}
                                >
                                    <span className="truncate text-sm">{subItem.title}</span>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </nav>

            <div className="mt-auto p-2">
                <DropdownMenu>
                    <DropdownMenuTrigger
                        render={
                            <button
                                className={cn(
                                    "w-full rounded-lg data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground",
                                    navItemClass(false)
                                )}
                            />
                        }
                    >
                        <Avatar className="h-8 w-8 rounded-lg">
                            <AvatarImage src="/placeholder.svg" alt={user?.display_name || "User"} />
                            <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                        </Avatar>
                        {!isCollapsed && (
                            <>
                                <div className="grid flex-1 text-left text-sm leading-tight">
                                    <span className="truncate font-semibold">{user?.display_name || "Loading..."}</span>
                                    <span className="truncate text-xs text-muted-foreground">{user?.email || ""}</span>
                                </div>
                                <ChevronsUpDown className="ml-auto size-4" />
                            </>
                        )}
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                        className="w-56 rounded-lg"
                        side="bottom"
                        align="end"
                        sideOffset={4}
                    >
                        <DropdownMenuGroup>
                            <DropdownMenuLabel className="p-0 font-normal">
                                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                                    <Avatar className="h-8 w-8 rounded-lg">
                                        <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                                    </Avatar>
                                    <div className="grid flex-1 text-left text-sm leading-tight">
                                        <span className="truncate font-semibold">{user?.display_name}</span>
                                        <span className="truncate text-xs">{user?.role}</span>
                                    </div>
                                </div>
                            </DropdownMenuLabel>
                        </DropdownMenuGroup>
                        <DropdownMenuSeparator />
                        <DropdownMenuGroup>
                            <DropdownMenuItem
                                className="flex items-center"
                                render={<Link href="/settings" prefetch={false} />}
                            >
                                <User className="mr-2 h-4 w-4" />
                                Profile
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="flex items-center"
                                render={<Link href="/settings/notifications" prefetch={false} />}
                            >
                                <Bell className="mr-2 h-4 w-4" />
                                Notifications
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="flex items-center"
                                render={<Link href="/settings" prefetch={false} />}
                            >
                                <Settings className="mr-2 h-4 w-4" />
                                Settings
                            </DropdownMenuItem>
                        </DropdownMenuGroup>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                            <LogOut className="mr-2 h-4 w-4" />
                            Log out
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    )

    return (
        <div className="flex min-h-svh w-full bg-sidebar">
            {isMobile && mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            <aside
                className={cn(
                    "bg-sidebar text-sidebar-foreground z-50 flex h-svh flex-col border-r border-sidebar-border transition-[width,transform] duration-200 ease-linear",
                    isCollapsed ? "w-12" : "w-64",
                    isMobile && "fixed inset-y-0 left-0",
                    isMobile && (mobileOpen ? "translate-x-0" : "-translate-x-full")
                )}
            >
                {sidebarContent}
            </aside>

            <div className="flex min-w-0 flex-1 flex-col bg-background">
                <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4 print:hidden">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleSidebar}
                        aria-label="Toggle sidebar"
                    >
                        <PanelLeftIcon className="size-4" />
                    </Button>
                    <div className="flex items-center gap-2">
                        <NotificationBell />
                        <ThemeToggle />
                    </div>
                </header>
                <main className="flex-1 min-w-0 overflow-hidden print:overflow-visible">{children}</main>
            </div>

            <SearchCommandDialog open={searchOpen} onOpenChange={setSearchOpen} />
        </div>
    )
}
