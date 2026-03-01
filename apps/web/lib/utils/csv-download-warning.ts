const SPREADSHEET_TEXT_EXTENSIONS = new Set(["csv", "tsv"])

function _extension(filename: string): string {
    const parts = filename.trim().toLowerCase().split(".")
    return parts.length > 1 ? parts[parts.length - 1] || "" : ""
}

export function isSpreadsheetTextFile(filename: string): boolean {
    return SPREADSHEET_TEXT_EXTENSIONS.has(_extension(filename))
}

export function confirmSpreadsheetTextDownload(filename: string): boolean {
    if (!isSpreadsheetTextFile(filename)) return true
    if (typeof window === "undefined") return true

    return window.confirm(
        `"${filename}" is a spreadsheet text file and may contain formulas. Download and open only if you trust the source.`,
    )
}

export function openDownloadUrlWithSpreadsheetWarning(downloadUrl: string, filename: string): boolean {
    if (!confirmSpreadsheetTextDownload(filename)) {
        return false
    }
    window.open(downloadUrl, "_blank", "noopener,noreferrer")
    return true
}
