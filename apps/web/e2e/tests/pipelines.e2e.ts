import { test } from "@e2e-dev/web"
import { expect, type Screen } from "e2e"

const STAGE = "E2E Custom Stage"

/** Saves the pipeline through the unsaved-changes bar and waits for it to clear. */
async function savePipeline(screen: Screen) {
    const bar = screen.getByRole("region", "Unsaved changes")
    await bar.getByRole("button", "Save changes").tap()
    await expect(bar).toBeHidden({ timeout: 15_000 })
}

test(
    "the surrogate pipeline counts a stage and the dashboard links into its filtered list",
    { session: "admin", tags: ["pipelines"] },
    async ({ app, screen }) => {
        await app.open("/settings/pipelines")
        const row = screen.getByRole("row").filter({ has: screen.getByRole("button", "Open New Unread settings") })
        await expect(row).toBeVisible({ timeout: 10_000 })
        // The "#" and "Surrogates" cells are the row's only bare numbers; the count comes last.
        const count = Number((await row.getByRole("cell").filter({ hasText: /^\d+$/ }).last().textContent()) ?? "")
        expect(count).toBeGreaterThan(1)

        // The dashboard's stage link carries the same filter as the list.
        await app.open("/dashboard")
        const stageLink = screen.getByRole("link", "View New Unread surrogates")
        await expect(stageLink).toBeVisible({ timeout: 10_000 })
        const href = (await stageLink.getAttribute("href")) ?? ""
        expect(href).toMatch(/^\/surrogates\?/)
        await app.open(href)
        await expect(screen.getByRole("button", "Remove filter: Stage: New Unread")).toBeVisible({ timeout: 10_000 })
        // Earlier tests in the run may add New Unread surrogates after the pipeline count was computed.
        const footer = screen.getByText(/^Showing 1-30 of \d+ surrogates$/)
        await expect(footer).toBeVisible({ timeout: 10_000 })
        const total = Number(((await footer.textContent()) ?? "").match(/of (\d+) surrogates/)?.[1] ?? 0)
        expect(total).toBeGreaterThanOrEqual(count)
    },
)

test(
    "a custom stage saves, survives a reload, and is removed",
    { session: "admin", tags: ["pipelines"] },
    async ({ app, screen, browser }) => {
        await app.open("/settings/pipelines")
        await expect(screen.getByRole("button", "Add Custom Stage")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("button", "Add Custom Stage").tap()
        // The new stage joins the end of the table with an empty label.
        await screen.getByRole("textbox", /^Stage \d+ label$/).last().fill(STAGE)
        await savePipeline(screen)

        await browser.reload()
        await expect(screen.getByRole("button", `Remove ${STAGE}`)).toBeVisible({ timeout: 10_000 })

        // Removal asks where to remap the stage's records; the empty custom stage needs no remap.
        await screen.getByRole("button", `Remove ${STAGE}`).tap()
        await screen.getByRole("dialog", `Remove ${STAGE}?`).getByRole("button", "Confirm Removal").tap()
        await savePipeline(screen)
        await browser.reload()
        await expect(screen.getByRole("button", "Add Custom Stage")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("button", `Remove ${STAGE}`)).toHaveCount(0)
    },
)
