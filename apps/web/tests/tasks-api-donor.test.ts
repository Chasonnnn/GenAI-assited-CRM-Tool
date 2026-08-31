import { beforeEach, describe, expect, it, vi } from "vitest"

import { createTask, getTasks, updateTask } from "@/lib/api/tasks"

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()

vi.mock("@/lib/api", () => ({
    __esModule: true,
    default: {
        get: (...args: unknown[]) => mockGet(...args),
        post: (...args: unknown[]) => mockPost(...args),
        patch: (...args: unknown[]) => mockPatch(...args),
    },
}))

describe("donor task API contract", () => {
    beforeEach(() => {
        mockGet.mockReset().mockResolvedValue({ items: [], total: 0 })
        mockPost.mockReset().mockResolvedValue({})
        mockPatch.mockReset().mockResolvedValue({})
    })

    it("filters a donor detail task list by donor id", async () => {
        await getTasks({ donor_id: "donor-1", exclude_approvals: true })
        expect(mockGet).toHaveBeenCalledWith(
            "/tasks?donor_id=donor-1&exclude_approvals=true",
        )
    })

    it("creates, changes, and clears an exclusive linked record", async () => {
        await createTask({ title: "Review donor", donor_id: "donor-1" })
        await updateTask("task-1", {
            donor_id: null,
            surrogate_id: null,
            intended_parent_id: null,
        })

        expect(mockPost).toHaveBeenCalledWith("/tasks", {
            title: "Review donor",
            donor_id: "donor-1",
        })
        expect(mockPatch).toHaveBeenCalledWith("/tasks/task-1", {
            donor_id: null,
            surrogate_id: null,
            intended_parent_id: null,
        })
    })
})
