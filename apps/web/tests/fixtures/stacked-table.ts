import { within } from "@testing-library/react"
import { expect } from "vitest"

/**
 * A table that stacks below sm must keep its column headers in the accessibility tree.
 * jsdom ignores media queries, so this checks the markup instead of the rendered width.
 */
export function expectStackedTableSemantics(table: HTMLElement, headers: string[]) {
    expect(table).toHaveAttribute("role", "table")
    const thead = table.querySelector("thead")
    expect(thead).not.toBeNull()
    expect(thead).not.toHaveAttribute("aria-hidden")
    expect(thead?.className ?? "").not.toMatch(/(^|\s)([\w-]+:)*hidden(\s|$)/)
    expect(thead).toHaveClass("max-sm:sr-only")
    expect(getComputedStyle(thead as HTMLElement).display).not.toBe("none")
    expect(within(table).getAllByRole("columnheader").map((header) => header.textContent)).toEqual(headers)
    for (const row of within(table).getAllByRole("row")) expect(row).toHaveAttribute("role", "row")
    for (const cell of within(table).getAllByRole("cell")) expect(cell).toHaveAttribute("role", "cell")
}
