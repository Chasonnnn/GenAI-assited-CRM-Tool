import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { SEED_SIZES } from "../local-stack"

const DONOR = { name: "E2E Dana Example", email: "e2e.dana@example.com" }

test(
    "global search finds the seeded surrogates and opens one",
    { session: "admin", tags: ["records"] },
    async ({ app, screen, browser }) => {
        await app.open("/search?q=Nora")
        const hits = screen.getByRole("link", /^Nora .* Surrogate S\d{5}$/)
        await expect(hits.first()).toBeVisible({ timeout: 10_000 })
        expect(await hits.count()).toBeGreaterThanOrEqual(20)

        await hits.first().tap()
        await expect(browser).toHaveURL(/\/surrogates\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", /^Surrogate #S\d{5}$/)).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "the dashboard counts the seeded surrogates and links into the filtered list",
    { session: "admin", tags: ["records"] },
    async ({ app, screen, browser }) => {
        await app.open("/dashboard")
        const active = screen.getByRole("link", /^Active Surrogates [\d,]+/)
        await expect(active).toBeVisible({ timeout: 10_000 })
        const count = Number(((await active.textContent()) ?? "").match(/Active Surrogates\s*([\d,]+)/)?.[1]?.replace(/,/g, "") ?? 0)
        expect(count).toBeGreaterThanOrEqual(SEED_SIZES.surrogates)

        // The stage links sit under the chart, so the test follows the href instead of tapping.
        const stageLink = screen.getByRole("link", "View New Unread surrogates")
        await expect(stageLink).toBeVisible({ timeout: 10_000 })
        const href = (await stageLink.getAttribute("href")) ?? ""
        expect(href).toMatch(/^\/surrogates\?/)
        await app.open(href)
        await expect(browser).toHaveURL(/\/surrogates\?/, { timeout: 10_000 })
        await expect(screen.getByRole("combobox", "Filter by stage")).toContainText("New Unread", { timeout: 10_000 })
        await expect(screen.getByText(/^Showing 1-30 of \d+ surrogates$/)).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "an admin creates an egg donor and finds it in the list",
    { session: "admin", tags: ["records"] },
    async ({ app, screen }) => {
        await app.open("/donors")
        await expect(screen.getByRole("heading", "No egg donors yet")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("button", "New Donor").tap()
        const dialog = screen.getByRole("dialog", "New Egg Donor")
        await dialog.getByRole("textbox", "Full name").fill(DONOR.name)
        await dialog.getByRole("textbox", "Email").fill(DONOR.email)
        await dialog.getByRole("button", "Create").tap()
        await expect(dialog).toBeHidden({ timeout: 10_000 })

        await app.open("/donors")
        await screen.getByRole("searchbox", "Search donors").fill("Dana")
        await expect(screen.getByRole("row").filter({ hasText: DONOR.name })).toHaveCount(1, { timeout: 10_000 })
    },
)

test(
    "the booking link dialog shows the admin's link",
    { session: "admin", tags: ["records"] },
    async ({ app, screen }) => {
        await app.open("/appointments")
        await screen.getByRole("button", "Share booking link").tap()
        const dialog = screen.getByRole("dialog", "Your Booking Link")
        await expect(dialog.getByRole("textbox", "Booking link")).toHaveValue(/\/book\/test-admin$/)
        await dialog.getByRole("button", "Close").tap()
        await expect(dialog).toBeHidden()
    },
)
