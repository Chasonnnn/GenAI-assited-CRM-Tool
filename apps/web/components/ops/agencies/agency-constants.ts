import { createSelectLabelGetter } from "@/lib/select-labels"

// Keys match VALID_PLANS and VALID_STATUSES in apps/api/app/services/platform_service.py.
export const SUBSCRIPTION_PLAN_LABELS = {
    starter: "Starter",
    professional: "Professional",
    enterprise: "Enterprise",
} as const

export const getSubscriptionPlanLabel = createSelectLabelGetter(SUBSCRIPTION_PLAN_LABELS, {
    emptyLabel: "No plan",
    unknownLabel: "Unknown plan",
})

export const SUBSCRIPTION_STATUS_LABELS = {
    active: "Active",
    trial: "Trial",
    past_due: "Past due",
    canceled: "Canceled",
} as const

export const getSubscriptionStatusLabel = createSelectLabelGetter(SUBSCRIPTION_STATUS_LABELS, {
    emptyLabel: "All statuses",
    unknownLabel: "Unknown status",
})

export const STATUS_BADGE_VARIANTS: Record<string, string> = {
    active: "bg-green-500/10 text-green-600 border-green-500/20",
    trial: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    past_due: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    canceled: "bg-red-500/10 text-red-600 border-red-500/20",
}

export const PLAN_BADGE_VARIANTS: Record<string, string> = {
    starter: "bg-muted text-muted-foreground",
    professional: "bg-primary/10 text-primary",
    enterprise: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
}

export const INVITE_STATUS_VARIANTS: Record<string, string> = {
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    accepted: "bg-green-500/10 text-green-600 border-green-500/20",
    expired: "bg-muted text-muted-foreground border-border",
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

// Keys match AlertStatus and AlertSeverity in apps/api/app/db/enums/integration_health.py.
export const ALERT_STATUS_LABELS = {
    open: "Open",
    acknowledged: "Acknowledged",
    resolved: "Resolved",
    snoozed: "Snoozed",
} as const

export const getAlertStatusLabel = createSelectLabelGetter(ALERT_STATUS_LABELS, {
    emptyLabel: "All statuses",
    unknownLabel: "Unknown status",
})

export const ALERT_SEVERITY_LABELS = {
    critical: "Critical",
    error: "Error",
    warn: "Warning",
} as const

export const getAlertSeverityLabel = createSelectLabelGetter(ALERT_SEVERITY_LABELS, {
    emptyLabel: "All severities",
    unknownLabel: "Unknown severity",
})

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
