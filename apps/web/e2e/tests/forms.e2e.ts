import { test } from "@e2e-dev/web"
import { expect, type App, type Screen } from "e2e"

import { grantAdminSession } from "../admin-session"

const APPLICANT = { name: "Erin Example", phone: "(512) 555-0142", email: "erin.example@example.com" }

/** Creates a form with the four identity fields and publishes it at `intakePath`. */
async function publishForm(app: App, screen: Screen, name: string, intakePath: string) {
    await app.open("/automation/forms")
    await screen.getByRole("button", "Create Form").first().tap()
    const createDialog = screen.getByRole("dialog", "Create New Form")
    await createDialog.getByRole("textbox", "Form Name *").fill(name)
    await createDialog.getByRole("button", "Create Form").tap()

    // A form cannot be published until it has the four identity fields.
    await expect(screen.getByRole("button", "Publish")).toBeDisabled({ timeout: 20_000 })
    for (const field of ["Full Name", "Date of Birth", "Phone", "Email"]) {
        await screen.getByRole("button", `Add ${field} to form`).tap()
    }
    await screen.getByRole("button", "Publish").tap()
    await screen.getByRole("alertdialog", "Publish Form").getByRole("button", "Publish").tap()

    const share = screen.getByRole("alertdialog", "Share Application Intake")
    await expect(share).toContainText(intakePath, { timeout: 15_000 })
    await share.getByRole("button", "Close").tap()
}

/** Fills the public form and submits it. The applicant has no account, so the admin session is dropped first. */
async function submitApplication(app: App, screen: Screen, intakePath: string, email: string) {
    await app.clearState()
    await app.open(intakePath)
    await screen.getByRole("textbox", "Full Name *").fill(APPLICANT.name)
    await screen.getByRole("button", "Select a date").tap()
    await screen.getByRole("combobox", "Choose the Year").selectOption("1995")
    await screen.getByRole("combobox", "Choose the Month").selectOption("Jun")
    await screen.getByRole("gridcell", "Thursday, June 15th, 1995").tap()
    await screen.getByRole("textbox", "Phone *").fill(APPLICANT.phone)
    await screen.getByRole("textbox", "Email *").fill(email)
    await screen.getByRole("checkbox", /^I confirm that the information provided is accurate/).check()
    await screen.getByRole("button", "Submit Application").tap()
}

test(
    "an admin publishes a form and receives an applicant's submission",
    { session: "admin", tags: ["forms"] },
    async ({ app, screen, browser }) => {
        await publishForm(app, screen, "E2E interest form", "/intake/e2e-interest-form")
        const builderUrl = await browser.url()

        await submitApplication(app, screen, "/intake/e2e-interest-form", APPLICANT.email)
        await expect(screen.getByRole("heading", "Application Submitted!")).toBeVisible({ timeout: 15_000 })

        // Back as the admin, the submission waits in the form's routing review.
        await grantAdminSession(browser)
        await browser.goto(builderUrl)
        await screen.getByRole("tab", "Submissions 1").tap()
        const submission = screen.getByRole("article", APPLICANT.name)
        await expect(submission).toContainText(APPLICANT.email)
        await expect(submission).toContainText("Pending Review")
    },
)

test(
    "the public form rejects a reserved email domain before it submits",
    { session: "admin", tags: ["forms"] },
    async ({ app, screen }) => {
        await publishForm(app, screen, "E2E reserved email form", "/intake/e2e-reserved-email-form")

        await submitApplication(app, screen, "/intake/e2e-reserved-email-form", "erin.example@example.test")
        const email = screen.getByRole("textbox", "Email *")
        await expect(screen.getByText("Email must be a valid email address.")).toBeVisible()
        await expect(email).toBeFocused()

        // Nothing reached the API: it sends no rejection toast, and the form is still open.
        await expect(screen.getByRole("alert").filter({ hasText: "Field 'Email'" })).toHaveCount(0)
        await expect(screen.getByRole("heading", "Application Submitted!")).toHaveCount(0)

        // A deliverable address clears the error and goes through.
        await email.fill(APPLICANT.email)
        await expect(screen.getByText("Email must be a valid email address.")).toHaveCount(0)
        await screen.getByRole("button", "Submit Application").tap()
        await expect(screen.getByRole("heading", "Application Submitted!")).toBeVisible({ timeout: 15_000 })
    },
)

test(
    "the public form names the field the API rejected",
    { session: "admin", tags: ["forms"] },
    async ({ app, screen }) => {
        await publishForm(app, screen, "E2E email check form", "/intake/e2e-email-check-form")

        // The page cannot decode a Punycode label, so only the API rejects this address.
        await submitApplication(app, screen, "/intake/e2e-email-check-form", "erin.example@xn--a.com")
        // The toast is an alert whose text is the API's message; an alert takes no name from its content.
        const rejection = screen.getByRole("alert").filter({ hasText: "Field 'Email' must be a valid email address" })
        await expect(rejection).toBeVisible({ timeout: 15_000 })

        // The applicant stays on the form and can correct the address.
        await expect(screen.getByRole("textbox", "Email *")).toHaveValue("erin.example@xn--a.com")
        await expect(screen.getByRole("button", "Submit Application")).toBeEnabled()
    },
)
