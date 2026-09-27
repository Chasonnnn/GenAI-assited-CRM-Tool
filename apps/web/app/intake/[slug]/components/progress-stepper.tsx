import { cn } from "@/lib/utils"

export type Step = {
    id: number
    label: string
    shortLabel: string
}

export function ProgressStepper({
    currentStep,
    steps,
}: {
    currentStep: number
    steps: Step[]
}) {
    const totalSteps = steps.length
    const progressValue = totalSteps <= 0 ? 0 : Math.round((currentStep / totalSteps) * 100)
    const maxVisible = 5
    let start = Math.max(0, currentStep - 1 - Math.floor(maxVisible / 2))
    let end = start + maxVisible - 1
    if (end > totalSteps - 1) {
        end = totalSteps - 1
        start = Math.max(0, end - maxVisible + 1)
    }
    const visibleSteps = steps.slice(start, end + 1)

    return (
        <div className="space-y-3">
            {/* The current page title is the card heading below; it is not repeated here. */}
            <div className="text-center text-[11px] font-medium uppercase tracking-[0.22em] text-stone-500">
                Step {currentStep} of {totalSteps}
            </div>
            <progress
                aria-label="Application progress"
                value={progressValue}
                max={100}
                className="block h-1.5 w-full appearance-none overflow-hidden rounded-full border-0 bg-stone-200 accent-primary [&::-moz-progress-bar]:bg-primary [&::-webkit-progress-bar]:bg-stone-200 [&::-webkit-progress-value]:bg-primary"
            >
                {progressValue}%
            </progress>
            <div className="flex items-center justify-between gap-2 text-xs text-stone-500">
                {start > 0 && <span className="shrink-0 px-1">…</span>}
                {visibleSteps.map((step) => (
                    <div key={step.id} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                        <span
                            className={cn(
                                "size-1.5 rounded-full transition-colors",
                                step.id <= currentStep ? "bg-primary" : "bg-stone-300",
                            )}
                        />
                        <span
                            className={cn(
                                "max-w-full truncate transition-colors",
                                step.id === currentStep ? "font-semibold text-stone-950" : "text-stone-500",
                            )}
                        >
                            {step.shortLabel}
                        </span>
                    </div>
                ))}
                {end < totalSteps - 1 && <span className="shrink-0 px-1">…</span>}
            </div>
        </div>
    )
}
