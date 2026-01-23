import { format, parseISO } from "date-fns"
import { InfoIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import type { JourneyMilestone, JourneyResponse } from "@/lib/api/journey"

interface JourneyPrintViewProps {
    journey: JourneyResponse
}

interface MilestoneWithMeta {
    milestone: JourneyMilestone
    globalIndex: number
    side: "left" | "right"
}

interface PhaseWithMilestones {
    slug: string
    label: string
    milestones: MilestoneWithMeta[]
}

export function JourneyPrintView({ journey }: JourneyPrintViewProps) {
    const generatedDate = format(new Date(), "MMMM yyyy")

    let globalIndex = 0
    const phasesWithMeta: PhaseWithMilestones[] = journey.phases.map((phase) => ({
        slug: phase.slug,
        label: phase.label,
        milestones: phase.milestones.map((milestone) => {
            const meta: MilestoneWithMeta = {
                milestone,
                globalIndex,
                side: globalIndex % 2 === 0 ? "left" : "right",
            }
            globalIndex += 1
            return meta
        }),
    }))

    return (
        <div data-journey-print="ready" className="min-h-screen bg-background text-foreground">
            <Card className="relative overflow-hidden bg-gradient-to-br from-stone-50 via-stone-50/80 to-white">
                <div
                    className="pointer-events-none absolute inset-0 opacity-[0.03]"
                    style={{
                        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 4 4' xmlns='http://www.w3.org/2000/svg'%3E%3Ccircle cx='2' cy='2' r='0.5' fill='%2378716c'/%3E%3C/svg%3E")`,
                        backgroundSize: "4px 4px",
                    }}
                />
                <div className="relative border-b border-stone-200/80 px-6 py-8">
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

                <CardContent className="relative p-6 pt-8">
                    <div className="mx-auto max-w-[900px] space-y-12">
                        {journey.is_terminal && journey.terminal_message && (
                            <div className="relative overflow-hidden rounded-lg border border-stone-200 bg-stone-50 px-5 py-4">
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
                                    <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-stone-200">
                                        <InfoIcon className="size-3.5 text-stone-500" />
                                    </div>
                                    <div className="space-y-0.5">
                                        <p className="text-sm font-medium text-stone-600">
                                            {journey.terminal_message}
                                        </p>
                                        {journey.terminal_date && (
                                            <p className="text-xs text-stone-500">
                                                {format(parseISO(journey.terminal_date), "MMMM yyyy")}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {phasesWithMeta.map((phase) => (
                            <section key={phase.slug}>
                                <header className="mb-10 flex items-center gap-4">
                                    <div className="h-px flex-1 bg-stone-200" />
                                    <h3 className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.15em] text-stone-400">
                                        {phase.label}
                                    </h3>
                                    <div className="h-px flex-1 bg-stone-200" />
                                </header>

                                <div className="relative">
                                    <div
                                        className="absolute left-1/2 top-[6px] hidden w-px -translate-x-1/2 bg-stone-300 md:block"
                                        style={{ height: "calc(100% - 12px)" }}
                                        aria-hidden="true"
                                    />

                                    <div className="flex flex-col gap-y-16">
                                        {phase.milestones.map((meta) => (
                                            <div
                                                key={meta.milestone.slug}
                                                className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto_1fr] md:gap-8"
                                            >
                                                <div className="hidden md:block">
                                                    {meta.side === "left" && (
                                                        <JourneyPrintMilestoneCard milestone={meta.milestone} side="left" />
                                                    )}
                                                </div>

                                                <div className="hidden items-start justify-center md:flex">
                                                    <MilestoneDot status={meta.milestone.status} />
                                                </div>

                                                <div className="hidden md:block">
                                                    {meta.side === "right" && (
                                                        <JourneyPrintMilestoneCard milestone={meta.milestone} side="right" />
                                                    )}
                                                </div>

                                                <div className="flex gap-4 md:hidden">
                                                    <div className="flex flex-col items-center">
                                                        <MilestoneDot status={meta.milestone.status} />
                                                    </div>
                                                    <div className="flex-1">
                                                        <JourneyPrintMilestoneCard milestone={meta.milestone} side="left" />
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </section>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

function MilestoneDot({ status }: { status: "completed" | "current" | "upcoming" }) {
    if (status === "completed") {
        return <div className="size-3 rounded-full bg-emerald-500" />
    }

    if (status === "current") {
        return (
            <div className="relative">
                <div className="size-3.5 rounded-full bg-primary ring-4 ring-primary/20" />
            </div>
        )
    }

    return <div className="size-2.5 rounded-full border-2 border-stone-300 bg-transparent" />
}

function JourneyPrintMilestoneCard({
    milestone,
    side,
}: {
    milestone: JourneyMilestone
    side: "left" | "right"
}) {
    const completedDate = milestone.completed_at ? parseISO(milestone.completed_at) : null
    const showDate = !!completedDate && !milestone.is_soft
    const imageUrl = milestone.featured_image_url || milestone.default_image_url

    const titleClass = milestone.status === "upcoming" ? "text-muted-foreground" : "text-foreground"
    const descriptionClass = milestone.status === "upcoming" ? "text-muted-foreground/60" : "text-muted-foreground"
    const metaClass = milestone.status === "upcoming" ? "text-muted-foreground/50" : "text-muted-foreground/70"

    return (
        <article
            className={cn(
                "space-y-3",
                side === "left" ? "md:text-right" : "md:text-left"
            )}
        >
            <h4 className={cn("text-lg font-semibold leading-snug tracking-tight", titleClass)}>
                {milestone.label}
            </h4>
            <p className={cn("text-sm leading-loose line-clamp-4", descriptionClass)}>
                {milestone.description}
            </p>
            {showDate && completedDate && (
                <p className={cn("text-xs", metaClass)}>
                    {milestone.status === "completed" ? "Completed " : ""}
                    {format(completedDate, "MMMM yyyy")}
                </p>
            )}
            <div className="relative mt-4 aspect-[16/9] overflow-hidden rounded-lg bg-stone-100">
                {imageUrl ? (
                    <img
                        src={imageUrl}
                        alt={`${milestone.label} milestone`}
                        className="size-full object-cover"
                    />
                ) : (
                    <MilestonePlaceholder slug={milestone.slug} />
                )}
            </div>
        </article>
    )
}

function MilestonePlaceholder({ slug }: { slug: string }) {
    const hash = slug.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0)
    const patternIndex = hash % 4

    const patterns = [
        <svg key="circles" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <circle cx="80" cy="45" r="35" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <circle cx="80" cy="45" r="25" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <circle cx="80" cy="45" r="15" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <circle cx="80" cy="45" r="5" fill="currentColor" className="text-stone-300" />
        </svg>,
        <svg key="waves" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <path d="M0 35 Q40 25 80 35 T160 35" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <path d="M0 45 Q40 35 80 45 T160 45" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <path d="M0 55 Q40 45 80 55 T160 55" fill="none" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
        </svg>,
        <svg key="diagonals" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            <line x1="40" y1="10" x2="120" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <line x1="60" y1="10" x2="140" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
            <line x1="20" y1="10" x2="100" y2="80" stroke="currentColor" strokeWidth="0.5" className="text-stone-300" />
        </svg>,
        <svg key="dots" className="size-full" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice">
            {[30, 50, 70, 90, 110, 130].map((x) =>
                [25, 45, 65].map((y) => (
                    <circle key={`${x}-${y}`} cx={x} cy={y} r="2" fill="currentColor" className="text-stone-300" />
                ))
            )}
        </svg>,
    ]

    return patterns[patternIndex]
}
