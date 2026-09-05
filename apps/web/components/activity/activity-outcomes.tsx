import { OutcomeBadge } from "@/components/surrogates/OutcomeBadge"
import { getSurrogateOutcomePresentation } from "@/lib/surrogate-outcome-presentation"

// Specialized contact/interview rendering stays behind the activity adapter.
export type ActivityOutcomeKind = "contact" | "interview"

export function getActivityOutcomePresentation(kind: ActivityOutcomeKind, value: string) {
    const presentation = getSurrogateOutcomePresentation(kind, value)
    if (!presentation) return null
    return {
        accentClassName: presentation.accentClassName,
        iconContainerClassName: presentation.iconContainerClassName,
        badge: <OutcomeBadge kind={kind} outcome={value} />,
    }
}
