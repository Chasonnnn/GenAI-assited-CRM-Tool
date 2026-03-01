import { afterEach, describe, expect, it, vi } from "vitest"

import { openDownloadUrlWithSpreadsheetWarning } from "@/lib/utils/csv-download-warning"

describe("CSV download warnings", () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("opens non-spreadsheet text files without confirmation", () => {
        const openSpy = vi.spyOn(window, "open").mockImplementation(() => null)
        const confirmSpy = vi.spyOn(window, "confirm")

        const opened = openDownloadUrlWithSpreadsheetWarning(
            "https://example.com/contract.pdf",
            "contract.pdf",
        )

        expect(opened).toBe(true)
        expect(confirmSpy).not.toHaveBeenCalled()
        expect(openSpy).toHaveBeenCalledWith(
            "https://example.com/contract.pdf",
            "_blank",
            "noopener,noreferrer",
        )
    })

    it("blocks spreadsheet text downloads when user cancels confirmation", () => {
        const openSpy = vi.spyOn(window, "open").mockImplementation(() => null)
        vi.spyOn(window, "confirm").mockReturnValue(false)

        const opened = openDownloadUrlWithSpreadsheetWarning(
            "https://example.com/report.csv",
            "report.csv",
        )

        expect(opened).toBe(false)
        expect(openSpy).not.toHaveBeenCalled()
    })

    it("allows spreadsheet text downloads when user confirms", () => {
        const openSpy = vi.spyOn(window, "open").mockImplementation(() => null)
        vi.spyOn(window, "confirm").mockReturnValue(true)

        const opened = openDownloadUrlWithSpreadsheetWarning(
            "https://example.com/report.tsv",
            "report.tsv",
        )

        expect(opened).toBe(true)
        expect(openSpy).toHaveBeenCalledWith(
            "https://example.com/report.tsv",
            "_blank",
            "noopener,noreferrer",
        )
    })
})
