import { test } from "@e2e-dev/web"
import { expect, type Screen } from "e2e"

const INVITEE = "e2e.invitee@example.com"

const memberRows = (screen: Screen) => screen.getByRole("row").filter({ hasText: "@test.com" })

test(
    "the people list filters the seeded members and opens one",
    { session: "admin", tags: ["team"] },
    async ({ app, screen, browser }) => {
        await app.open("/settings/team")
        await expect(screen.getByRole("tab", "Members (4)")).toBeVisible({ timeout: 10_000 })
        await expect(memberRows(screen)).toHaveCount(4)

        await screen.getByRole("textbox", "Search people").fill("Case")
        await expect(memberRows(screen)).toHaveCount(1, { timeout: 10_000 })
        await expect(memberRows(screen)).toContainText("specialist@test.com")

        await screen.getByRole("textbox", "Search people").fill("")
        await screen.getByRole("combobox", "Filter by role").tap()
        await screen.getByRole("option", "Intake Specialist").tap()
        await expect(memberRows(screen)).toHaveCount(1, { timeout: 10_000 })
        const intake = memberRows(screen).filter({ hasText: "intake@test.com" })
        await expect(intake).toBeVisible()

        // Another member's page offers the role control; the admin's own page locks it.
        await intake.getByRole("link", "Manage").tap()
        await expect(browser).toHaveURL(/\/settings\/team\/members\/[0-9a-f-]{36}/, { timeout: 10_000 })
        await expect(screen.getByRole("combobox", "Role")).toBeEnabled({ timeout: 10_000 })
        await expect(screen.getByRole("heading", "Role permissions")).toBeVisible()
    },
)

test(
    "an invitation without a platform email sender reports the error and keeps the form",
    { session: "admin", tags: ["team"] },
    async ({ app, screen }) => {
        await app.open("/settings/team")
        await screen.getByRole("button", "Invite Member").tap()
        const dialog = screen.getByRole("dialog", "Invite Team Member")
        await dialog.getByRole("textbox", "Email address").fill(INVITEE)
        await dialog.getByRole("combobox", "Role").tap()
        await screen.getByRole("option", "Case Manager").tap()
        await dialog.getByRole("button", "Send Invitation").tap()

        // The e2e API has no platform sender, so the invite is refused before it is created.
        const failure = screen.getByRole("alert").filter({ hasText: "Failed to send invitation" })
        await expect(failure).toBeVisible({ timeout: 10_000 })
        await expect(failure).toContainText("Platform email sender is not configured")
        await expect(dialog.getByRole("textbox", "Email address")).toHaveValue(INVITEE)
        await dialog.getByRole("button", "Cancel").tap()
        await expect(dialog).toBeHidden()
        await expect(screen.getByRole("tab", "Invitations (0)")).toBeVisible()
    },
)

test(
    "the roles page shows each role's permissions read-only",
    { session: "admin", tags: ["team"] },
    async ({ app, screen }) => {
        await app.open("/settings/team/roles")
        const records = screen.getByRole("region", "Surrogates permissions").getByRole("region", "Records")
        await expect(screen.getByRole("button", "Case Manager")).toHaveAttribute("aria-pressed", "true", { timeout: 10_000 })
        await expect(records.getByRole("switch", "Delete")).toBeChecked({ checked: false })
        await expect(records.getByRole("switch", "View")).toBeChecked()
        await expect(records.getByRole("switch", "View")).toBeDisabled()

        await screen.getByRole("button", "Admin").tap()
        await expect(records.getByRole("switch", "Delete")).toBeChecked({ timeout: 10_000 })
    },
)
