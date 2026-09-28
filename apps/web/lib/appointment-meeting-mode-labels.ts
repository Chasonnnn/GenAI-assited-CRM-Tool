import type { MeetingMode } from "@/lib/api/appointments"
import { createSelectLabelGetter, toSelectOptions } from "@/lib/select-labels"

export const MEETING_MODE_LABELS: Record<MeetingMode, string> = {
    zoom: "Zoom",
    google_meet: "Google Meet",
    phone: "Phone",
    in_person: "In-Person",
}

export const MEETING_MODE_OPTIONS = toSelectOptions(MEETING_MODE_LABELS)

export function isMeetingMode(value: unknown): value is MeetingMode {
    return typeof value === "string" && Object.prototype.hasOwnProperty.call(MEETING_MODE_LABELS, value)
}

/** Format filter trigger, chips and the appointment detail format line. */
export const getMeetingModeLabel = createSelectLabelGetter(MEETING_MODE_LABELS, {
    emptyLabel: "All Formats",
    allValue: "all",
    unknownLabel: "Unknown format",
})
