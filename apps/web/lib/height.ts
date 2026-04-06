export function parseHeightFt(value: number | string | null | undefined): number | null {
    if (value === null || value === undefined) return null

    const numericValue =
        typeof value === "number"
            ? value
            : typeof value === "string"
                ? Number(value.trim())
                : Number.NaN

    return Number.isFinite(numericValue) ? numericValue : null
}

export function heightFtToTotalInches(value: number | string | null | undefined): number | null {
    const numericValue = parseHeightFt(value)
    if (numericValue === null) return null
    return Math.round(numericValue * 12)
}

export function totalInchesToHeightFt(totalInches: number | null | undefined): number | null {
    if (totalInches === null || totalInches === undefined || !Number.isFinite(totalInches) || totalInches < 0) {
        return null
    }
    return Number((totalInches / 12).toFixed(2))
}

export function splitHeightFt(value: number | string | null | undefined): { feet: string; inches: string } {
    const totalInches = heightFtToTotalInches(value)
    if (totalInches === null || totalInches < 0) {
        return { feet: "", inches: "" }
    }

    return {
        feet: String(Math.floor(totalInches / 12)),
        inches: String(totalInches % 12),
    }
}

export function serializeHeightSelection(feet: string, inches: string): number | null {
    if (feet === "" && inches === "") {
        return null
    }

    const feetValue = Number(feet || 0)
    const inchesValue = Number(inches || 0)
    if (!Number.isFinite(feetValue) || !Number.isFinite(inchesValue) || feetValue < 0 || inchesValue < 0) {
        return null
    }

    return totalInchesToHeightFt((feetValue * 12) + inchesValue)
}
