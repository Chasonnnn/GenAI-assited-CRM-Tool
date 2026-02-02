"""Seed Jotform surrogate application platform form template.

Revision ID: 20260202_2359
Revises: 20260202_2355
Create Date: 2026-02-02 23:59:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260202_2359"
down_revision: Union[str, Sequence[str], None] = "20260202_2355"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_NAME = "Surrogate Application Form Template"
TEMPLATE_DESCRIPTION = "Template based on the Jotform Surrogate Application Form."
OLD_TEMPLATE_NAMES = [
    "Jotform Surrogate Intake",
    "Surrogate Application Form (Official)",
]
COMPLIANCE_NOTICE = (
    "By submitting this form, you consent to the collection and use of your information, "
    "including health-related details, for eligibility review and care coordination. "
    "Access is limited to authorized staff and retained per policy."
)

YES_NO = ["Yes", "No"]
YES_NO_UNSURE = ["Yes", "No", "Unsure"]
BLOOD_TYPE = ["A", "B", "AB", "O", "Unsure"]
RH_FACTOR = ["Positive", "Negative", "Unsure"]
PREGNANCY_CONDITIONS = [
    "None",
    "Gestational Diabetes",
    "Hypertension",
    "Toxemia",
    "Placenta Previa",
    "Pre-Eclampsia",
    "Placenta Abruption",
    "Post-partum depression",
    "Pre-term labor",
    "Short cervix",
    "Bedrest",
]
DISEASE_OPTIONS = [
    "Herpes",
    "Gonorrhea",
    "Chlamydia",
    "Syphilis",
    "HPV",
    "Genital warts",
    "Hepatitis B",
    "Hepatitis C",
]
IP_TYPE_OPTIONS = [
    "Hetero-sexual couples (male/female)",
    "Hetero-sexual individuals",
    "Same-sex couples (male/male or female/female)",
    "Same-sex individuals",
]


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
                        "key": "religion",
                        "label": "Do you have any religions? (If Yes, please specify your religion)",
                        "type": "text",
                    },
                ],
            },
            {
                "title": "Eligibility & Background",
                "fields": [
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
                        "help_text": "Married, single, committed relationship, divorced, etc.",
                    },
                    {
                        "key": "marriage_date",
                        "label": "If married, please list date of marriage",
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
                        "label": "What languages do you speak fluently?",
                        "type": "text",
                    },
                    {
                        "key": "schedule_flexible",
                        "label": "Is your schedule flexible?",
                        "type": "radio",
                        "options": _options(YES_NO),
                        "help_text": "You might be required to attend more than one medical appointment per week.",
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
                        "label": "What is the name of your health insurance carrier?",
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
                        "label": "Have you been involved in ANY legal cases, or any that are pending?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "government_assistance",
                        "label": (
                            "Do you currently receive any forms of government assistance "
                            "(e.g. Cash Aid/TANF/Food stamps/Medicaid/Section 8/etc.)?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                ],
            },
            {
                "title": "Education & Employment",
                "fields": [
                    {
                        "key": "education_level",
                        "label": "What is the highest-level education you have completed?",
                        "type": "text",
                    },
                    {
                        "key": "further_education_plans",
                        "label": "Do you have plans on furthering your education?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "currently_employed",
                        "label": "Are you currently employed?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "employer_title",
                        "label": "Who is your present employer? What is your title/position?",
                        "type": "text",
                        "help_text": "Please put N/A if no.",
                        "show_if": {
                            "field_key": "currently_employed",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "employment_duration",
                        "label": "How long have you been employed?",
                        "type": "text",
                        "help_text": "Please put N/A if no.",
                        "show_if": {
                            "field_key": "currently_employed",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                ],
            },
            {
                "title": "Pregnancy Info",
                "fields": [
                    {
                        "key": "pregnancy_list",
                        "label": "List of pregnancies",
                        "type": "repeatable_table",
                        "help_text": (
                            "Include: own/surrogacy, # babies, delivery date, vaginal/C-section, "
                            "gender, weight (lbs/oz), weeks at birth, complications."
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
                        "key": "abortion_when",
                        "label": "If yes, please specify when",
                        "type": "text",
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
                        "key": "miscarriage_when",
                        "label": "If yes, please specify when",
                        "type": "text",
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
                        "label": "If yes, what kind of birth control?",
                        "type": "text",
                        "help_text": "Birth control pills, IUD, etc.",
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
                        "label": "What is the date of your last Pap Smear? What is the result?",
                        "type": "text",
                    },
                    {
                        "key": "reproductive_illnesses",
                        "label": "Please list any reproductive illness you have ever experienced",
                        "type": "textarea",
                        "help_text": "Please put N/A if none.",
                    },
                ],
            },
            {
                "title": "Family Support",
                "fields": [
                    {
                        "key": "spouse_significant_other",
                        "label": "Do you have a spouse or significant other?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "spouse_occupation",
                        "label": "Your spouse or significant other occupation",
                        "type": "text",
                        "show_if": {
                            "field_key": "spouse_significant_other",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "family_support",
                        "label": "Does your family support your decision to become a Gestational Carrier?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "bedrest_help",
                        "label": "Who would help if you were ordered to be on bed rest for a period of time?",
                        "type": "textarea",
                    },
                    {
                        "key": "anticipated_difficulties",
                        "label": "Do you anticipate any difficulties in becoming a surrogate?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "anticipated_difficulties_detail",
                        "label": "If yes, please explain",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "anticipated_difficulties",
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
                        "label": (
                            "Please list everyone living in your household including ages and relationship"
                        ),
                        "type": "repeatable_table",
                        "columns": [
                            {"key": "name", "label": "Name", "type": "text", "required": True},
                            {"key": "age", "label": "Age", "type": "number"},
                            {"key": "relationship", "label": "Relationship", "type": "text"},
                        ],
                    },
                    {
                        "key": "pets_at_home",
                        "label": "Do you have any pets at home?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "pets_detail",
                        "label": "If yes, please specify",
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
                        "label": "Your Blood type?",
                        "type": "radio",
                        "options": _options(BLOOD_TYPE),
                    },
                    {
                        "key": "rh_factor",
                        "label": "What is your Rh factor?",
                        "type": "radio",
                        "options": _options(RH_FACTOR),
                    },
                    {"key": "weight_medical", "label": "Weight", "type": "number"},
                    {"key": "height_medical", "label": "Height", "type": "number"},
                    {
                        "key": "alcohol_use",
                        "label": "Do you drink alcoholic beverages?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "alcohol_use_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "alcohol_use",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "household_smoke",
                        "label": "Do you or anyone in your household smoke?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "household_smoke_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "household_smoke",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "household_illicit_drugs",
                        "label": "Do you or anyone in your household use illicit drugs?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "household_illicit_drugs_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "household_illicit_drugs",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "illicit_drugs_past_6_months",
                        "label": (
                            "Have you had any form of Tobacco, Marijuana, or any form of "
                            "illicit drugs within the past 6 months?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "illicit_drugs_past_6_months_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "illicit_drugs_past_6_months",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                ],
            },
            {
                "title": "Medical Info (continued)",
                "fields": [
                    {
                        "key": "taking_medications",
                        "label": "Are you taking any medication?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "medications_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "taking_medications",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "medical_conditions_treated",
                        "label": "Are you currently being treated for any medical conditions?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "medical_conditions_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "medical_conditions_treated",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "significant_illness",
                        "label": "Please list any significant illness you have had",
                        "type": "textarea",
                        "help_text": "Please put N/A if none.",
                    },
                    {
                        "key": "hospitalizations_operations",
                        "label": "Please list any hospitalization or operations you have had",
                        "type": "textarea",
                        "help_text": "Please do NOT include the birth of your children.",
                    },
                    {
                        "key": "nearest_hospital",
                        "label": (
                            "How close are you to the nearest hospital? What is the name / "
                            "city it is located in?"
                        ),
                        "type": "textarea",
                    },
                    {
                        "key": "psychiatric_diagnosis",
                        "label": (
                            "Have you ever been diagnosed with depression, anxiety, bipolar "
                            "disorder, postpartum depression, or any other psychiatric condition?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "psychiatric_diagnosis_detail",
                        "label": "If yes, please specify",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "psychiatric_diagnosis",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "psychiatric_medications",
                        "label": "Have you ever taken medications for depression or anxiety?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "psychiatric_medications_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "psychiatric_medications",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "partner_psychiatric_hospitalized",
                        "label": (
                            "Have you or any of your partners ever been hospitalized for "
                            "psychiatric illness?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "partner_psychiatric_hospitalized_detail",
                        "label": "If yes, please specify",
                        "type": "text",
                        "show_if": {
                            "field_key": "partner_psychiatric_hospitalized",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "hep_b_immunized",
                        "label": (
                            "Have you been immunized for Hepatitis B in the past? (This "
                            "vaccine was not a standard childhood vaccination until 1992)"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO_UNSURE),
                    },
                    {
                        "key": "diagnosed_diseases",
                        "label": "Have you ever been diagnosed with the following diseases?",
                        "type": "checkbox",
                        "options": _options(DISEASE_OPTIONS),
                    },
                    {
                        "key": "diagnosed_diseases_detail",
                        "label": "If yes, please specify",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "diagnosed_diseases",
                            "operator": "is_not_empty",
                            "value": "",
                        },
                    },
                    {
                        "key": "partner_diagnosed_diseases",
                        "label": (
                            "Has your partner/spouse ever been diagnosed with the following diseases?"
                        ),
                        "type": "checkbox",
                        "options": _options(DISEASE_OPTIONS),
                    },
                    {
                        "key": "partner_diagnosed_diseases_detail",
                        "label": "If yes, please specify",
                        "type": "textarea",
                        "show_if": {
                            "field_key": "partner_diagnosed_diseases",
                            "operator": "is_not_empty",
                            "value": "",
                        },
                    },
                ],
            },
            {
                "title": "Characteristics",
                "fields": [
                    {
                        "key": "surrogate_why",
                        "label": (
                            "Why do you want to be a surrogate? What message would you like "
                            "to give to your Intended Parents?"
                        ),
                        "type": "textarea",
                    },
                    {
                        "key": "personality",
                        "label": "Please describe your personality and character",
                        "type": "textarea",
                    },
                    {
                        "key": "hobbies",
                        "label": "What are your hobbies, interests and talents?",
                        "type": "textarea",
                    },
                    {
                        "key": "daily_diet",
                        "label": "What does your daily diet consist of?",
                        "type": "textarea",
                    },
                ],
            },
            {
                "title": "Decisions",
                "fields": [
                    {
                        "key": "intended_parent_types",
                        "label": "Are you willing to work with intended parents (IPs):",
                        "type": "checkbox",
                        "options": _options(IP_TYPE_OPTIONS),
                    },
                    {
                        "key": "international_ips",
                        "label": (
                            "Are you willing to work with International Intended Parents? "
                            "(Please note we only work with US and Canada clinics)"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "travel_canada",
                        "label": (
                            "Are you willing to travel to Canada for physical screening "
                            "as well as the embryo transfer? (Hybrid Program Only)"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                        "show_if": {
                            "field_key": "international_ips",
                            "operator": "equals",
                            "value": "Yes",
                        },
                    },
                    {
                        "key": "ip_hep_b",
                        "label": "Are you willing to carry for an intended parent/s who carries Hep B Virus?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "ip_hep_b_recovered",
                        "label": (
                            "Are you willing to carry for an intended parent/s who does not "
                            "carry Hep B virus, but recovered from an old infection (Not infected)?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "ip_hiv",
                        "label": "Are you willing to carry for an intended parent/s who have HIV?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "donor_eggs_sperm",
                        "label": (
                            "Are you willing to carry a child whereby the recipients used "
                            "donor eggs or donor sperm?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "different_religion",
                        "label": (
                            "Are you willing to carry a child for a recipient who will raise "
                            "this child in a religion different from your own?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "relationship_preference",
                        "label": (
                            "What kind of relationship do you want with intended parents "
                            "during conception and pregnancy?"
                        ),
                        "type": "textarea",
                    },
                    {
                        "key": "max_embryos_transfer",
                        "label": "What is the maximum number of embryos are you willing to transfer per cycle?",
                        "type": "number",
                    },
                    {
                        "key": "twins_if_split",
                        "label": "Are you willing to carry twins if an embryo split?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "terminate_abnormality",
                        "label": (
                            "Would you be willing to terminate a pregnancy due to a birth "
                            "abnormality or deformity?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "terminate_life_threat",
                        "label": (
                            "Would you be willing to terminate a pregnancy if your life or "
                            "baby's life was in danger?"
                        ),
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
                        "label": (
                            "Would you be willing to do somewhat invasive procedures during "
                            "your surrogacy if medically necessary?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                        "help_text": "For example, D&C, amniocentesis and/or chronic villus sampling.",
                    },
                    {
                        "key": "pump_breast_milk",
                        "label": "Are you willing to pump breast milk after birth?",
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "ob_appointments_with_ips",
                        "label": "Would you be comfortable if the Intended Parents attended the OB appointments with you?",
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
                        "label": (
                            "You will be required to take IVF medications. Some meds might require "
                            "using injectable needles. Do you agree to take ALL medications required?"
                        ),
                        "type": "radio",
                        "options": _options(YES_NO),
                    },
                    {
                        "key": "agree_abstain",
                        "label": (
                            "Do you and your partner agree to abstain from sexual activity during medical "
                            "treatment as directed by the physician?"
                        ),
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
                        "label": (
                            "Please Upload at least 4 pics of you and your family "
                            "(at least 2 showing face clearly)"
                        ),
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
        "public_title": TEMPLATE_NAME,
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

    names_to_update = [TEMPLATE_NAME, *OLD_TEMPLATE_NAMES]
    update_stmt = (
        sa.update(template_table)
        .where(template_table.c.name.in_(names_to_update))
        .values(
            name=TEMPLATE_NAME,
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
