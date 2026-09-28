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

const USER_ID = "7c0e5a52-7d7f-4cc4-9b1e-2d0f5c1a9e11"

function UserOptions() {
    return <SelectItem value={USER_ID}>Dana Lee</SelectItem>
}

describe("SelectValue never renders a raw stored value", () => {
    it("shows the muted placeholder while async options have not loaded", () => {
        const { rerender } = render(
            <Select value={USER_ID}>
                <SelectTrigger aria-label="Assignee">
                    <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>{[]}</SelectContent>
            </Select>
        )

        const trigger = screen.getByRole("combobox", { name: "Assignee" })
        expect(trigger).toHaveTextContent("Select a user")
        expect(trigger).not.toHaveTextContent(USER_ID)
        expect(trigger.querySelector('[data-slot="select-value-unresolved"]')).toHaveClass("text-muted-foreground")

        rerender(
            <Select value={USER_ID}>
                <SelectTrigger aria-label="Assignee">
                    <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value={USER_ID}>Dana Lee</SelectItem>
                </SelectContent>
            </Select>
        )
        expect(screen.getByRole("combobox", { name: "Assignee" })).toHaveTextContent("Dana Lee")
    })

    it("renders an empty trigger without a placeholder", () => {
        render(
            <Select value="post_approval">
                <SelectTrigger aria-label="Category">
                    <SelectValue />
                </SelectTrigger>
            </Select>
        )

        const trigger = screen.getByRole("combobox", { name: "Category" })
        expect(trigger).not.toHaveTextContent("post_approval")
        expect(trigger.querySelector('[data-slot="select-value"]')).toBeEmptyDOMElement()
    })

    it("does not leak the value when SelectItems render inside a custom child component", () => {
        render(
            <Select value={USER_ID}>
                <SelectTrigger aria-label="Assignee">
                    <SelectValue placeholder="Select a user" />
                </SelectTrigger>
                <SelectContent>
                    <UserOptions />
                </SelectContent>
            </Select>
        )

        const trigger = screen.getByRole("combobox", { name: "Assignee" })
        expect(trigger).not.toHaveTextContent(USER_ID)
        expect(trigger).toHaveTextContent("Select a user")
    })

    it("resolves labels from the root items prop, including grouped items", () => {
        const { rerender } = render(
            <Select value="post_approval" items={{ intake: "Intake", post_approval: "Post-approval" }}>
                <SelectTrigger aria-label="Category">
                    <SelectValue />
                </SelectTrigger>
            </Select>
        )
        expect(screen.getByRole("combobox", { name: "Category" })).toHaveTextContent("Post-approval")

        rerender(
            <Select
                value="terminal"
                items={[{ value: "closed", items: [{ value: "terminal", label: "Terminal" }] }]}
            >
                <SelectTrigger aria-label="Category">
                    <SelectValue />
                </SelectTrigger>
            </Select>
        )
        expect(screen.getByRole("combobox", { name: "Category" })).toHaveTextContent("Terminal")
    })

    it("keeps caller-provided children", () => {
        render(
            <Select value={USER_ID}>
                <SelectTrigger aria-label="Assignee">
                    <SelectValue placeholder="Select a user">{() => "Dana Lee"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                    <UserOptions />
                </SelectContent>
            </Select>
        )

        expect(screen.getByRole("combobox", { name: "Assignee" })).toHaveTextContent("Dana Lee")
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
