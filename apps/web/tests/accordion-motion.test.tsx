import { fireEvent, render, screen } from "@testing-library/react"
import type { ComponentProps } from "react"
import { describe, expect, it } from "vitest"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"

function renderAccordion(props: ComponentProps<typeof Accordion>) {
    return render(
        <Accordion {...props}>
            <AccordionItem value="variables">
                <AccordionTrigger>Variables</AccordionTrigger>
                <AccordionContent className="space-y-4">Variable fields</AccordionContent>
            </AccordionItem>
        </Accordion>,
    )
}

describe("Accordion motion", () => {
    it("animates height on the panel element that Base UI sizes", () => {
        renderAccordion({ defaultValue: ["variables"] })

        const panel = screen.getByRole("region")
        expect(panel.style.getPropertyValue("--accordion-panel-height")).not.toBe("")
        expect(panel).toHaveClass(
            "h-(--accordion-panel-height)",
            "data-starting-style:h-0",
            "data-ending-style:h-0",
            "overflow-hidden",
            "transition-[height]",
            "duration-200",
            "ease-smooth-out",
        )
        expect(panel.className).not.toMatch(/animate-accordion/)

        const body = screen.getByText("Variable fields")
        expect(body).toHaveClass("pb-4", "space-y-4")
        expect(body.className).not.toMatch(/accordion-panel-height|data-(starting|ending)-style/)
    })

    it("keeps a hidden-until-found panel collapsed through its starting style", () => {
        renderAccordion({ defaultValue: [], hiddenUntilFound: true })

        const panel = document.querySelector('[data-slot="accordion-content"]')
        expect(panel).toHaveAttribute("hidden", "until-found")
        expect(panel).toHaveAttribute("data-starting-style")
        expect(panel).toHaveClass("data-starting-style:h-0")
    })

    it("rotates one chevron with the trigger's open state", () => {
        renderAccordion({ defaultValue: [] })

        const trigger = screen.getByRole("button", { name: "Variables" })
        expect(trigger).toHaveClass("group/accordion-trigger")
        expect(trigger).not.toHaveAttribute("data-panel-open")
        expect(trigger.querySelectorAll("svg")).toHaveLength(1)

        const icon = trigger.querySelector("svg")
        expect(icon).toHaveClass(
            "lucide-chevron-down",
            "group-data-panel-open/accordion-trigger:rotate-180",
            "transition-transform",
        )
        expect(icon).toHaveAttribute("aria-hidden", "true")

        fireEvent.click(trigger)

        expect(trigger).toHaveAttribute("data-panel-open")
        expect(trigger.querySelectorAll("svg")).toHaveLength(1)
        expect(trigger.querySelector("svg")).toBe(icon)
    })
})
