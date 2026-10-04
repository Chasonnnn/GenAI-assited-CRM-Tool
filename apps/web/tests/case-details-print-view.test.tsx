import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CaseDetailsPrintView } from "@/components/surrogates/detail/print/CaseDetailsPrintView"

describe("CaseDetailsPrintView", () => {
    it("renders the header without helper copy and maps empty values and the source", () => {
        render(
            <CaseDetailsPrintView
                data={
                    {
                        surrogate: {
                            id: "sur-1",
                            surrogate_number: "S10001",
                            full_name: "Taylor Example",
                            email: "taylor@example.com",
                            phone: null,
                            state: null,
                            created_at: "2026-03-15T12:00:00Z",
                            date_of_birth: null,
                            race: null,
                            height_ft: null,
                            weight_lb: null,
                            bmi: null,
                            source: "manual",
                        },
                        activities: [],
                        tasks: [],
                        show_pregnancy: false,
                        medical_records: [],
                    } as never
                }
            />,
        )

        expect(screen.getByRole("heading", { level: 1, name: "Case Details" })).toBeInTheDocument()
        expect(screen.queryByText("Generated from current case data")).not.toBeInTheDocument()
        expect(screen.getByText("Manual")).toBeInTheDocument()
        expect(screen.queryByText("manual")).not.toBeInTheDocument()
        expect(screen.queryByText("-")).not.toBeInTheDocument()
        expect(screen.getAllByText("—").length).toBeGreaterThan(0)
    })

    it("renders each current medical record as its own section", () => {
        const record = {
            id: "rec-1",
            section: "clinic",
            status: "current",
            effective_date: "2026-01-05",
            end_date: null,
            source: "manual",
            provider_name: null,
            name: "Austin Fertility Center",
            address_line1: "100 Main St",
            address_line2: null,
            city: "Austin",
            state: "TX",
            postal: "78701",
            phone: null,
            fax: null,
            email: null,
            plan_name: null,
            policy_number: null,
            member_id: null,
            group_number: null,
            subscriber_name: null,
            subscriber_dob: null,
            archived_on: null,
            archived_by_name: null,
            revision: 1,
            created_by_name: "Case Manager",
            created_at: "2026-01-05T12:00:00Z",
            corrections: [],
        }
        render(
            <CaseDetailsPrintView
                data={
                    {
                        surrogate: {
                            id: "sur-1",
                            surrogate_number: "S10001",
                            full_name: "Taylor Example",
                            email: "taylor@example.com",
                            phone: null,
                            state: null,
                            created_at: "2026-03-15T12:00:00Z",
                            date_of_birth: null,
                            race: null,
                            height_ft: null,
                            weight_lb: null,
                            bmi: null,
                        },
                        activities: [],
                        tasks: [],
                        show_pregnancy: false,
                        medical_records: [
                            record,
                            { ...record, id: "rec-2", section: "insurance", name: "Blue Shield", subscriber_dob: "1990-05-14" },
                        ],
                    } as never
                }
            />,
        )

        const headings = screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)
        expect(headings.indexOf("Insurance")).toBeLessThan(headings.indexOf("IVF Clinic"))
        expect(screen.getByText("Austin Fertility Center")).toBeInTheDocument()
        expect(screen.getByText("100 Main St, Austin, TX, 78701")).toBeInTheDocument()
        expect(screen.getByText("Blue Shield")).toBeInTheDocument()
        expect(screen.getByText("May 14, 1990")).toBeInTheDocument()
        expect(screen.queryByText("Pregnancy Tracker")).not.toBeInTheDocument()
    })

    it("renders the API-provided eligibility checklist rows", () => {
        render(
            <CaseDetailsPrintView
                data={
                    {
                        surrogate: {
                            id: "sur-1",
                            surrogate_number: "S10001",
                            full_name: "Taylor Example",
                            email: "taylor@example.com",
                            phone: null,
                            state: null,
                            created_at: "2026-03-15T12:00:00Z",
                            date_of_birth: null,
                            race: null,
                            height_ft: null,
                            weight_lb: null,
                            bmi: null,
                            source: "manual",
                            has_surrogate_experience: true,
                            journey_timing_preference: null,
                            eligibility_checklist: [
                                {
                                    key: "is_age_eligible",
                                    label: "Age Eligible (21-36)",
                                    type: "boolean",
                                    value: true,
                                    display_value: "Yes",
                                },
                                {
                                    key: "journey_timing_preference",
                                    label: "Journey Timing",
                                    type: "text",
                                    value: "months_0_3",
                                    display_value: "0–3 months",
                                },
                            ],
                        },
                        activities: [],
                        tasks: [],
                        show_pregnancy: false,
                        medical_records: [],
                    } as never
                }
            />,
        )

        expect(screen.getByText("Journey Timing")).toBeInTheDocument()
        expect(screen.getByText("0–3 months")).toBeInTheDocument()
        expect(screen.queryByText("Prior Surrogate Experience")).not.toBeInTheDocument()
    })
})
