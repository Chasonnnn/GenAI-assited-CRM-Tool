"use client"

import { format, parseISO } from "date-fns"
import { cn } from "@/lib/utils"
import type { JourneyMilestone, JourneyMilestoneStatus } from "@/lib/api/journey"

interface JourneyMilestoneCardProps {
    milestone: JourneyMilestone
    side: "left" | "right"
}

const STATUS_STYLES: Record<JourneyMilestoneStatus, {
    title: string
    description: string
    meta: string
}> = {
    completed: {
        title: "text-foreground",
        description: "text-muted-foreground",
        meta: "text-muted-foreground/70",
    },
    current: {
        title: "text-foreground",
        description: "text-muted-foreground",
        meta: "text-muted-foreground/70",
    },
    upcoming: {
        title: "text-muted-foreground",
        description: "text-muted-foreground/60",
        meta: "text-muted-foreground/50",
    },
}

export function JourneyMilestoneCard({ milestone, side }: JourneyMilestoneCardProps) {
    const styles = STATUS_STYLES[milestone.status]
    const completedDate = milestone.completed_at ? parseISO(milestone.completed_at) : null

    // Show date only for completed/current milestones that are not soft
    const showDate = !!completedDate && !milestone.is_soft

    return (
        <article
            className={cn(
                "space-y-3",
                side === "left" ? "md:text-right" : "md:text-left",
                "print:break-inside-avoid print:page-break-inside-avoid"
            )}
        >
            {/* Title - larger, prominent */}
            <h4
                className={cn(
                    "text-lg font-semibold leading-snug tracking-tight",
                    styles.title
                )}
            >
                {milestone.label}
            </h4>

            {/* Narrative description - comfortable reading with truncation */}
            <p
                className={cn(
                    "text-sm leading-loose",
                    "line-clamp-4",
                    styles.description
                )}
            >
                {milestone.description}
            </p>

            {/* Meta line - human-readable date */}
            {showDate && (
                <p className={cn("text-xs", styles.meta)}>
                    {milestone.status === "completed" ? "Completed " : ""}
                    {format(completedDate, "MMMM yyyy")}
                </p>
            )}

            {/* Featured image placeholder - abstract illustration */}
            <div
                className={cn(
                    "relative mt-4 aspect-[16/9] overflow-hidden rounded-lg",
                    "bg-stone-100 dark:bg-stone-800/50",
                    "print:hidden"
                )}
            >
                <MilestonePlaceholder slug={milestone.slug} />
            </div>
        </article>
    )
}

/**
 * Deterministic placeholder illustration based on milestone slug.
 * Abstract, symbolic, stone-toned patterns.
 */
function MilestonePlaceholder({ slug }: { slug: string }) {
    // Generate a deterministic pattern variation based on slug
    const hash = slug.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0)
    const patternIndex = hash % 4

    const patterns = [
        // Concentric circles
        <svg key="circles" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <circle cx="80" cy="45" r="35" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <circle cx="80" cy="45" r="25" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <circle cx="80" cy="45" r="15" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <circle cx="80" cy="45" r="5" fill="currentColor" className="text-stone-300 dark:text-stone-600" />
        </svg>,
        // Wave lines
        <svg key="waves" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <path d="M0 35 Q40 25 80 35 T160 35" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <path d="M0 45 Q40 35 80 45 T160 45" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <path d="M0 55 Q40 45 80 55 T160 55" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
        </svg>,
        // Diagonal lines
        <svg key="diagonals" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <line x1="40" y1="10" x2="120" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <line x1="60" y1="10" x2="140" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
            <line x1="20" y1="10" x2="100" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300 dark:text-stone-600" />
        </svg>,
        // Dot grid
        <svg key="dots" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            {[30, 50, 70, 90, 110, 130].map((x) =>
                [25, 45, 65].map((y) => (
                    <circle key={`${x}-${y}`} cx={x} cy={y} r="2" fill="currentColor" className="text-stone-300 dark:text-stone-600" />
                ))
            )}
        </svg>,
    ]

    return patterns[patternIndex]
}
