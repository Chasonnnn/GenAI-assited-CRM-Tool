import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { readFileSync } from "node:fs"
import { AIFloatingButton } from "@/components/ai/AIFloatingButton"
import { ErrorState } from "@/components/error-state"
import { DashboardFilterBar } from "../app/(app)/dashboard/components/dashboard-filter-bar"

const mockUseAIContext = vi.fn()
const mockUsePathname = vi.fn()
const mockUseAuth = vi.fn()
const mockUseAssignees = vi.fn()
const mockUseDashboardFilters = vi.fn()
const FIXED_LAST_UPDATED = Date.parse("2026-01-01T00:00:00.000Z")
const readSource = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8")

vi.mock("@/lib/context/ai-context", () => ({
    useAIContext: () => mockUseAIContext(),
}))

vi.mock("next/navigation", () => ({
    usePathname: () => mockUsePathname(),
}))

vi.mock("@/lib/auth-context", () => ({
    useAuth: () => mockUseAuth(),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useAssignees: () => mockUseAssignees(),
}))

vi.mock("../app/(app)/dashboard/context/dashboard-filters", () => ({
    useDashboardFilters: () => mockUseDashboardFilters(),
}))

vi.mock("@/components/ui/date-range-picker", () => ({
    DateRangePicker: ({ ariaLabel }: { ariaLabel?: string }) => (
        <div data-testid="date-range-picker">{ariaLabel}</div>
    ),
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectTrigger: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
    SelectValue: ({ children }: { children?: React.ReactNode | ((value: string | null) => React.ReactNode) }) => (
        <span>{typeof children === "function" ? children(null) : children}</span>
    ),
    SelectContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    SelectItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

describe("accessibility hardening", () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockUsePathname.mockReturnValue("/dashboard")
        mockUseAIContext.mockReturnValue({
            canUseAI: true,
            isOpen: false,
            togglePanel: vi.fn(),
            entityName: "Alexandria Example",
        })
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "u1",
                role: "admin",
            },
        })
        mockUseAssignees.mockReturnValue({ data: [] })
        mockUseDashboardFilters.mockReturnValue({
            filters: {
                dateRange: "all",
                customRange: { from: undefined, to: undefined },
                assigneeId: undefined,
            },
            setDateRange: vi.fn(),
            setCustomRange: vi.fn(),
            setAssigneeId: vi.fn(),
            resetFilters: vi.fn(),
        })
    })

    it("gives the floating AI button an accessible name", () => {
        render(<AIFloatingButton />)

        expect(
            screen.getByRole("button", { name: /open ai assistant for alexandria example/i })
        ).toBeInTheDocument()
    })

    it("labels the dashboard refresh control", () => {
        render(
            <DashboardFilterBar
                lastUpdated={FIXED_LAST_UPDATED}
                onRefresh={vi.fn()}
                isRefreshing={false}
            />
        )

        expect(
            screen.getByRole("button", { name: /refresh dashboard/i })
        ).toBeInTheDocument()
    })

    it("does not rewrite dashboard filters when a non-admin filter bar mounts", () => {
        const setAssigneeId = vi.fn()
        mockUseAuth.mockReturnValue({
            user: {
                user_id: "case-manager-1",
                role: "case_manager",
            },
        })
        mockUseDashboardFilters.mockReturnValue({
            filters: {
                dateRange: "all",
                customRange: { from: undefined, to: undefined },
                assigneeId: undefined,
            },
            setDateRange: vi.fn(),
            setCustomRange: vi.fn(),
            setAssigneeId,
            resetFilters: vi.fn(),
        })

        render(<DashboardFilterBar />)

        expect(setAssigneeId).not.toHaveBeenCalled()
    })

    it("exposes error detail expansion state and hides the decorative chevron", () => {
        render(<ErrorState error={new Error("Boom")} reset={vi.fn()} showDetails />)

        const toggle = screen.getByRole("button", { name: /error details/i })
        expect(toggle).toHaveAttribute("aria-expanded", "false")
        expect(toggle.querySelector("svg")).toHaveAttribute("aria-hidden", "true")

        fireEvent.click(toggle)

        expect(toggle).toHaveAttribute("aria-expanded", "true")
        expect(toggle.querySelector("svg")).toHaveAttribute("aria-hidden", "true")
    })

    it("keeps shared calendar chevrons decorative", () => {
        const source = readSource("../components/ui/calendar.tsx")

        expect(source).toContain('<ChevronLeftIcon className={cn("size-4", className)} aria-hidden="true" {...props} />')
        expect(source).toContain('<ChevronRightIcon className={cn("size-4", className)} aria-hidden="true" {...props} />')
        expect(source).toContain('<ChevronDownIcon className={cn("size-4", className)} aria-hidden="true" {...props} />')
    })

    it("keeps dropdown trigger icons decorative without layout-only wrappers", () => {
        const surrogatesSource = readSource("../app/(app)/surrogates/page.client.tsx")
        const campaignsSource = readSource("../app/(app)/automation/campaigns/page.tsx")
        const intendedParentSource = readSource("../app/(app)/intended-parents/[id]/components/IntendedParentDetailSections.tsx")
        const surrogateHeaderSource = readSource("../components/surrogates/detail/SurrogateDetailLayout/HeaderActions.tsx")

        expect(surrogatesSource).toContain('<UserPlusIcon className="size-4" aria-hidden="true" />')
        expect(surrogatesSource).toContain('<MoreVerticalIcon className="size-4" aria-hidden="true" />')
        expect(surrogatesSource).not.toContain('<span className="inline-flex items-center gap-1">')
        expect(campaignsSource).toContain('<MoreVerticalIcon className="size-4" aria-hidden="true" />')
        expect(campaignsSource).not.toContain('<span className="inline-flex items-center justify-center">')
        expect(intendedParentSource).toContain('<MoreVerticalIcon className="size-4" aria-hidden="true" />')
        expect(surrogateHeaderSource).toContain('<MoreVerticalIcon className="size-4" aria-hidden="true" />')
    })
})
