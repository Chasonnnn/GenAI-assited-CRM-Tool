import { expect, type App, type Screen } from "e2e"

export const APPLICANT = { name: "Erin Example", phone: "(512) 555-0142", email: "erin.example@example.com" }

/** Creates a form with the four identity fields and publishes it at `intakePath`. */
export async function publishForm(app: App, screen: Screen, name: string, intakePath: string) {
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
export async function submitApplication(app: App, screen: Screen, intakePath: string, email: string) {
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
