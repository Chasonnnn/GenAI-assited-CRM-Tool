import type { TicketStatus } from "@/lib/api/tickets"

export const TICKET_STATUS_LABELS: Record<TicketStatus, string> = {
    new: "New",
    open: "Open",
    pending: "Pending",
    resolved: "Resolved",
    closed: "Closed",
    spam: "Spam",
}

export function getCorrespondenceTicketStatusLabel(status: string): string {
    return TICKET_STATUS_LABELS[status as TicketStatus] ?? "Unknown status"
}
