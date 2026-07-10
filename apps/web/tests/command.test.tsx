import { fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { describe, expect, it, vi } from "vitest"

import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command"

describe("Command", () => {
    it("supports controlled search text and pointer selection", () => {
        const onSelect = vi.fn()

        function Harness() {
            const [query, setQuery] = useState("")
            return (
                <Command shouldFilter={false}>
                    <CommandInput
                        aria-label="Search records"
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList>
                        <CommandGroup heading="Results">
                            <CommandItem value="surrogate-1" onSelect={() => onSelect("surrogate-1")}>
                                Jane Smith
                            </CommandItem>
                        </CommandGroup>
                    </CommandList>
                </Command>
            )
        }

        render(<Harness />)

        const input = screen.getByRole("combobox", { name: "Search records" })
        fireEvent.change(input, { target: { value: "Jane" } })
        expect(input).toHaveValue("Jane")

        const item = screen.getByRole("option", { name: /Jane Smith/i })
        fireEvent.mouseMove(item)
        fireEvent.click(item)
        expect(onSelect).toHaveBeenCalledWith("surrogate-1")
    })

    it("keeps empty-state content in the inline list", () => {
        render(
            <Command shouldFilter={false}>
                <CommandInput aria-label="Search variables" />
                <CommandList>
                    <CommandEmpty>No variables found.</CommandEmpty>
                </CommandList>
            </Command>,
        )

        expect(screen.getByRole("status")).toHaveTextContent("No variables found.")
    })

    it("selects the highlighted item with the keyboard", () => {
        const onSelect = vi.fn()
        render(
            <Command shouldFilter={false}>
                <CommandInput aria-label="Search commands" />
                <CommandList>
                    <CommandItem value="first" onSelect={onSelect}>First result</CommandItem>
                    <CommandItem value="second" onSelect={onSelect}>Second result</CommandItem>
                </CommandList>
            </Command>,
        )

        const input = screen.getByRole("combobox", { name: "Search commands" })
        input.focus()
        fireEvent.keyDown(input, { key: "ArrowDown" })
        fireEvent.keyDown(input, { key: "Enter" })

        expect(onSelect).toHaveBeenCalledWith("first")
    })
})
