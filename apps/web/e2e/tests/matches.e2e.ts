import { test } from "@e2e-dev/web"
import { expect, type Locator, type Screen } from "e2e"

import { SEED_SIZES } from "../local-stack"

const LIST_BUDGET_MS = 8_000

const PARENTS = { name: "E2E Casey & Jordan Example", email: "e2e.casey@example.com" }

const matchRows = (screen: Screen) => screen.getByRole("row").filter({ hasText: /M\d{5}/ })

/** Waits for a surrogate picker's options to load, picks one by position, and returns that surrogate's name. */
async function pickSurrogate(screen: Screen, picker: Locator, index = 0): Promise<string> {
    await picker.tap()
    const candidate = screen.getByRole("option").nth(index)
    await expect(candidate).toBeVisible({ timeout: 10_000 })
    const name = ((await candidate.textContent()) ?? "").split(" #S")[0] ?? ""
    await candidate.tap()
    return name
}

/** Moves the open record to a stage through the shared stage dialog and waits for the toast. */
async function changeStage(screen: Screen, stage: string) {
    await screen.getByRole("button", "Change Stage").tap()
    const stageDialog = screen.getByRole("dialog", "Change Stage")
    await stageDialog.getByRole("button", stage).tap()
    await stageDialog.getByRole("button", "Save Change").tap()
    await expect(stageDialog).toBeHidden({ timeout: 10_000 })
    await expect(screen.getByRole("dialog", `Stage updated to ${stage}`)).toBeVisible({ timeout: 10_000 })
}

test(
    "the intended parents list searches the seeded records and opens one",
    { session: "admin", tags: ["matches", "load"] },
    async ({ app, screen, browser }) => {
        await app.open("/intended-parents")
        const rows = screen.getByRole("row").filter({ hasText: /I\d{5}/ })
        await expect(rows.first()).toBeVisible({ timeout: LIST_BUDGET_MS })

        await screen.getByRole("textbox", "Search intended parents").fill("Lopez")
        await expect(rows.first()).toContainText("Lopez", { timeout: LIST_BUDGET_MS })
        await expect(rows.filter({ hasText: "Lopez" })).toHaveCount(await rows.count())

        await screen.getByRole("link").filter({ hasText: /^I\d{5}$/ }).first().tap()
        await expect(browser).toHaveURL(/\/intended-parents\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("button", "Propose Match")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("heading", /Lopez/)).toBeVisible()
    },
)

test(
    "an admin creates intended parents, proposes a match, and accepts it",
    { session: "admin", tags: ["matches"] },
    async ({ app, screen, browser }) => {
        await app.open("/intended-parents")
        await screen.getByRole("button", "New Intended Parent").tap()
        const createDialog = screen.getByRole("dialog", "New Intended Parent")
        await createDialog.getByRole("textbox", "Full Name *").fill(PARENTS.name)
        await createDialog.getByRole("textbox", "Email *").fill(PARENTS.email)
        await createDialog.getByRole("button", "Create").tap()
        await expect(createDialog).toBeHidden({ timeout: 10_000 })

        // The new record joins the list; its row opens the detail page.
        const createdRow = screen.getByRole("row").filter({ hasText: PARENTS.name })
        await expect(createdRow).toBeVisible({ timeout: 10_000 })
        await createdRow.getByRole("link").first().tap()
        await expect(browser).toHaveURL(/\/intended-parents\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", PARENTS.name)).toBeVisible({ timeout: 10_000 })

        // Only parents at Ready to Match may accept, so the stage moves before the proposal.
        await changeStage(screen, "Ready to Match")

        await screen.getByRole("button", "Propose Match").tap()
        const proposeDialog = screen.getByRole("dialog", `Propose match for ${PARENTS.name}`)
        // The surrogate picker takes no accessible name; it is the combobox after the kind picker.
        const surrogateName = await pickSurrogate(screen, proposeDialog.getByRole("combobox").nth(1))
        await proposeDialog.getByRole("button", "Propose Match").tap()
        await expect(proposeDialog).toBeHidden({ timeout: 10_000 })
        const matchLink = screen.getByRole("link", new RegExp(`^M\\d{5} · ${surrogateName} Surrogate · `))
        await expect(matchLink).toContainText("Under Review", { timeout: 10_000 })

        // Acceptance happens on the match itself and asks for confirmation.
        await matchLink.tap()
        await expect(browser).toHaveURL(/\/intended-parents\/matches\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await screen.getByRole("button", "Accept Match").tap()
        await screen.getByRole("alertdialog", /^Accept match M\d{5}\?$/).getByRole("button", "Accept Match").tap()
        await expect(screen.getByRole("button", "Accept Match")).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByText("Accepted").first()).toBeVisible({ timeout: 10_000 })

        await browser.back()
        await expect(matchLink).toContainText("Accepted", { timeout: 10_000 })
    },
)

test(
    "the matches list filters the seeded matches by stage and a match takes a note",
    { session: "admin", tags: ["matches", "load"] },
    async ({ app, screen, browser }) => {
        // Earlier tests in the run may add matches, so the total is at least the seeded count.
        await app.open("/intended-parents/matches")
        const footer = screen.getByText(/^Showing 1 to 20 of \d+$/)
        await expect(footer).toBeVisible({ timeout: LIST_BUDGET_MS })
        const total = Number(((await footer.textContent()) ?? "").replace(/\D/g, "").slice(3))
        expect(total).toBeGreaterThanOrEqual(SEED_SIZES.matches)
        await expect(matchRows(screen)).toHaveCount(20)

        await screen.getByRole("combobox", "Filter by stage").tap()
        // The stage options carry their counts, such as "Accepted 50".
        await screen.getByRole("option", /^Accepted/).tap()
        await expect(footer).toBeHidden({ timeout: LIST_BUDGET_MS })
        await expect(matchRows(screen).first()).toBeVisible({ timeout: LIST_BUDGET_MS })
        await expect(matchRows(screen).filter({ hasText: "Accepted" })).toHaveCount(await matchRows(screen).count())

        await screen.getByRole("link").filter({ hasText: /^M\d{5}$/ }).first().tap()
        await expect(browser).toHaveURL(/\/intended-parents\/matches\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", / ↔ /)).toBeVisible({ timeout: 10_000 })

        // The overview opens on its Notes tab; a note goes through a dialog.
        await screen.getByRole("tabpanel", "Notes").getByRole("button", "Add Note").tap()
        const noteDialog = screen.getByRole("dialog", "Add Note")
        await noteDialog.getByRole("textbox", "Note Content").fill("E2E note: clinic intake call booked.")
        await noteDialog.getByRole("button", "Add Note").tap()
        await expect(noteDialog).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByText("E2E note: clinic intake call booked.")).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "an admin creates a match from the matches list",
    { session: "admin", tags: ["matches"] },
    async ({ app, screen, browser }) => {
        await app.open("/intended-parents/matches")
        await screen.getByRole("button", "New Match").tap()
        const dialog = screen.getByRole("dialog", "New Match")
        // The proposal test pairs the first ready surrogate with the first parents, so this takes the second.
        const surrogateName = await pickSurrogate(screen, dialog.getByRole("combobox", "Surrogate (Ready to Match Only)"), 1)
        // The closed surrogate picker keeps its hidden options, so the parents option is matched by number.
        await dialog.getByRole("combobox", "Intended Parents").tap()
        const parents = screen.getByRole("option", /#I\d{5}$/).first()
        await expect(parents).toBeVisible({ timeout: 10_000 })
        await parents.tap()
        await dialog.getByRole("button", "Create Match").tap()
        await expect(dialog).toBeHidden({ timeout: 15_000 })

        // The list stays open: a toast offers the new match, and its row joins the list under review.
        await expect(screen.getByText(/^Match M\d{5} proposed$/)).toBeVisible({ timeout: 10_000 })
        const newRow = matchRows(screen).filter({ hasText: surrogateName }).filter({ hasText: "Under Review" })
        await expect(newRow.first()).toBeVisible({ timeout: LIST_BUDGET_MS })
        await newRow.first().getByRole("link").filter({ hasText: /^M\d{5}$/ }).tap()
        await expect(browser).toHaveURL(/\/intended-parents\/matches\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", new RegExp(`^${surrogateName} ↔ `))).toBeVisible({ timeout: 10_000 })
    },
)
