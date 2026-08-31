import { ActivityIcon, PlusIcon } from "lucide-react"

import { Button } from "@/components/ui/button"

export function AutomationPageHeader({
    activeTab,
    onOpenExecutions,
    onCreateTemplate,
}: {
    activeTab: string
    onOpenExecutions: () => void
    onCreateTemplate: () => void
}) {
    return (
        <div className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="flex h-16 items-center justify-between px-6">
                <h1 className="text-2xl font-semibold">Workflows</h1>
                <div className="flex gap-3">
                    {activeTab === "workflows" && (
                        <Button variant="outline" onClick={onOpenExecutions}>
                            <ActivityIcon className="mr-2 size-4" />
                            Execution History
                        </Button>
                    )}
                    {activeTab === "email-templates" && (
                        <Button onClick={onCreateTemplate}>
                            <PlusIcon className="mr-2 size-4" />
                            New Template
                        </Button>
                    )}
                </div>
            </div>
        </div>
    )
}
