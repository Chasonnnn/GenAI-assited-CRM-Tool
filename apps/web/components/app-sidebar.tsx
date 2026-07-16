"use client"

import * as React from "react"
import { useEffect, useReducer } from "react"
import type { Route } from "next"
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
    Inbox,
    FolderOpen,
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
    Sparkles,
    ChevronRightIcon,
    HeartHandshake,
    Search,
    PanelLeftIcon,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { useEffectivePermissions } from "@/lib/hooks/use-permissions"
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
        title: "Tickets",
        url: "/tickets",
        icon: Inbox,
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
        requiredPermission: "view_intended_parents",
    },
    {
        title: "Matches",
        url: "/intended-parents/matches",
        icon: HeartHandshake,
        requiredPermission: "view_matches",
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

const aiStudioNavigation = {
    title: "AI Studio Preview",
    url: "/ai-studio",
    icon: Sparkles,
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

type NavLinkItem = {
    title: string
    url: string
    icon: React.ComponentType<{ className?: string }>
}

type SidebarSection = "tasks" | "automation" | "settings"

type AppSidebarState = {
    pathname: string | null
    isExpanded: boolean
    mobileOpen: boolean
    automationOpen: boolean
    settingsOpen: boolean
    tasksOpen: boolean
    searchOpen: boolean
}

type AppSidebarAction =
    | { type: "setExpanded"; isExpanded: boolean }
    | { type: "setMobileOpen"; mobileOpen: boolean }
    | { type: "toggleMobileOpen" }
    | { type: "toggleSection"; section: SidebarSection }
    | { type: "syncPathname"; pathname: string | null }
    | { type: "setSearchOpen"; searchOpen: boolean }

function readSidebarCookie() {
    if (typeof document === "undefined") return true
    const match = document.cookie
        .split(";")
        .map((c) => c.trim())
        .find((c) => c.startsWith(`${SIDEBAR_COOKIE_NAME}=`))
    if (!match) return true
    return match.split("=")[1] === "true"
}

function getSectionsForPath(pathname: string | null) {
    return {
        automationOpen: pathname?.startsWith("/automation") === true,
        settingsOpen:
            pathname?.startsWith("/settings") === true &&
            pathname?.startsWith("/settings/appointments") !== true,
        tasksOpen:
            pathname?.startsWith("/tasks") === true ||
            pathname?.startsWith("/appointments") === true ||
            pathname === "/settings/appointments",
    }
}

function createInitialAppSidebarState(pathname: string | null): AppSidebarState {
    const sections = getSectionsForPath(pathname)
    return {
        pathname,
        isExpanded: readSidebarCookie(),
        mobileOpen: false,
        ...sections,
        searchOpen: false,
    }
}

function appSidebarReducer(state: AppSidebarState, action: AppSidebarAction): AppSidebarState {
    switch (action.type) {
        case "setExpanded":
            return { ...state, isExpanded: action.isExpanded }
        case "setMobileOpen":
            return { ...state, mobileOpen: action.mobileOpen }
        case "toggleMobileOpen":
            return { ...state, mobileOpen: !state.mobileOpen }
        case "toggleSection":
            return { ...state, [`${action.section}Open`]: !state[`${action.section}Open`] }
        case "syncPathname": {
            if (state.pathname === action.pathname) return state
            const sections = getSectionsForPath(action.pathname)
            return {
                ...state,
                pathname: action.pathname,
                automationOpen: state.automationOpen || sections.automationOpen,
                settingsOpen: state.settingsOpen || sections.settingsOpen,
                tasksOpen: state.tasksOpen || sections.tasksOpen,
            }
        }
        case "setSearchOpen":
            return { ...state, searchOpen: action.searchOpen }
    }
}

function getNavItemClass(active: boolean) {
    return cn(
        "ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground gap-2 rounded-lg p-2 text-left text-sm flex w-full items-center transition-colors focus-visible:ring-2 outline-none",
        active && "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
    )
}

function SidebarNavLink({
    item,
    active,
    isCollapsed,
}: {
    item: NavLinkItem
    active: boolean
    isCollapsed: boolean
}) {
    const Icon = item.icon
    return (
        <Link
            href={item.url as Route}
            prefetch={false}
            className={getNavItemClass(active)}
            title={item.title}
        >
            <Icon className="size-4 shrink-0" />
            {!isCollapsed && <span className="truncate">{item.title}</span>}
        </Link>
    )
}

type SidebarSubItem = { title: string; url: string; tab?: string | null }

type SidebarUser = {
    org_display_name?: string | null
    org_name?: string | null
    display_name?: string | null
    email?: string | null
    role?: string | null
    ai_enabled?: boolean | null
}

type AppSidebarContentProps = {
    user: SidebarUser | null | undefined
    initials: string
    pathname: string | null
    navigationItems: NavLinkItem[]
    tasksItems: SidebarSubItem[]
    automationItems: SidebarSubItem[]
    settingsItems: SidebarSubItem[]
    viewState: {
        collapsed: boolean
        reportsVisible: boolean
        sections: Record<SidebarSection, boolean>
    }
    activeState: {
        navItem: (item: NavLinkItem) => boolean
        automationItem: (item: SidebarSubItem) => boolean
        settingsItem: (item: SidebarSubItem) => boolean
    }
    onOpenSearch: () => void
    onLogout: () => void
    dispatch: React.Dispatch<AppSidebarAction>
}

function AppSidebarContent({
    user,
    initials,
    pathname,
    navigationItems,
    tasksItems,
    automationItems,
    settingsItems,
    viewState,
    activeState,
    onOpenSearch,
    onLogout,
    dispatch,
}: AppSidebarContentProps) {
    const { collapsed, reportsVisible, sections } = viewState

    return (
        <div className="flex h-full flex-col">
            <div className="p-2">
                <div className={cn("flex items-center gap-2 rounded-lg p-2", collapsed && "justify-center")}
                >
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                        <Users className="size-4" />
                    </div>
                    {!collapsed && (
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
                        collapsed && "justify-center"
                    )}
                    onClick={onOpenSearch}
                    title="Search (⌘K)"
                >
                    <Search className="size-4" />
                    {!collapsed && (
                        <span className="flex-1 text-left text-muted-foreground">Search</span>
                    )}
                </Button>
            </div>

            <nav className="flex-1 px-2 pt-3" aria-label="Navigation">
                {!collapsed && (
                    <div className="mb-2 text-xs font-medium text-muted-foreground">Navigation</div>
                )}
                <div className="flex flex-col gap-1">
                    {navigationItems.map((item) => (
                        <SidebarNavLink
                            key={item.title}
                            item={item}
                            active={activeState.navItem(item)}
                            isCollapsed={collapsed}
                        />
                    ))}

                    <Button unstyled
                        type="button"
                        onClick={() => dispatch({ type: "toggleSection", section: "tasks" })}
                        className={getNavItemClass(Boolean(pathname?.startsWith("/tasks")) || Boolean(pathname?.startsWith("/appointments")) || pathname === "/settings/appointments")}
                        title={tasksNavigation.title}
                        aria-expanded={sections.tasks}
                    >
                        <tasksNavigation.icon className="size-4 shrink-0" />
                        {!collapsed && (
                            <>
                                <span className="truncate">{tasksNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        sections.tasks && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </Button>
                    {!collapsed && sections.tasks && (
                        <div className="ml-6 flex flex-col gap-1">
                            {tasksItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url as Route}
                                    prefetch={false}
                                    className={getNavItemClass(pathname === subItem.url || Boolean(pathname?.startsWith(subItem.url + "/")))}
                                >
                                    <span className="truncate text-sm">{subItem.title}</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    <Button unstyled
                        type="button"
                        onClick={() => dispatch({ type: "toggleSection", section: "automation" })}
                        className={getNavItemClass(Boolean(pathname?.startsWith("/automation")))}
                        title={automationNavigation.title}
                        aria-expanded={sections.automation}
                    >
                        <automationNavigation.icon className="size-4 shrink-0" />
                        {!collapsed && (
                            <>
                                <span className="truncate">{automationNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        sections.automation && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </Button>
                    {!collapsed && sections.automation && (
                        <div className="ml-6 flex flex-col gap-1">
                            {automationItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url as Route}
                                    prefetch={false}
                                    className={getNavItemClass(activeState.automationItem(subItem))}
                                >
                                    <span className="truncate text-sm">{subItem.title}</span>
                                </Link>
                            ))}
                        </div>
                    )}

                    {user?.ai_enabled && (
                        <SidebarNavLink
                            item={aiStudioNavigation}
                            active={activeState.navItem(aiStudioNavigation)}
                            isCollapsed={collapsed}
                        />
                    )}

                    {reportsVisible && (
                        <SidebarNavLink
                            item={reportsNavigation}
                            active={activeState.navItem(reportsNavigation)}
                            isCollapsed={collapsed}
                        />
                    )}

                    {user?.ai_enabled && (
                        <SidebarNavLink
                            item={aiNavigation}
                            active={activeState.navItem(aiNavigation)}
                            isCollapsed={collapsed}
                        />
                    )}

                    <Button unstyled
                        type="button"
                        onClick={() => dispatch({ type: "toggleSection", section: "settings" })}
                        className={getNavItemClass(Boolean(pathname?.startsWith("/settings")) && !pathname?.startsWith("/settings/appointments"))}
                        title={settingsNavigation.title}
                        aria-expanded={sections.settings}
                    >
                        <settingsNavigation.icon className="size-4 shrink-0" />
                        {!collapsed && (
                            <>
                                <span className="truncate">{settingsNavigation.title}</span>
                                <ChevronRightIcon
                                    className={cn(
                                        "ml-auto transition-transform",
                                        sections.settings && "rotate-90"
                                    )}
                                />
                            </>
                        )}
                    </Button>
                    {!collapsed && sections.settings && (
                        <div className="ml-6 flex flex-col gap-1">
                            {settingsItems.map((subItem) => (
                                <Link
                                    key={subItem.url}
                                    href={subItem.url as Route}
                                    prefetch={false}
                                    className={getNavItemClass(activeState.settingsItem(subItem))}
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
                            <Button unstyled
                                type="button"
                                className={cn(
                                    "w-full rounded-lg data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground",
                                    getNavItemClass(false)
                                )}
                                aria-label="User menu"
                            />
                        }
                    >
                        <Avatar className="size-8 rounded-lg">
                            <AvatarImage src="/placeholder.svg" alt={user?.display_name || "User"} />
                            <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                        </Avatar>
                        {!collapsed && (
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
                                <div className="flex items-center gap-2 p-1.5 text-left text-sm">
                                    <Avatar className="size-8 rounded-lg">
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
                                <User className="mr-2 size-4" />
                                Profile
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="flex items-center"
                                render={<Link href="/settings/notifications" prefetch={false} />}
                            >
                                <Bell className="mr-2 size-4" />
                                Notifications
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                className="flex items-center"
                                render={<Link href="/settings" prefetch={false} />}
                            >
                                <Settings className="mr-2 size-4" />
                                Settings
                            </DropdownMenuItem>
                        </DropdownMenuGroup>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={onLogout} className="cursor-pointer">
                            <LogOut className="mr-2 size-4" />
                            Log out
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    )
}

export function AppSidebar({ children }: AppSidebarProps) {
    const pathname = usePathname()
    const searchParams = useSearchParams()
    const { user } = useAuth()
    const isDeveloper = user?.role === "developer"
    const { data: effectivePermissions } = useEffectivePermissions(user?.user_id ?? null)
    const permissionSet = new Set(effectivePermissions?.permissions ?? [])
    const canViewTeam = isDeveloper || permissionSet.has("manage_team")
    const canViewTickets = isDeveloper
    const canViewPipelines = isDeveloper || permissionSet.has("manage_pipelines")
    const canViewQueues = isDeveloper || permissionSet.has("manage_queues")
    const canViewCompliance = isDeveloper || permissionSet.has("manage_compliance")
    const canViewAudit = isDeveloper || permissionSet.has("view_audit_log")
    const canViewIntegrations = isDeveloper || permissionSet.has("manage_integrations")
    const canAccessPersonalIntegrations =
        user?.role === "intake_specialist" || user?.role === "case_manager"
    const canAccessIntegrations = canViewIntegrations || canAccessPersonalIntegrations
    const canViewAlerts = isDeveloper || permissionSet.has("manage_ops")
    const canViewAutomationExecutions = isDeveloper || permissionSet.has("manage_automation")
    const isMobile = useIsMobile()

    const canViewReports = isDeveloper || permissionSet.has("view_reports")

    const navigationItems = navigation.filter((item) => {
        if (item.url === "/tickets") return canViewTickets
        if ("requiredPermission" in item) {
            return isDeveloper || permissionSet.has(item.requiredPermission)
        }
        return true
    })

    const activeNavUrl = (() => {
        if (!pathname) return null
        const matches = navigationItems.filter(
            (item) => pathname === item.url || pathname.startsWith(item.url + "/")
        )
        if (matches.length === 0) return null
        matches.sort((a, b) => b.url.length - a.url.length)
        return matches[0]!.url
    })()

    const [state, dispatch] = useReducer(
        appSidebarReducer,
        pathname,
        createInitialAppSidebarState
    )
    if (state.pathname !== pathname) {
        dispatch({ type: "syncPathname", pathname })
    }
    const currentState = state.pathname === pathname
        ? state
        : appSidebarReducer(state, { type: "syncPathname", pathname })
    const {
        isExpanded,
        mobileOpen,
        automationOpen,
        settingsOpen,
        tasksOpen,
        searchOpen,
    } = currentState
    const activeTab = searchParams.get("tab")
    const activeSettingsTab = activeTab
    const activeAutomationTab = activeTab

    const isCollapsed = !isExpanded && !isMobile

    const setExpanded = (open: boolean) => {
        dispatch({ type: "setExpanded", isExpanded: open })
        document.cookie = `${SIDEBAR_COOKIE_NAME}=${open}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`
    }

    const toggleSidebar = () => {
        if (isMobile) {
            dispatch({ type: "toggleMobileOpen" })
            return
        }
        setExpanded(!isExpanded)
    }

    // Sync cookie on mount when switching between mobile/desktop
    useEffect(() => {
        if (!isMobile) {
            dispatch({ type: "setExpanded", isExpanded: readSidebarCookie() })
        }
    }, [isMobile])

    const settingsItems: Array<{ title: string; url: string; tab?: string | null }> = [
        { title: "General", url: "/settings", tab: null },
        { title: "Notification", url: "/settings/notifications" },
        ...(canViewTeam ? [{ title: "Team", url: "/settings/team" }] : []),
        ...(canViewPipelines ? [{ title: "Pipelines", url: "/settings/pipelines" }] : []),
        ...(canViewQueues ? [{ title: "Queue Management", url: "/settings/queues" }] : []),
        ...(canViewAudit ? [{ title: "Audit Log", url: "/settings/audit" }] : []),
        ...(canViewCompliance ? [{ title: "Compliance", url: "/settings/compliance" }] : []),
        ...(canAccessIntegrations ? [{ title: "Integrations", url: "/settings/integrations" }] : []),
        ...(canViewAlerts ? [{ title: "System Alerts", url: "/settings/alerts" }] : []),
    ]

    const automationItems: Array<{ title: string; url: string; tab?: string | null }> = [
        { title: "Workflows", url: "/automation", tab: null },
        { title: "Campaigns", url: "/automation/campaigns" },
        { title: "Email Templates", url: "/automation/email-templates" },
        { title: "Form Builder", url: "/automation/forms" },
        { title: "AI Builder", url: "/automation/ai-builder" },
        ...(canViewAutomationExecutions ? [{ title: "Executions", url: "/automation/executions" }] : []),
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

    const openSearch = () => dispatch({ type: "setSearchOpen", searchOpen: true })
    useSearchHotkey(openSearch)

    const isNavItemActive = (item: NavLinkItem) => activeNavUrl === item.url

    const sidebarContent = (
        <AppSidebarContent
            user={user}
            initials={initials}
            pathname={pathname}
            navigationItems={navigationItems}
            tasksItems={tasksItems}
            automationItems={automationItems}
            settingsItems={settingsItems}
            viewState={{
                collapsed: isCollapsed,
                reportsVisible: canViewReports,
                sections: {
                    tasks: tasksOpen,
                    automation: automationOpen,
                    settings: settingsOpen,
                },
            }}
            activeState={{
                navItem: isNavItemActive,
                automationItem: isAutomationItemActive,
                settingsItem: isSettingsItemActive,
            }}
            onOpenSearch={openSearch}
            onLogout={handleLogout}
            dispatch={dispatch}
        />
    )

    return (
        <div className="flex min-h-svh w-full bg-sidebar">
            {isMobile && mobileOpen && (
                <Button unstyled
                    type="button"
                    className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm appearance-none border-0 p-0 m-0"
                    onClick={() => dispatch({ type: "setMobileOpen", mobileOpen: false })}
                    aria-label="Close sidebar overlay"
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

            <SearchCommandDialog
                open={searchOpen}
                onOpenChange={(nextOpen) => dispatch({ type: "setSearchOpen", searchOpen: nextOpen })}
            />
        </div>
    )
}
