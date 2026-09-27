import * as React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import { StageOptionLabel, StageSelect, groupStageOptions } from "@/components/stage-select"
import {
    getMatchStatusFilterLabel,
    getStageOptionLabel,
    matchStatusStageOptions,
    pipelineStageOptions,
    type StageOption,
} from "@/lib/stage-options"

const STAGES = [
    { id: "s-lost", stage_key: "lost", label: "Lost", color: "#EF4444", order: 24, stage_type: "terminal" as const, is_active: true },
    { id: "s-new", stage_key: "new_unread", label: "New Unread", color: "#3B82F6", order: 1, stage_type: "intake" as const, is_active: true },
    { id: "s-matched", stage_key: "matched", label: "Matched", color: "#6366F1", order: 12, stage_type: "post_approval" as const, is_active: true },
    { id: "s-hold", stage_key: "on_hold", label: "On-Hold", color: "#B4536A", order: 22, stage_type: "paused" as const, is_active: true },
    { id: "s-old", stage_key: "old", label: "Retired Stage", color: "#64748B", order: 2, stage_type: "intake" as const, is_active: false },
]

function ControlledStageSelect({
    initialValue,
    onChange,
    ...props
}: Omit<React.ComponentProps<typeof StageSelect>, "value" | "onValueChange"> & {
    initialValue: string
    onChange?: (value: string) => void
}) {
    const [value, setValue] = React.useState(initialValue)
    return (
        <StageSelect
            {...props}
            value={value}
            onValueChange={(next) => {
                setValue(next)
                onChange?.(next)
            }}
        />
    )
}

describe("pipelineStageOptions", () => {
    it("orders by pipeline order and groups intake, post-approval, then paused and terminal together", () => {
        const options = pipelineStageOptions(STAGES)

        expect(options.map((option) => option.label)).toEqual([
            "New Unread",
            "Retired Stage",
            "Matched",
            "On-Hold",
            "Lost",
        ])
        expect(options.map((option) => option.group)).toEqual([
            "Intake",
            "Intake",
            "Post-approval",
            "Paused & closed",
            "Paused & closed",
        ])
        expect(options[0]).toMatchObject({ value: "s-new", color: "#3B82F6" })
    })

    it("stores stage_key when asked and can drop inactive stages", () => {
        const options = pipelineStageOptions(STAGES, { valueKey: "stage_key", activeOnly: true })

        expect(options.map((option) => option.value)).toEqual(["new_unread", "matched", "on_hold", "lost"])
    })
})

describe("stage option labels", () => {
    const options = pipelineStageOptions(STAGES)

    it("maps the sentinel, known ids and unknown ids through one helper", () => {
        expect(getStageOptionLabel("all", options)).toBe("All Stages")
        expect(getStageOptionLabel(null, options)).toBe("All Stages")
        expect(getStageOptionLabel("s-matched", options)).toBe("Matched")
        expect(getStageOptionLabel("deleted-stage-id", options)).toBe("Unknown stage")
        expect(getStageOptionLabel("", options, { emptyLabel: "Select a stage" })).toBe("Select a stage")
    })

    it("covers every match status, including the closed ones", () => {
        const matchOptions = matchStatusStageOptions({ proposed: 8, cancelled: 3 })

        expect(matchOptions.map((option) => option.label)).toEqual([
            "Proposed",
            "Reviewing",
            "Accepted",
            "Cancel Pending",
            "Rejected",
            "Cancelled",
            "Completed",
        ])
        expect(matchOptions.filter((option) => option.group === "Closed").map((option) => option.value)).toEqual([
            "rejected",
            "cancelled",
            "completed",
        ])
        expect(matchOptions[0]).toMatchObject({ count: 8, dotClassName: "bg-blue-500" })
        expect(matchOptions[1]).not.toHaveProperty("count")
        expect(getMatchStatusFilterLabel("cancel_pending")).toBe("Cancel Pending")
        expect(getMatchStatusFilterLabel("all")).toBe("All Stages")
        expect(getMatchStatusFilterLabel("bogus")).toBe("Unknown stage")
    })

    it("buckets options by group in first-appearance order", () => {
        const grouped = groupStageOptions([
            { value: "a", label: "A", group: "One" },
            { value: "b", label: "B", group: "Two" },
            { value: "c", label: "C", group: "One" },
        ])

        expect(grouped.map((group) => [group.label, group.options.map((option) => option.value)])).toEqual([
            ["One", ["a", "c"]],
            ["Two", ["b"]],
        ])
    })
})

describe("StageSelect", () => {
    const options = pipelineStageOptions(STAGES, { activeOnly: true })

    it("shows the all label, then the selected stage with its color dot", async () => {
        const onChange = vi.fn()
        render(
            <ControlledStageSelect
                initialValue="all"
                options={options}
                allLabel="All Stages"
                aria-label="Filter by stage"
                className="w-[180px]"
                onChange={onChange}
            />
        )

        const trigger = screen.getByRole("combobox", { name: "Filter by stage" })
        expect(trigger).toHaveTextContent("All Stages")
        expect(trigger).toHaveClass("w-[180px]")

        fireEvent.click(trigger)
        const option = await screen.findByRole("option", { name: "Matched" })
        fireEvent.mouseMove(option)
        fireEvent.click(option)

        expect(onChange).toHaveBeenCalledWith("s-matched")
        await waitFor(() => expect(trigger).toHaveTextContent("Matched"))
        const dot = trigger.querySelector('[data-slot="stage-dot"]') as HTMLElement
        expect(dot).toHaveStyle({ backgroundColor: "#6366F1" })
        expect(dot).toHaveAttribute("aria-hidden", "true")
    })

    it("renders group headings, separators and a popup sized to its content", async () => {
        render(
            <ControlledStageSelect
                initialValue="all"
                options={options}
                allLabel="All Stages"
                aria-label="Filter by stage"
            />
        )

        fireEvent.click(screen.getByRole("combobox", { name: "Filter by stage" }))
        const listbox = await screen.findByRole("listbox")

        const optionNames = within(listbox).getAllByRole("option").map((option) => option.textContent)
        expect(optionNames).toEqual(["All Stages", "New Unread", "Matched", "On-Hold", "Lost"])
        expect(within(listbox).getByText("Intake")).toHaveAttribute("data-slot", "select-label")
        expect(within(listbox).getByText("Post-approval")).toBeInTheDocument()
        expect(within(listbox).getByText("Paused & closed")).toBeInTheDocument()
        expect(listbox.querySelectorAll('[data-slot="select-separator"]')).toHaveLength(3)
        expect(within(listbox).getAllByRole("group")).toHaveLength(3)

        const popup = document.querySelector('[data-slot="select-content"]') as HTMLElement
        expect(popup).toHaveClass("w-max", "min-w-(--anchor-width)", "max-h-[min(28rem,var(--available-height))]")
        expect(popup).not.toHaveClass("w-(--anchor-width)")
    })

    it("shows the placeholder when a picker has no value and no all option", () => {
        render(
            <ControlledStageSelect
                initialValue=""
                options={options}
                id="bulk-stage"
                aria-label="Target stage"
            />
        )

        const trigger = screen.getByRole("combobox", { name: "Target stage" })
        expect(trigger).toHaveAttribute("id", "bulk-stage")
        expect(trigger).toHaveTextContent("Select a stage")
    })

    it("takes its name from a Label and carries the field error wiring", () => {
        render(
            <>
                <label htmlFor="bulk-stage">Stage</label>
                <ControlledStageSelect
                    initialValue=""
                    options={options}
                    id="bulk-stage"
                    aria-invalid
                    aria-describedby="bulk-stage-error"
                />
                <p id="bulk-stage-error">Select a stage</p>
            </>
        )

        const trigger = screen.getByRole("combobox", { name: "Stage" })
        expect(trigger).toHaveAttribute("aria-invalid", "true")
        expect(trigger).toHaveAccessibleDescription("Select a stage")
    })

    it("never shows a raw id for a stage that is no longer in the options", () => {
        render(
            <ControlledStageSelect
                initialValue="deleted-stage-id"
                options={options}
                allLabel="All Stages"
                aria-label="Filter by stage"
            />
        )

        const trigger = screen.getByRole("combobox", { name: "Filter by stage" })
        expect(trigger).toHaveTextContent("Unknown stage")
        expect(trigger).not.toHaveTextContent("deleted-stage-id")
    })

    it("renders counts and class-based dots for match statuses", async () => {
        render(
            <ControlledStageSelect
                initialValue="all"
                options={matchStatusStageOptions({ proposed: 8 })}
                allLabel="All Stages"
                aria-label="Filter by stage"
            />
        )

        fireEvent.click(screen.getByRole("combobox", { name: "Filter by stage" }))
        const proposed = await screen.findByRole("option", { name: /Proposed/ })
        expect(proposed).toHaveTextContent("8")
        const dot = proposed.querySelector('[data-slot="stage-dot"]')
        expect(dot).toHaveClass("bg-blue-500")
        // SelectItem's ItemText is a flex row without cross-axis centering; the dot, label and
        // count need their own centered row or the 8px dot sits at the top of the 20px line.
        const row = dot?.parentElement
        expect(row).toHaveClass("flex", "items-center")
        expect(row).toContainElement(screen.getByText("8"))
    })
})

describe("StageOptionLabel", () => {
    it("falls back to a muted dot when a stage has no color", () => {
        const option: StageOption = { value: "x", label: "Custom" }
        const { container } = render(<StageOptionLabel option={option} />)

        expect(screen.getByText("Custom")).toBeInTheDocument()
        expect(container.querySelector('[data-slot="stage-dot"]')).toHaveClass("bg-muted-foreground")
    })
})
