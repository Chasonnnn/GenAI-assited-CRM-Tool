import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { grantAdminSession } from "../admin-session"
import { API_URL } from "../local-stack"

// The `ops` session belongs to the seeded developer, whom the e2e stack lists in
// PLATFORM_ADMIN_EMAILS. Test Organization is the only agency, so nothing here confirms a
// delete, and creating an agency stops at validation: its invite email has no sender.
const PLATFORM_TEMPLATE = { name: "E2E platform onboarding", subject: "Welcome aboard" }

test(
    "a platform admin finds the agency from the dashboard and opens its details",
    { session: "ops", tags: ["ops"] },
    async ({ app, screen, browser }) => {
        await app.open("/ops")
        await expect(screen.getByRole("heading", "Dashboard", { level: 1 })).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByRole("heading", "No open alerts")).toBeVisible({ timeout: 10_000 })

        await screen.getByRole("navigation").getByRole("link", "Agencies").tap()
        await expect(browser).toHaveURL("/ops/agencies", { timeout: 10_000 })
        const agencyRow = screen.getByRole("row").filter({ hasText: "Test Organization" })
        await expect(agencyRow).toBeVisible({ timeout: 10_000 })
        await expect(agencyRow).toContainText("Active")

        // Test Organization has no subscription row; the Active filter keeps it, as the table shows.
        await screen.getByRole("combobox", "Filter by status").tap()
        await screen.getByRole("option", "Active").tap()
        await expect(agencyRow).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("combobox", "Filter by status").tap()
        await screen.getByRole("option", "Trial").tap()
        await expect(screen.getByRole("heading", "No matching agencies")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("combobox", "Filter by status").tap()
        await screen.getByRole("option", "All statuses").tap()

        await screen.getByRole("textbox", "Search agencies").fill("no-such-agency")
        await expect(screen.getByRole("heading", "No matching agencies")).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("textbox", "Search agencies").fill("test-org")
        await agencyRow.tap()

        await expect(browser).toHaveURL(/\/ops\/agencies\/[0-9a-f-]{36}$/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", "Test Organization", { level: 1 })).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("tab", /^Users/).tap()
        await expect(screen.getByRole("row").filter({ hasText: "intake@test.com" })).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("tab", "Subscription").tap()
        await expect(screen.getByRole("heading", "No subscription record")).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "creating an agency refuses a taken and a reserved slug",
    { session: "ops", tags: ["ops"] },
    async ({ app, screen }) => {
        await app.open("/ops/agencies/new")
        await expect(screen.getByRole("heading", "Create Agency", { level: 1 })).toBeVisible({ timeout: 15_000 })
        await screen.getByRole("textbox", "Agency Name").fill("Second Agency")
        await screen.getByRole("textbox", "First Admin Email").fill("owner@second-agency.example.com")

        await screen.getByRole("textbox", "Slug").fill("test-org")
        await screen.getByRole("button", "Create Agency").tap()
        await expect(screen.getByText("Slug 'test-org' is already taken.")).toBeVisible({ timeout: 10_000 })

        await screen.getByRole("textbox", "Slug").fill("ops")
        await screen.getByRole("button", "Create Agency").tap()
        await expect(screen.getByText("Reserved slug: ops")).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "a platform admin approves a terminal's CLI login and signs it out",
    { session: "ops", tags: ["ops"] },
    async ({ app, screen }) => {
        const start = await fetch(`${API_URL}/platform/cli/login/start`, { method: "POST" })
        expect(start.status).toBe(200)
        const { user_code: userCode, device_code: deviceCode } = (await start.json()) as {
            user_code: string
            device_code: string
        }
        const exchange = async () =>
            (await (
                await fetch(`${API_URL}/platform/cli/login/exchange`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ device_code: deviceCode }),
                })
            ).json()) as { status: string; token?: string }
        expect((await exchange()).status).toBe("pending")

        await app.open("/ops/cli")
        await expect(screen.getByText("No CLI sessions.")).toBeVisible({ timeout: 15_000 })
        await screen.getByRole("textbox", "Code from your terminal").fill(userCode)
        await screen.getByRole("button", "Sign in to CLI").tap()
        await expect(screen.getByText("Approved. Return to your terminal.")).toBeVisible({ timeout: 10_000 })

        const approved = await exchange()
        expect(approved.status).toBe("approved")
        expect(approved.token).toBeTruthy()

        await expect(screen.getByText(/^Signed in /)).toBeVisible({ timeout: 10_000 })
        await screen.getByRole("button", "Sign out").tap()
        await expect(screen.getByText("Signed out")).toBeVisible({ timeout: 10_000 })

        // A code nobody started is refused.
        await screen.getByRole("button", "Connect another terminal").tap()
        await screen.getByRole("textbox", "Code from your terminal").fill("ZZZZ-ZZZZ-ZZZZ")
        await screen.getByRole("button", "Sign in to CLI").tap()
        await expect(screen.getByRole("alert").filter({ hasText: "Unable to approve." })).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "a template published to all organizations reaches the agency's platform library",
    { session: "ops", tags: ["ops"] },
    async ({ app, screen, browser }) => {
        await app.open("/ops/templates/email/new")
        await screen.getByRole("textbox", "Template name").fill(PLATFORM_TEMPLATE.name)
        await screen.getByRole("textbox", "Subject *").fill(PLATFORM_TEMPLATE.subject)
        await screen.getByRole("region", "Blocks").getByRole("button", "Text").tap()
        await screen.getByRole("textbox", "Email body").fill("Your workspace is ready.")
        await screen.getByRole("button", "Save draft").tap()
        await expect(screen.getByText("Template saved")).toBeVisible({ timeout: 10_000 })
        await expect(browser).toHaveURL(/\/ops\/templates\/email\/[0-9a-f-]{36}$/, { timeout: 10_000 })

        await screen.getByRole("button", "Publish").tap()
        const dialog = screen.getByRole("dialog", "Publish template")
        await dialog.getByRole("radio", /^Publish to all organizations/).check()
        await dialog.getByRole("button", "Publish").tap()
        await expect(screen.getByText("Template published")).toBeVisible({ timeout: 10_000 })

        await grantAdminSession(browser)
        await app.open("/automation/email-templates")
        await screen.getByRole("tab", /^Platform/).tap()
        await expect(screen.getByRole("heading", PLATFORM_TEMPLATE.name)).toBeVisible({ timeout: 10_000 })
    },
)
