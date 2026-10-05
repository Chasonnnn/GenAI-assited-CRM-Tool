"use client"

import * as React from "react"
import { useParams } from "next/navigation"
import { QueryErrorState } from "@/components/error-state"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { usePermissionCheck } from "@/lib/hooks/use-permission-check"
import { Loader2Icon, SparklesIcon } from "lucide-react"
import { SurrogateDetailHeader } from "@/components/surrogates/detail/SurrogateDetailHeader"
import { SurrogateDetailProvider } from "@/components/surrogates/detail/SurrogateDetailContext"
import {
    SurrogateDetailLayoutProvider,
    useSurrogateDetailData,
    useSurrogateDetailTabs,
} from "./context"
import { HeaderActions } from "./HeaderActions"
import { Dialogs } from "./dialogs"
import { AppointmentHeaderBadge } from "@/components/surrogates/InterviewAppointmentManager"

// ============================================================================
// Main Layout Component
// ============================================================================

function SurrogateDetailLayoutContent({ children }: { children: React.ReactNode }) {
    const {
        surrogate,
        isLoading,
        error,
        refetchSurrogate,
        isFetchingSurrogate,
        pausedFromStage,
        statusLabel,
        statusColor,
        noteCount,
        taskCount,
        canViewProfile,
        canEditSurrogate,
        navigateToList,
    } = useSurrogateDetailData()
    const {
        currentTab,
        setTab,
    } = useSurrogateDetailTabs()
    const { can } = usePermissionCheck()
    const canViewEmails = can("view_tickets")

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading surrogate</span>
            </div>
        )
    }

    if (error || !surrogate) {
        return (
            <div className="flex min-w-0 flex-1 flex-col items-center justify-center p-6">
                <QueryErrorState
                    error={error}
                    onRetry={refetchSurrogate}
                    isRetrying={isFetchingSurrogate}
                    title="Couldn't load surrogate"
                    forbidden={{
                        title: "No access to this surrogate",
                        description: "Ask an admin or the case owner for access.",
                        secondaryHref: "/surrogates",
                        secondaryLabel: "Back to Surrogates",
                    }}
                    notFound={{
                        title: "Surrogate not found",
                        backHref: "/surrogates",
                        backLabel: "Back to Surrogates",
                    }}
                    headingLevel={1}
                />
            </div>
        )
    }

    return (
        <div className="flex min-w-0 flex-1 flex-col">
            <SurrogateDetailHeader
                surrogateNumber={surrogate.surrogate_number}
                currentStageKey={surrogate.stage_key ?? null}
                currentStageSlug={surrogate.stage_slug ?? null}
                statusLabel={statusLabel}
                statusColor={statusColor}
                statusBadge={<>
                    {surrogate.is_shared_pool && <Badge variant="secondary">Surrogate Pool</Badge>}
                    <AppointmentHeaderBadge surrogateId={surrogate.id} />
                </>}
                latestContactOutcome={surrogate.latest_contact_outcome}
                pausedFromLabel={
                    surrogate.paused_from_stage_id
                        ? surrogate.paused_from_stage_label ?? pausedFromStage?.label ?? null
                        : null
                }
                isArchived={surrogate.is_archived}
                onBack={navigateToList}
            >
                <HeaderActions />
            </SurrogateDetailHeader>

            <div className="flex min-w-0 flex-1 flex-col gap-4 p-4 md:p-6">
                <Tabs value={currentTab} onValueChange={setTab} className="min-w-0 w-full">
                    <div className="mb-4 max-w-full overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden print:hidden">
                        <TabsList>
                            <TabsTrigger value="overview">Overview</TabsTrigger>
                            {canViewEmails && <TabsTrigger value="emails">Emails</TabsTrigger>}
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
                            <TabsTrigger value="journey">
                                Journey
                            </TabsTrigger>
                            <TabsTrigger value="ai" className="gap-1">
                                <SparklesIcon className="size-3" />
                                AI
                            </TabsTrigger>
                        </TabsList>
                    </div>

                    <SurrogateDetailProvider surrogate={surrogate} canEditSurrogate={canEditSurrogate}>
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
export {
    useSurrogateDetailData,
    useSurrogateDetailTabs,
    useSurrogateDetailDialogs,
    useSurrogateDetailQueue,
    useSurrogateDetailZoom,
    useSurrogateDetailActions,
} from "./context"
