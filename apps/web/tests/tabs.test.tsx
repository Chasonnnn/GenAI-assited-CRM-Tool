import { fireEvent, render, screen } from "@testing-library/react"
import { renderToString } from "react-dom/server"
import { afterEach, describe, expect, it, vi } from "vitest"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const TAB_WIDTH = 80
const TAB_HEIGHT = 30

function ExampleTabs({ variant, listClassName }: { variant?: "default" | "line"; listClassName?: string }) {
    return (
        <Tabs defaultValue="overview">
            <TabsList variant={variant} className={listClassName}>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>
            <TabsContent value="overview">Overview panel</TabsContent>
            <TabsContent value="history">History panel</TabsContent>
        </Tabs>
    )
}

function getIndicator() {
    const indicators = screen.getByRole("tablist").querySelectorAll('[data-slot="tabs-indicator"]')
    expect(indicators).toHaveLength(1)
    return indicators[0] as HTMLElement
}

// jsdom has no layout; give each tab a fixed box laid out left to right.
function stubTabLayout() {
    const tabIndex = (element: HTMLElement) =>
        Array.from(element.parentElement?.querySelectorAll('[role="tab"]') ?? []).indexOf(element)
    const width = (element: HTMLElement) =>
        element.getAttribute("role") === "tab" ? TAB_WIDTH : element.getAttribute("role") === "tablist" ? 2 * TAB_WIDTH : 0
    const height = (element: HTMLElement) =>
        element.getAttribute("role") === "tab" || element.getAttribute("role") === "tablist" ? TAB_HEIGHT : 0

    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(function (this: HTMLElement) {
        return width(this)
    })
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(function (this: HTMLElement) {
        return height(this)
    })
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
        const left = this.getAttribute("role") === "tab" ? tabIndex(this) * TAB_WIDTH : 0
        return DOMRect.fromRect({ x: left, y: 0, width: width(this), height: height(this) })
    })
}

describe("Tabs indicator", () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it("renders one sliding indicator and keeps the active surface off the triggers", () => {
        render(<ExampleTabs />)

        const list = screen.getByRole("tablist")
        expect(list).toHaveClass("relative", "isolate")
        expect(list.lastElementChild).toHaveAttribute("data-slot", "tabs-indicator")

        const indicator = getIndicator()
        expect(indicator).toHaveAttribute("role", "presentation")
        expect(indicator).toHaveClass(
            "-z-1",
            "translate-x-(--active-tab-left)",
            "translate-y-(--active-tab-top)",
            "w-(--active-tab-width)",
            "h-(--active-tab-height)",
            "transition-[translate,width,height]",
            "duration-200",
            "ease-smooth-out",
            "rounded-xl",
            "bg-background",
            "dark:border-input",
            "dark:bg-input/30",
        )

        for (const tab of screen.getAllByRole("tab")) {
            expect(tab.className).not.toMatch(/data-active:(bg|border)-|after:/)
            expect(tab).toHaveClass("data-active:text-foreground", "focus-visible:ring-[3px]")
        }
    })

    it("draws the line variant underline with the indicator", () => {
        render(<ExampleTabs variant="line" />)

        const indicator = getIndicator()
        expect(indicator).toHaveClass(
            "h-0.5",
            "w-(--active-tab-width)",
            "translate-y-[calc(var(--active-tab-top)+var(--active-tab-height)+1px)]",
            "bg-foreground",
        )
        expect(indicator).not.toHaveClass("bg-background", "rounded-xl")
    })

    it("follows the active tab", () => {
        stubTabLayout()
        render(<ExampleTabs />)

        const indicator = getIndicator()
        expect(indicator).not.toHaveAttribute("hidden")
        expect(indicator.style.getPropertyValue("--active-tab-left")).toBe("0px")
        expect(indicator.style.getPropertyValue("--active-tab-width")).toBe(`${TAB_WIDTH}px`)

        fireEvent.click(screen.getByRole("tab", { name: "History" }))

        expect(screen.getByRole("tab", { name: "History" })).toHaveAttribute("data-active")
        expect(getIndicator().style.getPropertyValue("--active-tab-left")).toBe(`${TAB_WIDTH}px`)
    })

    it("positions the indicator before hydration from server markup", () => {
        const html = renderToString(<ExampleTabs />)

        const indicatorIndex = html.indexOf('data-slot="tabs-indicator"')
        expect(indicatorIndex).toBeGreaterThan(html.lastIndexOf('role="tab"'))
        expect(html.indexOf("<script", indicatorIndex)).toBeGreaterThan(indicatorIndex)
    })

})

describe("TabsList layout", () => {
    it("does not force a fixed height on wrapped or scrolling lists", () => {
        render(<ExampleTabs listClassName="h-auto flex-wrap" />)

        const list = screen.getByRole("tablist")
        expect(list).toHaveClass("h-auto", "flex-wrap")
        expect(list.className).not.toMatch(/(^|\s)(group-data-horizontal\/tabs:)?(min-)?h-9(\s|$)/)
    })

    it("keeps the first tab reachable when a scrolling list overflows", () => {
        render(<ExampleTabs listClassName="max-w-full overflow-x-auto" />)

        const list = screen.getByRole("tablist")
        expect(list).toHaveClass("justify-center-safe", "overflow-x-auto")
        expect(list).not.toHaveClass("justify-center")
    })
})
