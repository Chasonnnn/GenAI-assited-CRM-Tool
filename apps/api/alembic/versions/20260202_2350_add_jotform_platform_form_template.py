"""Seed Jotform surrogate intake platform form template.

Revision ID: 20260202_2350
Revises: 20260202_2315
Create Date: 2026-02-02 23:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260202_2350"
down_revision: Union[str, Sequence[str], None] = "20260202_2315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_NAME = "Jotform Surrogate Intake"
TEMPLATE_DESCRIPTION = "Template based on the Jotform surrogate intake form."
COMPLIANCE_NOTICE = (
    "By submitting this form, you consent to the collection and use of your information, "
    "including health-related details, for eligibility review and care coordination. "
    "Access is limited to authorized staff and retained per policy."
)

YES_NO = ["Yes", "No"]
YES_NO_UNSURE = ["Yes", "No", "Not sure"]
BLOOD_TYPE = ["A", "B", "AB", "O"]
RH_FACTOR = ["Positive", "Negative", "Unknown"]
PREGNANCY_CONDITIONS = [
    "Gestational diabetes",
    "Preeclampsia",
    "Preterm labor",
    "Placenta previa",
    "Other complications",
]
DISEASE_OPTIONS = ["HIV", "Hepatitis B", "Hepatitis C", "Herpes", "Syphilis", "Other"]
IP_TYPE_OPTIONS = ["Heterosexual couple", "Same-sex couple", "Single parent", "Not sure"]


def _options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _schema() -> dict:
    return {
        "pages": [
            {
                "title": "Personal Info",
                "fields": [
                    {"key": "first_name", "label": "First Name", "type": "text", "required": True},
                    {"key": "last_name", "label": "Last Name", "type": "text", "required": True},
                    {
                        "key": "date_of_birth",
                        "label": "Date of Birth",
                        "type": "date",
                        "required": True,
                    },
                    {
                        "key": "height_ft",
                        "label": "Height",
                        "type": "number",
                        "help_text": "Feet (e.g., 5.5).",
                    },
                    {
                        "key": "weight_lb",
                        "label": "Weight",
                        "type": "number",
                        "help_text": "Pounds.",
                    },
                    {"key": "email", "label": "Email", "type": "email", "required": True},
                    {
                        "key": "cell_phone",
                        "label": "Phone Number",
                        "type": "phone",
                        "required": True,
                    },
                    {
                        "key": "address_line_1",
                        "label": "Home Address",
                        "type": "text",
                        "required": True,
                    },
                    {"key": "address_line_2", "label": "Street Address Line 2", "type": "text"},
                    {"key": "city", "label": "City", "type": "text", "required": True},
                    {"key": "state", "label": "State", "type": "text", "required": True},
                    {"key": "postal_code", "label": "Zip Code", "type": "text", "required": True},
                ],
            },
            {
                "title": "Eligibility & Background",
                "fields": [
                    {
                        "key": "covid_vaccine_received",
                        "label": "Have you received Covid vaccine in the past?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "covid_vaccine_when",
                        "label": "If yes, when?",
                        "type": "date",
                        "help_text": "Date of your most recent vaccine.",
                        "show_if": {
                            "field_key": "covid_vaccine_received",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "covid_vaccine_willing",
                        "label": "If no, are you willing to receive Covid vaccine?",
                        "type": "radio",
                        "options": _options(YES_NO),
                        "show_if": {
                            "field_key": "covid_vaccine_received",
                            "operator": "equals",
                            "value": "No",
                        },
                    },
                    {
                        "key": "tattoos_past_year",
                        "label": "Have you received any tattoos in the past year?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "tattoo_last_date",
                        "label": "Please list date of your last tattoo",
                        "type": "date",
                        "show_if": {
                            "field_key": "tattoos_past_year",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "religion_yes_no",
                        "label": "Do you have any religions?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "religion_detail",
                        "label": "If yes, please specify your religion",
                        "type": "text",
                        "show_if": {
                            "field_key": "religion_yes_no",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "us_citizen",
                        "label": "Are you a US citizen or permanent resident?",
                        "type": "radio",
                        "required": True,
                        "options": _options(YES_NO),
                    },
                    {"key": "race", "label": "What is your race?", "type": "text"},
                    {"key": "sexual_orientation", "label": "Sexual Orientation", "type": "text"},
                    {
                        "key": "marital_status",
                        "label": "Marital status",
                        "type": "text",
                        "help_text": "Single, married, partnered, divorced, etc.",
                    },
                    {
                        "key": "marriage_date",
                        "label": "If married, date of marriage",
                        "type": "date",
                    },
                    {
                        "key": "biological_children_count",
                        "label": "How many biological children do you have?",
                        "type": "number",
                        "help_text": "Enter 0 if none.",
                    },
                    {
                        "key": "languages_spoken",
                        "label": "What languages do you speak?",
                        "type": "text",
                    },
                    {
                        "key": "schedule_flexible",
                        "label": "Is your daily schedule flexible?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "drivers_license",
                        "label": "Do you have a valid driver's license?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "transportation",
                        "label": "Do you have reliable transportation?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "car_insurance",
                        "label": "Do you have car insurance?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "health_insurance_carrier",
                        "label": "Name of health insurance carrier?",
                        "type": "text",
                    },
                    {
                        "key": "arrested",
                        "label": "Have you been arrested?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "arrested_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {"field_key": "arrested", "operator": "equals", "value": "Yes"},
                    },
                    {
                        "key": "legal_cases_pending",
                        "label": "Are you currently involved in any legal cases that are pending?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "legal_cases_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "legal_cases_pending",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "government_assistance",
                        "label": "Do you receive any government assistance (WIC, Medicaid, Food Stamps, Disability)?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "government_assistance_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "government_assistance",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                ],
            },
            {
                "title": "Education & Employment",
                "fields": [
                    {
                        "key": "education_level",
                        "label": "Highest level of education completed?",
                        "type": "text",
                    },
                    {
                        "key": "further_education_plans",
                        "label": "Do you plan on furthering your education?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "further_education_details",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "further_education_plans",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "currently_employed",
                        "label": "Are you currently employed?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "employer_title",
                        "label": "If yes, present employer and title",
                        "type": "text",
                        "show_if": {
                            "field_key": "currently_employed",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "employment_duration",
                        "label": "How long have you been employed there?",
                        "type": "text",
                        "show_if": {
                            "field_key": "currently_employed",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                ],
            },
            {
                "title": "Pregnancy Information",
                "fields": [
                    {
                        "key": "pregnancy_list",
                        "label": "List of pregnancies",
                        "type": "repeatable_table",
                        "help_text": (
                            "Include: own/surrogacy, # babies, delivery date, vaginal/C-section, "
                            "gender, weight, weeks at birth, complications."
                        ),
                        "columns": [
                            {
                                "key": "preg_type",
                                "label": "Type",
                                "type": "select",
                                "required": True,
                                "options": _options(["Own", "Surrogacy"]),
                            },
                            {
                                "key": "babies",
                                "label": "# Babies",
                                "type": "number",
                                "required": True,
                            },
                            {"key": "delivery_date", "label": "Delivery Date", "type": "date"},
                            {
                                "key": "delivery_type",
                                "label": "Delivery Type",
                                "type": "select",
                                "options": _options(["Vaginal", "C-Section"]),
                            },
                            {"key": "gender", "label": "Gender", "type": "text"},
                            {"key": "weight", "label": "Birth Weight", "type": "text"},
                            {"key": "weeks", "label": "Weeks at Birth", "type": "number"},
                            {"key": "complications", "label": "Complications", "type": "text"},
                        ],
                    },
                    {
                        "key": "had_abortion",
                        "label": "Have you ever had an abortion?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "abortion_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "had_abortion",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "had_miscarriage",
                        "label": "Have you ever had a miscarriage?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "miscarriage_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "had_miscarriage",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "pregnancy_conditions",
                        "label": "Have you ever experienced the following conditions?",
                        "type": "checkbox",
                        "options": _options(PREGNANCY_CONDITIONS),
                    },
                    {
                        "key": "pregnancy_conditions_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "pregnancy_conditions",
                            "operator": "is_not_empty",
                            "value": "",
                        },
                    },
                    {
                        "key": "breastfeeding",
                        "label": "Are you currently breastfeeding?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "breastfeeding_stop",
                        "label": "If yes, when do you plan to stop?",
                        "type": "text",
                        "show_if": {
                            "field_key": "breastfeeding",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "sexually_active",
                        "label": "Are you sexually active?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "birth_control",
                        "label": "Are you using birth control?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "birth_control_type",
                        "label": "If yes, what kind?",
                        "type": "text",
                        "show_if": {
                            "field_key": "birth_control",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "regular_cycles",
                        "label": "Do you have regular monthly menstrual cycles?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "irregular_cycles_detail",
                        "label": "If no, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "regular_cycles",
                            "operator": "equals",
                            "value": "No",
                        },
                    },
                    {
                        "key": "last_obgyn_visit",
                        "label": "When did you last see your Ob/Gyn?",
                        "type": "date",
                    },
                    {
                        "key": "last_pap_smear",
                        "label": "Date of last Pap Smear and result?",
                        "type": "text",
                    },
                    {
                        "key": "reproductive_illnesses",
                        "label": "List any reproductive illness you have experienced",
                        "type": "textarea",
                    },
                ],
            },
            {
                "title": "Family Support",
                "fields": [
                    {
                        "key": "spouse_significant_other",
                        "label": "Do you have a spouse/significant other?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "spouse_occupation",
                        "label": "If yes, what is your spouse/significant other's occupation?",
                        "type": "text",
                        "show_if": {
                            "field_key": "spouse_significant_other",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "family_support",
                        "label": "Does your family support your decision to become a surrogate?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "bed_rest_help",
                        "label": "Who would help you if placed on bed rest?",
                        "type": "textarea",
                    },
                    {
                        "key": "anticipate_difficulties",
                        "label": "Do you anticipate any difficulties in becoming a surrogate?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "difficulties_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "anticipate_difficulties",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "living_conditions",
                        "label": "Describe your current living conditions",
                        "type": "textarea",
                    },
                    {
                        "key": "household_members",
                        "label": "List everyone living in household with you, including age and relationship",
                        "type": "repeatable_table",
                        "columns": [
                            {
                                "key": "member_name",
                                "label": "Name",
                                "type": "text",
                                "required": True,
                            },
                            {
                                "key": "member_age",
                                "label": "Age",
                                "type": "number",
                                "required": True,
                            },
                            {
                                "key": "relationship",
                                "label": "Relationship",
                                "type": "text",
                                "required": True,
                            },
                        ],
                    },
                    {
                        "key": "pets_at_home",
                        "label": "Do you have pets at home?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "pets_details",
                        "label": "If yes, what kind?",
                        "type": "text",
                        "show_if": {
                            "field_key": "pets_at_home",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                ],
            },
            {
                "title": "Medical Info",
                "fields": [
                    {
                        "key": "blood_type",
                        "label": "What is your blood type?",
                        "type": "select",
                        "options": _options(BLOOD_TYPE),
                    },
                    {
                        "key": "rh_factor",
                        "label": "What is your Rh factor?",
                        "type": "select",
                        "options": _options(RH_FACTOR),
                    },
                    {
                        "key": "current_weight",
                        "label": "Weight",
                        "type": "number",
                        "help_text": "Pounds.",
                    },
                    {
                        "key": "current_height",
                        "label": "Height",
                        "type": "number",
                        "help_text": "Feet (e.g., 5.5).",
                    },
                    {
                        "key": "drink_alcohol",
                        "label": "Do you drink alcohol?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "drink_alcohol_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "drink_alcohol",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "household_smoke",
                        "label": "Does anyone in your household smoke?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "household_smoke_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "household_smoke",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "used_illicit_drugs",
                        "label": "Have you ever used illicit drugs?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "used_illicit_drugs_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "used_illicit_drugs",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "used_tobacco_last_6_months",
                        "label": "Have you used tobacco, marijuana or illicit drugs within the past 6 months?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "used_tobacco_last_6_months_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "used_tobacco_last_6_months",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "taking_medication",
                        "label": "Are you taking any medication?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "taking_medication_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "taking_medication",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "treated_conditions",
                        "label": "Are you being treated for any medical conditions?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "treated_conditions_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "treated_conditions",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "significant_illness_history",
                        "label": "Have you or your immediate family had a history of significant illness or medical condition?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "significant_illness_history_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "significant_illness_history",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "hospitalized_operations",
                        "label": "Have you ever been hospitalized or had any operations (excluding birth)?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "hospitalized_operations_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "hospitalized_operations",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "nearest_hospital",
                        "label": "How close are you to nearest hospital? Please list name and city.",
                        "type": "text",
                    },
                    {
                        "key": "psychiatric_conditions",
                        "label": "Have you ever been diagnosed or treated for any psychiatric conditions?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "psychiatric_conditions_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "psychiatric_conditions",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "depression_anxiety_meds",
                        "label": "Have you ever taken any medication for depression/anxiety?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "depression_anxiety_meds_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "depression_anxiety_meds",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "partner_psychiatric_hospital",
                        "label": "Has your partner/spouse ever been hospitalized for psychiatric illness?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "partner_psychiatric_hospital_explain",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "partner_psychiatric_hospital",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "immunized_hep_b",
                        "label": "Have you ever been immunized for Hepatitis B? (past only)",
                        "type": "radio",
                        "options": _options(YES_NO_UNSURE),
                    },
                    {
                        "key": "immunized_hep_b_explain",
                        "label": "If yes or unsure, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "immunized_hep_b",
                            "operator": "not_equals",
                            "value": "No",
                        },
                    },
                    {
                        "key": "diseases_self",
                        "label": "Have you ever been diagnosed with any of the following diseases?",
                        "type": "checkbox",
                        "options": _options(DISEASE_OPTIONS),
                    },
                    {
                        "key": "diseases_partner",
                        "label": "Has your partner/spouse ever been diagnosed with any of the following diseases?",
                        "type": "checkbox",
                        "options": _options(DISEASE_OPTIONS),
                    },
                ],
            },
            {
                "title": "Characteristics",
                "fields": [
                    {
                        "key": "why_surrogate",
                        "label": "Why do you want to be a surrogate? Message to intended parents?",
                        "type": "textarea",
                    },
                    {
                        "key": "personality",
                        "label": "Describe your personality and character",
                        "type": "textarea",
                    },
                    {
                        "key": "hobbies",
                        "label": "What are your hobbies, interests, and talents?",
                        "type": "textarea",
                    },
                    {"key": "daily_diet", "label": "What is your daily diet?", "type": "textarea"},
                ],
            },
            {
                "title": "Decisions",
                "fields": [
                    {
                        "key": "willing_ip_types",
                        "label": "Will you work with intended parents who are:",
                        "type": "checkbox",
                        "options": _options(IP_TYPE_OPTIONS),
                    },
                    {
                        "key": "willing_international",
                        "label": "Would you be willing to work with intended parents from other countries?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_travel_canada",
                        "label": "Would you be willing to travel to Canada?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_ip_hep_b",
                        "label": "Would you be willing to carry for intended parents who carry Hepatitis B?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_ip_hep_b_recovered",
                        "label": "Would you be willing to carry for intended parents who do not carry Hepatitis B but have recovered?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_ip_hiv",
                        "label": "Would you be willing to carry for intended parents who have HIV?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_donor",
                        "label": "Would you be willing to carry a child with donor eggs or sperm?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "willing_different_religion",
                        "label": "Would you be willing to carry for intended parents of a different religion?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "relationship_with_ips",
                        "label": "What kind of relationship do you want with intended parents during conception and pregnancy?",
                        "type": "textarea",
                    },
                    {
                        "key": "max_embryos_transfer",
                        "label": "Maximum number of embryos you are willing to transfer per cycle",
                        "type": "number",
                    },
                    {
                        "key": "willing_twins",
                        "label": "Would you be willing to carry twins if embryo split or two transferred?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "terminate_abnormality",
                        "label": "Would you be willing to terminate a pregnancy due to a birth abnormality or deformity?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "terminate_life_risk",
                        "label": "Would you be willing to terminate a pregnancy if your life or baby's life was in danger?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "reduce_multiple_pregnancy",
                        "label": "Are you okay with reducing multiple pregnancy if it is medically necessary?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "terminate_gender",
                        "label": "Would you be willing to terminate a pregnancy due to gender?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "invasive_procedures",
                        "label": "Would you be willing to do any invasive procedures (D&C, Amniocentesis, Chronic Villus Sampling)?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "pump_breast_milk",
                        "label": "Would you be willing to pump breast milk after delivery?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "ip_attend_ob",
                        "label": "Would you be comfortable with intended parents attending OB appointments?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "delivery_room",
                        "label": "Who are you willing to have in the delivery room?",
                        "type": "textarea",
                    },
                    {
                        "key": "agree_ivf_medications",
                        "label": "You will be required to take IVF medications. Do you agree?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "agree_abstain",
                        "label": "Will you abstain from sexual activity while undergoing treatment and throughout pregnancy?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                ],
            },
            {
                "title": "Uploads & Signature",
                "fields": [
                    {
                        "key": "upload_photos",
                        "label": "Please Upload at least 4 pics of you and your family (at least 2 showing face clearly)",
                        "type": "file",
                        "required": True,
                        "help_text": "Upload 4+ clear photos.",
                    },
                    {"key": "file_upload_1", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_2", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_3", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_4", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_5", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_6", "label": "File Upload", "type": "file"},
                    {"key": "file_upload_7", "label": "File Upload", "type": "file"},
                    {
                        "key": "signature_name",
                        "label": "Signature",
                        "type": "text",
                        "required": True,
                        "help_text": "Type your full legal name.",
                    },
                ],
            },
        ],
        "public_title": "Surrogate Intake Form",
        "privacy_notice": COMPLIANCE_NOTICE,
    }


def _settings() -> dict:
    return {
        "max_file_size_bytes": 15 * 1024 * 1024,
        "max_file_count": 12,
        "allowed_mime_types": ["image/*", "application/pdf"],
        "mappings": [
            {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
            {"field_key": "height_ft", "surrogate_field": "height_ft"},
            {"field_key": "weight_lb", "surrogate_field": "weight_lb"},
            {"field_key": "email", "surrogate_field": "email"},
            {"field_key": "cell_phone", "surrogate_field": "phone"},
            {"field_key": "state", "surrogate_field": "state"},
            {"field_key": "us_citizen", "surrogate_field": "is_citizen_or_pr"},
            {"field_key": "race", "surrogate_field": "race"},
        ],
    }


def _template_table() -> sa.Table:
    return sa.table(
        "platform_form_templates",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("schema_json", postgresql.JSONB),
        sa.column("settings_json", postgresql.JSONB),
        sa.column("published_name", sa.String),
        sa.column("published_description", sa.Text),
        sa.column("published_schema_json", postgresql.JSONB),
        sa.column("published_settings_json", postgresql.JSONB),
        sa.column("status", sa.String),
        sa.column("current_version", sa.Integer),
        sa.column("published_version", sa.Integer),
        sa.column("is_published_globally", sa.Boolean),
        sa.column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.column("updated_at", sa.TIMESTAMP(timezone=True)),
    )


def upgrade() -> None:
    schema = _schema()
    settings = _settings()
    template_table = _template_table()
    conn = op.get_bind()

    update_stmt = (
        sa.update(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
        .values(
            description=TEMPLATE_DESCRIPTION,
            schema_json=schema,
            settings_json=settings,
            published_name=TEMPLATE_NAME,
            published_description=TEMPLATE_DESCRIPTION,
            published_schema_json=schema,
            published_settings_json=settings,
            status="published",
            current_version=template_table.c.current_version + 1,
            published_version=template_table.c.published_version + 1,
            is_published_globally=True,
            published_at=sa.text("now()"),
            updated_at=sa.text("now()"),
        )
    )
    conn.execute(update_stmt)

    exists = conn.execute(
        sa.select(sa.literal(1))
        .select_from(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
    ).first()
    if not exists:
        conn.execute(
            sa.insert(template_table).values(
                name=TEMPLATE_NAME,
                description=TEMPLATE_DESCRIPTION,
                schema_json=schema,
                settings_json=settings,
                published_name=TEMPLATE_NAME,
                published_description=TEMPLATE_DESCRIPTION,
                published_schema_json=schema,
                published_settings_json=settings,
                status="published",
                current_version=1,
                published_version=1,
                is_published_globally=True,
                published_at=sa.text("now()"),
            )
        )


def downgrade() -> None:
    template_table = _template_table()
    conn = op.get_bind()
    conn.execute(
        sa.delete(template_table).where(
            sa.and_(
                template_table.c.name == TEMPLATE_NAME,
                template_table.c.description == TEMPLATE_DESCRIPTION,
                template_table.c.current_version == 1,
                template_table.c.published_version == 1,
            )
        )
    )
