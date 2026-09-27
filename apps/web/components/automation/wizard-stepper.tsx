import { CheckIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Labeled step indicator for the workflow and campaign wizards. Steps are 1-based.
 * Below sm only the current step keeps its label so four steps fit at 390px.
 */
export function WizardStepper({
    steps,
    currentStep,
    className,
}: {
    steps: readonly string[]
    currentStep: number
    className?: string
}) {
    return (
        <ol aria-label="Progress" className={cn("flex items-center gap-2 sm:gap-3", className)}>
            {steps.map((label, index) => {
                const step = index + 1
                const isDone = step < currentStep
                const isCurrent = step === currentStep
                return (
                    <li
                        key={label}
                        aria-current={isCurrent ? "step" : undefined}
                        className={cn(
                            "flex min-w-0 items-center gap-2 sm:gap-3",
                            index < steps.length - 1 && "flex-1",
                            // The current step shows its label at every width; without this its
                            // equal flex share is narrower than the label and it overlaps the next step.
                            isCurrent && "min-w-fit",
                        )}
                    >
                        <span className="flex shrink-0 items-center gap-2">
                            <span
                                aria-hidden="true"
                                className={cn(
                                    "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                                    isDone && "bg-primary text-primary-foreground",
                                    isCurrent && "border-2 border-primary text-primary",
                                    !isDone && !isCurrent && "border border-border text-muted-foreground",
                                )}
                            >
                                {isDone ? <CheckIcon className="size-3.5" /> : step}
                            </span>
                            <span
                                className={cn(
                                    "text-sm",
                                    isCurrent ? "font-semibold text-foreground" : "sr-only sm:not-sr-only",
                                    isDone && "font-medium text-foreground",
                                    !isDone && !isCurrent && "text-muted-foreground",
                                )}
                            >
                                {label}
                                <span className="sr-only">
                                    {isDone ? " (completed)" : isCurrent ? " (current step)" : ""}
                                </span>
                            </span>
                        </span>
                        {index < steps.length - 1 ? (
                            <span
                                aria-hidden="true"
                                className={cn(
                                    "h-0.5 min-w-4 flex-1 rounded-full",
                                    isDone ? "bg-primary" : "bg-border",
                                )}
                            />
                        ) : null}
                    </li>
                )
            })}
        </ol>
    )
}
