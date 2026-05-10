import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SortableTableHead } from "@/components/ui/sortable-table-head"

function renderHeader(onSort = vi.fn()) {
    render(
        <table>
            <thead>
                <tr>
                    <SortableTableHead
                        column="created_at"
                        label="Created"
                        currentSort="created_at"
                        currentOrder="asc"
                        onSort={onSort}
                    />
                </tr>
            </thead>
        </table>,
    )
    return onSort
}

describe("SortableTableHead", () => {
    it("sorts by its configured column when clicked", () => {
        const onSort = renderHeader()

        fireEvent.click(screen.getByRole("columnheader", { name: /created/i }))

        expect(onSort).toHaveBeenCalledWith("created_at")
    })
})
