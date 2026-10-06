import { test } from "@e2e-dev/web"
import { expect, type App, type Screen } from "e2e"

import { SEED_SIZES } from "../local-stack"

// A list page over the seeded records must paint its rows within this budget.
const LIST_BUDGET_MS = 8_000

const CREATED = { name: "E2E Quinn Example", email: "e2e.quinn@example.com" }

const surrogateRows = (screen: Screen) => screen.getByRole("row").filter({ hasText: /#S\d{5}/ })

/** Opens the first surrogate on the list and waits for its header actions. */
async function openFirstSurrogate(app: App, screen: Screen) {
    await app.open("/surrogates")
    await screen.getByRole("link").filter({ hasText: /^#S\d{5}$/ }).first().tap()
    await expect(screen.getByRole("button", "Change Stage")).toBeVisible({ timeout: 10_000 })
}

test(
    "the surrogates list pages, filters, and searches the seeded records",
    { session: "admin", tags: ["surrogates", "load"] },
    async ({ app, screen }) => {
        const total = SEED_SIZES.surrogates
        await app.open("/surrogates")
        await expect(screen.getByText(`Showing 1-30 of ${total} surrogates`)).toBeVisible({ timeout: LIST_BUDGET_MS })
        await expect(surrogateRows(screen)).toHaveCount(30)

        await screen.getByRole("button", "Next").tap()
        await expect(screen.getByText(`Showing 31-60 of ${total} surrogates`)).toBeVisible({ timeout: LIST_BUDGET_MS })

        const lastPage = Math.ceil(total / 30)
        await screen.getByRole("spinbutton", "Page number").fill(String(lastPage))
        await screen.getByRole("button", "Go to page").tap()
        await expect(screen.getByText(`Showing ${(lastPage - 1) * 30 + 1}-${total} of ${total} surrogates`)).toBeVisible({
            timeout: LIST_BUDGET_MS,
        })

        // A search runs against every seeded record; the footer disappears when one page holds all hits.
        await screen.getByRole("textbox", "Search surrogates").fill("Nora Taylor")
        await expect(surrogateRows(screen).first()).toContainText("Nora Taylor", { timeout: LIST_BUDGET_MS })
        await expect(screen.getByText(`of ${total} surrogates`)).toHaveCount(0)
        const hits = await surrogateRows(screen).count()
        await expect(surrogateRows(screen).filter({ hasText: "Nora Taylor" })).toHaveCount(hits)

        await screen.getByRole("textbox", "Search surrogates").fill("")
        await screen.getByRole("combobox", "Filter by stage").tap()
        await screen.getByRole("option", "Approved").tap()
        await expect(screen.getByText(/^Showing 1-30 of \d+ surrogates$/)).toBeVisible({ timeout: LIST_BUDGET_MS })
        await expect(screen.getByText(`of ${total} surrogates`)).toHaveCount(0)
        await expect(surrogateRows(screen).filter({ hasText: "Approved" })).toHaveCount(30)
    },
)

test(
    "an admin creates a surrogate and finds it in the list and in search",
    { session: "admin", tags: ["surrogates"] },
    async ({ app, screen, browser }) => {
        await app.open("/surrogates")
        await screen.getByRole("button", "New surrogate").tap()
        const dialog = screen.getByRole("dialog", "New surrogate")
        await dialog.getByRole("textbox", "Full name").fill(CREATED.name)
        await dialog.getByRole("textbox", "Email").fill(CREATED.email)
        await dialog.getByRole("combobox", "Source").tap()
        await screen.getByRole("option", "Website").tap()
        await dialog.getByRole("button", "Create").tap()

        await expect(browser).toHaveURL(/\/surrogates\/[0-9a-f-]{36}/, { timeout: 15_000 })
        await expect(screen.getByRole("heading", /^Surrogate #S\d{5}$/)).toBeVisible()
        await expect(screen.getByText(CREATED.name)).toBeVisible()

        await app.open("/surrogates")
        await screen.getByRole("textbox", "Search surrogates").fill("Quinn")
        await expect(surrogateRows(screen).filter({ hasText: CREATED.name })).toHaveCount(1, { timeout: LIST_BUDGET_MS })

        await app.open("/search?q=Quinn")
        await expect(screen.getByRole("link", /^E2E Quinn Example Surrogate #?S\d{5}$/)).toBeVisible({ timeout: LIST_BUDGET_MS })
    },
)

test(
    "a stage change and a note on a surrogate show on its tabs and history",
    { session: "admin", tags: ["surrogates"] },
    async ({ app, screen }) => {
        await openFirstSurrogate(app, screen)

        await screen.getByRole("button", "Change Stage").tap()
        const stageDialog = screen.getByRole("dialog", "Change Stage")
        await stageDialog.getByRole("button", "On-Hold").tap()
        // A pause asks for a reason and offers an optional reminder task.
        await stageDialog.getByRole("textbox", "Reason *").fill("E2E: travelling until next month.")
        await stageDialog.getByRole("button", "Save Change").tap()
        await expect(stageDialog).toBeHidden({ timeout: 10_000 })
        // The change confirms with an undo window; the header shows the new stage.
        await expect(screen.getByRole("dialog", "Stage updated to On-Hold")).toBeVisible({ timeout: 10_000 })

        await screen.getByRole("tab", /^Notes/).tap()
        await expect(screen.getByRole("heading", "Notes")).toBeVisible({ timeout: 10_000 })
        // The rich-text editor is the only textbox in the Notes panel; its name comes from the placeholder.
        await screen.getByRole("tabpanel", /^Notes/).getByRole("textbox").fill("E2E note: called and left a voicemail.")
        await screen.getByRole("button", "Add Note").tap()
        await expect(screen.getByText("E2E note: called and left a voicemail.")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("tab", "Notes (2)")).toBeVisible()

        await screen.getByRole("tab", "History").tap()
        const history = screen.getByRole("tabpanel", "History")
        await expect(history).toContainText("→ On-Hold", { timeout: 10_000 })
        await expect(history).toContainText("E2E note: called and left a voicemail.")
    },
)
