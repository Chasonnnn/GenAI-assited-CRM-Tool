import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { InputGroup, InputGroupAddon } from "@/components/ui/input-group"

describe("InputGroup", () => {
  it("keeps decorative addons out of the tab order while preserving pointer focus", () => {
    const { container } = render(
      <InputGroup>
        <input aria-label="Search" />
        <InputGroupAddon>Search</InputGroupAddon>
      </InputGroup>
    )

    const input = screen.getByLabelText("Search")
    const addon = container.querySelector('[data-slot="input-group-addon"]')

    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(addon).toBeInTheDocument()
    expect(addon).not.toHaveAttribute("tabindex")

    fireEvent.pointerDown(addon!)

    expect(input).toHaveFocus()
  })
})
