import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { SurrogateTasksCalendar } from "@/components/surrogates/SurrogateTasksCalendar"
import type { TaskListItem } from "@/lib/api/tasks"

vi.mock("@/components/appointments/UnifiedCalendar", () => ({
    UnifiedCalendar: ({ taskFilter }: { taskFilter?: { surrogate_id?: string } }) => (
        <div data-surrogate-id={taskFilter?.surrogate_id ?? ""} data-testid="unified-calendar">
            Calendar view
        </div>
    ),
}))

function installTaskViewStorage(initialView: "list" | "calendar" = "list") {
    const storage = new Map<string, string>([["surrogate-tasks-view-s1", initialView]])
    const setItem = vi.fn((key: string, value: string) => {
        storage.set(key, value)
    })

    Object.defineProperty(window, "localStorage", {
        value: {
            getItem: vi.fn((key: string) => storage.get(key) ?? null),
            setItem,
            removeItem: vi.fn((key: string) => {
                storage.delete(key)
            }),
        },
        configurable: true,
        writable: true,
    })

    return { setItem, storage }
}

function makeTask(overrides: Partial<TaskListItem> = {}): TaskListItem {
    return {
        id: "t1",
        title: "Initial Consultation",
        description: null,
        task_type: "other",
        surrogate_id: "s1",
        surrogate_number: "S10001",
        owner_type: "user",
        owner_id: "u1",
        owner_name: "User 1",
        created_by_user_id: "u1",
        created_by_name: "User 1",
        due_date: "2000-01-01",
        due_time: null,
        duration_minutes: null,
        is_completed: false,
        completed_at: null,
        completed_by_name: null,
        created_at: new Date().toISOString(),
        ...overrides,
    }
}

beforeEach(() => {
    installTaskViewStorage()
})

describe("SurrogateTasksCalendar accessibility", () => {
    it("renders task titles as buttons and provides checkbox aria-labels", async () => {
        const onTaskToggle = vi.fn()
        const onAddTask = vi.fn()
        const onTaskClick = vi.fn()

        const tasks = [
            {
                ...makeTask(),
            },
            makeTask({
                id: "t2",
                title: "Background Check",
                is_completed: true,
                completed_at: new Date().toISOString(),
                completed_by_name: "User 1",
            }),
        ] as TaskListItem[]

        render(
            <SurrogateTasksCalendar
                surrogateId="s1"
                tasks={tasks}
                onTaskToggle={onTaskToggle}
                onAddTask={onAddTask}
                onTaskClick={onTaskClick}
            />
        )

        const activeTitleButton = await screen.findByRole("button", {
            name: /Initial Consultation/,
        })
        expect(activeTitleButton).toHaveClass(
            "focus-visible:ring-2",
            "focus-visible:ring-ring",
            "focus-visible:ring-offset-2",
        )
        fireEvent.click(activeTitleButton)
        expect(onTaskClick).toHaveBeenCalledWith(expect.objectContaining({ id: "t1" }))

        expect(
            screen.getByLabelText("Mark Initial Consultation as complete")
        ).toBeInTheDocument()

        // Expand completed section and ensure completed tasks are also buttons.
        fireEvent.click(screen.getByText("Completed"))
        const completedTitleButton = await screen.findByRole("button", {
            name: /Background Check/,
        })
        expect(completedTitleButton).toHaveClass(
            "focus-visible:ring-2",
            "focus-visible:ring-ring",
            "focus-visible:ring-offset-2",
        )
        fireEvent.click(completedTitleButton)
        expect(onTaskClick).toHaveBeenCalledWith(expect.objectContaining({ id: "t2" }))

        expect(
            screen.getByLabelText("Mark Background Check as incomplete")
        ).toBeInTheDocument()
    })

    it("uses the persisted calendar view and stores view changes", async () => {
        const { setItem } = installTaskViewStorage("calendar")
        const onTaskClick = vi.fn()

        render(
            <SurrogateTasksCalendar
                surrogateId="s1"
                tasks={[makeTask()]}
                onTaskToggle={vi.fn()}
                onAddTask={vi.fn()}
                onTaskClick={onTaskClick}
            />
        )

        const calendar = await screen.findByTestId("unified-calendar")
        expect(calendar).toHaveAttribute("data-surrogate-id", "s1")

        fireEvent.click(screen.getByRole("button", { name: /list/i }))

        expect(setItem).toHaveBeenCalledWith("surrogate-tasks-view-s1", "list")
        expect(
            await screen.findByRole("button", { name: /Initial Consultation/ })
        ).toBeInTheDocument()
    })
})
