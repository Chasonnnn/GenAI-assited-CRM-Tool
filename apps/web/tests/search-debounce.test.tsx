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
    mockUseDebouncedValue: vi.fn((value: string) => value),
    mockGlobalSearch: vi.fn(),
}))

vi.mock("@tanstack/react-query", () => ({
    useQuery: (options: unknown) => mockUseQuery(options),
}))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
}))

vi.mock("@/components/app-link", () => ({
    default: ({
        children,
        href,
    }: {
        children: ReactNode
        href: string
    }) => <a href={href}>{children}</a>,
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
            screen.getByPlaceholderText("Search surrogates, intended parents, notes, files..."),
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
            screen.getByPlaceholderText("Search surrogates, intended parents, notes, files..."),
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
})
