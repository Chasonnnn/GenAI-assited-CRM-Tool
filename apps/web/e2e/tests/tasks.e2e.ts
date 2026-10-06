import { test } from "@e2e-dev/web"
import { expect } from "e2e"

const TASK = "E2E follow-up call"

test(
    "an admin adds a task, finds it, and completes it",
    { session: "admin", tags: ["tasks"] },
    async ({ app, screen }) => {
        await app.open("/tasks")
        await screen.getByRole("button", "Add task").tap()
        const dialog = screen.getByRole("dialog", "Add Task")
        await dialog.getByRole("textbox", "Title *").fill(TASK)
        await dialog.getByRole("button", "Create task").tap()
        await expect(dialog).toBeHidden({ timeout: 10_000 })

        await screen.getByRole("button", "List").tap()
        const openTask = screen.getByRole("button", `Open task ${TASK}`)
        await expect(openTask).toBeVisible({ timeout: 10_000 })

        await screen.getByRole("textbox", "Search tasks").fill("follow-up")
        await expect(openTask).toBeVisible({ timeout: 10_000 })

        // Completion saves on the server first, so the open list drops the task once it lands.
        await screen.getByRole("checkbox", `Mark task ${TASK} complete`).tap()
        await expect(openTask).toBeHidden({ timeout: 10_000 })
        await screen.getByRole("combobox", "Filter by status").tap()
        await screen.getByRole("option", "Completed").tap()
        await expect(openTask).toBeVisible({ timeout: 10_000 })
    },
)

test(
    "a task added on a surrogate shows on the surrogate and in all tasks",
    { session: "admin", tags: ["tasks"] },
    async ({ app, screen }) => {
        await app.open("/surrogates")
        await screen.getByRole("link").filter({ hasText: /^#S\d{5}$/ }).first().tap()
        await expect(screen.getByRole("button", "Change Stage")).toBeVisible({ timeout: 10_000 })
        const heading = (await screen.getByRole("heading", /^Surrogate #S\d{5}$/).textContent()) ?? ""
        const title = `E2E medical records for ${heading.replace("Surrogate ", "")}`

        await screen.getByRole("tab", "Tasks").tap()
        await screen.getByRole("button", "Add Task").tap()
        const dialog = screen.getByRole("dialog", "Add Task")
        await dialog.getByRole("textbox", "Title *").fill(title)
        await dialog.getByRole("button", "Create Task").tap()
        await expect(dialog).toBeHidden({ timeout: 10_000 })
        await expect(screen.getByRole("checkbox", `Mark ${title} as complete`)).toBeVisible({ timeout: 10_000 })

        await app.open("/tasks?filter=all")
        await screen.getByRole("button", "List").tap()
        await screen.getByRole("textbox", "Search tasks").fill("E2E medical records")
        await expect(screen.getByRole("button", `Open task ${title}`)).toBeVisible({ timeout: 10_000 })
    },
)
