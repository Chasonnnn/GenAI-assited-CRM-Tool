import { parseDateInput } from "@/lib/utils/date"

export function formatDateTime(dateString: string): string {
    const parsed = parseDateInput(dateString)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    })
}

export function formatDate(dateString: string): string {
    const parsed = parseDateInput(dateString)
    if (Number.isNaN(parsed.getTime())) return "—"
    return parsed.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
    })
}

export function formatHeight(heightFt: number | string | null | undefined): string {
    const numericHeight =
        typeof heightFt === "number"
            ? heightFt
            : typeof heightFt === "string"
                ? Number(heightFt.trim())
                : Number.NaN
    if (!Number.isFinite(numericHeight)) return "-"
    const totalInches = Math.round(numericHeight * 12)
    if (totalInches <= 0) return "-"
    const feet = Math.floor(totalInches / 12)
    const inches = totalInches % 12
    return `${feet} ft ${inches} in`
}

export function computeBmi(heightFt: number | null, weightLb: number | null): number | null {
    if (!heightFt || !weightLb) return null
    const heightInches = heightFt * 12
    if (heightInches <= 0) return null
    return Math.round((weightLb / (heightInches ** 2)) * 703 * 10) / 10
}

export function toLocalIsoDateTime(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, "0")
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
}

export function formatMeetingTimeForInvite(date: Date): string {
    return date.toLocaleString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
    })
}
