import { test } from "@e2e-dev/web"
import { expect } from "e2e"

const CAMPAIGN = "E2E spring newsletter"

test(
    "an admin sets up an email campaign and it waits as a draft",
    { session: "admin", tags: ["campaigns"] },
    async ({ app, screen }) => {
        await app.open("/automation/campaigns")
        await expect(screen.getByRole("heading", "No campaigns yet")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("button", "Create Campaign").first().tap()
        const dialog = screen.getByRole("dialog", "Create Campaign")

        await dialog.getByRole("combobox", "Channel").tap()
        await screen.getByRole("option", "Email").tap()
        await dialog.getByRole("textbox", "Campaign name").fill(CAMPAIGN)
        await dialog.getByRole("button", "Next").tap()

        // Audience: the default recipient type covers every stage.
        await expect(dialog.getByRole("combobox", "Recipient type")).toBeVisible({ timeout: 10_000 })
        await dialog.getByRole("button", "Next").tap()

        // Content: a seeded organization template; the step cannot advance without one.
        const template = dialog.getByRole("combobox", /template/i)
        await expect(template).toBeVisible({ timeout: 10_000 })
        await expect(dialog.getByRole("button", "Next")).toBeDisabled()
        await template.tap()
        await screen.getByRole("option", "Welcome New Lead").tap()
        await dialog.getByRole("button", "Next").tap()

        // Review: the campaign is kept as a draft, so nothing is sent.
        await dialog.getByRole("radiogroup", "When to send").getByRole("radio", "Save as draft").check()
        await dialog.getByRole("button", "Save Draft").tap()
        await expect(screen.getByText("Campaign saved as draft")).toBeVisible({ timeout: 10_000 })
        await expect(dialog).toBeHidden({ timeout: 10_000 })

        await screen.getByRole("tab", "Draft").tap()
        await expect(screen.getByRole("button", `Actions for ${CAMPAIGN}`)).toBeVisible({ timeout: 10_000 })
        await expect(screen.getByRole("heading", "No campaigns yet")).toHaveCount(0)
    },
)
