export function formatLocalDate(date: Date, timeZone?: string): string {
    if (timeZone) {
        return date.toLocaleDateString("en-CA", { timeZone })
    }

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, "0")
    const day = String(date.getDate()).padStart(2, "0")
    return `${year}-${month}-${day}`
}

export function parseDateInput(value: string): Date {
    if (value.includes("T")) {
        return new Date(value)
    }
    return new Date(`${value}T00:00:00`)
}

export function startOfLocalDay(date: Date = new Date()): Date {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}
