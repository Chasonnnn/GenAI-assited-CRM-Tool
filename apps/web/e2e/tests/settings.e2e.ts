import { test } from "@e2e-dev/web"
import { expect, type Screen } from "e2e"

/** Saves a settings page through its unsaved-changes bar and waits for the bar to clear. */
async function saveChanges(screen: Screen) {
    const bar = screen.getByRole("region", "Unsaved changes")
    await expect(bar).toBeVisible({ timeout: 10_000 })
    await expect(bar).toContainText("1 unsaved change")
    await bar.getByRole("button", "Save changes").tap()
    await expect(bar).toBeHidden({ timeout: 15_000 })
}

test(
    "profile changes save through the unsaved-changes bar",
    { session: "admin", tags: ["settings"] },
    async ({ app, screen, browser }) => {
        await app.open("/settings")
        const title = screen.getByRole("textbox", "Title")
        await expect(title).toHaveValue("QA Lead", { timeout: 10_000 })
        await title.fill("QA Director")
        await saveChanges(screen)

        await browser.reload()
        await expect(screen.getByRole("textbox", "Title")).toHaveValue("QA Director", { timeout: 10_000 })

        await screen.getByRole("textbox", "Title").fill("QA Lead")
        await saveChanges(screen)
    },
)

test(
    "notification preferences save at once and persist",
    { session: "admin", tags: ["settings"] },
    async ({ app, screen, browser }) => {
        await app.open("/settings/notifications")
        const digest = screen.getByRole("switch", "Daily Digest email")
        await expect(digest).toBeChecked({ checked: false, timeout: 10_000 })
        await digest.tap()
        await expect(digest).toBeChecked({ timeout: 10_000 })

        await browser.reload()
        await expect(digest).toBeChecked({ timeout: 10_000 })
        await digest.tap()
        await expect(digest).toBeChecked({ checked: false, timeout: 10_000 })
    },
)

test(
    "compliance retention changes save and persist",
    { session: "admin", tags: ["settings"] },
    async ({ app, screen, browser }) => {
        await app.open("/settings/compliance")
        const notes = screen.getByRole("switch", "Notes retention active")
        await expect(notes).toBeChecked({ timeout: 10_000 })
        await notes.tap()
        await saveChanges(screen)

        await browser.reload()
        await expect(screen.getByRole("switch", "Notes retention active")).toBeChecked({ checked: false, timeout: 10_000 })
        await screen.getByRole("switch", "Notes retention active").tap()
        await saveChanges(screen)
    },
)

test(
    "the integrations list shows the organization providers before any setup",
    { session: "admin", tags: ["settings"] },
    async ({ app, screen }) => {
        await app.open("/settings/integrations")
        const org = screen.getByRole("region", "Organization")
        for (const provider of ["AI Assistant", "Email delivery", "Messaging (Twilio)", "Zapier", "Meta Lead Ads"]) {
            await expect(org.getByRole("heading", provider)).toBeVisible({ timeout: 10_000 })
        }
        await expect(org.getByRole("button", "Configure Email delivery")).toBeVisible()
    },
)

test(
    "the audit log page offers exports and paging",
    { session: "admin", tags: ["settings"] },
    async ({ app, screen }) => {
        await app.open("/settings/audit")
        await expect(screen.getByRole("heading", "Audit Log")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("button", "Create Export")).toBeVisible()
        await expect(screen.getByText("No export jobs yet.")).toBeVisible()
        await expect(screen.getByRole("button", "Previous")).toBeDisabled()
    },
)
