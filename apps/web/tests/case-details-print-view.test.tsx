import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CaseDetailsPrintView } from "@/components/surrogates/detail/print/CaseDetailsPrintView"

describe("CaseDetailsPrintView", () => {
    it("shows medical information even when the old stage gate flag is absent", () => {
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
                            insurance_company: "Blue Shield",
                            insurance_plan_name: null,
                            insurance_policy_number: null,
                            insurance_member_id: null,
                            insurance_group_number: null,
                            insurance_phone: null,
                            insurance_subscriber_name: null,
                            insurance_subscriber_dob: null,
                            clinic_name: "Austin Fertility Center",
                            clinic_address_line1: null,
                            clinic_address_line2: null,
                            clinic_city: null,
                            clinic_state: null,
                            clinic_postal: null,
                            clinic_phone: null,
                            clinic_email: null,
                            monitoring_clinic_name: "Austin Monitoring",
                            monitoring_clinic_address_line1: null,
                            monitoring_clinic_address_line2: null,
                            monitoring_clinic_city: null,
                            monitoring_clinic_state: null,
                            monitoring_clinic_postal: null,
                            monitoring_clinic_phone: null,
                            monitoring_clinic_email: null,
                            ob_provider_name: null,
                            ob_clinic_name: null,
                            ob_address_line1: null,
                            ob_address_line2: null,
                            ob_city: null,
                            ob_state: null,
                            ob_postal: null,
                            ob_phone: null,
                            ob_email: null,
                            delivery_hospital_name: null,
                            delivery_hospital_address_line1: null,
                            delivery_hospital_address_line2: null,
                            delivery_hospital_city: null,
                            delivery_hospital_state: null,
                            delivery_hospital_postal: null,
                            delivery_hospital_phone: null,
                            delivery_hospital_email: null,
                            pregnancy_start_date: null,
                            pregnancy_due_date: null,
                            actual_delivery_date: null,
                            delivery_baby_gender: null,
                            delivery_baby_weight: null,
                        },
                        activities: [],
                        tasks: [],
                        show_pregnancy: false,
                    } as never
                }
            />,
        )

        expect(screen.getByText("Medical Information")).toBeInTheDocument()
        expect(screen.getByText("Austin Fertility Center")).toBeInTheDocument()
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
                    } as never
                }
            />,
        )

        expect(screen.getByText("Journey Timing")).toBeInTheDocument()
        expect(screen.getByText("0–3 months")).toBeInTheDocument()
        expect(screen.queryByText("Prior Surrogate Experience")).not.toBeInTheDocument()
    })
})
