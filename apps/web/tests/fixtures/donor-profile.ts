import type { DonorProfile } from "@/lib/types/donor-profile"

export const donorProfileFixture: DonorProfile = {
    "marital_status": null,
    "address_line1": null,
    "address_line2": null,
    "address_city": null,
    "address_state": null,
    "address_postal": null,
    "partner_name": null,
    "partner_date_of_birth": null,
    "partner_email": null,
    "partner_phone": null,
    "partner_address_line1": null,
    "partner_address_line2": null,
    "partner_city": null,
    "partner_state": null,
    "partner_postal": null,
    "date_of_birth": "2000-05-14",
    "race": "Asian",
    "height_ft": "5.5",
    "weight_lb": 135,
    "education": "B.S. Biology",
    "college": null,
    "nicotine": null,
    "cannabis": null,
    "infectious_disease": null,
    "previous_donation": null,
    "ssn_masked": null,
    "partner_ssn_masked": null,
    "eligibility_checklist": [
        {
            "key": "education",
            "label": "Education level",
            "question": "Highest education level",
            "value": "B.S. Biology",
            "options": [
                {
                    "value": "High school",
                    "label": "High school"
                },
                {
                    "value": "Some college",
                    "label": "Some college"
                },
                {
                    "value": "Associate degree",
                    "label": "Associate degree"
                },
                {
                    "value": "Bachelor’s degree",
                    "label": "Bachelor’s degree"
                },
                {
                    "value": "Master’s degree",
                    "label": "Master’s degree"
                },
                {
                    "value": "Doctorate / professional degree",
                    "label": "Doctorate / professional degree"
                },
                {
                    "value": "Other",
                    "label": "Other"
                }
            ]
        },
        {
            "key": "college",
            "label": "University / college",
            "question": "University / college",
            "value": null,
            "options": []
        },
        {
            "key": "nicotine",
            "label": "Nicotine / tobacco use",
            "question": "Do you currently use nicotine or tobacco products?",
            "value": null,
            "options": [
                {
                    "value": "Yes",
                    "label": "Yes"
                },
                {
                    "value": "No",
                    "label": "No"
                }
            ]
        },
        {
            "key": "cannabis",
            "label": "Cannabis use",
            "question": "Do you currently use cannabis?",
            "value": null,
            "options": [
                {
                    "value": "Yes",
                    "label": "Yes"
                },
                {
                    "value": "No",
                    "label": "No"
                }
            ]
        },
        {
            "key": "infectious_disease",
            "label": "Infectious disease / STI history",
            "question": "Have you ever had an infectious disease such as HIV, hepatitis B/C, or an STI?",
            "value": null,
            "options": [
                {
                    "value": "Yes",
                    "label": "Yes"
                },
                {
                    "value": "No",
                    "label": "No"
                },
                {
                    "value": "Prefer to discuss with the team",
                    "label": "Prefer to discuss with the team"
                }
            ]
        },
        {
            "key": "previous_donation",
            "label": "Previous donation",
            "question": "Have you been an egg or sperm donor before?",
            "value": null,
            "options": [
                {
                    "value": "Yes",
                    "label": "Yes"
                },
                {
                    "value": "No",
                    "label": "No"
                }
            ]
        }
    ]
}
