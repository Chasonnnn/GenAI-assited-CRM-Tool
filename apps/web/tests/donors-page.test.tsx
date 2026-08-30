import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import DonorsPage from "../app/(app)/donors/page"
import { ApiError } from "@/lib/api"

const mockSearchParams = new URLSearchParams()
const mockRouterReplace = vi.fn()
const mockUseDonors = vi.fn()
const mockCreateDonor = vi.fn()
const mockUseEffectivePermissions = vi.fn()

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => ({ user: { user_id: "user-1", role: "admin" } }),
}))

vi.mock("@/lib/hooks/use-permissions", () => ({
    useEffectivePermissions: () => mockUseEffectivePermissions(),
}))

vi.mock("next/navigation", () => ({
    useSearchParams: () => ({
        get: (key: string) => mockSearchParams.get(key),
        toString: () => mockSearchParams.toString(),
    }),
    useRouter: () => ({
        push: vi.fn(),
        replace: mockRouterReplace,
    }),
}))

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: React.ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("@/components/ui/date-range-picker", () => ({
    DateRangePicker: ({ preset }: { preset: string }) => (
        <button type="button" aria-label="Created date range">{preset}</button>
    ),
}))

vi.mock("@/lib/hooks/use-donors", () => ({
    useDonors: (filters: unknown) => mockUseDonors(filters),
    useCreateDonor: () => ({ mutateAsync: mockCreateDonor, isPending: false }),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    useDefaultPipeline: (entityType: string) => ({
        data: {
            id: `pipeline-${entityType}`,
            entity_type: entityType,
            stages: [
                {
                    id: `${entityType}-new`,
                    stage_key: "new",
                    slug: "new",
                    label: "New",
                    color: "#3B82F6",
                    order: 1,
                    stage_type: "intake",
                    is_active: true,
                },
                {
                    id: `${entityType}-ready`,
                    stage_key: "ready_to_match",
                    slug: "ready-to-match",
                    label: "Ready to Match",
                    color: "#F59E0B",
                    order: 2,
                    stage_type: "post_approval",
                    is_active: true,
                },
            ],
        },
    }),
}))

describe("DonorsPage", () => {
    beforeEach(() => {
        mockSearchParams.delete("type")
        mockSearchParams.delete("stage")
        mockSearchParams.delete("q")
        mockSearchParams.delete("page")
        mockSearchParams.delete("archive")
        mockSearchParams.delete("new")
        mockSearchParams.delete("dynamic_filter")
        mockSearchParams.delete("owner_id")
        mockSearchParams.delete("range")
        mockSearchParams.delete("from")
        mockSearchParams.delete("to")
        mockSearchParams.delete("sort_by")
        mockSearchParams.delete("sort_order")
        mockRouterReplace.mockReset()
        mockUseDonors.mockReset()
        mockCreateDonor.mockReset()
        mockCreateDonor.mockResolvedValue({ id: "donor-created" })
        mockUseEffectivePermissions.mockReset()
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_donors", "edit_donors"] },
        })
        mockUseDonors.mockReturnValue({
            data: {
                items: [
                    {
                        id: "donor-1",
                        donor_number: "D10001",
                        donor_type: "egg",
                        full_name: "Maya Thompson",
                        email: "maya@example.com",
                        phone: "(415) 555-0142",
                        state: "CA",
                        education: "B.S. Biology",
                        source: "manual",
                        owner_type: null,
                        owner_id: null,
                        stage_id: "egg_donor-ready",
                        stage_key: "ready_to_match",
                        stage_slug: "ready-to-match",
                        status: "ready_to_match",
                        status_label: "Ready to Match",
                        profile_photo_attachment_id: null,
                        is_archived: false,
                        archived_at: null,
                        created_at: "2026-08-27T12:00:00Z",
                        updated_at: "2026-08-27T12:00:00Z",
                    },
                ],
                total: 1,
                page: 1,
                per_page: 20,
                pages: 1,
            },
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        })
    })

    it("renders the Egg Donors list with the platform donor number format", () => {
        render(<DonorsPage />)

        expect(screen.getByRole("heading", { name: "Donors" })).toBeInTheDocument()
        expect(screen.getByRole("tab", { name: "Egg Donors" })).toHaveAttribute(
            "aria-selected",
            "true",
        )
        expect(screen.getByRole("tab", { name: "Sperm Donors" })).toBeInTheDocument()
        expect(screen.getByRole("columnheader", { name: /Donor #/ })).toBeInTheDocument()
        expect(screen.getByRole("columnheader", { name: /Education/ })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "D10001" })).toHaveAttribute(
            "href",
            "/donors/donor-1?return_to=%2Fdonors",
        )
        expect(screen.getByText("Maya Thompson")).toBeInTheDocument()
        expect(screen.getByText("B.S. Biology")).toBeInTheDocument()
        expect(screen.getByText("Ready to Match")).toBeInTheDocument()
        expect(mockUseDonors).toHaveBeenCalledWith(
            expect.objectContaining({ donor_type: "egg", page: 1, per_page: 20 }),
        )
    })

    it("creates a donor in the active donor type", async () => {
        render(<DonorsPage />)

        fireEvent.click(screen.getByRole("button", { name: "New Donor" }))
        expect(screen.getByRole("heading", { name: "New Egg Donor" })).toBeInTheDocument()
        expect(screen.queryByRole("combobox", { name: "Donor type" })).not.toBeInTheDocument()
        fireEvent.change(screen.getByLabelText("Full name"), {
            target: { value: "Maya Thompson" },
        })
        fireEvent.change(screen.getByLabelText("Email"), {
            target: { value: "maya@example.com" },
        })
        fireEvent.click(screen.getByRole("combobox", { name: "State" }))
        const california = await screen.findByRole("option", { name: "California (CA)" })
        fireEvent.mouseMove(california)
        fireEvent.click(california)

        fireEvent.click(screen.getByRole("button", { name: "Create" }))

        await vi.waitFor(() => {
            expect(mockCreateDonor).toHaveBeenCalledWith(
                expect.objectContaining({
                    donor_type: "egg",
                    full_name: "Maya Thompson",
                    email: "maya@example.com",
                    state: "CA",
                }),
            )
        })
    })

    it("opens donor creation from a URL-backed dashboard action", () => {
        mockSearchParams.set("type", "sperm")
        mockSearchParams.set("new", "true")

        render(<DonorsPage />)

        expect(screen.getByRole("dialog")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "New Sperm Donor" })).toBeInTheDocument()
        expect(screen.queryByRole("combobox", { name: "Donor type" })).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith("/donors?type=sperm", {
            scroll: false,
        })
    })

    it("cannot change the subtype away from the active sperm-donor tab", async () => {
        mockSearchParams.set("type", "sperm")
        render(<DonorsPage />)

        fireEvent.click(screen.getByRole("button", { name: "New Donor" }))
        fireEvent.change(screen.getByLabelText("Full name"), {
            target: { value: "Ethan Brooks" },
        })
        fireEvent.change(screen.getByLabelText("Email"), {
            target: { value: "ethan@example.com" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Create" }))

        await vi.waitFor(() => expect(mockCreateDonor).toHaveBeenCalledWith(
            expect.objectContaining({ donor_type: "sperm" }),
        ))
    })

    it("loads the Sperm Donors pipeline and list from the URL-backed tab", () => {
        mockSearchParams.set("type", "sperm")
        mockSearchParams.set("q", "ethan")

        render(<DonorsPage />)

        expect(screen.getByRole("tab", { name: "Sperm Donors" })).toHaveAttribute(
            "aria-selected",
            "true",
        )
        expect(mockUseDonors).toHaveBeenCalledWith(
            expect.objectContaining({ donor_type: "sperm", q: "ethan" }),
        )
        expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Sperm Donors")
    })

    it("loads archived donors from a URL-backed record-status filter", () => {
        mockSearchParams.set("archive", "archived")

        render(<DonorsPage />)

        expect(screen.getByRole("combobox", { name: "Record status" })).toHaveTextContent(
            "Archived Donors",
        )
        expect(mockUseDonors).toHaveBeenCalledWith(
            expect.objectContaining({ include_archived: true, archived_only: true }),
        )
    })

    it("loads the dashboard stuck-donor filter and owner from the URL", () => {
        mockSearchParams.set("type", "sperm")
        mockSearchParams.set("dynamic_filter", "attention_stuck")
        mockSearchParams.set("owner_id", "owner-1")

        render(<DonorsPage />)

        expect(mockUseDonors).toHaveBeenCalledWith(
            expect.objectContaining({
                donor_type: "sperm",
                dynamic_filter: "attention_stuck",
                owner_id: "owner-1",
            }),
        )
        expect(screen.getByRole("button", { name: "Remove filter: Attention Needed: Stuck Donors" }))
            .toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Remove filter: Assignee: Assigned user" }))
            .toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Reset filters" })).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Remove filter: Assignee: Assigned user" }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            "/donors?type=sperm&dynamic_filter=attention_stuck",
            { scroll: false },
        )
    })

    it("forwards dashboard date ranges and preserves them in donor detail return context", () => {
        mockSearchParams.set("type", "sperm")
        mockSearchParams.set("stage", "sperm-ready")
        mockSearchParams.set("range", "custom")
        mockSearchParams.set("from", "2026-08-01")
        mockSearchParams.set("to", "2026-08-29")

        render(<DonorsPage />)

        expect(mockUseDonors).toHaveBeenCalledWith(expect.objectContaining({
            donor_type: "sperm",
            stage_id: "sperm-ready",
            created_from: "2026-08-01",
            created_to: "2026-08-29",
        }))
        expect(screen.getByRole("button", { name: "Created date range" })).toHaveTextContent("custom")
        expect(screen.getByRole("button", { name: /Remove filter: Date:/ })).toBeInTheDocument()
        expect(screen.getByRole("link", { name: "D10001" })).toHaveAttribute(
            "href",
            "/donors/donor-1?return_to=%2Fdonors%3Ftype%3Dsperm%26stage%3Dsperm-ready%26range%3Dcustom%26from%3D2026-08-01%26to%3D2026-08-29",
        )

        fireEvent.click(screen.getByRole("button", { name: /Remove filter: Date:/ }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            "/donors?type=sperm&stage=sperm-ready",
            { scroll: false },
        )
    })

    it("uses explicit dashboard week boundaries instead of recalculating a rolling window", () => {
        mockSearchParams.set("range", "week")
        mockSearchParams.set("from", "2026-08-23")
        mockSearchParams.set("to", "2026-08-29")

        render(<DonorsPage />)

        expect(mockUseDonors).toHaveBeenCalledWith(expect.objectContaining({
            created_from: "2026-08-23",
            created_to: "2026-08-29",
        }))
    })

    it("uses allowlisted URL-backed sorting and toggles an active header", () => {
        mockSearchParams.set("sort_by", "full_name")
        mockSearchParams.set("sort_order", "asc")

        render(<DonorsPage />)

        expect(mockUseDonors).toHaveBeenCalledWith(expect.objectContaining({
            sort_by: "full_name",
            sort_order: "asc",
        }))
        fireEvent.click(screen.getByRole("columnheader", { name: /Name/ }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            "/donors?sort_by=full_name&sort_order=desc",
            { scroll: false },
        )

        fireEvent.click(screen.getByRole("columnheader", { name: /Education/ }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            "/donors?sort_by=education&sort_order=desc",
            { scroll: false },
        )
    })

    it.each([
        ["Donor #", "donor_number"],
        ["Name", "full_name"],
        ["State", "state"],
        ["Education", "education"],
        ["Stage", "stage"],
        ["Created", "created_at"],
    ])("sorts from the %s header", (label, sortField) => {
        render(<DonorsPage />)

        fireEvent.click(screen.getByRole("columnheader", { name: new RegExp(label) }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith(
            `/donors?sort_by=${sortField}&sort_order=desc`,
            { scroll: false },
        )
    })

    it("ignores unsupported sort fields instead of forwarding them", () => {
        mockSearchParams.set("sort_by", "email")
        mockSearchParams.set("sort_order", "asc")

        render(<DonorsPage />)

        expect(mockUseDonors).toHaveBeenCalledWith(expect.not.objectContaining({ sort_by: "email" }))
    })

    it("clears a pipeline-specific stage when switching donor type", () => {
        mockSearchParams.set("stage", "egg-ready")
        mockSearchParams.set("q", "maya")
        mockSearchParams.set("page", "3")

        render(<DonorsPage />)
        fireEvent.click(screen.getByRole("tab", { name: "Sperm Donors" }))

        const [href, options] = mockRouterReplace.mock.calls.at(-1) ?? []
        expect(href).toContain("type=sperm")
        expect(href).toContain("q=maya")
        expect(href).not.toContain("stage=")
        expect(href).not.toContain("page=")
        expect(options).toEqual({ scroll: false })
    })

    it("distinguishes first-use and filtered empty states", () => {
        mockUseDonors.mockReturnValue({
            data: { items: [], total: 0, page: 1, per_page: 20, pages: 0 },
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        })

        const { unmount } = render(<DonorsPage />)
        expect(screen.getByRole("heading", { name: "No egg donors yet" })).toBeInTheDocument()
        unmount()

        mockSearchParams.set("q", "missing")
        render(<DonorsPage />)
        expect(
            screen.getByRole("heading", { name: "No donors match these filters" }),
        ).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Clear filters" }))
        expect(mockRouterReplace).toHaveBeenLastCalledWith("/donors", { scroll: false })
    })

    it("shows the donor permission state for a forbidden list", () => {
        const refetch = vi.fn()
        mockUseDonors.mockReturnValue({
            data: undefined,
            isLoading: false,
            isError: true,
            error: new ApiError(403, "Forbidden", "Forbidden"),
            refetch,
        })

        render(<DonorsPage />)
        expect(screen.getByText("Permission required")).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Try again" }))
        expect(refetch).toHaveBeenCalledTimes(1)
    })

    it("hides donor creation without edit permission", () => {
        mockUseEffectivePermissions.mockReturnValue({
            data: { permissions: ["view_donors"] },
        })

        render(<DonorsPage />)
        expect(screen.queryByRole("button", { name: "New Donor" })).not.toBeInTheDocument()
    })
})
