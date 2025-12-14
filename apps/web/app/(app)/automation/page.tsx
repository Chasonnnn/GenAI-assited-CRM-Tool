"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import {
    PlusIcon,
    MoreVerticalIcon,
    MailIcon,
    BellIcon,
    UserIcon,
    CalendarIcon,
    ClockIcon,
    CheckCircle2Icon,
    WorkflowIcon,
    ZapIcon,
} from "lucide-react"

// Sample automation workflows - TODO: Replace with API data
const automations = [
    {
        id: 1,
        name: "New Case Welcome Email",
        description: "Send welcome email when new case created",
        trigger: "Status → New",
        enabled: true,
        icon: MailIcon,
    },
    {
        id: 2,
        name: "Task Reminder Notifications",
        description: "Send reminder 24 hours before due",
        trigger: "24h before task",
        enabled: true,
        icon: BellIcon,
    },
    {
        id: 3,
        name: "Auto-assign to Team Lead",
        description: "Assign Meta leads to team lead",
        trigger: "Source = Meta",
        enabled: false,
        icon: UserIcon,
    },
    {
        id: 4,
        name: "Weekly Status Report",
        description: "Generate weekly case status report",
        trigger: "Mon 9:00 AM",
        enabled: true,
        icon: CalendarIcon,
    },
    {
        id: 5,
        name: "Case Follow-up Reminder",
        description: "Create task if inactive 7 days",
        trigger: "7 days inactive",
        enabled: false,
        icon: ClockIcon,
    },
    {
        id: 6,
        name: "Match Notification",
        description: "Notify all when case matched",
        trigger: "Status → Matched",
        enabled: true,
        icon: CheckCircle2Icon,
    },
]

// Sample automation templates
const templates = [
    {
        id: 1,
        name: "Welcome Email Series",
        description: "Automated onboarding emails for new cases",
        steps: 4,
        icon: "📧",
    },
    {
        id: 2,
        name: "Task Reminder System",
        description: "Automatic reminders before task deadlines",
        steps: 3,
        icon: "⏰",
    },
    {
        id: 3,
        name: "Status Change Alerts",
        description: "Notify team on important status changes",
        steps: 2,
        icon: "🔔",
    },
    {
        id: 4,
        name: "Weekly Digest",
        description: "Send weekly summary to stakeholders",
        steps: 1,
        icon: "📊",
    },
    {
        id: 5,
        name: "Lead Assignment",
        description: "Auto-assign based on source or criteria",
        steps: 2,
        icon: "🎯",
    },
    {
        id: 6,
        name: "Follow-up Generator",
        description: "Create follow-up tasks for inactive cases",
        steps: 3,
        icon: "📝",
    },
]

export default function AutomationPage() {
    const [activeTab, setActiveTab] = useState("workflows")
    const [enabledStates, setEnabledStates] = useState<Record<number, boolean>>(
        automations.reduce(
            (acc, auto) => {
                acc[auto.id] = auto.enabled
                return acc
            },
            {} as Record<number, boolean>,
        ),
    )

    const handleToggle = (id: number) => {
        setEnabledStates((prev) => ({
            ...prev,
            [id]: !prev[id],
        }))
    }

    return (
        <div className="flex min-h-screen flex-col">
            {/* Page Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div className="flex h-16 items-center justify-between px-6">
                    <h1 className="text-2xl font-semibold">Automation</h1>
                    <Button>
                        <PlusIcon className="mr-2 size-4" />
                        Create Automation
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                    {/* Sub-tabs */}
                    <TabsList>
                        <TabsTrigger value="workflows">Workflows</TabsTrigger>
                        <TabsTrigger value="templates">Templates</TabsTrigger>
                    </TabsList>

                    {/* Workflows Tab */}
                    <TabsContent value="workflows" className="space-y-4">
                        {/* Automation Cards */}
                        {automations.map((automation) => {
                            const IconComponent = automation.icon
                            return (
                                <Card key={automation.id}>
                                    <CardContent className="flex items-center justify-between p-6">
                                        <div className="flex items-start gap-4">
                                            {/* Icon */}
                                            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                                <IconComponent className="size-6" />
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1">
                                                <h3 className="font-semibold">{automation.name}</h3>
                                                <p className="text-sm text-muted-foreground">{automation.description}</p>
                                                <div className="mt-2">
                                                    <Badge variant="secondary" className="text-xs">
                                                        Trigger: {automation.trigger}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Actions */}
                                        <div className="flex items-center gap-3">
                                            <Switch
                                                checked={enabledStates[automation.id]}
                                                onCheckedChange={() => handleToggle(automation.id)}
                                            />
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="size-8 p-0">
                                                        <MoreVerticalIcon className="size-4" />
                                                        <span className="sr-only">Open menu</span>
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem>Edit</DropdownMenuItem>
                                                    <DropdownMenuItem>Duplicate</DropdownMenuItem>
                                                    <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </div>
                                    </CardContent>
                                </Card>
                            )
                        })}

                        {/* View Logs Button */}
                        <div className="flex justify-center pt-4">
                            <Button variant="ghost">
                                <WorkflowIcon className="mr-2 size-4" />
                                View automation logs
                            </Button>
                        </div>
                    </TabsContent>

                    {/* Templates Tab */}
                    <TabsContent value="templates" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {templates.map((template) => (
                                <Card key={template.id} className="flex flex-col">
                                    <CardHeader className="flex-1">
                                        {/* Icon */}
                                        <div className="mb-4 flex size-16 items-center justify-center rounded-lg bg-primary/10 text-4xl">
                                            {template.icon}
                                        </div>

                                        <CardTitle className="text-lg">{template.name}</CardTitle>
                                        <CardDescription className="flex-1">{template.description}</CardDescription>

                                        <div className="pt-2">
                                            <Badge variant="secondary" className="text-xs">
                                                {template.steps} {template.steps === 1 ? "step" : "steps"}
                                            </Badge>
                                        </div>
                                    </CardHeader>

                                    <CardContent className="pt-0">
                                        <Button className="w-full">
                                            <ZapIcon className="mr-2 size-4" />
                                            Use Template
                                        </Button>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}
