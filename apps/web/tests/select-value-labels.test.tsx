import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { createSelectLabelGetter, getSelectLabel, toSelectOptions } from "@/lib/select-labels"

const OUTCOMES = [
    { value: "reached", label: "Reached" },
    { value: "no_answer", label: "No answer" },
]

function OutcomeSelect({ value, placeholder }: { value: string | null; placeholder?: string }) {
    return (
        <Select value={value}>
            <SelectTrigger aria-label="Outcome">
                <SelectValue {...(placeholder ? { placeholder } : {})} />
            </SelectTrigger>
            <SelectContent>
                {OUTCOMES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                        {option.label}
                    </SelectItem>
                ))}
            </SelectContent>
        </Select>
    )
}

describe("SelectValue placeholder", () => {
    it("shows the placeholder for an empty-string value instead of Unknown selection", () => {
        render(<OutcomeSelect value="" placeholder="Select outcome" />)

        const trigger = screen.getByRole("combobox", { name: "Outcome" })
        expect(trigger).toHaveTextContent("Select outcome")
        expect(trigger).not.toHaveTextContent("Unknown selection")
        expect(trigger).toHaveAttribute("data-placeholder")
    })

    it("shows the placeholder for a null value", () => {
        render(<OutcomeSelect value={null} placeholder="Select outcome" />)

        expect(screen.getByRole("combobox", { name: "Outcome" })).toHaveTextContent("Select outcome")
    })

    it("still shows the item label for a matching value and flags unknown values", () => {
        const { unmount } = render(<OutcomeSelect value="no_answer" placeholder="Select outcome" />)
        expect(screen.getByRole("combobox", { name: "Outcome" })).toHaveTextContent("No answer")
        unmount()

        render(<OutcomeSelect value="09:00:00" placeholder="Select outcome" />)
        expect(screen.getByRole("combobox", { name: "Outcome" })).toHaveTextContent("Unknown selection")
    })

    it("keeps an explicit empty-value item's label over the placeholder", () => {
        render(
            <Select value="">
                <SelectTrigger aria-label="Stage">
                    <SelectValue placeholder="Stage" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="">Any stage</SelectItem>
                    <SelectItem value="s1">Contacted</SelectItem>
                </SelectContent>
            </Select>
        )

        expect(screen.getByRole("combobox", { name: "Stage" })).toHaveTextContent("Any stage")
    })

    it("falls back to the placeholder when a render function returns a blank label", () => {
        render(
            <Select value="">
                <SelectTrigger aria-label="Model">
                    <SelectValue placeholder="Default model">{(value: string | null) => value ?? ""}</SelectValue>
                </SelectTrigger>
            </Select>
        )

        expect(screen.getByRole("combobox", { name: "Model" })).toHaveTextContent("Default model")
    })

    it("keeps a render function's own label for the empty state", () => {
        const getStageLabel = createSelectLabelGetter(
            [{ value: "s1", label: "Contacted" }],
            { emptyLabel: "All Stages", allValue: "all" }
        )
        render(
            <Select value="all">
                <SelectTrigger aria-label="Stage">
                    <SelectValue placeholder="Stage">{getStageLabel}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Stages</SelectItem>
                    <SelectItem value="s1">Contacted</SelectItem>
                </SelectContent>
            </Select>
        )

        expect(screen.getByRole("combobox", { name: "Stage" })).toHaveTextContent("All Stages")
    })
})

describe("select label helpers", () => {
    const CATEGORY_LABELS = {
        intake: "Intake",
        post_approval: "Post-approval",
        terminal: "Terminal",
    } as const

    it("maps empty values and the all sentinel to the empty label", () => {
        const options = { emptyLabel: "All categories", allValue: "all" }
        expect(getSelectLabel(null, CATEGORY_LABELS, options)).toBe("All categories")
        expect(getSelectLabel("", CATEGORY_LABELS, options)).toBe("All categories")
        expect(getSelectLabel("all", CATEGORY_LABELS, options)).toBe("All categories")
    })

    it("maps known keys to labels and never returns a raw key", () => {
        const getCategoryLabel = createSelectLabelGetter(CATEGORY_LABELS, {
            emptyLabel: "Select category",
            unknownLabel: "Unknown category",
        })

        expect(getCategoryLabel("post_approval")).toBe("Post-approval")
        expect(getCategoryLabel("paused")).toBe("Unknown category")
        expect(getCategoryLabel("constructor")).toBe("Unknown category")
        expect(getSelectLabel("x", [], { emptyLabel: "Any" })).toBe("Unknown selection")
    })

    it("builds items from the same label map in order", () => {
        expect(toSelectOptions(CATEGORY_LABELS)).toEqual([
            { value: "intake", label: "Intake" },
            { value: "post_approval", label: "Post-approval" },
            { value: "terminal", label: "Terminal" },
        ])
    })
})
