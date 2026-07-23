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
                            attempted_at: "2024-01-01T09:30:00Z",
                            note_preview: "Left voicemail requesting callback",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Contact Attempt")).toBeInTheDocument()
        expect(screen.getByText("No Answer")).toBeInTheDocument()
        expect(screen.queryByText(/phone: no answer/i)).not.toBeInTheDocument()
        expect(screen.getByText(/phone/i)).toBeInTheDocument()
        expect(screen.getByText(/attempted:/i)).toBeInTheDocument()
        expect(screen.getByText(/left voicemail requesting callback/i)).toBeInTheDocument()
    })

    it("renders interview outcome details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-interview",
                        activity_type: "interview_outcome_logged",
                        actor_name: "Alex",
                        created_at: "2024-01-05T00:00:00Z",
                        details: {
                            outcome: "no_show",
                            occurred_at: "2024-01-04T16:30:00Z",
                            scheduled_start: "2024-01-04T16:00:00Z",
                            scheduled_end: "2024-01-04T16:30:00Z",
                            notes: "Did not join the call.",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Interview Outcome Logged")).toBeInTheDocument()
        expect(screen.getByText("No Show")).toBeInTheDocument()
        expect(screen.queryByText(/outcome: no show/i)).not.toBeInTheDocument()
        expect(screen.getByText(/occurred:/i)).toBeInTheDocument()
        expect(screen.getByText(/appointment:/i)).toBeInTheDocument()
        expect(screen.getByText(/did not join the call/i)).toBeInTheDocument()
    })

    it("renders upcoming interview appointment details from stage changes", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-interview-scheduled",
                        activity_type: "interview_scheduled",
                        actor_name: "Alex",
                        created_at: "2026-05-30T12:00:00Z",
                        details: {
                            source: "stage_change",
                            appointment_id: "appt-1",
                            scheduled_start: "2026-06-01T17:15:00Z",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Interview Scheduled")).toBeInTheDocument()
        expect(screen.getByText("Upcoming")).toBeInTheDocument()
        expect(screen.getByText(/appointment:/i)).toBeInTheDocument()
        expect(screen.getByText("Appointment: formatted 2026-06-01T17:15:00Z")).toBeInTheDocument()
        expect(screen.queryByText(/initial interview/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/^type:/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/^mode:/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/1:45 pm/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/stage_change/i)).not.toBeInTheDocument()
    })

    it("renders backdated stage change timing details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-stage",
                        activity_type: "status_changed",
                        actor_name: "Alex",
                        created_at: "2024-01-06T00:00:00Z",
                        details: {
                            from: "New Unread",
                            to: "Contacted",
                            effective_at: "2024-01-03T12:00:00Z",
                            recorded_at: "2024-01-06T00:00:00Z",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/new unread → contacted/i)).toBeInTheDocument()
        expect(screen.getByText(/effective:/i)).toBeInTheDocument()
        expect(screen.getByText(/recorded:/i)).toBeInTheDocument()
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

    it("renders email template name instead of template uuid", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-email-template-name",
                        activity_type: "email_sent",
                        actor_name: "System",
                        created_at: "2024-01-04T00:00:00Z",
                        details: {
                            subject: "Welcome",
                            provider: "resend",
                            template_id: "392d2938-69a0-4840-8e4e-acd84e6064d1",
                            template_name: "New Lead Welcome",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/template new lead welcome/i)).toBeInTheDocument()
        expect(
            screen.queryByText(/392d2938-69a0-4840-8e4e-acd84e6064d1/i)
        ).not.toBeInTheDocument()
    })

    it("renders Resend delivery and engagement details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-email-engagement",
                        activity_type: "email_sent",
                        actor_name: "System",
                        created_at: "2026-07-21T14:00:00Z",
                        details: {
                            subject: "Welcome",
                            provider: "resend",
                            delivery_status: "delivered",
                            delivered_at: "2026-07-21T14:03:00Z",
                            open_count: 2,
                            opened_at: "2026-07-21T14:08:00Z",
                            click_count: 1,
                            clicked_at: "2026-07-21T14:12:00Z",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/delivered/i)).toBeInTheDocument()
        expect(screen.getByText(/2 opens/i)).toBeInTheDocument()
        expect(screen.getByText(/1 click/i)).toBeInTheDocument()
        expect(screen.getByText(/open tracking is approximate/i)).toBeInTheDocument()
    })

    it("renders queue names in queue activity details", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a4",
                        activity_type: "surrogate_assigned_to_queue",
                        actor_name: "Niki",
                        created_at: "2024-01-04T00:00:00Z",
                        details: {
                            to_queue_id: "cd46256e-59b2-49a8-8a38-60672137289c",
                            to_queue_name: "Unassigned",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/assigned to unassigned/i)).toBeInTheDocument()
        expect(
            screen.queryByText(/cd46256e-59b2-49a8-8a38-60672137289c/i)
        ).not.toBeInTheDocument()
    })

    it("renders assigned activity with clear from/to user names", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-assigned",
                        activity_type: "assigned",
                        actor_name: "Janet Zhu",
                        created_at: "2026-03-01T20:27:00Z",
                        details: {
                            from_user_id: "71f5b271-8f48-4a88-bdc5-2b53f6b8fbd4",
                            from_user_name: "Cam Lee",
                            to_user_id: "5db7dfe0-c52b-4f58-a4b5-2fef9441bdb5",
                            to_user_name: "Niki Torres",
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Assigned")).toBeInTheDocument()
        expect(screen.getByText(/janet zhu/i)).toBeInTheDocument()
        expect(screen.getByText(/reassigned from cam lee to niki torres/i)).toBeInTheDocument()
    })

    it("formats edited height and weight like overview", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a5",
                        activity_type: "info_edited",
                        actor_name: "Janet",
                        created_at: "2024-01-05T00:00:00Z",
                        details: {
                            changes: {
                                height_ft: 5.6,
                                weight_lb: 142,
                            },
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/height: 5 ft 7 in/i)).toBeInTheDocument()
        expect(screen.getByText(/weight: 142 lb/i)).toBeInTheDocument()
    })

    it("renders sensitive edit action summaries without redacted value noise", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-sensitive-edit",
                        activity_type: "info_edited",
                        actor_name: "Niki",
                        created_at: "2024-01-06T00:00:00Z",
                        details: {
                            changes: {
                                email: { action: "updated" },
                                ssn: { action: "cleared" },
                            },
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/email: updated/i)).toBeInTheDocument()
        expect(screen.getByText(/ssn: cleared/i)).toBeInTheDocument()
        expect(screen.queryByText(/redacted/i)).not.toBeInTheDocument()
    })

    it("renders old scalar redacted activity rows as updated", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-old-redacted",
                        activity_type: "info_edited",
                        actor_name: "Niki",
                        created_at: "2024-01-07T00:00:00Z",
                        details: {
                            changes: {
                                email: "[redacted]",
                            },
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText(/email: updated/i)).toBeInTheDocument()
        expect(screen.queryByText(/redacted/i)).not.toBeInTheDocument()
    })

    it("renders sensitive reveal events without field values", () => {
        render(
            <SurrogateHistoryTab
                activities={[
                    {
                        id: "a-reveal",
                        activity_type: "sensitive_info_revealed",
                        actor_name: "Niki",
                        created_at: "2024-01-08T00:00:00Z",
                        details: {
                            fields: ["ssn", "date_of_birth"],
                        },
                    },
                ]}
                formatDateTime={formatDateTime}
            />
        )

        expect(screen.getByText("Sensitive Info Revealed")).toBeInTheDocument()
        expect(screen.getByText(/ssn: revealed/i)).toBeInTheDocument()
        expect(screen.getByText(/date of birth: revealed/i)).toBeInTheDocument()
    })
})
