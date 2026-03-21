import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Select, SelectTrigger, SelectValue } from "@/components/ui/select"

describe("SelectValue", () => {
    it("shows the selected item label instead of the raw stored value", () => {
        render(
            <Select
                items={[
                    { value: "active", label: "Active" },
                    { value: "past_due", label: "Past Due" },
                ]}
                defaultValue="past_due"
            >
                <SelectTrigger>
                    <SelectValue placeholder="All statuses" />
                </SelectTrigger>
            </Select>
        )

        expect(screen.getByText("Past Due")).toBeInTheDocument()
        expect(screen.queryByText(/^past_due$/)).not.toBeInTheDocument()
    })

    it("still supports explicit render functions for custom trigger labels", () => {
        render(
            <Select defaultValue="past_due">
                <SelectTrigger>
                    <SelectValue placeholder="All statuses">
                        {(value: string | null) => (value === "past_due" ? "Past Due Review" : "All statuses")}
                    </SelectValue>
                </SelectTrigger>
            </Select>
        )

        expect(screen.getByText("Past Due Review")).toBeInTheDocument()
    })
})
