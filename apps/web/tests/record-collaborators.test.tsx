import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { beforeEach, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { RecordCollaborators } from "@/components/permissions/record-collaborators"

const state = vi.hoisted(() => ({role: "case_manager", policy: 2, list: vi.fn(), options: vi.fn(), remove: vi.fn(), add: vi.fn()}))
vi.mock("@/lib/auth-context", () => ({useAuth: () => ({user: {user_id: "manager"}})}))
vi.mock("@/lib/hooks/use-permissions", () => ({useEffectivePermissions: () => ({data: {role: state.role, policy_version: state.policy}})}))
vi.mock("@/lib/api/record-scopes", () => ({getCollaborators: state.list, getCollaboratorOptions: state.options, removeCollaborator: state.remove, addCollaborator: state.add}))
const show = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}, mutations: {retry: false}}})}><RecordCollaborators kind="donor" recordId="donor" /></QueryClientProvider>)
beforeEach(() => {
    vi.clearAllMocks(); state.role = "case_manager"; state.policy = 2
    state.list.mockResolvedValue([{id: "collab", user_id: "intake", display_name: "Alex Intake"}])
    state.options.mockResolvedValue([]); state.remove.mockResolvedValue(undefined)
})
it("lets case managers remove retained access by name", async () => {
    show()
    fireEvent.click(await screen.findByRole("button", {name: "Remove Alex Intake"}))
    await waitFor(() => expect(state.remove).toHaveBeenCalledWith("donor", "donor", "intake"))
})
it("shows Intake collaborators without management controls", async () => {
    state.role = "intake_specialist"; show()
    expect(await screen.findByText("Alex Intake")).toBeInTheDocument()
    expect(screen.queryByRole("button", {name: "Remove Alex Intake"})).not.toBeInTheDocument()
    expect(state.options).not.toHaveBeenCalled()
})
it("offers retry on failed loads", async () => {
    state.list.mockRejectedValue(new Error("Failed")); show()
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load collaborators")
    state.list.mockResolvedValue([])
    fireEvent.click(screen.getByRole("button", {name: "Retry"}))
    expect(await screen.findByText("No Intake collaborators")).toBeInTheDocument()
})
it("does not request collaborators before policy activation", () => {
    state.policy = 1; show()
    expect(state.list).not.toHaveBeenCalled()
    expect(screen.queryByText("Intake collaborators")).not.toBeInTheDocument()
})
