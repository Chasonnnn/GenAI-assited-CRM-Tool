import { describe, expect, it, vi, beforeEach } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"

import { ScheduleParserDialog } from "@/components/ai/ScheduleParserDialog"

const mockParseSchedule = vi.fn()
const mockCreateBulkTasks = vi.fn()

vi.mock("@/components/ui/dialog", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
    DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}))

vi.mock("@/components/ui/select", () => ({
    Select: ({
        value,
        onValueChange,
        children,
    }: {
        value?: string
        onValueChange?: (value: string) => void
        children: ReactNode
    }) => (
        <select value={value ?? ""} onChange={(event) => onValueChange?.(event.target.value)}>
            {children}
        </select>
    ),
    SelectTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectValue: () => null,
    SelectContent: ({ children }: { children: ReactNode }) => <>{children}</>,
    SelectItem: ({ value, children }: { value: string; children: ReactNode }) => (
        <option value={value}>{children}</option>
    ),
}))

vi.mock("@/components/ui/checkbox", () => ({
    Checkbox: ({
        checked,
        onCheckedChange,
    }: {
        checked?: boolean
        onCheckedChange?: (checked: boolean) => void
    }) => (
        <input
            type="checkbox"
            checked={checked}
            onChange={(event) => onCheckedChange?.(event.target.checked)}
        />
    ),
}))

vi.mock("@/lib/hooks/use-schedule-parser", () => ({
    useParseSchedule: () => ({
        mutateAsync: mockParseSchedule,
        isPending: false,
    }),
    useCreateBulkTasks: () => ({
        mutateAsync: mockCreateBulkTasks,
        isPending: false,
    }),
}))

function renderDialog(onOpenChange = vi.fn()) {
    const view = render(
        <ScheduleParserDialog
            open
            onOpenChange={onOpenChange}
            entityType="surrogate"
            entityId="surrogate-1"
            entityName="Alex Chen"
        />
    )
    return { ...view, onOpenChange }
}

function parsedTask(overrides = {}) {
    return {
        title: "PIO injection",
        description: "Nightly injection",
        due_date: "2026-02-20",
        due_time: "21:00",
        task_type: "medication",
        confidence: 0.9,
        dedupe_key: "pio-2026-02-20",
        ...overrides,
    }
}

describe("ScheduleParserDialog", () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it("shows parser warnings without advancing when no tasks are proposed", async () => {
        mockParseSchedule.mockResolvedValueOnce({
            proposed_tasks: [],
            warnings: ["Could not find any schedule dates."],
            assumed_timezone: "America/New_York",
            assumed_reference_date: "2026-02-01",
        })
        renderDialog()

        fireEvent.change(screen.getByRole("textbox"), {
            target: { value: "No usable dates here" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Parse Schedule" }))

        await waitFor(() => expect(mockParseSchedule).toHaveBeenCalledTimes(1))
        expect(mockParseSchedule).toHaveBeenCalledWith({
            text: "No usable dates here",
            surrogate_id: "surrogate-1",
            user_timezone: expect.any(String),
        })
        expect(await screen.findByText("Could not find any schedule dates.")).toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Parse Schedule" })).toBeInTheDocument()
        expect(screen.queryByText(/Parsed with timezone:/)).not.toBeInTheDocument()
    })

    it("creates selected parsed tasks and shows the success state", async () => {
        mockParseSchedule.mockResolvedValueOnce({
            proposed_tasks: [parsedTask()],
            warnings: ["Double-check medication dose."],
            assumed_timezone: "America/New_York",
            assumed_reference_date: "2026-02-01",
        })
        mockCreateBulkTasks.mockResolvedValueOnce({
            success: true,
            created: [{ task_id: "task-1", title: "PIO injection" }],
        })
        renderDialog()

        fireEvent.change(screen.getByRole("textbox"), {
            target: { value: "PIO nightly at 9pm on Feb 20" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Parse Schedule" }))

        expect(await screen.findByDisplayValue("PIO injection")).toBeInTheDocument()
        expect(screen.getByText("Double-check medication dose.")).toBeInTheDocument()
        expect(screen.getByText(/Parsed with timezone: America\/New_York/)).toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Create 1 Task" }))

        await waitFor(() => expect(mockCreateBulkTasks).toHaveBeenCalledTimes(1))
        expect(mockCreateBulkTasks).toHaveBeenCalledWith({
            request_id: expect.any(String),
            surrogate_id: "surrogate-1",
            tasks: [
                {
                    title: "PIO injection",
                    description: "Nightly injection",
                    due_date: "2026-02-20",
                    due_time: "21:00",
                    task_type: "medication",
                    dedupe_key: "pio-2026-02-20",
                },
            ],
        })
        expect(await screen.findByText("Tasks Created Successfully!")).toBeInTheDocument()
    })

    it("resets parsed review state when cancelled", async () => {
        const onOpenChange = vi.fn()
        mockParseSchedule.mockResolvedValueOnce({
            proposed_tasks: [parsedTask()],
            warnings: [],
            assumed_timezone: "America/New_York",
            assumed_reference_date: "2026-02-01",
        })
        renderDialog(onOpenChange)

        fireEvent.change(screen.getByRole("textbox"), {
            target: { value: "PIO nightly at 9pm on Feb 20" },
        })
        fireEvent.click(screen.getByRole("button", { name: "Parse Schedule" }))
        expect(await screen.findByDisplayValue("PIO injection")).toBeInTheDocument()

        fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

        expect(onOpenChange).toHaveBeenCalledWith(false)
        expect(screen.getByRole("textbox")).toHaveValue("")
        expect(screen.queryByDisplayValue("PIO injection")).not.toBeInTheDocument()
    })
})
