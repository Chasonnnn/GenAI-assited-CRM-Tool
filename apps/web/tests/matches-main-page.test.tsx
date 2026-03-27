import { describe, it, expect, vi, beforeEach } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import type { ReactNode } from "react"

import MatchesPage from "../app/(app)/matches/page"

const mockUseMatches = vi.fn()
const mockUseMatchStats = vi.fn()
const mockUseSurrogates = vi.fn()
const mockUseDefaultPipeline = vi.fn()

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => (
        <a href={href}>{children}</a>
    ),
}))

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({
        children,
        open,
    }: {
        children: ReactNode
        open?: boolean
    }) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    SelectTrigger: ({ children }: { children: ReactNode }) => <button>{children}</button>,
    SelectValue: ({ placeholder }: { placeholder?: string }) => <span>{placeholder}</span>,
    SelectContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    SelectItem: ({
        children,
        value,
    }: {
        children: ReactNode
        value: string
    }) => <div data-value={value}>{children}</div>,
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
    useSurrogates: () => mockUseSurrogates(),
}))

vi.mock("@/lib/hooks/use-pipelines", () => ({
    useDefaultPipeline: (...args: unknown[]) => mockUseDefaultPipeline(...args),
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
        mockUseSurrogates.mockReturnValue({ data: { items: [] }, isLoading: false })
        mockUseDefaultPipeline.mockReturnValue({
            data: {
                id: "pipeline-1",
                entity_type: "surrogate",
                name: "Default Pipeline",
                is_default: true,
                current_version: 1,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                stages: [
                    {
                        id: "stage-ready",
                        stage_key: "ready_to_match",
                        slug: "matching_queue",
                        label: "Matching Queue",
                        color: "#0ea5e9",
                        order: 1,
                        stage_type: "post_approval",
                        is_active: true,
                        is_locked: true,
                        system_role: "handoff",
                        lock_reason: "This is a protected system stage used by platform workflows.",
                        locked_fields: [],
                        semantics: {
                            capabilities: {
                                counts_as_contacted: false,
                                eligible_for_matching: true,
                                locks_match_state: false,
                                shows_pregnancy_tracking: false,
                                requires_delivery_details: false,
                                tracks_interview_outcome: false,
                            },
                            pause_behavior: "none",
                            terminal_outcome: "none",
                            integration_bucket: "converted",
                            analytics_bucket: "matching_queue",
                            suggestion_profile_key: null,
                            requires_reason_on_enter: false,
                        },
                    },
                    {
                        id: "stage-matched",
                        stage_key: "matched",
                        slug: "match_confirmed",
                        label: "Matched",
                        color: "#10b981",
                        order: 2,
                        stage_type: "post_approval",
                        is_active: true,
                        is_locked: true,
                        system_role: "matched",
                        lock_reason: "This is a protected system stage used by platform workflows.",
                        locked_fields: [],
                        semantics: {
                            capabilities: {
                                counts_as_contacted: false,
                                eligible_for_matching: false,
                                locks_match_state: true,
                                shows_pregnancy_tracking: false,
                                requires_delivery_details: false,
                                tracks_interview_outcome: false,
                            },
                            pause_behavior: "none",
                            terminal_outcome: "none",
                            integration_bucket: "converted",
                            analytics_bucket: "matched",
                            suggestion_profile_key: null,
                            requires_reason_on_enter: false,
                        },
                    },
                ],
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

    it("uses pipeline semantics to show protected handoff-stage surrogates in the new match dialog", () => {
        mockUseSurrogates.mockReturnValue({
            data: {
                items: [
                    {
                        id: "sur_1",
                        surrogate_number: "S10001",
                        full_name: "Eligible Surrogate",
                        stage_key: null,
                        stage_slug: "matching_queue",
                        status_label: "Matching Queue",
                        state: "TX",
                    },
                    {
                        id: "sur_2",
                        surrogate_number: "S10002",
                        full_name: "Ineligible Surrogate",
                        stage_key: null,
                        stage_slug: "match_confirmed",
                        status_label: "Matched",
                        state: "CA",
                    },
                ],
            },
            isLoading: false,
        })

        render(<MatchesPage />)

        fireEvent.click(screen.getByRole("button", { name: /new match/i }))

        expect(screen.getByText(/surrogate \(matching queue only\)/i)).toBeInTheDocument()
        expect(screen.getByText(/eligible surrogate/i)).toBeInTheDocument()
        expect(screen.queryByText(/ineligible surrogate/i)).not.toBeInTheDocument()
    })
})
