import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import type { ReactNode } from "react"

import MatchesPage from "../app/(app)/matches/page"

const mockUseMatches = vi.fn()
const mockUseMatchStats = vi.fn()

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("@tanstack/react-query", () => ({
    useQueryClient: () => ({
        invalidateQueries: vi.fn(),
    }),
}))

vi.mock("@/lib/hooks/use-matches", () => ({
    useMatches: (params: unknown) => mockUseMatches(params),
    useMatchStats: () => mockUseMatchStats(),
    useCreateMatch: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("@/lib/hooks/use-surrogates", () => ({
    useSurrogates: () => ({ data: { items: [] }, isLoading: false }),
}))

vi.mock("@/lib/hooks/use-intended-parents", () => ({
    useIntendedParents: () => ({ data: { items: [] }, isLoading: false }),
}))

describe("MatchesPage", () => {
    beforeEach(() => {
        mockUseMatches.mockClear()
        mockUseMatchStats.mockReset()

        mockUseMatches.mockReturnValue({
            data: {
                items: [],
                total: 0,
                page: 1,
                per_page: 50,
            },
            isLoading: false,
            isError: false,
        })

        mockUseMatchStats.mockReturnValue({
            data: {
                total: 16,
                by_status: {
                    proposed: 7,
                    reviewing: 4,
                    accepted: 3,
                    cancel_pending: 0,
                    rejected: 2,
                    cancelled: 0,
                },
            },
            isLoading: false,
        })
    })

    it("renders stats from the match stats endpoint", () => {
        render(<MatchesPage />)

        expect(mockUseMatchStats).toHaveBeenCalledTimes(1)
        expect(mockUseMatches).not.toHaveBeenCalledWith({ status: "proposed" })
        expect(mockUseMatches).not.toHaveBeenCalledWith({ status: "reviewing" })
        expect(mockUseMatches).not.toHaveBeenCalledWith({ status: "accepted" })
        expect(mockUseMatches).not.toHaveBeenCalledWith({ status: "rejected" })

        expect(screen.getByText("7")).toBeInTheDocument()
        expect(screen.getByText("4")).toBeInTheDocument()
        expect(screen.getByText("3")).toBeInTheDocument()
        expect(screen.getByText("2")).toBeInTheDocument()
    })
})
