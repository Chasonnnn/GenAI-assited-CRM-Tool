const APPOINTMENT_STATUS_LABELS: Record<string, string> = {
    pending: "Pending",
    confirmed: "Confirmed",
    completed: "Completed",
    cancelled: "Cancelled",
    no_show: "No Show",
    expired: "Expired",
}

export function getAppointmentStatusLabel(status: string): string {
    return APPOINTMENT_STATUS_LABELS[status] ?? "Unknown status"
}
