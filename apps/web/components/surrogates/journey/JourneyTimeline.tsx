"use client"

import { InfoIcon } from "lucide-react"
import { format, parseISO } from "date-fns"
import { JourneyMilestoneCard } from "./JourneyMilestoneCard"
import type { JourneyResponse, JourneyMilestone } from "@/lib/api/journey"

interface JourneyTimelineProps {
    journey: JourneyResponse
    surrogateId?: string
    canEditImages?: boolean
    onEditImage?: (milestoneSlug: string) => void
}

interface MilestoneWithMeta {
    milestone: JourneyMilestone
    globalIndex: number
    isFirst: boolean
    isLast: boolean
    side: "left" | "right"
}

interface PhaseWithMilestones {
    slug: string
    label: string
    milestones: MilestoneWithMeta[]
}

export function JourneyTimeline({
    journey,
    surrogateId,
    canEditImages = false,
    onEditImage,
}: JourneyTimelineProps) {
    // Flatten all milestones and compute metadata
    const allMilestones = journey.phases.flatMap((phase) => phase.milestones)
    const totalMilestones = allMilestones.length

    // Build phases with milestone metadata (including alternation)
    let globalIndex = 0
    const phasesWithMeta: PhaseWithMilestones[] = journey.phases.map((phase) => ({
        slug: phase.slug,
        label: phase.label,
        milestones: phase.milestones.map((milestone) => {
            const meta: MilestoneWithMeta = {
                milestone,
                globalIndex,
                isFirst: globalIndex === 0,
                isLast: globalIndex === totalMilestones - 1,
                side: globalIndex % 2 === 0 ? "left" : "right",
            }
            globalIndex++
            return meta
        }),
    }))

    return (
        <div className="space-y-12 print:space-y-8">
            {/* Terminal state banner */}
            {journey.is_terminal && journey.terminal_message && (
                <div className="relative overflow-hidden rounded-lg border border-stone-200 bg-stone-50 px-5 py-4 dark:border-stone-700 dark:bg-stone-900/50 print:border print:bg-white">
                    <div className="pointer-events-none absolute inset-0 opacity-[0.03]">
                        <svg className="size-full" xmlns="http://www.w3.org/2000/svg">
                            <defs>
                                <pattern id="terminal-dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
                                    <circle cx="2" cy="2" r="1" fill="currentColor" />
                                </pattern>
                            </defs>
                            <rect width="100%" height="100%" fill="url(#terminal-dots)" />
                        </svg>
                    </div>
                    <div className="relative flex items-start gap-3">
                        <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-stone-200 dark:bg-stone-700">
                            <InfoIcon className="size-3.5 text-stone-500 dark:text-stone-400" />
                        </div>
                        <div className="space-y-0.5">
                            <p className="text-sm font-medium text-stone-600 dark:text-stone-300">
                                {journey.terminal_message}
                            </p>
                            {journey.terminal_date && (
                                <p className="text-xs text-stone-500 dark:text-stone-400">
                                    {format(parseISO(journey.terminal_date), "MMMM yyyy")}
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Journey content with phases */}
            {phasesWithMeta.map((phase, phaseIndex) => (
                <section key={phase.slug}>
                    {/* Phase header - full width divider */}
                    <header className="mb-10 flex items-center gap-4 print:mb-6">
                        <div className="h-px flex-1 bg-stone-200 dark:bg-stone-700" />
                        <h3 className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.15em] text-stone-400 dark:text-stone-500">
                            {phase.label}
                        </h3>
                        <div className="h-px flex-1 bg-stone-200 dark:bg-stone-700" />
                    </header>

                    {/* Milestones with continuous spine (desktop: 3-column grid) */}
                    <div className="relative">
                        {/* Continuous spine - desktop only, hidden on mobile and print */}
                        <div
                            className="absolute left-1/2 top-[6px] hidden w-px -translate-x-1/2 bg-stone-300 dark:bg-stone-600 md:block print:hidden"
                            style={{
                                height: `calc(100% - 12px)`,
                            }}
                            aria-hidden="true"
                        />

                        {/* Milestones grid */}
                        <div className="flex flex-col gap-y-16 print:gap-y-8">
                            {phase.milestones.map((meta) => (
                                <div
                                    key={meta.milestone.slug}
                                    className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto_1fr] md:gap-8"
                                >
                                    {/* Left column */}
                                    <div className="hidden md:block print:hidden">
                                        {meta.side === "left" && (
                                            <JourneyMilestoneCard
                                                milestone={meta.milestone}
                                                side="left"
                                                surrogateId={surrogateId}
                                                canEdit={canEditImages}
                                                onEditImage={onEditImage}
                                            />
                                        )}
                                    </div>

                                    {/* Center column - dot only (desktop) */}
                                    <div className="hidden items-start justify-center md:flex print:hidden">
                                        <MilestoneDot status={meta.milestone.status} />
                                    </div>

                                    {/* Right column */}
                                    <div className="hidden md:block print:hidden">
                                        {meta.side === "right" && (
                                            <JourneyMilestoneCard
                                                milestone={meta.milestone}
                                                side="right"
                                                surrogateId={surrogateId}
                                                canEdit={canEditImages}
                                                onEditImage={onEditImage}
                                            />
                                        )}
                                    </div>

                                    {/* Mobile layout - full width with dot on left */}
                                    <div className="flex gap-4 md:hidden print:flex">
                                        <div className="flex flex-col items-center">
                                            <MilestoneDot status={meta.milestone.status} />
                                        </div>
                                        <div className="flex-1">
                                            <JourneyMilestoneCard
                                                milestone={meta.milestone}
                                                side="left"
                                                surrogateId={surrogateId}
                                                canEdit={canEditImages}
                                                onEditImage={onEditImage}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>
            ))}
        </div>
    )
}

/**
 * Milestone dot - the only status indicator.
 * Completed: solid emerald
 * Current: solid primary with ring/glow
 * Upcoming: hollow (border only)
 */
function MilestoneDot({ status }: { status: "completed" | "current" | "upcoming" }) {
    if (status === "completed") {
        return (
            <div className="size-3 rounded-full bg-emerald-500 print:border print:border-stone-400 print:bg-white" />
        )
    }

    if (status === "current") {
        return (
            <div className="relative">
                <div className="size-3.5 rounded-full bg-primary ring-4 ring-primary/20 print:border-2 print:border-stone-900 print:bg-white print:ring-0" />
            </div>
        )
    }

    // Upcoming - hollow dot
    return (
        <div className="size-2.5 rounded-full border-2 border-stone-300 bg-transparent dark:border-stone-600 print:border-stone-400" />
    )
}
