import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { SurrogateHistoryTab } from "@/components/surrogates/detail/SurrogateHistoryTab"

const formatDateTime = (value: string) => `formatted ${value}`

describe("SurrogateHistoryTab", () => {
    it("shows empty state when there are no activities", () => {
        render(<SurrogateHistoryTab activities={[]} formatDateTime={formatDateTime} />)

        expect(screen.getByText("Activity Log")).toBeInTheDocument()
        expect(screen.getByText("No activity recorded.")).toBeInTheDocument()
    })

    it("renders activity entries with details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a1",
                        activity_type: "status_changed",
                        actor_name: "Alex",
                        created_at: "2024-01-01T00:00:00Z",
                        details: { from: "New", to: "Contacted", reason: "Phone" },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Status Changed")).toBeInTheDocument()
        expect(screen.getByText("Alex • formatted 2024-01-01T00:00:00Z")).toBeInTheDocument()
        expect(screen.getByText("New → Contacted: Phone")).toBeInTheDocument()
    })
})
