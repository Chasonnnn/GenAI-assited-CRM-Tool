import type { ComponentProps } from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { GoogleCalendarBindingSettings } from "@/components/appointments/GoogleCalendarBindingSettings"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ApiError } from "@/lib/api"

const save = vi.fn()
const sync = vi.fn()
let schedulingV2Enabled = true
const mockToast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock("@/components/ui/toast", () => ({ toast: mockToast }))

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
    usePathname: () => "/settings/integrations",
    useSearchParams: () => new URLSearchParams(),
}))

type SettingsProps = ComponentProps<typeof GoogleCalendarBindingSettings>

// The component renders the status bar, body and footer of a sectioned dialog.
function renderInDialog(props: Partial<SettingsProps> = {}) {
    const content = (next: Partial<SettingsProps>) => (
        <Dialog open>
            <DialogContent layout="sectioned" size="2xl">
                <DialogHeader>
                    <DialogTitle>Google Calendar &amp; Meet</DialogTitle>
                </DialogHeader>
                <GoogleCalendarBindingSettings enabled lastSyncLabel="5 minutes ago" {...next} />
            </DialogContent>
        </Dialog>
    )
    const view = render(content(props))
    return { ...view, rerenderWith: (next: Partial<SettingsProps>) => view.rerender(content(next)) }
}

vi.mock("@/lib/hooks/use-user-integrations", () => ({
    useGoogleCalendarBindings: (enabled: boolean) => ({
        data: enabled ? {
            enabled: schedulingV2Enabled,
            items: [{ calendar_id: "primary", display_name: "Primary", access_role: "owner", check_busy: true, show_events: true, write_bookings: true, is_active: true, sync_error: null }],
        } : undefined,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
    }),
    useGoogleCalendarDiscovery: () => ({ data: { items: [{ calendar_id: "team", display_name: "Team", access_role: "writer", primary: false }, { calendar_id: "read-only", display_name: "Read only", access_role: "reader", primary: false }] }, isLoading: false, isError: false, refetch: vi.fn() }),
    useSaveGoogleCalendarBindings: () => ({ mutate: save, isPending: false }),
    useSyncGoogleCalendarBindings: () => ({ mutate: sync, isPending: false }),
}))

describe("GoogleCalendarBindingSettings", () => {
    beforeEach(() => {
        schedulingV2Enabled = true
        save.mockReset()
        sync.mockReset()
        mockToast.success.mockReset()
        mockToast.error.mockReset()
    })

    it("only renders bindings when the server gate is enabled", () => {
        const { rerenderWith } = renderInDialog({ enabled: false })
        expect(screen.queryByText("Calendars")).not.toBeInTheDocument()
        rerenderWith({ enabled: true })
        expect(screen.getAllByText("Primary")).not.toHaveLength(0)
        expect(screen.getAllByText("Team")).not.toHaveLength(0)
    })

    it("lists calendars in one table with a conflict and an events checkbox per row", () => {
        renderInDialog()
        const table = screen.getByRole("table")
        expect(table).toHaveTextContent("Check conflicts")
        expect(table).toHaveTextContent("Show events")
        // Narrow wrapping headers keep the Show events column inside the dialog at 390px.
        for (const name of ["Check conflicts", "Show events"]) {
            expect(screen.getByRole("columnheader", { name })).toHaveClass("w-24", "whitespace-normal", "sm:w-32")
        }
        expect(screen.getByRole("checkbox", { name: "Check conflicts on Primary" })).toBeChecked()
        expect(screen.getByRole("checkbox", { name: "Show events from Team" })).not.toBeChecked()
        fireEvent.click(screen.getByRole("checkbox", { name: "Show events from Team" }))
        expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled()
    })

    it("shows last sync and the Google Meet section", () => {
        renderInDialog()
        expect(screen.getByText("Last sync")).toBeInTheDocument()
        expect(screen.getByText("5 minutes ago")).toBeInTheDocument()
        expect(screen.getByRole("heading", { name: "Google Meet" })).toBeInTheDocument()
        expect(screen.getByText("Meet links")).toBeInTheDocument()
        expect(screen.getByRole("link", { name: /Appointment types/ })).toHaveAttribute("href", "/settings/appointments")
    })

    it("confirms Sync now with a toast and keeps provider errors out of the failure toast", () => {
        sync.mockImplementationOnce((_input: unknown, options: { onSuccess: () => void }) => options.onSuccess())
        renderInDialog()
        fireEvent.click(screen.getByRole("button", { name: "Sync now" }))
        expect(mockToast.success).toHaveBeenCalledWith("Sync queued")

        sync.mockImplementationOnce((_input: unknown, options: { onError: (error: unknown) => void }) =>
            options.onError(new ApiError(502, "Bad Gateway", "invalid_grant: token revoked")),
        )
        fireEvent.click(screen.getByRole("button", { name: "Sync now" }))
        expect(mockToast.error).toHaveBeenCalledWith("Couldn't queue calendar sync")
    })

    it("renders the footer start slot and the notice", () => {
        renderInDialog({
            footerStart: <button type="button">Disconnect…</button>,
            notice: <p>Tasks notice</p>,
        })
        expect(screen.getByRole("button", { name: "Disconnect…" })).toBeInTheDocument()
        expect(screen.getByText("Tasks notice")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument()
    })

    it("uses one writable booking destination and saves the dirty active bindings", () => {
        const onSaved = vi.fn()
        save.mockImplementation((_items: unknown, options: { onSuccess: () => void }) => options.onSuccess())
        renderInDialog({ onSaved })
        expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled()
        fireEvent.click(screen.getByRole("combobox", { name: "Add bookings to" }))
        expect(screen.getByRole("option", { name: /read only — view only/i })).toHaveAttribute("aria-disabled", "true")
        const team = screen.getByRole("option", { name: "Team" })
        fireEvent.pointerDown(team)
        fireEvent.click(team)
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        const [items] = save.mock.calls[0]
        expect(items).toEqual(expect.arrayContaining([expect.objectContaining({ calendar_id: "primary", check_busy: true, show_events: true, write_bookings: false }), expect.objectContaining({ calendar_id: "team", write_bookings: true })]))
        expect(mockToast.success).toHaveBeenCalledWith("Calendar settings saved")
        expect(onSaved).toHaveBeenCalled()
    })

    it("keeps only the legacy sync action when scheduling v2 is off", () => {
        const legacySync = vi.fn()
        schedulingV2Enabled = false
        renderInDialog({ onLegacySync: legacySync })
        fireEvent.click(screen.getByRole("button", { name: "Sync now" }))
        expect(legacySync).toHaveBeenCalled()
        expect(sync).not.toHaveBeenCalled()
        expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument()
        // The header X is also named "Close"; the footer button is the one with visible text.
        expect(screen.getAllByRole("button", { name: "Close" }).some((button) => button.textContent === "Close")).toBe(true)
        schedulingV2Enabled = true
    })
})
