import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"

import { WizardStepper } from "@/components/automation/wizard-stepper"

const STEPS = ["Trigger", "Conditions", "Actions", "Review"] as const

describe("WizardStepper", () => {
    it("keeps the current step as wide as its label so it cannot overlap the next step", () => {
        render(<WizardStepper steps={STEPS} currentStep={2} />)

        const items = screen.getAllByRole("listitem")
        const current = items[1]
        expect(current).toHaveAttribute("aria-current", "step")
        expect(current).toHaveClass("min-w-fit")
        expect(current).not.toHaveClass("min-w-0")
        for (const item of [items[0], items[2], items[3]]) {
            expect(item).not.toHaveAttribute("aria-current")
            expect(item).toHaveClass("min-w-0")
        }
    })

    it("announces completed and current steps", () => {
        render(<WizardStepper steps={STEPS} currentStep={3} />)

        expect(screen.getAllByText("(completed)", { exact: false, selector: "span" })).toHaveLength(2)
        expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Actions (current step)")
    })
})
