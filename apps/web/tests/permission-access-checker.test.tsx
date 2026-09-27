import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { PermissionAccessChecker } from "@/components/permissions/permission-access-checker"
import { getMembers } from "@/lib/api/permissions"
import { getSurrogates } from "@/lib/api/surrogates"
import { checkRecordAccess } from "@/lib/api/record-scopes"

vi.mock("@/lib/api/permissions", async (original) => ({ ...await original<typeof import("@/lib/api/permissions")>(), getMembers: vi.fn() }))
vi.mock("@/lib/api/surrogates", () => ({ getSurrogates: vi.fn() }))
vi.mock("@/lib/api/record-scopes", async (original) => ({ ...await original<typeof import("@/lib/api/record-scopes")>(), checkRecordAccess: vi.fn() }))
function choose(label: string, option: string) { fireEvent.click(screen.getByRole("combobox", { name: label })); const item = screen.getByRole("option", { name: option }); fireEvent.mouseMove(item); fireEvent.click(item) }

describe("record access checker", () => {
    beforeEach(() => {
        vi.mocked(getMembers).mockReset().mockResolvedValue([{ id: "member-1", user_id: "user-1", display_name: "Taylor Morgan", email: "taylor@example.test", role: "case_manager", created_at: "2026-09-07", last_login_at: null }])
        vi.mocked(getSurrogates).mockReset().mockResolvedValue({ items: [{ id: "record-1", surrogate_number: "S10001", full_name: "Sample Record" }], total: 1 } as Awaited<ReturnType<typeof getSurrogates>>)
        vi.mocked(checkRecordAccess).mockReset().mockResolvedValue({ allowed: true, sources: ["role"], reason: null })
    })
    it("checks the selected member and record, then clears the result when scope changes", async () => {
        render(<PermissionAccessChecker />)
        await screen.findByRole("combobox", { name: "Person" })
        choose("Person", "Taylor Morgan")
        fireEvent.change(screen.getByRole("textbox", { name: "Record name or number" }), { target: { value: "S10001" } })
        fireEvent.click(screen.getByRole("button", { name: "Search" }))
        await screen.findByRole("combobox", { name: "Record" })
        choose("Record", "S10001 · Sample Record")
        fireEvent.click(screen.getByRole("button", { name: "Check access" }))
        expect(await screen.findByText("Record visible")).toBeVisible()
        expect(screen.getByText("Role scope")).toBeVisible()
        expect(vi.mocked(checkRecordAccess).mock.calls[0]?.[0]).toEqual({ user_id: "user-1", record_id: "record-1", kind: "surrogate", personal_only: false })
        fireEvent.click(screen.getByRole("switch", { name: "Personal workflow scope" }))
        expect(screen.queryByText("Record visible")).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Check access" }))
        await waitFor(() => expect(vi.mocked(checkRecordAccess).mock.calls[1]?.[0]).toEqual({ user_id: "user-1", record_id: "record-1", kind: "surrogate", personal_only: true }))
    })
    it("shows empty search results with no record selected", async () => {
        vi.mocked(getSurrogates).mockResolvedValue({ items: [], total: 0 } as Awaited<ReturnType<typeof getSurrogates>>)
        render(<PermissionAccessChecker />)
        fireEvent.click(await screen.findByRole("button", { name: "Search" }))
        expect(await screen.findByText("No records found.")).toBeVisible()
        expect(screen.getByRole("button", { name: "Check access" })).toBeDisabled()
    })
    it("renders a denied search response without exposing an old result", async () => {
        vi.mocked(getSurrogates).mockRejectedValue(new Error("Record search denied"))
        render(<PermissionAccessChecker />)
        fireEvent.click(await screen.findByRole("button", { name: "Search" }))
        expect(await screen.findByRole("alert")).toHaveTextContent("Record search denied")
        expect(screen.getByRole("button", { name: "Check access" })).toBeDisabled()
    })
})
