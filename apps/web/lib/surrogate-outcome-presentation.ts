import type { LucideIcon } from "lucide-react"
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, MinusIcon } from "lucide-react"

import type { ContactOutcome, InterviewOutcome } from "@/lib/api/surrogates"

export type OutcomeTone = "success" | "follow_up" | "failed" | "neutral"
export type SurrogateOutcomeKind = "contact" | "interview"

type OutcomeDefinition<T extends string> = {
    label: string
    tone: OutcomeTone
    icon: LucideIcon
    value: T
}

export type OutcomePresentation<T extends string> = OutcomeDefinition<T> & {
    badgeClassName: string
    accentClassName: string
    iconContainerClassName: string
    dotClassName: string
}

const TONE_STYLES: Record<
    OutcomeTone,
    Pick<OutcomePresentation<string>, "badgeClassName" | "accentClassName" | "iconContainerClassName" | "dotClassName">
> = {
    success: {
        badgeClassName: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-900/30 dark:text-emerald-300",
        accentClassName: "bg-emerald-500",
        iconContainerClassName: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
        dotClassName: "bg-emerald-500",
    },
    follow_up: {
        badgeClassName: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:border-amber-400/20 dark:bg-amber-900/30 dark:text-amber-300",
        accentClassName: "bg-amber-500",
        iconContainerClassName: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
        dotClassName: "bg-amber-500",
    },
    failed: {
        badgeClassName: "border-orange-500/20 bg-orange-500/10 text-orange-700 dark:border-orange-400/20 dark:bg-orange-900/30 dark:text-orange-300",
        accentClassName: "bg-orange-500",
        iconContainerClassName: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
        dotClassName: "bg-orange-500",
    },
    neutral: {
        badgeClassName: "border-slate-500/20 bg-slate-500/10 text-slate-700 dark:border-slate-400/20 dark:bg-slate-900/30 dark:text-slate-300",
        accentClassName: "bg-slate-500",
        iconContainerClassName: "bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300",
        dotClassName: "bg-slate-500",
    },
}

const CONTACT_OUTCOMES = {
    reached: { value: "reached", label: "Reached", tone: "success", icon: CheckCircleIcon },
    no_answer: { value: "no_answer", label: "No Answer", tone: "follow_up", icon: ClockIcon },
    voicemail: { value: "voicemail", label: "Voicemail", tone: "follow_up", icon: ClockIcon },
    wrong_number: { value: "wrong_number", label: "Wrong Number", tone: "failed", icon: AlertTriangleIcon },
    email_bounced: { value: "email_bounced", label: "Email Bounced", tone: "failed", icon: AlertTriangleIcon },
} satisfies Record<ContactOutcome, OutcomeDefinition<ContactOutcome>>

const INTERVIEW_OUTCOMES = {
    completed: { value: "completed", label: "Completed", tone: "success", icon: CheckCircleIcon },
    rescheduled: { value: "rescheduled", label: "Rescheduled", tone: "follow_up", icon: ClockIcon },
    no_show: { value: "no_show", label: "No Show", tone: "failed", icon: AlertTriangleIcon },
    cancelled: { value: "cancelled", label: "Cancelled", tone: "neutral", icon: MinusIcon },
} satisfies Record<InterviewOutcome, OutcomeDefinition<InterviewOutcome>>

function withToneStyles<T extends string>(definition: OutcomeDefinition<T>): OutcomePresentation<T> {
    return {
        ...definition,
        ...TONE_STYLES[definition.tone],
    }
}

export function getContactOutcomePresentation(
    outcome: ContactOutcome | string | null | undefined,
): OutcomePresentation<ContactOutcome> | null {
    if (!outcome || !(outcome in CONTACT_OUTCOMES)) {
        return null
    }
    return withToneStyles(CONTACT_OUTCOMES[outcome as ContactOutcome])
}

export function getInterviewOutcomePresentation(
    outcome: InterviewOutcome | string | null | undefined,
): OutcomePresentation<InterviewOutcome> | null {
    if (!outcome || !(outcome in INTERVIEW_OUTCOMES)) {
        return null
    }
    return withToneStyles(INTERVIEW_OUTCOMES[outcome as InterviewOutcome])
}

export function getSurrogateOutcomePresentation(
    kind: SurrogateOutcomeKind,
    outcome: string | null | undefined,
): OutcomePresentation<string> | null {
    if (kind === "contact") {
        return getContactOutcomePresentation(outcome)
    }
    return getInterviewOutcomePresentation(outcome)
}
