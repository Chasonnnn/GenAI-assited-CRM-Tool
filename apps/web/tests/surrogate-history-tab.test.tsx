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

    it("shows contact note preview for contact attempt entries", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a2",
                        activity_type: "contact_attempt",
                        actor_name: "Alex",
                        created_at: "2024-01-02T00:00:00Z",
                        details: {
                            contact_methods: ["phone"],
                            outcome: "no_answer",
                            note_preview: "Left voicemail requesting callback",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Contact Attempt")).toBeInTheDocument()
        expect(screen.getByText(/phone: no answer/i)).toBeInTheDocument()
        expect(screen.getByText(/left voicemail requesting callback/i)).toBeInTheDocument()
    })

    it("renders email bounced activity details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a3",
                        activity_type: "email_bounced",
                        actor_name: "System",
                        created_at: "2024-01-03T00:00:00Z",
                        details: {
                            subject: "Welcome to EWI",
                            reason: "bounced",
                            bounce_type: "hard",
                            provider: "resend",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Email Bounced")).toBeInTheDocument()
        expect(screen.getByText(/subject: welcome to ewi/i)).toBeInTheDocument()
        expect(screen.getByText(/reason: bounced/i)).toBeInTheDocument()
        expect(screen.getByText(/hard bounce/i)).toBeInTheDocument()
        expect(screen.getByText(/via resend/i)).toBeInTheDocument()
    })
})
