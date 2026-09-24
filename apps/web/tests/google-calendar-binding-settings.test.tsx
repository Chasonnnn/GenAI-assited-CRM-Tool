import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { GoogleCalendarBindingSettings } from "@/components/appointments/GoogleCalendarBindingSettings"

const save = vi.fn()
const sync = vi.fn()
let schedulingV2Enabled = true

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
    it("only renders bindings when the server gate is enabled", () => {
        const { rerender } = render(<GoogleCalendarBindingSettings enabled={false} />)
        expect(screen.queryByText("Calendar settings")).not.toBeInTheDocument()
        rerender(<GoogleCalendarBindingSettings enabled />)
        expect(screen.getAllByText("Primary")).not.toHaveLength(0)
        expect(screen.getAllByText("Team")).not.toHaveLength(0)
    })

    it("uses one writable booking destination and saves the dirty active bindings", () => {
        render(<GoogleCalendarBindingSettings enabled />)
        expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled()
        fireEvent.click(screen.getByRole("combobox", { name: "Add bookings to" }))
        expect(screen.getByRole("option", { name: /read only — view only/i })).toHaveAttribute("aria-disabled", "true")
        const team = screen.getByRole("option", { name: "Team" })
        fireEvent.pointerDown(team)
        fireEvent.click(team)
        fireEvent.click(screen.getByRole("button", { name: "Save changes" }))
        const [items] = save.mock.calls[0]
        expect(items).toEqual(expect.arrayContaining([expect.objectContaining({ calendar_id: "primary", check_busy: true, show_events: true, write_bookings: false }), expect.objectContaining({ calendar_id: "team", write_bookings: true })]))
    })

    it("keeps only the legacy sync action when scheduling v2 is off", () => {
        const legacySync = vi.fn()
        schedulingV2Enabled = false
        render(<GoogleCalendarBindingSettings enabled onLegacySync={legacySync} />)
        fireEvent.click(screen.getByRole("button", { name: "Sync" }))
        expect(legacySync).toHaveBeenCalled()
        expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument()
        schedulingV2Enabled = true
    })
})
