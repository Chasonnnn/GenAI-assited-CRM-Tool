import { test } from "@e2e-dev/web"
import { expect } from "e2e"

// A seeded org workflow with a "Surrogate Created" trigger.
const WORKFLOW = "New Lead Welcome"

test(
    "a seeded org workflow switches on, stays on after a reload, and switches off",
    { session: "admin", tags: ["workflows"] },
    async ({ app, screen, browser }) => {
        await app.open("/automation")
        const toggle = screen.getByRole("switch", `Toggle workflow ${WORKFLOW}`)
        await expect(toggle).toBeChecked({ checked: false, timeout: 10_000 })

        await toggle.tap()
        await expect(toggle).toBeChecked({ timeout: 10_000 })
        await browser.reload()
        await expect(toggle).toBeChecked({ timeout: 10_000 })

        await toggle.tap()
        await expect(toggle).toBeChecked({ checked: false, timeout: 10_000 })
    },
)

test(
    "an admin duplicates an org workflow, reads the copy's details, and deletes it",
    { session: "admin", tags: ["workflows"] },
    async ({ app, screen }) => {
        await app.open("/automation")
        await screen.getByRole("button", `Actions for workflow ${WORKFLOW}`).tap()
        await screen.getByRole("menuitem", "Duplicate").tap()
        const copy = `${WORKFLOW} (Copy)`
        await expect(screen.getByRole("heading", copy)).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("switch", `Toggle workflow ${copy}`)).toBeChecked({ checked: false })

        await screen.getByRole("button", `Actions for workflow ${copy}`).tap()
        await screen.getByRole("menuitem", "Details").tap()
        const details = screen.getByRole("dialog", copy)
        await expect(details).toContainText("Organization", { timeout: 10_000 })
        await details.getByRole("button", "Close").tap()
        await expect(details).toBeHidden()

        // Deletion asks for confirmation; the copy leaves the list, the original stays.
        await screen.getByRole("button", `Actions for workflow ${copy}`).tap()
        await screen.getByRole("menuitem", "Delete").tap()
        await screen.getByRole("alertdialog", `Delete ${copy}?`).getByRole("button", "Delete").tap()
        await expect(screen.getByText("Workflow deleted")).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("heading", copy)).toHaveCount(0, { timeout: 10_000 })
        await expect(screen.getByRole("heading", WORKFLOW)).toBeVisible()
    },
)

test(
    "a test run of an org workflow reports the actions that would run",
    { session: "admin", tags: ["workflows"] },
    async ({ app, screen }) => {
        await app.open("/automation")
        await screen.getByRole("button", `Actions for workflow ${WORKFLOW}`).tap()
        await screen.getByRole("menuitem", "Test Workflow").tap()
        const dialog = screen.getByRole("dialog", "Test Workflow")
        await expect(dialog.getByRole("button", "Run Test")).toBeDisabled()

        // The picker lists seeded surrogates; the first one is the test subject.
        await dialog.getByRole("button", /^S\d{5} • /).first().tap()
        await dialog.getByRole("button", "Run Test").tap()
        await expect(dialog).toContainText("Actions that would run:", { timeout: 15_000 })
    },
)
