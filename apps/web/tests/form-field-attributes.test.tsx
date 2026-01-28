import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Command, CommandInput } from "@/components/ui/command"

describe("form field identifiers", () => {
    it("assigns an id to Input when missing", () => {
        render(<Input />)
        const input = screen.getByRole("textbox")
        expect(input).toHaveAttribute("id")
        expect(input.getAttribute("id")).not.toBe("")
    })

    it("keeps provided id on Input", () => {
        render(<Input id="email" />)
        const input = screen.getByRole("textbox")
        expect(input).toHaveAttribute("id", "email")
    })

    it("assigns an id to Textarea when missing", () => {
        render(<Textarea />)
        const textarea = screen.getByRole("textbox")
        expect(textarea).toHaveAttribute("id")
        expect(textarea.getAttribute("id")).not.toBe("")
    })

    it("assigns an id to CommandInput when missing", () => {
        render(
            <Command>
                <CommandInput placeholder="Search" />
            </Command>
        )
        const input = screen.getByPlaceholderText("Search")
        expect(input).toHaveAttribute("id")
        expect(input.getAttribute("id")).not.toBe("")
    })
})
