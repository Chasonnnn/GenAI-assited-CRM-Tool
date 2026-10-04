import * as React from "react"
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { BulkChangeStageModal, type BulkStageSurrogate } from "@/components/surrogates/BulkChangeStageModal"
import type { PipelineStage } from "@/lib/api/pipelines"

vi.mock("@/components/ui/select", () => {
    const SelectContext = React.createContext<{
        value: string
        onValueChange: (value: string) => void
        disabled: boolean
    }>({
        value: "",
        onValueChange: () => undefined,
        disabled: false,
    })

    function Select({
        value,
        onValueChange,
        disabled = false,
        children,
    }: {
        value: string
        onValueChange: (value: string) => void
        disabled?: boolean
        children: React.ReactNode
    }) {
        return (
            <SelectContext.Provider value={{ value, onValueChange, disabled }}>
                <div>{children}</div>
            </SelectContext.Provider>
        )
    }

    function SelectTrigger({
        id,
        children,
        ...props
    }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
        const { disabled } = React.use(SelectContext)
        return (
            <button
                id={id}
                type="button"
                role="combobox"
                aria-controls={`${id || "mock-select"}-listbox`}
                aria-expanded="false"
                disabled={disabled}
                {...props}
            >
                {children}
            </button>
        )
    }

    function SelectValue({
        placeholder,
        children,
    }: {
        placeholder?: string
        children?: ((value: string | null) => React.ReactNode) | React.ReactNode
    }) {
        const { value } = React.use(SelectContext)
        if (!value) return <span>{placeholder}</span>
        if (typeof children === "function") {
            return <span>{children(value)}</span>
        }
        return <span>{value}</span>
    }

    function SelectContent({ children, className }: { children: React.ReactNode; className?: string }) {
        return <div id="mock-select-listbox" role="listbox" className={className}>{children}</div>
    }

    function SelectItem({
        value,
        children,
    }: {
        value: string
        children: React.ReactNode
    }) {
        const { onValueChange, value: selectedValue } = React.use(SelectContext)
        return (
            <button
                type="button"
                role="option"
                aria-selected={selectedValue === value}
                onClick={() => onValueChange(value)}
            >
                {children}
            </button>
        )
    }

    // StageSelect groups options under headings with separators.
    function SelectGroup({ children }: { children: React.ReactNode }) {
        return <div role="group">{children}</div>
    }

    function SelectLabel({ children }: { children: React.ReactNode }) {
        return <div>{children}</div>
    }

    function SelectSeparator() {
        return <hr />
    }

    return {
        Select,
        SelectTrigger,
        SelectValue,
        SelectContent,
        SelectItem,
        SelectGroup,
        SelectLabel,
        SelectSeparator,
    }
})

function stage(id: string, key: string, label: string, order: number, overrides: Partial<PipelineStage> = {}) {
    return {
        id,
        slug: key,
        stage_key: key,
        label,
        color: "#3b82f6",
        order,
        stage_type: "intake",
        is_active: true,
        ...overrides,
    } as PipelineStage
}

const stages: PipelineStage[] = [
    stage("s-delivered", "delivered", "Delivered", 20, { stage_type: "post_approval" }),
    stage("s-new", "new_unread", "New Unread", 1),
    stage("s-contacted", "contacted", "Contacted", 2, { color: "#0ea5e9" }),
    stage("s-interview", "interview_scheduled", "Interview Scheduled", 4),
    stage("s-approved", "approved", "Approved", 8),
    stage("s-on-hold", "on_hold", "On-Hold", 22, { stage_type: "paused" }),
    stage("s-cold", "cold_leads", "Cold Leads", 23, { stage_type: "terminal" }),
    stage("s-lost", "lost", "Lost", 24, { stage_type: "terminal" }),
    stage("s-disqualified", "disqualified", "Disqualified", 25, { stage_type: "terminal" }),
    stage("s-archived", "legacy", "Legacy Stage", 26, { is_active: false }),
]

const newRows: [BulkStageSurrogate, BulkStageSurrogate] = [
    { id: "a", full_name: "Ava Cole", stage_id: "s-new", paused_from_stage_id: null },
    { id: "b", full_name: "Mia Ross", stage_id: "s-new", paused_from_stage_id: null },
]

function modal(surrogates: BulkStageSurrogate[], onSubmit: React.ComponentProps<typeof BulkChangeStageModal>["onSubmit"], isPending = false) {
    return (
        <BulkChangeStageModal
            open
            onOpenChange={vi.fn()}
            surrogates={surrogates}
            stages={stages}
            isPending={isPending}
            onSubmit={onSubmit}
        />
    )
}

function renderModal(surrogates: BulkStageSurrogate[] = newRows, onSubmit = vi.fn().mockResolvedValue(undefined)) {
    render(modal(surrogates, onSubmit))
    return onSubmit
}

function chooseStage(name: string) {
    fireEvent.click(screen.getByRole("combobox", { name: "Target stage" }))
    fireEvent.click(screen.getByRole("option", { name }))
}

function localValue(offsetMs: number): string {
    const date = new Date(Date.now() + offsetMs)
    const pad = (value: number) => String(value).padStart(2, "0")
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

describe("BulkChangeStageModal", () => {
    it("lists every active stage in pipeline order without the immediate-only notice", () => {
        renderModal()

        expect(screen.getByRole("heading", { name: "Change stage for 2 surrogates" })).toBeInTheDocument()
        const options = within(screen.getByRole("listbox")).getAllByRole("option").map((option) => option.textContent)
        expect(options).toEqual([
            "New Unread",
            "Contacted",
            "Interview Scheduled",
            "Approved",
            "Delivered",
            "On-Hold",
            "Cold Leads",
            "Lost",
            "Disqualified",
        ])
        expect(screen.queryByText(/immediate/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/per-surrogate review/i)).not.toBeInTheDocument()
        // Shared StageSelect rendering: a colour dot per option.
        expect(
            screen.getByRole("option", { name: "Contacted" }).querySelector('[data-slot="stage-dot"]'),
        ).toHaveStyle({ backgroundColor: "#0ea5e9" })
    })

    it("caps the stage list height so it opens below the trigger inside the dialog", () => {
        renderModal()

        const listbox = screen.getByRole("listbox")
        expect(listbox).toHaveClass("max-h-[min(18rem,var(--available-height))]")
        expect(listbox).not.toHaveClass("max-h-[min(28rem,var(--available-height))]")
    })

    it("submits a forward move without a reason field", async () => {
        const onSubmit = renderModal()

        chooseStage("Contacted")
        expect(screen.queryByLabelText(/Reason/)).not.toBeInTheDocument()
        fireEvent.click(screen.getByRole("button", { name: "Change stage" }))

        await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ stage_id: "s-contacted" }))
    })

    it("requires the shared reason for a stage that requires one", async () => {
        const onSubmit = renderModal()

        chooseStage("Disqualified")
        const submit = screen.getByRole("button", { name: "Change stage" })
        expect(submit).toBeDisabled()

        fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "  Not eligible  " } })
        expect(submit).toBeEnabled()
        fireEvent.click(submit)

        await waitFor(() =>
            expect(onSubmit).toHaveBeenCalledWith({ stage_id: "s-disqualified", reason: "Not eligible" }),
        )
    })

    it("requires a reason when any selected row would move backward", () => {
        renderModal([
            ...newRows,
            { id: "c", full_name: "Zoe Park", stage_id: "s-approved", paused_from_stage_id: null },
        ])

        chooseStage("Contacted")

        expect(screen.getByLabelText(/Reason/)).toBeRequired()
        expect(screen.getByRole("button", { name: "Change stage" })).toBeDisabled()
    })

    it("treats a move back to the paused-from stage as a resume", () => {
        renderModal([{ id: "c", full_name: "Zoe Park", stage_id: "s-on-hold", paused_from_stage_id: "s-contacted" }])

        chooseStage("Contacted")

        expect(screen.queryByLabelText(/Reason/)).not.toBeInTheDocument()
        expect(screen.getByRole("button", { name: "Change stage" })).toBeEnabled()
    })

    it("offers the On-Hold follow-up choice and submits it", async () => {
        const onSubmit = renderModal()

        chooseStage("On-Hold")
        const group = screen.getByRole("group", { name: "Follow-up reminder" })
        expect(within(group).getAllByRole("button").map((button) => button.textContent)).toEqual([
            "No follow-up",
            "1 month",
            "3 months",
            "6 months",
        ])
        expect(within(group).getByRole("button", { name: "No follow-up" })).toHaveAttribute("aria-pressed", "true")

        fireEvent.click(within(group).getByRole("button", { name: "3 months" }))
        // The outline variant sets dark background and border, so the selected state sets both too.
        const selected = within(group).getByRole("button", { name: "3 months" })
        const unselected = within(group).getByRole("button", { name: "No follow-up" })
        expect(selected).toHaveAttribute("aria-pressed", "true")
        expect(selected).toHaveClass("bg-primary/10", "border-primary", "dark:bg-primary/10", "dark:border-primary")
        expect(unselected).toHaveAttribute("aria-pressed", "false")
        expect(unselected).not.toHaveClass("dark:bg-primary/10")
        fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Travelling" } })
        fireEvent.click(screen.getByRole("button", { name: "Change stage" }))

        await waitFor(() =>
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "s-on-hold",
                reason: "Travelling",
                on_hold_follow_up_months: 3,
            }),
        )
    })

    it("requires a future interview time for each selected surrogate", async () => {
        const onSubmit = renderModal()

        chooseStage("Interview Scheduled")
        const section = screen.getByRole("region", { name: "Interview times" })
        const avaInput = within(section).getByLabelText("Ava Cole")
        const miaInput = within(section).getByLabelText("Mia Ross")
        const submit = screen.getByRole("button", { name: "Change stage" })

        expect(screen.queryByLabelText(/Reason/)).not.toBeInTheDocument()
        const avaTime = localValue(2 * 24 * 60 * 60 * 1000)
        fireEvent.change(avaInput, { target: { value: avaTime } })
        expect(submit).toBeDisabled()

        fireEvent.change(miaInput, { target: { value: localValue(-60 * 60 * 1000) } })
        expect(miaInput).toHaveAttribute("aria-invalid", "true")
        expect(submit).toBeDisabled()

        const miaTime = localValue(3 * 24 * 60 * 60 * 1000)
        fireEvent.change(miaInput, { target: { value: miaTime } })
        expect(miaInput).toHaveAttribute("aria-invalid", "false")
        expect(submit).toBeEnabled()
        fireEvent.click(submit)

        await waitFor(() =>
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "s-interview",
                interview_times: [
                    { surrogate_id: "a", scheduled_at: new Date(avaTime).toISOString() },
                    { surrogate_id: "b", scheduled_at: new Date(miaTime).toISOString() },
                ],
            }),
        )
    })

    it("requires the shared reason when overriding availability", async () => {
        const onSubmit = renderModal([newRows[0]])

        chooseStage("Interview Scheduled")
        const avaTime = localValue(2 * 24 * 60 * 60 * 1000)
        fireEvent.change(screen.getByLabelText("Ava Cole"), { target: { value: avaTime } })
        const submit = screen.getByRole("button", { name: "Change stage" })
        expect(submit).toBeEnabled()

        fireEvent.click(screen.getByRole("checkbox", { name: "Allow times outside availability" }))
        expect(screen.getByLabelText(/Reason/)).toBeRequired()
        expect(submit).toBeDisabled()

        fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Booked by phone" } })
        fireEvent.click(submit)

        await waitFor(() =>
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "s-interview",
                reason: "Booked by phone",
                override_availability: true,
                interview_times: [{ surrogate_id: "a", scheduled_at: new Date(avaTime).toISOString() }],
            }),
        )
    })

    it("widens the dialog through its size prop for per-surrogate interview times", () => {
        renderModal()

        const dialog = screen.getByRole("dialog")
        expect(dialog).toHaveAttribute("data-size", "lg")
        expect(dialog).toHaveAttribute("data-layout", "sectioned")

        chooseStage("Interview Scheduled")

        expect(dialog).toHaveAttribute("data-size", "xl")
    })

    it("leaves rows already in the target stage out of the interview time list", async () => {
        const onSubmit = renderModal([
            newRows[0],
            { id: "c", full_name: "Zoe Park", stage_id: "s-interview", paused_from_stage_id: null },
        ])

        chooseStage("Interview Scheduled")
        const section = screen.getByRole("region", { name: "Interview times" })
        expect(within(section).queryByLabelText("Zoe Park")).not.toBeInTheDocument()
        const avaTime = localValue(2 * 24 * 60 * 60 * 1000)
        fireEvent.change(within(section).getByLabelText("Ava Cole"), { target: { value: avaTime } })
        const submit = screen.getByRole("button", { name: "Change stage" })
        expect(submit).toBeEnabled()
        fireEvent.click(submit)

        await waitFor(() =>
            expect(onSubmit).toHaveBeenCalledWith({
                stage_id: "s-interview",
                interview_times: [{ surrogate_id: "a", scheduled_at: new Date(avaTime).toISOString() }],
            }),
        )
    })

    it("shows a loading state and locks the form while the change runs", () => {
        const onSubmit = vi.fn()
        const { rerender } = render(modal(newRows, onSubmit))
        chooseStage("Interview Scheduled")
        fireEvent.click(screen.getByRole("checkbox", { name: "Allow times outside availability" }))

        rerender(modal(newRows, onSubmit, true))

        const submit = screen.getByRole("button", { name: "Changing..." })
        expect(submit).toBeDisabled()
        expect(submit.querySelector(".animate-spin")).not.toBeNull()
        expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled()
        expect(screen.getByRole("combobox", { name: "Target stage" })).toBeDisabled()
        expect(screen.getByLabelText(/Reason/)).toBeDisabled()
        expect(screen.getByLabelText("Ava Cole")).toBeDisabled()
        expect(screen.getByLabelText("Mia Ross")).toBeDisabled()
        expect(screen.getByRole("checkbox", { name: "Allow times outside availability" })).toHaveAttribute(
            "aria-disabled",
            "true",
        )
    })

    it("blocks more than 100 selected surrogates", () => {
        const many = Array.from({ length: 101 }, (_, index) => ({
            id: `row-${index}`,
            full_name: `Surrogate ${index}`,
            stage_id: "s-new",
            paused_from_stage_id: null,
        }))
        renderModal(many)

        chooseStage("Interview Scheduled")

        expect(screen.getByRole("alert")).toHaveTextContent("Select up to 100 surrogates.")
        const section = screen.getByRole("region", { name: "Interview times" })
        expect(section.querySelectorAll('input[type="datetime-local"]')).toHaveLength(100)
        expect(screen.getByRole("button", { name: "Change stage" })).toBeDisabled()
    })
})
