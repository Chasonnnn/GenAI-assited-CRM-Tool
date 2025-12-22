"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuGroup,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarInset,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    SidebarMenuSub,
    SidebarMenuSubButton,
    SidebarMenuSubItem,
    SidebarProvider,
    SidebarRail,
    SidebarTrigger,
} from "@/components/ui/sidebar"
import {
    Home,
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
    ChevronRightIcon,
    CalendarIcon,
    CalendarDays,
    HeartHandshake,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { NotificationBell } from "@/components/notification-bell"
import { ThemeToggle } from "@/components/theme-toggle"

const navigation = [
    {
        title: "Dashboard",
        url: "/dashboard",
        icon: Home,
    },
    {
        title: "Cases",
        url: "/cases",
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
    {
        title: "Reports",
        url: "/reports",
        icon: BarChart3,
    },
]

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

export function AppSidebar({ children }: AppSidebarProps) {
    const pathname = usePathname()
    const searchParams = useSearchParams()
    const { user } = useAuth()
    const isManager = user?.role && ['admin', 'developer'].includes(user.role)
    const isAdmin = user?.role === 'admin'
    const isDeveloper = user?.role === 'developer'
    const activeSettingsTab = searchParams.get("tab")
    const activeAutomationTab = searchParams.get("tab")

    // Controlled collapsible state to avoid hydration warning
    const [automationOpen, setAutomationOpen] = React.useState(false)
    const [settingsOpen, setSettingsOpen] = React.useState(false)
    const [tasksOpen, setTasksOpen] = React.useState(false)

    // Sync collapsible state with pathname on mount/navigation
    React.useEffect(() => {
        if (pathname?.startsWith("/automation")) setAutomationOpen(true)
        if (pathname?.startsWith("/settings")) setSettingsOpen(true)
        if (pathname?.startsWith("/tasks") || pathname?.startsWith("/appointments")) setTasksOpen(true)
    }, [pathname])

    const settingsItems: Array<{ title: string; url: string; tab?: string | null }> = [
        { title: "General", url: "/settings", tab: null },
        { title: "Notifications", url: "/settings?tab=notifications", tab: "notifications" },
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
        { title: "Email Templates", url: "/automation?tab=email-templates", tab: "email-templates" },
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
                    "X-Requested-With": "XMLHttpRequest",
                },
            })
        } catch {
            // Ignore errors - we'll redirect anyway
        }
        window.location.href = "/login"
    }

    return (
        <SidebarProvider>
            <Sidebar collapsible="icon">
                <SidebarHeader>
                    <SidebarMenu>
                        <SidebarMenuItem>
                            <Link href="/dashboard">
                                <SidebarMenuButton
                                    size="lg"
                                    tooltip="Surrogacy CRM"
                                >
                                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                                        <svg
                                            xmlns="http://www.w3.org/2000/svg"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="2"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            className="size-4"
                                        >
                                            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                                            <circle cx="9" cy="7" r="4" />
                                            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                                            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                                        </svg>
                                    </div>
                                    <div className="grid flex-1 text-left text-sm leading-tight">
                                        <span className="truncate font-semibold">Surrogacy CRM</span>
                                        <span className="truncate text-xs text-muted-foreground">
                                            {user?.org_name || "Loading..."}
                                        </span>
                                    </div>
                                </SidebarMenuButton>
                            </Link>
                        </SidebarMenuItem>
                    </SidebarMenu>
                </SidebarHeader>

                <SidebarContent>
                    <SidebarGroup>
                        <SidebarGroupLabel>Navigation</SidebarGroupLabel>
                        <SidebarMenu>
                            {navigation.map((item) => (
                                <SidebarMenuItem key={item.title}>
                                    <Link href={item.url}>
                                        <SidebarMenuButton
                                            isActive={pathname === item.url || pathname?.startsWith(item.url + "/")}
                                            tooltip={item.title}
                                        >
                                            <item.icon />
                                            <span>{item.title}</span>
                                        </SidebarMenuButton>
                                    </Link>
                                </SidebarMenuItem>
                            ))}
                            {/* Automation with sub-menu */}
                            <Collapsible
                                open={automationOpen}
                                onOpenChange={setAutomationOpen}
                                className="group/collapsible"
                            >
                                <SidebarMenuItem>
                                    <CollapsibleTrigger
                                        render={
                                            <SidebarMenuButton
                                                isActive={pathname?.startsWith("/automation")}
                                                tooltip={automationNavigation.title}
                                            >
                                                <automationNavigation.icon />
                                                <span>{automationNavigation.title}</span>
                                                <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                            </SidebarMenuButton>
                                        }
                                    />
                                    <CollapsibleContent>
                                        <SidebarMenuSub>
                                            {automationItems.map((subItem) => (
                                                <SidebarMenuSubItem key={subItem.url}>
                                                    <SidebarMenuSubButton
                                                        href={subItem.url}
                                                        isActive={isAutomationItemActive(subItem)}
                                                    >
                                                        <span>{subItem.title}</span>
                                                    </SidebarMenuSubButton>
                                                </SidebarMenuSubItem>
                                            ))}
                                        </SidebarMenuSub>
                                    </CollapsibleContent>
                                </SidebarMenuItem>
                            </Collapsible>
                            {/* Tasks & Scheduling with sub-menu */}
                            <Collapsible
                                open={tasksOpen}
                                onOpenChange={setTasksOpen}
                                className="group/collapsible"
                            >
                                <SidebarMenuItem>
                                    <CollapsibleTrigger
                                        render={
                                            <SidebarMenuButton
                                                isActive={pathname?.startsWith("/tasks") || pathname?.startsWith("/appointments") || pathname === "/settings/appointments"}
                                                tooltip={tasksNavigation.title}
                                            >
                                                <tasksNavigation.icon />
                                                <span>{tasksNavigation.title}</span>
                                                <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                            </SidebarMenuButton>
                                        }
                                    />
                                    <CollapsibleContent>
                                        <SidebarMenuSub>
                                            {tasksItems.map((subItem) => (
                                                <SidebarMenuSubItem key={subItem.url}>
                                                    <SidebarMenuSubButton
                                                        href={subItem.url}
                                                        isActive={pathname === subItem.url || pathname?.startsWith(subItem.url + "/")}
                                                    >
                                                        <span>{subItem.title}</span>
                                                    </SidebarMenuSubButton>
                                                </SidebarMenuSubItem>
                                            ))}
                                        </SidebarMenuSub>
                                    </CollapsibleContent>
                                </SidebarMenuItem>
                            </Collapsible>
                            {/* AI Assistant - only shown if enabled for org */}
                            {user?.ai_enabled && (
                                <SidebarMenuItem>
                                    <Link href={aiNavigation.url}>
                                        <SidebarMenuButton
                                            isActive={pathname === aiNavigation.url || pathname?.startsWith(aiNavigation.url + "/")}
                                            tooltip={aiNavigation.title}
                                        >
                                            <aiNavigation.icon />
                                            <span>{aiNavigation.title}</span>
                                        </SidebarMenuButton>
                                    </Link>
                                </SidebarMenuItem>
                            )}
                            {/* Settings with sub-menu */}
                            <Collapsible
                                open={settingsOpen}
                                onOpenChange={setSettingsOpen}
                                className="group/collapsible"
                            >
                                <SidebarMenuItem>
                                    <CollapsibleTrigger
                                        render={
                                            <SidebarMenuButton
                                                isActive={pathname?.startsWith("/settings")}
                                                tooltip={settingsNavigation.title}
                                            >
                                                <settingsNavigation.icon />
                                                <span>{settingsNavigation.title}</span>
                                                <ChevronRightIcon className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                                            </SidebarMenuButton>
                                        }
                                    />
                                    <CollapsibleContent>
                                        <SidebarMenuSub>
                                            {settingsItems.map((subItem) => (
                                                <SidebarMenuSubItem key={subItem.url}>
                                                    <SidebarMenuSubButton
                                                        href={subItem.url}
                                                        isActive={isSettingsItemActive(subItem)}
                                                    >
                                                        <span>{subItem.title}</span>
                                                    </SidebarMenuSubButton>
                                                </SidebarMenuSubItem>
                                            ))}
                                        </SidebarMenuSub>
                                    </CollapsibleContent>
                                </SidebarMenuItem>
                            </Collapsible>
                        </SidebarMenu>
                    </SidebarGroup>
                </SidebarContent>

                <SidebarFooter>
                    <SidebarMenu>
                        <SidebarMenuItem>
                            <DropdownMenu>
                                <DropdownMenuTrigger
                                    render={
                                        <SidebarMenuButton
                                            size="lg"
                                            className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                                        >
                                            <Avatar className="h-8 w-8 rounded-lg">
                                                <AvatarImage src="/placeholder.svg" alt={user?.display_name || "User"} />
                                                <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
                                            </Avatar>
                                            <div className="grid flex-1 text-left text-sm leading-tight">
                                                <span className="truncate font-semibold">{user?.display_name || "Loading..."}</span>
                                                <span className="truncate text-xs text-muted-foreground">{user?.email || ""}</span>
                                            </div>
                                            <ChevronsUpDown className="ml-auto size-4" />
                                        </SidebarMenuButton>
                                    }
                                />
                                <DropdownMenuContent
                                    className="w-56 rounded-lg"
                                    side="bottom"
                                    align="end"
                                    sideOffset={4}
                                >
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
                                    <DropdownMenuSeparator />
                                    <DropdownMenuGroup>
                                        <DropdownMenuItem>
                                            <Link href="/settings" className="flex items-center w-full">
                                                <User className="mr-2 h-4 w-4" />
                                                Profile
                                            </Link>
                                        </DropdownMenuItem>
                                        <DropdownMenuItem>
                                            <Link href="/notifications" className="flex items-center w-full">
                                                <Bell className="mr-2 h-4 w-4" />
                                                Notifications
                                            </Link>
                                        </DropdownMenuItem>
                                        <DropdownMenuItem>
                                            <Link href="/settings" className="flex items-center w-full">
                                                <Settings className="mr-2 h-4 w-4" />
                                                Settings
                                            </Link>
                                        </DropdownMenuItem>
                                    </DropdownMenuGroup>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
                                        <LogOut className="mr-2 h-4 w-4" />
                                        Log out
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </SidebarMenuItem>
                    </SidebarMenu>
                </SidebarFooter>
                <SidebarRail />
            </Sidebar>

            <SidebarInset>
                <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
                    <SidebarTrigger className="-ml-1" />
                    <div className="flex items-center gap-2">
                        <NotificationBell />
                        <ThemeToggle />
                    </div>
                </header>
                <main className="flex-1">{children}</main>
            </SidebarInset>
        </SidebarProvider>
    )
}
