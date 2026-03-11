import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { AIFloatingButton } from "@/components/ai/AIFloatingButton"
import { DashboardFilterBar } from "../app/(app)/dashboard/components/dashboard-filter-bar"

const mockUseAIContext = vi.fn()
const mockUsePathname = vi.fn()
const mockUseAuth = vi.fn()
const mockUseAssignees = vi.fn()
const mockUseDashboardFilters = vi.fn()

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
                lastUpdated={Date.now()}
                onRefresh={vi.fn()}
                isRefreshing={false}
            />
        )

        expect(
            screen.getByRole("button", { name: /refresh dashboard/i })
        ).toBeInTheDocument()
    })
})
