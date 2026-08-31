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
    const currentLabel = steps[currentStep - 1]?.label ?? ""
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
            <div className="text-center">
                <div className="text-[11px] font-medium uppercase tracking-[0.22em] text-stone-500">
                    Step {currentStep} of {totalSteps}
                </div>
                <div className="mt-1 text-sm font-semibold text-stone-950">{currentLabel}</div>
            </div>
            <progress
                aria-label="Application progress"
                value={progressValue}
                max={100}
                className="h-1.5 w-full overflow-hidden rounded-full accent-blue-500"
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
                                step.id <= currentStep ? "bg-blue-500" : "bg-stone-300",
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
