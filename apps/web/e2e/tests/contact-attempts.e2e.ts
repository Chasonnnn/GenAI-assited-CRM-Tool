import { test } from "@e2e-dev/web"
import { expect, type Screen } from "e2e"

const CREATED = { name: "E2E Rhea Contact", email: "e2e.rhea.contact@example.com" }

/** Logs a reached phone contact and waits for the dialog to close. */
async function logReachedContact(screen: Screen) {
    await screen.getByRole("button", "Log Contact").tap()
    const dialog = screen.getByRole("dialog", "Log Contact Attempt")
    await dialog.getByRole("checkbox", "Phone").tap()
    await dialog.getByRole("combobox", "Outcome").tap()
    await screen.getByRole("option", /^Reached/).tap()
    await dialog.getByRole("button", "Log Attempt").tap()
    await expect(dialog).toBeHidden({ timeout: 10_000 })
}

test(
    "a reached contact logs without moving the stage, including in Reschedule Needed",
    { session: "admin", tags: ["surrogates", "contact-attempts"] },
    async ({ app, screen, browser }) => {
        await app.open("/surrogates")
        await screen.getByRole("button", "New surrogate").tap()
        const createDialog = screen.getByRole("dialog", "New surrogate")
        await createDialog.getByRole("textbox", "Full name").fill(CREATED.name)
        await createDialog.getByRole("textbox", "Email").fill(CREATED.email)
        await createDialog.getByRole("combobox", "Source").tap()
        await screen.getByRole("option", "Website").tap()
        await createDialog.getByRole("button", "Create").tap()
        await expect(browser).toHaveURL(/\/surrogates\/[0-9a-f-]{36}/, { timeout: 15_000 })
        // A new surrogate starts in the intake queue; Log Contact needs a user owner.
        await screen.getByRole("button", "Claim Surrogate").tap()
        await expect(screen.getByRole("button", "Log Contact")).toBeVisible({ timeout: 10_000 })

        await logReachedContact(screen)
        await screen.getByRole("tab", "History").tap()
        const history = screen.getByRole("tabpanel", "History")
        await expect(history).toContainText("Phone", { timeout: 10_000 })
        await expect(history).not.toContainText("→ Contacted")

        await screen.getByRole("button", "Change Stage").tap()
        const stageDialog = screen.getByRole("dialog", "Change Stage")
        await stageDialog.getByRole("button", "Reschedule Needed").tap()
        await stageDialog.getByRole("button", "Save Change").tap()
        await expect(stageDialog).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByRole("dialog", "Stage updated to Reschedule Needed")).toBeVisible({ timeout: 10_000 })

        await logReachedContact(screen)
        await browser.reload()
        await expect(screen.getByRole("button", "Log Contact")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("tab", "History").tap()
        await expect(history).toContainText("→ Reschedule Needed", { timeout: 10_000 })
        await expect(history).not.toContainText("→ Contacted")
    },
)
