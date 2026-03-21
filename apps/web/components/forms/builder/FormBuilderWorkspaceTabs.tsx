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
        <div className="border-b border-border bg-background/95 px-4 py-1.5 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:px-6">
            <Tabs value={value} onValueChange={onValueChange} className="gap-0">
                <TabsList aria-label="Workspace sections" className="h-auto flex-wrap gap-1 bg-transparent p-0">
                    {tabs.map((tab) => (
                        <TabsTrigger key={tab.value} value={tab.value} className="flex-none text-sm">
                            {tab.label}
                            {tab.badgeCount && tab.badgeCount > 0 ? (
                                <Badge variant="secondary" className="ml-1 h-5 rounded-full px-1.5 text-[11px]">
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
