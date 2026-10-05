import { test } from "@e2e-dev/web"
import { expect } from "e2e"

import { grantAdminSession } from "../admin-session"

const FORM = "E2E interest form"
const INTAKE_PATH = "/intake/e2e-interest-form"
const APPLICANT = { name: "Erin Example", phone: "(512) 555-0142", email: "erin.example@example.com" }

test(
    "an admin publishes a form and receives an applicant's submission",
    { session: "admin", tags: ["forms"] },
    async ({ app, screen, browser }) => {
        await app.open("/automation/forms")
        await screen.getByRole("button", "Create Form").first().tap()
        const createDialog = screen.getByRole("dialog", "Create New Form")
        await createDialog.getByRole("textbox", "Form Name *").fill(FORM)
        await createDialog.getByRole("button", "Create Form").tap()

        // A form cannot be published until it has the four identity fields.
        await expect(screen.getByRole("button", "Publish")).toBeDisabled({ timeout: 20_000 })
        for (const field of ["Full Name", "Date of Birth", "Phone", "Email"]) {
            await screen.getByRole("button", `Add ${field} to form`).tap()
        }
        await screen.getByRole("button", "Publish").tap()
        await screen.getByRole("alertdialog", "Publish Form").getByRole("button", "Publish").tap()

        const share = screen.getByRole("alertdialog", "Share Application Intake")
        await expect(share).toContainText(INTAKE_PATH, { timeout: 15_000 })
        await share.getByRole("button", "Close").tap()
        const builderUrl = await browser.url()

        // The applicant has no account, so drop the admin session before the public form.
        await app.clearState()
        await app.open(INTAKE_PATH)
        await screen.getByRole("textbox", "Full Name *").fill(APPLICANT.name)
        await screen.getByRole("button", "Select a date").tap()
        await screen.getByRole("combobox", "Choose the Year").selectOption("1995")
        await screen.getByRole("combobox", "Choose the Month").selectOption("Jun")
        await screen.getByRole("gridcell", "Thursday, June 15th, 1995").tap()
        await screen.getByRole("textbox", "Phone *").fill(APPLICANT.phone)
        await screen.getByRole("textbox", "Email *").fill(APPLICANT.email)
        await screen.getByRole("checkbox", /^I confirm that the information provided is accurate/).check()
        await screen.getByRole("button", "Submit Application").tap()
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
