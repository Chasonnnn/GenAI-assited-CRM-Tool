import type { ReactNode } from "react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, within } from "@testing-library/react"

import { ReleaseQueueDialog } from "@/components/surrogates/detail/SurrogateDetailLayout/dialogs/ReleaseQueueDialog"
import { ZoomMeetingDialog } from "@/components/surrogates/detail/SurrogateDetailLayout/dialogs/ZoomMeetingDialog"

const mockUseSurrogateDetailData = vi.fn()
const mockUseSurrogateDetailDialogs = vi.fn()
const mockUseSurrogateDetailQueue = vi.fn()
const mockUseSurrogateDetailZoom = vi.fn()
const mockUseSurrogateDetailActions = vi.fn()

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ open, children }: { open?: boolean; children?: ReactNode }) => (open ? <div>{children}</div> : null),
    DialogContent: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/date-time-picker", () => ({
    DateTimePicker: () => <button type="button">Choose date and time</button>,
}))

vi.mock("@/components/surrogates/detail/SurrogateDetailLayout/context", () => ({
    useSurrogateDetailData: () => mockUseSurrogateDetailData(),
    useSurrogateDetailDialogs: () => mockUseSurrogateDetailDialogs(),
    useSurrogateDetailQueue: () => mockUseSurrogateDetailQueue(),
    useSurrogateDetailZoom: () => mockUseSurrogateDetailZoom(),
    useSurrogateDetailActions: () => mockUseSurrogateDetailActions(),
}))

describe("surrogate detail dialog pickers", () => {
    beforeEach(() => {
        mockUseSurrogateDetailData.mockReturnValue({
            surrogate: { email: "surrogate@example.com" },
            timezoneName: "America/New_York",
            queues: [
                { id: "queue-1", name: "Primary Queue" },
                { id: "queue-2", name: "Backup Queue" },
            ],
        })
        mockUseSurrogateDetailDialogs.mockReturnValue({
            activeDialog: { type: "none" },
            closeDialog: vi.fn(),
        })
        mockUseSurrogateDetailQueue.mockReturnValue({
            selectedQueueId: "",
            setSelectedQueueId: vi.fn(),
        })
        mockUseSurrogateDetailZoom.mockReturnValue({
            zoomForm: {
                topic: "Consultation",
                duration: 30,
                startAt: new Date("2026-05-13T16:15:00Z"),
                lastMeetingResult: null,
            },
            setZoomTopic: vi.fn(),
            setZoomDuration: vi.fn(),
            setZoomStartAt: vi.fn(),
            createZoomMeeting: vi.fn(),
            sendZoomInvite: vi.fn(),
            isCreateZoomPending: false,
            isSendZoomInvitePending: false,
        })
        mockUseSurrogateDetailActions.mockReturnValue({
            releaseSurrogate: vi.fn(),
            isReleasePending: false,
        })
    })

    it("uses a shadcn select for releasing to a queue", () => {
        mockUseSurrogateDetailDialogs.mockReturnValue({
            activeDialog: { type: "release_queue" },
            closeDialog: vi.fn(),
        })

        render(<ReleaseQueueDialog />)

        const trigger = screen.getByRole("combobox", { name: /select queue/i })
        expect(trigger).toHaveAttribute("data-slot", "select-trigger")
        expect(trigger).toHaveTextContent("Select a queue…")
    })

    it("does not offer the queue placeholder as a pickable option", async () => {
        mockUseSurrogateDetailDialogs.mockReturnValue({
            activeDialog: { type: "release_queue" },
            closeDialog: vi.fn(),
        })

        render(<ReleaseQueueDialog />)

        fireEvent.click(screen.getByRole("combobox", { name: /select queue/i }))
        const listbox = await screen.findByRole("listbox")
        expect(within(listbox).getAllByRole("option").map((option) => option.textContent)).toEqual([
            "Primary Queue",
            "Backup Queue",
        ])
        expect(screen.getByRole("button", { name: "Release" })).toBeDisabled()
    })

    it("uses a shadcn select for Zoom appointment duration", () => {
        mockUseSurrogateDetailDialogs.mockReturnValue({
            activeDialog: { type: "zoom_meeting" },
            closeDialog: vi.fn(),
        })

        render(<ZoomMeetingDialog />)

        expect(
            screen.getByRole("combobox", { name: /duration/i }),
        ).toHaveAttribute("data-slot", "select-trigger")
    })
})
