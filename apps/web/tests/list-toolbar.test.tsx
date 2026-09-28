import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import {
    FilterChips,
    ListToolbar,
    ListToolbarSearch,
    MoreFiltersPopover,
} from "@/components/list-toolbar"

describe("ListToolbar", () => {
    it("lays out filters, then search pushed right from xl, in a bordered bar", () => {
        const { container } = render(
            <ListToolbar
                filters={<button type="button">Stage</button>}
                search={
                    <ListToolbarSearch
                        value=""
                        onValueChange={() => undefined}
                        placeholder="Search matches"
                        aria-label="Search matches"
                    />
                }
            />
        )

        const bar = container.querySelector('[data-slot="list-toolbar"]')
        expect(bar).toHaveClass("border-b", "px-6", "py-3")

        const search = screen.getByRole("textbox", { name: "Search matches" })
        expect(search).toHaveAttribute("placeholder", "Search matches")
        expect(search.parentElement).toHaveClass("w-full", "xl:ml-auto", "xl:w-[320px]")

        const stage = screen.getByRole("button", { name: "Stage" })
        expect(stage.parentElement).toHaveClass("flex-wrap", "gap-3")
        expect(stage.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it("hides the chip row when no filter is active", () => {
        const { container } = render(<ListToolbar filters={<span>filters</span>} chips={[]} onReset={vi.fn()} />)

        expect(container.querySelector('[data-slot="filter-chips"]')).toBeNull()
        expect(screen.queryByRole("button", { name: "Reset" })).not.toBeInTheDocument()
    })

    it("skips inactive chip entries so pages can pass a conditional list", () => {
        const stage: string = "all"
        const kind: string = "donor"
        const { container } = render(
            <ListToolbar
                chips={[
                    stage !== "all" && { key: "stage", label: `Stage: ${stage}`, onRemove: vi.fn() },
                    kind !== "all" && { key: "kind", label: "Kind: Donor", onRemove: vi.fn() },
                    null,
                ]}
                onReset={vi.fn()}
            />
        )

        const row = container.querySelector('[data-slot="filter-chips"]')
        expect(row?.querySelectorAll("button")).toHaveLength(2)
        expect(screen.getByRole("button", { name: "Remove filter: Kind: Donor" })).toBeInTheDocument()

        render(<ListToolbar chips={[stage !== "all" && { key: "stage", label: "Stage", onRemove: vi.fn() }]} />)
        expect(container.ownerDocument.querySelectorAll('[data-slot="filter-chips"]')).toHaveLength(1)
    })

    it("removes one filter per chip and resets all", () => {
        const removeStage = vi.fn()
        const removeKind = vi.fn()
        const reset = vi.fn()

        render(
            <ListToolbar
                chips={[
                    { key: "stage", label: "Stage: Accepted", onRemove: removeStage },
                    { key: "kind", label: "Kind: Donor", onRemove: removeKind },
                ]}
                onReset={reset}
            />
        )

        fireEvent.click(screen.getByRole("button", { name: "Remove filter: Kind: Donor" }))
        expect(removeKind).toHaveBeenCalledTimes(1)
        expect(removeStage).not.toHaveBeenCalled()

        expect(screen.getByRole("button", { name: "Remove filter: Stage: Accepted" })).toHaveTextContent(
            "Stage: Accepted"
        )

        fireEvent.click(screen.getByRole("button", { name: "Reset" }))
        expect(reset).toHaveBeenCalledTimes(1)
    })
})

describe("ListToolbarSearch", () => {
    it("reports each typed value", () => {
        const onValueChange = vi.fn()
        render(
            <ListToolbarSearch
                value=""
                onValueChange={onValueChange}
                placeholder="Search surrogates"
                aria-label="Search surrogates"
            />
        )

        fireEvent.change(screen.getByRole("textbox", { name: "Search surrogates" }), {
            target: { value: "ava" },
        })

        expect(onValueChange).toHaveBeenCalledWith("ava")
    })

    it("can expose the searchbox role", () => {
        render(
            <ListToolbarSearch
                type="search"
                value="egg"
                onValueChange={() => undefined}
                placeholder="Search donors"
                aria-label="Search donors"
            />
        )

        expect(screen.getByRole("searchbox", { name: "Search donors" })).toHaveValue("egg")
    })
})

describe("MoreFiltersPopover", () => {
    it("opens its secondary filters and marks the trigger when one is active", async () => {
        const onOpenChange = vi.fn()
        const { rerender } = render(
            <MoreFiltersPopover open={false} onOpenChange={onOpenChange}>
                <label htmlFor="kind">Kind</label>
                <select id="kind" />
            </MoreFiltersPopover>
        )

        const trigger = screen.getByRole("button", { name: "More Filters" })
        expect(trigger).not.toHaveAttribute("data-active")
        fireEvent.click(trigger)
        expect(onOpenChange).toHaveBeenCalledWith(true, expect.anything())

        rerender(
            <MoreFiltersPopover open onOpenChange={onOpenChange} active>
                <label htmlFor="kind">Kind</label>
                <select id="kind" />
            </MoreFiltersPopover>
        )

        expect(await screen.findByLabelText("Kind")).toBeVisible()
        expect(screen.getByRole("button", { name: "More Filters" })).toHaveAttribute("data-active")
    })

    it("uses the shared shadow tokens instead of hard-coded shadow colors", async () => {
        render(
            <MoreFiltersPopover open onOpenChange={vi.fn()} active>
                <label htmlFor="kind">Kind</label>
                <select id="kind" />
            </MoreFiltersPopover>
        )

        const trigger = screen.getByRole("button", { name: "More Filters" })
        const content = (await screen.findByLabelText("Kind")).closest('[data-slot="popover-content"]')
        expect(content).not.toBeNull()
        expect(trigger).toHaveClass("shadow-sm")
        expect(content).toHaveClass("shadow-2xl", "ring-1", "ring-foreground/5")
        for (const element of [trigger, content as HTMLElement]) {
            expect(element.className).not.toMatch(/rgba?\(/)
            expect(element.className).not.toMatch(/shadow-\[/)
        }
    })
})

describe("FilterChips", () => {
    it("renders chips without Reset when no reset handler is given", () => {
        render(<FilterChips chips={[{ key: "q", label: "Search: ava", onRemove: vi.fn() }]} />)

        expect(screen.getByRole("button", { name: "Remove filter: Search: ava" })).toBeInTheDocument()
        expect(screen.queryByRole("button", { name: "Reset" })).not.toBeInTheDocument()
    })
})
