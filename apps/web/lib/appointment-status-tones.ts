export type AppointmentStatusTone = {
    /** Tinted surface with text that keeps at least 4.5:1 in light and dark themes (chips and badges). */
    tint: string
    /** Border color for items that mark status with a colored edge. */
    accent: string
    /** Solid fill for decorative dots next to a text label. */
    dot: string
}

export const APPOINTMENT_STATUSES = ["pending", "confirmed", "completed", "cancelled", "no_show", "expired"] as const

const NEUTRAL_TONE: AppointmentStatusTone = {
    tint: "border-gray-500/20 bg-gray-500/10 text-gray-800 dark:text-gray-200",
    accent: "border-gray-500",
    dot: "bg-gray-500",
}

const APPOINTMENT_STATUS_TONES: Record<(typeof APPOINTMENT_STATUSES)[number], AppointmentStatusTone> = {
    pending: {
        tint: "border-yellow-500/20 bg-yellow-500/10 text-yellow-800 dark:text-yellow-200",
        accent: "border-yellow-500",
        dot: "bg-yellow-500",
    },
    confirmed: {
        tint: "border-green-500/20 bg-green-500/10 text-green-800 dark:text-green-200",
        accent: "border-green-500",
        dot: "bg-green-500",
    },
    completed: {
        tint: "border-blue-500/20 bg-blue-500/10 text-blue-800 dark:text-blue-200",
        accent: "border-blue-500",
        dot: "bg-blue-500",
    },
    cancelled: {
        tint: "border-red-500/20 bg-red-500/10 text-red-800 dark:text-red-200",
        accent: "border-red-500",
        dot: "bg-red-500",
    },
    no_show: NEUTRAL_TONE,
    expired: NEUTRAL_TONE,
}

export function getAppointmentStatusTone(status: string): AppointmentStatusTone {
    return Object.hasOwn(APPOINTMENT_STATUS_TONES, status)
        ? APPOINTMENT_STATUS_TONES[status as keyof typeof APPOINTMENT_STATUS_TONES]
        : NEUTRAL_TONE
}
