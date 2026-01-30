"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Loader2Icon, SparklesIcon } from "lucide-react"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"
import { SurrogateDetailProvider } from "@/components/surrogates/detail/SurrogateDetailContext"
import {
    SurrogateDetailLayoutProvider,
    useSurrogateDetailLayout,
} from "./context"
import { HeaderActions } from "./HeaderActions"
import { Dialogs } from "./dialogs"

// ============================================================================
// Main Layout Component
// ============================================================================

function SurrogateDetailLayoutContent({ children }: { children: React.ReactNode }) {
    const {
        surrogate,
        isLoading,
        error,
        statusLabel,
        statusColor,
        noteCount,
        taskCount,
        currentTab,
        setTab,
        canViewJourney,
        canViewProfile,
        navigateToList,
    } = useSurrogateDetailLayout()

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading surrogate...</span>
            </div>
        )
    }

    if (error || !surrogate) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Card className="p-6">
                    <p className="text-destructive">
                        Error loading surrogate: {error?.message || "Not found"}
                    </p>
                    <Button
                        variant="outline"
                        className="mt-4"
                        onClick={navigateToList}
                    >
                        Back to Surrogates
                    </Button>
                </Card>
            </div>
        )
    }

    return (
        <div className="flex flex-1 flex-col">
            <SurrogateDetailHeader
                surrogateNumber={surrogate.surrogate_number}
                statusLabel={statusLabel}
                statusColor={statusColor}
                isArchived={surrogate.is_archived}
                onBack={navigateToList}
            >
                <HeaderActions />
            </SurrogateDetailHeader>

            <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs value={currentTab} onValueChange={setTab} className="w-full">
                    <TabsList className="mb-4 overflow-x-auto print:hidden">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="notes">
                            Notes {noteCount > 0 && `(${noteCount})`}
                        </TabsTrigger>
                        <TabsTrigger value="tasks">
                            Tasks {taskCount > 0 && `(${taskCount})`}
                        </TabsTrigger>
                        <TabsTrigger value="interviews">Interviews</TabsTrigger>
                        <TabsTrigger value="application">Application</TabsTrigger>
                        {canViewProfile && <TabsTrigger value="profile">Profile</TabsTrigger>}
                        <TabsTrigger value="history">History</TabsTrigger>
                        <TabsTrigger value="journey" disabled={!canViewJourney}>
                            Journey
                        </TabsTrigger>
                        <TabsTrigger value="ai" className="gap-1">
                            <SparklesIcon className="h-3 w-3" />
                            AI
                        </TabsTrigger>
                    </TabsList>
                    {!canViewJourney && (
                        <p className="mt-1 text-xs text-muted-foreground">
                            Journey available after Match Confirmed
                        </p>
                    )}

                    <SurrogateDetailProvider surrogate={surrogate}>
                        {children}
                    </SurrogateDetailProvider>
                </Tabs>
            </div>

            <Dialogs />
        </div>
    )
}

// ============================================================================
// Exported Layout Component
// ============================================================================

interface SurrogateDetailLayoutProps {
    children: React.ReactNode
}

export function SurrogateDetailLayout({ children }: SurrogateDetailLayoutProps) {
    const params = useParams<{ id: string }>()
    const id = params.id

    return (
        <SurrogateDetailLayoutProvider surrogateId={id}>
            <SurrogateDetailLayoutContent>{children}</SurrogateDetailLayoutContent>
        </SurrogateDetailLayoutProvider>
    )
}

// Re-export types and context hook
export { useSurrogateDetailLayout, type TabValue } from "./context"
export type { ActiveDialog, ZoomFormState, SurrogateDetailLayoutContextValue } from "./context"
