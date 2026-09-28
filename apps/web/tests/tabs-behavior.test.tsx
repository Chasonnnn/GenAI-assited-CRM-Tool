import * as React from "react"
import { describe, expect, it, vi } from "vitest"
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTabSearchParam } from "@/lib/hooks/use-tab-search-param"

const mockReplace = vi.fn()
let mockSearch = ""

vi.mock("next/navigation", () => ({
    usePathname: () => "/settings/appointments",
    useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
    useSearchParams: () => new URLSearchParams(mockSearch),
}))

function SettingsTabs({ isAdmin }: { isAdmin: boolean }) {
    return (
        <Tabs defaultValue="general">
            <TabsList aria-label="Settings sections">
                <TabsTrigger value="general">General</TabsTrigger>
                {isAdmin && <TabsTrigger value="signature">Email Signature</TabsTrigger>}
            </TabsList>
            <TabsContent value="general">General panel</TabsContent>
            <TabsContent value="signature">Signature panel</TabsContent>
        </Tabs>
    )
}

function UncontrolledTabs({ showSecond }: { showSecond: boolean }) {
    return (
        <Tabs defaultValue="a">
            <TabsList>
                <TabsTrigger value="a">A</TabsTrigger>
                {showSecond && <TabsTrigger value="b">B</TabsTrigger>}
            </TabsList>
            <TabsContent value="a">A panel</TabsContent>
            <TabsContent value="b">B panel</TabsContent>
        </Tabs>
    )
}

function WrappedTab({ value, children }: { value: string; children: React.ReactNode }) {
    return <TabsTrigger value={value}>{children}</TabsTrigger>
}

describe("TabsList with a single tab", () => {
    it("hides the tab bar when only one tab is available and keeps its panel", () => {
        render(<SettingsTabs isAdmin={false} />)

        expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
        expect(screen.queryByRole("tab")).not.toBeInTheDocument()
        expect(screen.getByText("General panel")).toBeVisible()
    })

    it("shows the tab bar once a second tab is available", () => {
        render(<SettingsTabs isAdmin />)

        expect(screen.getByRole("tablist", { name: "Settings sections" })).toBeInTheDocument()
        expect(screen.getAllByRole("tab")).toHaveLength(2)
    })

    it("counts tabs inside fragments and mapped arrays", () => {
        render(
            <Tabs defaultValue="a">
                <TabsList>
                    <>
                        {["a", "b"].map((value) => (
                            <TabsTrigger key={value} value={value}>
                                {value.toUpperCase()}
                            </TabsTrigger>
                        ))}
                    </>
                </TabsList>
            </Tabs>
        )

        expect(screen.getAllByRole("tab")).toHaveLength(2)
    })

    it("keeps the bar when a wrapper component renders the tab", () => {
        render(
            <Tabs defaultValue="a">
                <TabsList>
                    <WrappedTab value="a">A</WrappedTab>
                </TabsList>
            </Tabs>
        )

        expect(screen.getByRole("tablist")).toBeInTheDocument()
    })

    it("keeps the panel of an uncontrolled single tab that has no defaultValue", async () => {
        render(
            <Tabs>
                <TabsList>
                    <TabsTrigger value="general">General</TabsTrigger>
                </TabsList>
                <TabsContent value="general">General panel</TabsContent>
            </Tabs>
        )

        expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
        expect(await screen.findByText("General panel")).toBeVisible()
    })

    it("keeps the uncontrolled panel when a second tab goes away", async () => {
        const view = render(<UncontrolledTabs showSecond />)
        expect(screen.getAllByRole("tab")).toHaveLength(2)

        view.rerender(<UncontrolledTabs showSecond={false} />)

        expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
        await act(async () => {})
        expect(screen.getByText("A panel")).toBeVisible()
        expect(screen.getByRole("tabpanel")).toHaveAccessibleName("A")
    })

    it("can opt out and show a single tab", () => {
        render(
            <Tabs defaultValue="a">
                <TabsList hideSingleTab={false}>
                    <TabsTrigger value="a">Only</TabsTrigger>
                </TabsList>
            </Tabs>
        )

        expect(screen.getByRole("tab", { name: "Only" })).toBeInTheDocument()
    })
})

describe("Tabs resetScrollRef", () => {
    function ScrollingDialogTabs({
        onValueChange,
    }: {
        onValueChange: (value: unknown, eventDetails: unknown) => void
    }) {
        const bodyRef = React.useRef<HTMLDivElement>(null)
        return (
            <div ref={bodyRef} data-testid="dialog-body" style={{ overflowY: "auto" }}>
                <Tabs defaultValue="stages" resetScrollRef={bodyRef} onValueChange={onValueChange}>
                    <TabsList>
                        <TabsTrigger value="stages">Stage reporting</TabsTrigger>
                        <TabsTrigger value="activity">Activity</TabsTrigger>
                    </TabsList>
                    <TabsContent value="stages">Stages</TabsContent>
                    <TabsContent value="activity">Activity log</TabsContent>
                </Tabs>
            </div>
        )
    }

    it("scrolls the shared container to the top on tab change and still reports the value", () => {
        const onValueChange = vi.fn()
        render(<ScrollingDialogTabs onValueChange={onValueChange} />)

        const body = screen.getByTestId("dialog-body")
        body.scrollTop = 1752

        fireEvent.click(screen.getByRole("tab", { name: "Activity" }))

        expect(onValueChange).toHaveBeenCalledWith("activity", expect.anything())
        expect(body.scrollTop).toBe(0)
        expect(screen.getByText("Activity log")).toBeVisible()
    })

    it("keeps the scroll position when the caller cancels the change", () => {
        render(
            <ScrollingDialogTabs
                onValueChange={(_value, eventDetails) => (eventDetails as { cancel: () => void }).cancel()}
            />
        )

        const body = screen.getByTestId("dialog-body")
        body.scrollTop = 400

        fireEvent.click(screen.getByRole("tab", { name: "Activity" }))

        expect(body.scrollTop).toBe(400)
        expect(screen.getByText("Stages")).toBeVisible()
    })
})

describe("useTabSearchParam", () => {
    const TABS = ["availability", "types", "link"] as const

    it("reads the tab from the URL and falls back to the default for unknown values", () => {
        mockSearch = "tab=types"
        const { result, rerender } = renderHook(() => useTabSearchParam(TABS, "availability"))
        expect(result.current[0]).toBe("types")

        mockSearch = "tab=bogus"
        rerender()
        expect(result.current[0]).toBe("availability")
    })

    it("writes the tab through history.replaceState without a router navigation, keeps other params and drops the default", () => {
        mockReplace.mockReset()
        const replaceState = vi.spyOn(window.history, "replaceState")
        mockSearch = "q=ava"
        const { result } = renderHook(() => useTabSearchParam(TABS, "availability"))

        act(() => result.current[1]("link"))
        expect(replaceState).toHaveBeenLastCalledWith(null, "", "/settings/appointments?q=ava&tab=link")

        mockSearch = "q=ava&tab=link"
        const { result: onLink } = renderHook(() => useTabSearchParam(TABS, "availability"))
        act(() => onLink.current[1]("availability"))
        expect(replaceState).toHaveBeenLastCalledWith(null, "", "/settings/appointments?q=ava")

        replaceState.mockClear()
        act(() => onLink.current[1]("unknown"))
        act(() => onLink.current[1]("link"))
        expect(replaceState).not.toHaveBeenCalled()
        expect(mockReplace).not.toHaveBeenCalled()
        replaceState.mockRestore()
    })
})
