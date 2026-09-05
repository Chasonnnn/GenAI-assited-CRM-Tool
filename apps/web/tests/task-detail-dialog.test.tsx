import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { TaskDetailDialog } from "@/components/tasks/TaskDetailDialog"
import SurrogateTasksPage from "@/app/(app)/surrogates/[id]/tasks/page"
import type { TaskRead } from "@/lib/api/tasks"

const mocks = vi.hoisted(() => ({ task: vi.fn(), save: vi.fn(), close: vi.fn(), remove: vi.fn(), auth: vi.fn() }))
vi.mock("@/lib/hooks/use-tasks", () => ({
    useTask: mocks.task,
    useTasks: () => ({ data: { items: [{ id: "task-1", title: "Review screening" }] } }),
}))
vi.mock("@/lib/auth-context", () => ({ useAuth: mocks.auth }))
vi.mock("@/lib/hooks/use-permissions", () => ({ useEffectivePermissions: () => ({ data: { permissions: ["edit_tasks", "delete_tasks"] } }) }))
vi.mock("@/components/tasks/TaskRelatedRecordPicker", () => ({ TaskRelatedRecordPicker: () => null }))
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "surrogate-1" }) }))
vi.mock("@/lib/hooks/use-surrogates", () => ({ useSurrogate: () => ({ data: { full_name: "Surrogate" } }) }))
vi.mock("@/lib/hooks/use-task-actions", () => ({ useTaskActions: () => ({ update: mocks.save, remove: mocks.remove, create: vi.fn(), toggle: vi.fn(), isCreating: false, isDeleting: false }) }))
vi.mock("@/components/surrogates/AddSurrogateTaskDialog", () => ({ AddSurrogateTaskDialog: () => null }))
vi.mock("@/components/surrogates/tabs/SurrogateTasksTab", () => ({ SurrogateTasksTab: ({ onTaskClick }: { onTaskClick: (task: object) => void }) => <button onClick={() => onTaskClick({ id: "task-1", title: "Review screening" })}>Open listed task</button> }))

const fullTask: TaskRead = {
    id: "task-1", title: "Review screening", description: "Existing screening instructions", task_type: "review",
    surrogate_id: "surrogate-1", surrogate_number: "S10001", intended_parent_id: null, donor_id: null, donor_number: null, donor_type: null, donor_name: null,
    owner_type: "user", owner_id: "another-owner", owner_name: "Owner", created_by_user_id: "user-1", created_by_name: "Creator",
    due_date: "2026-09-10", due_time: null, duration_minutes: null, is_completed: false, completed_at: null, completed_by_name: null, completed_by_user_id: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
}
const props = { taskId: fullTask.id, onClose: mocks.close, onSave: mocks.save, onDelete: mocks.remove, isDeleting: false }

describe("TaskDetailDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mocks.auth.mockReturnValue({ user: { user_id: "user-1", role: "case_manager" } })
        mocks.task.mockReturnValue({ data: fullTask, isLoading: false, isError: false })
        mocks.save.mockResolvedValue({})
    })

    it("loads full details and preserves the description when only the title changes", async () => {
        render(<TaskDetailDialog {...props} />)
        expect(mocks.task).toHaveBeenCalledWith(fullTask.id)
        expect(screen.getByLabelText("Description")).toHaveValue(fullTask.description)
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Updated title" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))
        await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(fullTask.id, expect.objectContaining({ title: "Updated title", description: fullTask.description })))
    })

    it("blocks editing during loading and failed fetches, then retries full details", () => {
        mocks.task.mockReturnValue({ data: undefined, isLoading: true })
        const { rerender } = render(<TaskDetailDialog {...props} />)
        expect(screen.getByRole("status")).toHaveTextContent("Loading task")
        expect(screen.queryByRole("button", { name: "Save Changes" })).not.toBeInTheDocument()
        const retry = vi.fn()
        mocks.task.mockReturnValue({ data: undefined, isError: true, refetch: retry })
        rerender(<TaskDetailDialog {...props} />)
        expect(screen.getByRole("alert")).toHaveTextContent("Failed to load task")
        expect(screen.queryByLabelText("Description")).not.toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Delete Task" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Retry task" }))
        expect(retry).toHaveBeenCalledOnce()
        mocks.task.mockReturnValue({ data: fullTask, isError: false })
        rerender(<TaskDetailDialog {...props} />)
        expect(screen.getByLabelText("Description")).toHaveValue(fullTask.description)
    })

    it("uses creator metadata from full details and shows read-only data for others", () => {
        mocks.auth.mockReturnValue({ user: { user_id: "not-owner-or-creator", role: "case_manager" } })
        render(<TaskDetailDialog {...props} />)
        expect(screen.getByText(fullTask.description)).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Save Changes" })).not.toBeInTheDocument()
    })

    it("fetches full details from surrogate list selections before editing", async () => {
        render(<SurrogateTasksPage />)
        expect(mocks.task).not.toHaveBeenCalled()
        fireEvent.click(screen.getByRole("button", { name: "Open listed task" }))
        expect(mocks.task).toHaveBeenCalledWith(fullTask.id)
        expect(screen.getByLabelText("Description")).toHaveValue(fullTask.description)
        fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Revised review" } })
        fireEvent.click(screen.getByRole("button", { name: "Save Changes" }))
        await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(fullTask.id, expect.objectContaining({ description: fullTask.description })))
    })
})
