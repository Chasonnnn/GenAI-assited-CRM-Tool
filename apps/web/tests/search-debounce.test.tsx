import type { ReactNode } from "react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import SearchPage from "@/app/(app)/search/page"
import { SearchCommandDialog } from "@/components/search-command"

const {
    mockUseQuery,
    mockUseDebouncedValue,
    mockGlobalSearch,
} = vi.hoisted(() => ({
    mockUseQuery: vi.fn(),
    mockUseDebouncedValue: vi.fn((value: string, _delay: number) => value),
    mockGlobalSearch: vi.fn(),
}))

vi.mock("@tanstack/react-query", () => ({
    useQuery: (options: unknown) => mockUseQuery(options),
}))

const navigationState = vi.hoisted(() => ({ search: "" }))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => "/search",
    useSearchParams: () => new URLSearchParams(navigationState.search),
}))

vi.mock("@/components/app-link", () => ({
    default: ({
        children,
        href,
        className,
    }: {
        children: ReactNode
        href: string
        className?: string
    }) => <a href={href} className={className}>{children}</a>,
}))

vi.mock("@/components/ui/command", () => ({
    CommandDialog: ({ children, open }: { children: ReactNode; open: boolean }) =>
        open ? <div>{children}</div> : null,
    Command: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    CommandInput: ({
        value,
        onValueChange,
        placeholder,
    }: {
        value: string
        onValueChange: (value: string) => void
        placeholder: string
    }) => (
        <input
            aria-label="Search command input"
            placeholder={placeholder}
            value={value}
            onChange={(event) => onValueChange(event.target.value)}
        />
    ),
    CommandList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    CommandGroup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    CommandItem: ({
        children,
        onSelect,
    }: {
        children: ReactNode
        onSelect: () => void
    }) => <button onClick={onSelect}>{children}</button>,
    CommandEmpty: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/lib/hooks/use-debounced-value", () => ({
    useDebouncedValue: (value: string, delay: number) => mockUseDebouncedValue(value, delay),
}))

vi.mock("@/lib/api/search", () => ({
    globalSearch: (...args: unknown[]) => mockGlobalSearch(...args),
    createEmptySearchResponse: (query = "") => ({
        query,
        total: 0,
        results: [],
    }),
}))

describe("Search debounce and query options", () => {
    beforeEach(() => {
        navigationState.search = ""
        mockGlobalSearch.mockReset()
        mockUseDebouncedValue.mockClear()
        mockUseQuery.mockReset()
        mockUseQuery.mockReturnValue({
            data: null,
            isLoading: false,
            isError: false,
        })
    })

    it("uses 400ms debounce and keep-previous-data options in SearchCommandDialog", () => {
        render(<SearchCommandDialog open onOpenChange={vi.fn()} />)

        fireEvent.change(
            screen.getByPlaceholderText("Search surrogates, intended parents, donors, notes, files"),
            { target: { value: "Sur" } }
        )

        expect(mockUseDebouncedValue).toHaveBeenCalledWith("Sur", 400)

        const queryOptions = mockUseQuery.mock.calls.at(-1)?.[0] as Record<string, unknown>
        expect(queryOptions.queryKey).toEqual(["search-command", "Sur"])
        expect(typeof queryOptions.placeholderData).toBe("function")

        const placeholderData = queryOptions.placeholderData as (previous: unknown) => unknown
        const previous = { query: "Su", total: 1, results: [{ id: "x" }] }
        expect(placeholderData(previous)).toBe(previous)
    })

    it("uses 400ms debounce and keep-previous-data options on Search page", () => {
        render(<SearchPage />)

        fireEvent.change(
            screen.getByPlaceholderText("Search surrogates, intended parents, donors, notes, files"),
            { target: { value: "Parent" } }
        )

        expect(mockUseDebouncedValue).toHaveBeenCalledWith("Parent", 400)

        const queryOptions = mockUseQuery.mock.calls.at(-1)?.[0] as Record<string, unknown>
        expect(queryOptions.queryKey).toEqual(["search", "Parent"])
        expect(typeof queryOptions.placeholderData).toBe("function")

        const placeholderData = queryOptions.placeholderData as (previous: unknown) => unknown
        const previous = { query: "Par", total: 2, results: [{ id: "x" }, { id: "y" }] }
        expect(placeholderData(previous)).toBe(previous)
    })

    it("renders donor results with the existing donor detail route", () => {
        mockUseQuery.mockReturnValue({
            data: {
                query: "Avery",
                total: 1,
                results: [
                    {
                        entity_type: "donor",
                        entity_id: "donor-1",
                        title: "Avery Searchable",
                        snippet: "Egg donor · D12001",
                        rank: 0.5,
                        surrogate_id: null,
                        surrogate_name: null,
                        donor_id: null,
                    },
                ],
            },
            isLoading: false,
            isError: false,
        })

        render(<SearchPage />)

        expect(screen.getByRole("link", { name: /Avery Searchable/ })).toHaveAttribute(
            "href",
            "/donors/donor-1"
        )
        expect(screen.getByText("Donor")).toBeInTheDocument()
        expect(screen.getByText("Egg donor · D12001")).toBeInTheDocument()
    })

    it("routes donor note and file results back to the donor detail", () => {
        mockUseQuery.mockReturnValue({
            data: {
                query: "screening",
                total: 2,
                results: [
                    {
                        entity_type: "note",
                        entity_id: "note-1",
                        title: "Note on Avery Searchable",
                        snippet: "Screening complete",
                        rank: 0.5,
                        surrogate_id: null,
                        surrogate_name: null,
                        donor_id: "donor-1",
                    },
                    {
                        entity_type: "attachment",
                        entity_id: "attachment-1",
                        title: "screening-report.pdf",
                        snippet: "",
                        rank: 0.5,
                        surrogate_id: null,
                        surrogate_name: null,
                        donor_id: "donor-1",
                    },
                ],
            },
            isLoading: false,
            isError: false,
        })

        render(<SearchPage />)

        expect(screen.getByRole("link", { name: /Note on Avery Searchable/ })).toHaveAttribute(
            "href",
            "/donors/donor-1",
        )
        expect(screen.getByRole("link", { name: /screening-report.pdf/ })).toHaveAttribute(
            "href",
            "/donors/donor-1",
        )
        // Each result is its own list row, so rows stack with separators instead of touching cards.
        expect(screen.getAllByRole("listitem")).toHaveLength(2)
        // accent equals card in dark mode, so keyboard focus needs a ring, not only a background.
        expect(screen.getByRole("link", { name: /Note on Avery Searchable/ })).toHaveClass(
            "focus-visible:ring-2",
            "focus-visible:ring-inset",
            "focus-visible:ring-ring",
        )
    })

    it("seeds the query from ?q= and writes typing back to the URL", () => {
        const replaceState = vi.spyOn(window.history, "replaceState").mockImplementation(() => undefined)
        navigationState.search = "q=S10133"
        render(<SearchPage />)

        expect(screen.getByRole("searchbox", { name: "Search" })).toHaveValue("S10133")
        expect(mockUseDebouncedValue).toHaveBeenCalledWith("S10133", 400)

        fireEvent.change(screen.getByRole("searchbox", { name: "Search" }), { target: { value: "Avery" } })
        expect(replaceState).toHaveBeenLastCalledWith(null, "", "/search?q=Avery")

        fireEvent.click(screen.getByRole("button", { name: "Clear" }))
        expect(replaceState).toHaveBeenLastCalledWith(null, "", "/search")
        replaceState.mockRestore()
    })

    it("shows the page header without the search tips card", () => {
        render(<SearchPage />)

        expect(screen.getByRole("heading", { level: 1, name: "Search" })).toBeInTheDocument()
        expect(screen.queryByText("Search Tips")).not.toBeInTheDocument()
    })
})
