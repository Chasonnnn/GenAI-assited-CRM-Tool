import { test } from "@e2e-dev/web"
import { expect } from "e2e"

const WORKFLOW = "E2E welcome task"

test(
    "an admin builds a draft org workflow and reopens it",
    { session: "admin", tags: ["workflow-editor"] },
    async ({ app, screen, browser }) => {
        await app.open("/automation")
        await screen.getByRole("button", "Create Org Workflow").first().tap()

        await screen.getByRole("textbox", "Workflow name").fill(WORKFLOW)
        await screen.getByRole("combobox", "Trigger type").tap()
        await screen.getByRole("option", "Surrogate Created").tap()
        await screen.getByRole("button", "Create Task").tap()

        // An action that lacks its required field blocks saving.
        const firstAction = screen.getByRole("button", "Action 1: Create Task")
        await expect(firstAction).toContainText("Task actions need a title.")
        await expect(screen.getByRole("button", "Save draft")).toBeDisabled()

        await screen.getByRole("textbox", "Task title").fill("Call the new surrogate")
        await screen.getByRole("button", "Save draft").tap()

        // Saving returns to the list, where a draft is present and switched off.
        await expect(screen.getByRole("heading", WORKFLOW)).toBeVisible({ timeout: 15_000 })
        await expect(screen.getByRole("switch", `Toggle workflow ${WORKFLOW}`)).toBeChecked({ checked: false })

        // After a reload the editor shows the steps the server stored.
        await browser.reload()
        await screen.getByRole("button", `Actions for workflow ${WORKFLOW}`).tap()
        await screen.getByRole("menuitem", "Edit").tap()
        await expect(screen.getByRole("textbox", "Workflow name")).toHaveValue(WORKFLOW)
        await expect(screen.getByRole("button", "Trigger step")).toContainText("Surrogate Created")
        await expect(firstAction).toContainText("Call the new surrogate")
    },
)
