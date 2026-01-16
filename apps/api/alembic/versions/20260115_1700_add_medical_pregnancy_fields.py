"""Add medical, insurance, and pregnancy fields to surrogates.

Revision ID: 20260115_1700
Revises: 20260115_1500
Create Date: 2026-01-15 17:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260115_1700"
down_revision = "20260115_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # INSURANCE INFO (8 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("insurance_company", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("insurance_plan_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("insurance_phone", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("insurance_policy_number", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("insurance_member_id", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("insurance_group_number", sa.String(100), nullable=True))
    op.add_column("surrogates", sa.Column("insurance_subscriber_name", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("insurance_subscriber_dob", sa.Text(), nullable=True))  # EncryptedDate

    # ============================================
    # IVF CLINIC (8 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("clinic_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("clinic_address_line1", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("clinic_address_line2", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("clinic_city", sa.String(100), nullable=True))
    op.add_column("surrogates", sa.Column("clinic_state", sa.String(2), nullable=True))
    op.add_column("surrogates", sa.Column("clinic_postal", sa.String(20), nullable=True))
    op.add_column("surrogates", sa.Column("clinic_phone", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("clinic_email", sa.Text(), nullable=True))  # Encrypted

    # ============================================
    # MONITORING CLINIC (8 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("monitoring_clinic_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("monitoring_clinic_address_line1", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("monitoring_clinic_address_line2", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("monitoring_clinic_city", sa.String(100), nullable=True))
    op.add_column("surrogates", sa.Column("monitoring_clinic_state", sa.String(2), nullable=True))
    op.add_column("surrogates", sa.Column("monitoring_clinic_postal", sa.String(20), nullable=True))
    op.add_column("surrogates", sa.Column("monitoring_clinic_phone", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("monitoring_clinic_email", sa.Text(), nullable=True))  # Encrypted

    # ============================================
    # OB PROVIDER (9 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("ob_provider_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("ob_clinic_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("ob_address_line1", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("ob_address_line2", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("ob_city", sa.String(100), nullable=True))
    op.add_column("surrogates", sa.Column("ob_state", sa.String(2), nullable=True))
    op.add_column("surrogates", sa.Column("ob_postal", sa.String(20), nullable=True))
    op.add_column("surrogates", sa.Column("ob_phone", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("ob_email", sa.Text(), nullable=True))  # Encrypted

    # ============================================
    # DELIVERY HOSPITAL (8 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("delivery_hospital_name", sa.String(255), nullable=True))
    op.add_column("surrogates", sa.Column("delivery_hospital_address_line1", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("delivery_hospital_address_line2", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("delivery_hospital_city", sa.String(100), nullable=True))
    op.add_column("surrogates", sa.Column("delivery_hospital_state", sa.String(2), nullable=True))
    op.add_column("surrogates", sa.Column("delivery_hospital_postal", sa.String(20), nullable=True))
    op.add_column("surrogates", sa.Column("delivery_hospital_phone", sa.Text(), nullable=True))  # Encrypted
    op.add_column("surrogates", sa.Column("delivery_hospital_email", sa.Text(), nullable=True))  # Encrypted

    # ============================================
    # PREGNANCY TRACKING (2 fields)
    # ============================================
    op.add_column("surrogates", sa.Column("pregnancy_start_date", sa.Text(), nullable=True))  # EncryptedDate
    op.add_column("surrogates", sa.Column("pregnancy_due_date", sa.Text(), nullable=True))  # EncryptedDate


def downgrade() -> None:
    # Pregnancy tracking
    op.drop_column("surrogates", "pregnancy_due_date")
    op.drop_column("surrogates", "pregnancy_start_date")

    # Delivery hospital
    op.drop_column("surrogates", "delivery_hospital_email")
    op.drop_column("surrogates", "delivery_hospital_phone")
    op.drop_column("surrogates", "delivery_hospital_postal")
    op.drop_column("surrogates", "delivery_hospital_state")
    op.drop_column("surrogates", "delivery_hospital_city")
    op.drop_column("surrogates", "delivery_hospital_address_line2")
    op.drop_column("surrogates", "delivery_hospital_address_line1")
    op.drop_column("surrogates", "delivery_hospital_name")

    # OB provider
    op.drop_column("surrogates", "ob_email")
    op.drop_column("surrogates", "ob_phone")
    op.drop_column("surrogates", "ob_postal")
    op.drop_column("surrogates", "ob_state")
    op.drop_column("surrogates", "ob_city")
    op.drop_column("surrogates", "ob_address_line2")
    op.drop_column("surrogates", "ob_address_line1")
    op.drop_column("surrogates", "ob_clinic_name")
    op.drop_column("surrogates", "ob_provider_name")

    # Monitoring clinic
    op.drop_column("surrogates", "monitoring_clinic_email")
    op.drop_column("surrogates", "monitoring_clinic_phone")
    op.drop_column("surrogates", "monitoring_clinic_postal")
    op.drop_column("surrogates", "monitoring_clinic_state")
    op.drop_column("surrogates", "monitoring_clinic_city")
    op.drop_column("surrogates", "monitoring_clinic_address_line2")
    op.drop_column("surrogates", "monitoring_clinic_address_line1")
    op.drop_column("surrogates", "monitoring_clinic_name")

    # IVF clinic
    op.drop_column("surrogates", "clinic_email")
    op.drop_column("surrogates", "clinic_phone")
    op.drop_column("surrogates", "clinic_postal")
    op.drop_column("surrogates", "clinic_state")
    op.drop_column("surrogates", "clinic_city")
    op.drop_column("surrogates", "clinic_address_line2")
    op.drop_column("surrogates", "clinic_address_line1")
    op.drop_column("surrogates", "clinic_name")

    # Insurance
    op.drop_column("surrogates", "insurance_subscriber_dob")
    op.drop_column("surrogates", "insurance_subscriber_name")
    op.drop_column("surrogates", "insurance_group_number")
    op.drop_column("surrogates", "insurance_member_id")
    op.drop_column("surrogates", "insurance_policy_number")
    op.drop_column("surrogates", "insurance_phone")
    op.drop_column("surrogates", "insurance_plan_name")
    op.drop_column("surrogates", "insurance_company")
