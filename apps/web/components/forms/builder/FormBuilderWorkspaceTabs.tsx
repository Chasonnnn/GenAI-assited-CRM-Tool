"use client"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

type WorkspaceTab = {
    value: string
    label: string
    badgeCount?: number
}

type FormBuilderWorkspaceTabsProps = {
    value: string
    tabs: WorkspaceTab[]
    onValueChange: (value: string) => void
}

export function FormBuilderWorkspaceTabs({
    value,
    tabs,
    onValueChange,
}: FormBuilderWorkspaceTabsProps) {
    return (
        <div className="border-b border-border bg-background/95 px-4 py-2 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6">
            <Tabs value={value} onValueChange={onValueChange} className="gap-0">
                <TabsList aria-label="Workspace sections" className="h-auto flex-wrap bg-muted/70">
                    {tabs.map((tab) => (
                        <TabsTrigger key={tab.value} value={tab.value} className="flex-none">
                            {tab.label}
                            {tab.badgeCount && tab.badgeCount > 0 ? (
                                <Badge variant="secondary" className="ml-1">
                                    {tab.badgeCount}
                                </Badge>
                            ) : null}
                        </TabsTrigger>
                    ))}
                </TabsList>
            </Tabs>
        </div>
    )
}
