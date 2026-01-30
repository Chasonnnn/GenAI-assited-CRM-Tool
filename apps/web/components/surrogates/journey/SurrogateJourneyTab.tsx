"use client"

import { useState, useCallback } from "react"
import { ChevronDownIcon, DownloadIcon, Loader2Icon, SparklesIcon } from "lucide-react"
import { format } from "date-fns"
import { Card, CardContent } from "@/components/ui/card"
import { buttonVariants } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useSurrogateJourney } from "@/lib/hooks/use-journey"
import { exportJourneyPdf } from "@/lib/api/journey"
import type { JourneyExportVariant } from "@/lib/api/journey"
import { useAuth } from "@/lib/auth-context"
import { JourneyTimeline } from "./JourneyTimeline"
import { MilestoneImageSelector } from "./MilestoneImageSelector"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

// Roles that can edit journey images
const CAN_EDIT_ROLES = ["case_manager", "admin", "developer"]

interface SurrogateJourneyTabProps {
    surrogateId: string
}

export function SurrogateJourneyTab({ surrogateId }: SurrogateJourneyTabProps) {
    const { data: journey, isLoading, error } = useSurrogateJourney(surrogateId)
    const { user } = useAuth()

    // Image selector state
    const [selectorOpen, setSelectorOpen] = useState(false)
    const [selectedMilestone, setSelectedMilestone] = useState<{
        slug: string
        label: string
        currentAttachmentId: string | null
    } | null>(null)

    // Check if user can edit images
    const canEditImages = user?.role ? CAN_EDIT_ROLES.includes(user.role) : false

    const [exportingVariant, setExportingVariant] = useState<JourneyExportVariant | null>(null)
    const isExporting = exportingVariant !== null

    const handleExport = useCallback(async (variant: JourneyExportVariant) => {
        setExportingVariant(variant)
        try {
            await exportJourneyPdf(surrogateId, variant)
            toast.success("Journey exported as PDF")
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to export journey"
            toast.error(message)
        } finally {
            setExportingVariant(null)
        }
    }, [surrogateId])

    // Handle opening the image selector
    const handleEditImage = useCallback((milestoneSlug: string) => {
        if (!journey) return

        // Find the milestone to get its label and current attachment
        for (const phase of journey.phases) {
            const milestone = phase.milestones.find((m) => m.slug === milestoneSlug)
            if (milestone) {
                setSelectedMilestone({
                    slug: milestoneSlug,
                    label: milestone.label,
                    currentAttachmentId: milestone.featured_image_id,
                })
                setSelectorOpen(true)
                return
            }
        }
    }, [journey])

    if (isLoading) {
        return (
            <Card className="overflow-hidden">
                <div className="flex flex-col items-center justify-center py-20">
                    <div className="relative">
                        <Loader2Icon className="size-8 animate-spin text-primary/60" />
                        <div className="absolute inset-0 animate-pulse">
                            <Loader2Icon className="size-8 text-primary/20" />
                        </div>
                    </div>
                    <p className="mt-4 text-sm text-muted-foreground">
                        Loading journey...
                    </p>
                </div>
            </Card>
        )
    }

    if (error || !journey) {
        return (
            <Card className="overflow-hidden">
                <CardContent className="py-16 text-center">
                    <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-stone-100 dark:bg-stone-800">
                        <SparklesIcon className="size-7 text-stone-400" />
                    </div>
                    <p className="text-sm font-medium text-muted-foreground">
                        Unable to load journey timeline
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground/70">
                        Please try refreshing the page
                    </p>
                </CardContent>
            </Card>
        )
    }

    const generatedDate = format(new Date(), "MMMM yyyy")

    return (
        <Card className="relative overflow-hidden bg-gradient-to-br from-stone-50 via-stone-50/80 to-white dark:from-stone-900 dark:via-stone-900/90 dark:to-stone-950 print:border-0 print:bg-white print:shadow-none">
            {/* Paper grain texture overlay - hidden in print */}
            <div
                className="pointer-events-none absolute inset-0 opacity-[0.03] dark:opacity-[0.02] print:hidden"
                style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 4 4' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='2' cy='2' r='0.5' fill='%2378716c'/%3E%3C/svg%3E")`,
                    backgroundSize: "4px 4px",
                }}
            />

            {/* Document-style header */}
            <div className="relative border-b border-stone-200/80 px-6 py-8 dark:border-stone-700/50 print:py-6">
                <div className="absolute right-6 top-6 print:hidden">
                    <DropdownMenu>
                        <DropdownMenuTrigger
                            disabled={isExporting}
                            className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-2")}
                        >
                            {isExporting ? (
                                <Loader2Icon className="size-4 animate-spin" />
                            ) : (
                                <DownloadIcon className="size-4" />
                            )}
                            {isExporting ? "Exporting" : "Export"}
                            <ChevronDownIcon className="size-4 text-muted-foreground" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-64">
                            <DropdownMenuItem
                                onClick={() => handleExport("internal")}
                                disabled={isExporting}
                                className="flex flex-col items-start gap-0.5"
                            >
                                <span className="text-sm font-medium">Internal Use (Full)</span>
                                <span className="text-xs text-muted-foreground">
                                    Includes surrogate name and full timeline
                                </span>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                onClick={() => handleExport("client")}
                                disabled={isExporting}
                                className="flex flex-col items-start gap-0.5"
                            >
                                <span className="text-sm font-medium">Client Share (Redacted)</span>
                                <span className="text-xs text-muted-foreground">
                                    Name hidden · starts at Match Confirmed
                                </span>
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
                <div className="mx-auto max-w-[900px] text-center">
                    <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                        Surrogacy Journey
                    </h2>
                    <p className="mt-1 text-base text-muted-foreground">
                        {journey.surrogate_name}
                    </p>
                    <p className="mt-3 text-xs text-muted-foreground/70">
                        Generated {generatedDate}
                    </p>
                </div>
            </div>

            {/* Timeline content with max-width constraint */}
            <CardContent className="relative p-6 pt-8 print:p-8 print:pt-6">
                <div className="mx-auto max-w-[900px]">
                    <JourneyTimeline
                        journey={journey}
                        surrogateId={surrogateId}
                        canEditImages={canEditImages}
                        onEditImage={handleEditImage}
                    />
                </div>

                {/* Footer note for print */}
                <footer className="mx-auto mt-12 hidden max-w-[800px] border-t border-stone-200 pt-4 print:block">
                    <p className="text-center text-[10px] text-stone-400">
                        This document summarizes the surrogacy journey.
                        <br />
                        {journey.organization_name}
                    </p>
                </footer>
            </CardContent>

            {/* Image selector dialog */}
            {selectedMilestone && (
                <MilestoneImageSelector
                    open={selectorOpen}
                    onOpenChange={setSelectorOpen}
                    surrogateId={surrogateId}
                    milestoneSlug={selectedMilestone.slug}
                    milestoneLabel={selectedMilestone.label}
                    currentAttachmentId={selectedMilestone.currentAttachmentId}
                />
            )}
        </Card>
    )
}
