"use client"

import { Loader2Icon, SparklesIcon } from "lucide-react"
import { format } from "date-fns"
import { Card, CardContent } from "@/components/ui/card"
import { useSurrogateJourney } from "@/lib/hooks/use-journey"
import { JourneyTimeline } from "./JourneyTimeline"

interface SurrogateJourneyTabProps {
    surrogateId: string
}

export function SurrogateJourneyTab({ surrogateId }: SurrogateJourneyTabProps) {
    const { data: journey, isLoading, error } = useSurrogateJourney(surrogateId)

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
        <Card className="overflow-hidden print:border-0 print:shadow-none">
            {/* Document-style header */}
            <div className="border-b border-stone-200 bg-gradient-to-b from-stone-50 to-white px-6 py-8 dark:border-stone-700 dark:from-stone-900 dark:to-stone-900/50 print:bg-white print:py-6">
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
            <CardContent className="p-6 pt-8 print:p-8 print:pt-6">
                <div className="mx-auto max-w-[900px]">
                    <JourneyTimeline journey={journey} />
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
        </Card>
    )
}
