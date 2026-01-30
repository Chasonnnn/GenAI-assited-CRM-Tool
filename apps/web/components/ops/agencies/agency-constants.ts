export const STATUS_BADGE_VARIANTS: Record<string, string> = {
    active: "bg-green-500/10 text-green-600 border-green-500/20",
    trial: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    past_due: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    canceled: "bg-red-500/10 text-red-600 border-red-500/20",
}

export const PLAN_BADGE_VARIANTS: Record<string, string> = {
    starter: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
    professional: "bg-teal-500/10 text-teal-600 dark:text-teal-400",
    enterprise: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
}

export const INVITE_STATUS_VARIANTS: Record<string, string> = {
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    accepted: "bg-green-500/10 text-green-600 border-green-500/20",
    expired: "bg-stone-500/10 text-stone-600 border-stone-500/20",
    revoked: "bg-red-500/10 text-red-600 border-red-500/20",
}

export const INVITE_ROLE_OPTIONS = [
    "intake_specialist",
    "case_manager",
    "admin",
    "developer",
] as const
export type InviteRole = (typeof INVITE_ROLE_OPTIONS)[number]

export const INVITE_ROLE_LABELS: Record<InviteRole, string> = {
    intake_specialist: "Intake Specialist",
    case_manager: "Case Manager",
    admin: "Admin",
    developer: "Developer",
}

export const ALERT_STATUS_BADGES: Record<string, string> = {
    open: "bg-red-500/10 text-red-600 border-red-500/20",
    acknowledged: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    resolved: "bg-green-500/10 text-green-600 border-green-500/20",
}

export const ALERT_SEVERITY_BADGES: Record<string, string> = {
    critical: "bg-red-500/10 text-red-600 border-red-500/20",
    error: "bg-orange-500/10 text-orange-600 border-orange-500/20",
    warn: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    info: "bg-blue-500/10 text-blue-600 border-blue-500/20",
}
