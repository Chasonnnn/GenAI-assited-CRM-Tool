import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { SurrogateTasksCalendar } from "@/components/surrogates/SurrogateTasksCalendar"
import type { TaskListItem } from "@/lib/api/tasks"

beforeEach(() => {
    // Ensure list view is used.
    Object.defineProperty(window, "localStorage", {
        value: {
            getItem: vi.fn(() => "list"),
            setItem: vi.fn(),
            removeItem: vi.fn(),
        },
        writable: true,
    })
})

describe("SurrogateTasksCalendar accessibility", () => {
    it("renders task titles as buttons and provides checkbox aria-labels", async () => {
        const onTaskToggle = vi.fn()
        const onAddTask = vi.fn()
        const onTaskClick = vi.fn()

        const tasks = [
            {
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
                due_date: "2000-01-01", // overdue
                due_time: null,
                duration_minutes: null,
                is_completed: false,
                completed_at: null,
                completed_by_name: null,
                created_at: new Date().toISOString(),
            },
            {
                id: "t2",
                title: "Background Check",
                description: null,
                task_type: "other",
                surrogate_id: "s1",
                surrogate_number: "S10001",
                owner_type: "user",
                owner_id: "u1",
                owner_name: "User 1",
                created_by_user_id: "u1",
                created_by_name: "User 1",
                due_date: "2000-01-01", // completed overdue => should appear in Completed section
                due_time: null,
                duration_minutes: null,
                is_completed: true,
                completed_at: new Date().toISOString(),
                completed_by_name: "User 1",
                created_at: new Date().toISOString(),
            },
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
        fireEvent.click(completedTitleButton)
        expect(onTaskClick).toHaveBeenCalledWith(expect.objectContaining({ id: "t2" }))

        expect(
            screen.getByLabelText("Mark Background Check as incomplete")
        ).toBeInTheDocument()
    })
})
