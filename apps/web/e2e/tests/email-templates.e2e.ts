import { test } from "@e2e-dev/web"
import { expect, type Screen } from "e2e"

// The seeder creates these organization templates for every org. Other tests add more: the
// first booking email of each kind creates its default template, such as "Booking Confirmed".
const SEEDED_ORG_TEMPLATES = 17
const TEMPLATE = { name: "E2E welcome note", subject: "Welcome to the agency" }

const templateCards = (screen: Screen) => screen.getByRole("button", /^Actions for /)

test(
    "the organization tab lists the seeded templates and the search narrows them",
    { session: "admin", tags: ["email-templates"] },
    async ({ app, screen }) => {
        await app.open("/automation/email-templates")
        await screen.getByRole("tab", /^Organization/).tap()
        await expect(screen.getByRole("heading", "Welcome New Lead")).toBeVisible({ timeout: 10_000 })
        await expect.poll(() => templateCards(screen).count()).toBeGreaterThanOrEqual(SEEDED_ORG_TEMPLATES)

        await screen.getByRole("searchbox", "Search templates").fill("Appointment")
        await expect(screen.getByRole("heading", "Welcome New Lead")).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByRole("heading", "Appointment Confirmed")).toBeVisible()
        await expect(screen.getByRole("heading", "Appointment Reminder (24h)")).toBeVisible()

        await screen.getByRole("searchbox", "Search templates").fill("no such template")
        await expect(screen.getByRole("heading", "No matching templates")).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "an admin saves an organization template draft and finds it in the list",
    { session: "admin", tags: ["email-templates"] },
    async ({ app, screen, browser }) => {
        await app.open("/automation/email-templates")
        await screen.getByRole("tab", /^Organization/).tap()
        await expect(screen.getByRole("heading", "Welcome New Lead")).toBeVisible({ timeout: 10_000 })
        const templatesBefore = await templateCards(screen).count()
        await screen.getByRole("button", "Create Org Template").tap()
        await expect(browser).toHaveURL(/\/automation\/email-templates\/org\/new/, { timeout: 10_000 })
        await expect(screen.getByRole("heading", "New email template")).toBeVisible({ timeout: 10_000 })

        await screen.getByRole("textbox", "Template name").fill(TEMPLATE.name)
        await screen.getByRole("textbox", "Subject").fill(TEMPLATE.subject)
        // The body is built from blocks; a text block opens the body editor.
        await screen.getByRole("region", "Blocks").getByRole("button", "Text").tap()
        await screen.getByRole("textbox", "Email body").fill("Thank you for your interest.")
        await screen.getByRole("button", "Save draft").tap()
        await expect(screen.getByText(/^Saved/)).toBeVisible({ timeout: 10_000 })

        // The list offers the unpublished draft to resume.
        await screen.getByRole("button", "Back to email templates").tap()
        await screen.getByRole("tab", /^Organization/).tap()
        await expect(screen.getByRole("heading", `Resume ${TEMPLATE.name}`)).toBeVisible({ timeout: 10_000 })
        await expect(templateCards(screen)).toHaveCount(templatesBefore + 1, { timeout: 10_000 })
    },
)
