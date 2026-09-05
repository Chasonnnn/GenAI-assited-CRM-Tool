import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { EntityTasksSection } from "@/components/tasks/EntityTasksSection"
import type { TaskListItem, TaskListParams } from "@/lib/api/tasks"

const mocks = vi.hoisted(() => ({
    useTask: vi.fn(), useTasks: vi.fn(), create: vi.fn(), batch: vi.fn(), update: vi.fn(), complete: vi.fn(), reopen: vi.fn(), delete: vi.fn(),
    permissions: vi.fn(), auth: vi.fn(), error: vi.fn(),
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: mocks.auth }))
vi.mock("@/lib/hooks/use-permissions", () => ({ useEffectivePermissions: mocks.permissions }))
vi.mock("@/components/ui/toast", () => ({ toast: { error: mocks.error } }))
vi.mock("@/lib/hooks/use-tasks", () => ({
    useTasks: mocks.useTasks,
    useTask: mocks.useTask,
    useCreateTask: () => ({ mutateAsync: mocks.create, isPending: false }),
    useCreateTaskBatch: () => ({ mutateAsync: mocks.batch, isPending: false }),
    useUpdateTask: () => ({ mutateAsync: mocks.update, isPending: false }),
    useCompleteTask: () => ({ mutateAsync: mocks.complete, isPending: false }),
    useUncompleteTask: () => ({ mutateAsync: mocks.reopen, isPending: false }),
    useDeleteTask: () => ({ mutateAsync: mocks.delete, isPending: false }),
}))
vi.mock("@/components/tasks/TaskEditModal", () => ({
    TaskEditModal: ({ task, onSave, onDelete }: { task: TaskListItem; onSave: (id: string, data: object) => void; onDelete?: (id: string) => void }) => <div role="dialog" aria-label="Edit Task" data-description={task.description}><button onClick={() => onSave(task.id, { title: "Updated task" })}>Save task</button>{onDelete ? <button onClick={() => onDelete(task.id)}>Delete task</button> : null}</div>,
}))
vi.mock("@/components/tasks/AddTaskDialog", () => ({
    AddTaskDialog: ({ onSubmit, initialRelatedRecord }: { onSubmit: (data: object) => void; initialRelatedRecord: object }) => <button onClick={() => onSubmit({ title: "Weekly review", task_type: "review", recurrence: "weekly", due_date: "2026-09-07", repeat_until: "2026-09-21", ...initialRelatedRecord })}>Create recurring task</button>,
}))
const task: TaskListItem = {
    id: "task-1", title: "Review donor", description: "Check screening", task_type: "review",
    surrogate_id: null, surrogate_number: null, intended_parent_id: null, donor_id: "donor-1", donor_number: "D10001", donor_type: "egg", donor_name: "Donor",
    owner_type: "user", owner_id: "user-1", owner_name: "Owner", created_by_user_id: "user-1", created_by_name: "Owner",
    due_date: "2026-09-10", due_time: null, duration_minutes: null, is_completed: false, completed_at: null, completed_by_name: null, created_at: "2026-09-01T00:00:00Z",
}
const props = { subject: { donor_id: "donor-1" }, record: { donor_id: "donor-1" }, canView: true, canCreate: true }

describe("EntityTasksSection", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.useTask.mockReturnValue({ data: task, isLoading: false, isError: false })
        mocks.auth.mockReturnValue({ user: { user_id: "user-1", role: "case_manager" } })
        mocks.permissions.mockReturnValue({ data: { permissions: ["edit_tasks", "delete_tasks"] } })
        mocks.useTasks.mockImplementation((params: TaskListParams) => ({ data: { items: [{ ...task, is_completed: params.is_completed === true }], pages: 3 }, isLoading: false, isError: false }))
        for (const mutation of [mocks.create, mocks.batch, mocks.update, mocks.complete, mocks.reopen, mocks.delete]) mutation.mockResolvedValue({})
    })

    it("fetches complete details when a list projection lacks description and creator", () => {
        mocks.useTasks.mockReturnValue({ data: { items: [{ id: task.id, title: task.title, owner_type: "user", owner_id: "another-owner" }], pages: 1 } })
        mocks.useTask.mockReturnValue({ data: { ...task, description: "Complete instructions", owner_id: "another-owner" }, isError: false })
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        expect(mocks.useTask).toHaveBeenCalledWith(task.id)
        expect(screen.getByRole("dialog", { name: "Edit Task" })).toHaveAttribute("data-description", "Complete instructions")
    })

    it("pages within the record and resets pagination when changing completion filters", () => {
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: "Next" }))
        expect(mocks.useTasks).toHaveBeenLastCalledWith(expect.objectContaining({ donor_id: "donor-1", page: 2, is_completed: false, exclude_approvals: true }), { enabled: true })
        fireEvent.click(screen.getByRole("button", { name: "Completed", exact: true }))
        expect(mocks.useTasks).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, is_completed: true }), { enabled: true })
        fireEvent.click(screen.getByRole("button", { name: "All", exact: true }))
        expect(mocks.useTasks.mock.lastCall?.[0]).not.toHaveProperty("is_completed")
    })

    it("opens and edits a task, completes it, and reopens completed tasks", async () => {
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        fireEvent.click(screen.getByRole("button", { name: "Save task" }))
        await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ taskId: task.id, data: { title: "Updated task" } }))
        fireEvent.click(screen.getByRole("checkbox", { name: "Complete Review donor" }))
        await waitFor(() => expect(mocks.complete).toHaveBeenCalledWith(task.id))
        fireEvent.click(screen.getByRole("button", { name: "Completed", exact: true }))
        fireEvent.click(screen.getByRole("checkbox", { name: "Reopen Review donor" }))
        await waitFor(() => expect(mocks.reopen).toHaveBeenCalledWith(task.id))
    })

    it("deletes an owned task only when delete permission is present", async () => {
        const { unmount } = render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        fireEvent.click(screen.getByRole("button", { name: "Delete task" }))
        await waitFor(() => expect(mocks.delete).toHaveBeenCalledWith(task.id))
        unmount()
        mocks.permissions.mockReturnValue({ data: { permissions: ["edit_tasks"] } })
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        expect(screen.queryByRole("button", { name: "Delete task" })).not.toBeInTheDocument()
    })

    it("shows read-only details when the user cannot manage the task", () => {
        mocks.auth.mockReturnValue({ user: { user_id: "another-user", role: "case_manager" } })
        render(<EntityTasksSection {...props} />)
        expect(screen.getByRole("checkbox")).toHaveAttribute("aria-disabled", "true")
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        expect(screen.getByText("Check screening")).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Save task" })).not.toBeInTheDocument()
    })

    it("requires edit permission even for the task owner", () => {
        mocks.permissions.mockReturnValue({ data: { permissions: [] } })
        render(<EntityTasksSection {...props} />)
        expect(screen.getByRole("checkbox")).toHaveAttribute("aria-disabled", "true")
        fireEvent.click(screen.getByRole("button", { name: task.title }))
        expect(screen.queryByRole("button", { name: "Save task" })).not.toBeInTheDocument()
    })

    it("creates every requested recurrence using the shared batch mutation", async () => {
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: "Add Task" }))
        fireEvent.click(screen.getByRole("button", { name: "Create recurring task" }))
        await waitFor(() => expect(mocks.batch).toHaveBeenCalledWith([
            expect.objectContaining({ donor_id: "donor-1", due_date: "2026-09-07" }),
            expect.objectContaining({ donor_id: "donor-1", due_date: "2026-09-14" }),
            expect.objectContaining({ donor_id: "donor-1", due_date: "2026-09-21" }),
        ]))
        expect(mocks.create).not.toHaveBeenCalled()
    })

    it("shows mutation failures and keeps the task available", async () => {
        mocks.complete.mockRejectedValueOnce(new Error("Update failed"))
        render(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("checkbox"))
        await waitFor(() => expect(mocks.error).toHaveBeenCalledWith("Update failed"))
        expect(screen.getByRole("button", { name: task.title })).toBeInTheDocument()
    })

    it("renders loading, retryable error and empty states", () => {
        mocks.useTasks.mockReturnValue({ isLoading: true })
        const { rerender } = render(<EntityTasksSection {...props} />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading tasks")
        const retry = vi.fn()
        mocks.useTasks.mockReturnValue({ isError: true, refetch: retry })
        rerender(<EntityTasksSection {...props} />)
        fireEvent.click(screen.getByRole("button", { name: "Retry" }))
        expect(retry).toHaveBeenCalledOnce()
        mocks.useTasks.mockReturnValue({ data: { items: [], pages: 0 } })
        rerender(<EntityTasksSection {...props} />)
        expect(screen.getByText("No tasks yet.")).toBeInTheDocument()
    })

    it("disables the query without view access and hides creation for archived records", () => {
        const { rerender } = render(<EntityTasksSection {...props} canView={false} />)
        expect(mocks.useTasks).toHaveBeenLastCalledWith(expect.anything(), { enabled: false })
        expect(screen.queryByRole("heading", { name: "Tasks" })).not.toBeInTheDocument()
        rerender(<EntityTasksSection {...props} archived />)
        expect(screen.queryByRole("button", { name: "Add Task" })).not.toBeInTheDocument()
    })
})
