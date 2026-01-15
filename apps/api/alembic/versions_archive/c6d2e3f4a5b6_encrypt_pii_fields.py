"""Encrypt PII fields and add deterministic hashes.

Revision ID: c6d2e3f4a5b6
Revises: b1c3d5e7f9a1
Create Date: 2025-02-20 12:00:00.000000
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT


# revision identifiers, used by Alembic.
revision: str = "c6d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b1c3d5e7f9a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_str(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _maybe_decrypt(value: object | None, decrypt_value) -> object | None:
    if not value or not isinstance(value, str):
        return value
    if not value.startswith("enc:"):
        return value
    try:
        return decrypt_value(value)
    except Exception:
        return value


def _normalize_email(value: object | None) -> str:
    from app.utils.normalization import normalize_email

    raw = _safe_str(value)
    return normalize_email(raw) or raw.lower()


def _normalize_phone(value: object | None) -> str | None:
    if value is None:
        return None
    raw = _safe_str(value).strip()
    if not raw:
        return None
    from app.utils.normalization import normalize_phone

    try:
        return normalize_phone(raw)
    except Exception:
        return raw


def _coerce_date_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = _safe_str(value).strip()
    return raw or None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("cases", sa.Column("email_hash", sa.String(length=64), nullable=True))
    op.add_column("cases", sa.Column("phone_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "intended_parents",
        sa.Column("email_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "intended_parents",
        sa.Column("phone_hash", sa.String(length=64), nullable=True),
    )

    op.alter_column("cases", "email", type_=sa.Text(), postgresql_using="email::text")
    op.alter_column("cases", "phone", type_=sa.Text(), postgresql_using="phone::text")
    op.alter_column(
        "cases",
        "date_of_birth",
        type_=sa.Text(),
        postgresql_using="date_of_birth::text",
    )
    op.alter_column(
        "intended_parents",
        "email",
        type_=sa.Text(),
        postgresql_using="email::text",
    )
    op.alter_column(
        "intended_parents",
        "phone",
        type_=sa.Text(),
        postgresql_using="phone::text",
    )

    conn = op.get_bind()
    from app.core.encryption import decrypt_value, encrypt_value, hash_email, hash_phone

    case_rows = conn.execute(
        sa.text("SELECT id, email, phone, date_of_birth FROM cases")
    ).mappings()
    for row in case_rows:
        email_plain = _maybe_decrypt(row["email"], decrypt_value)
        normalized_email = _normalize_email(email_plain)
        email_hash = hash_email(normalized_email)
        encrypted_email = encrypt_value(normalized_email)

        phone_plain = _maybe_decrypt(row["phone"], decrypt_value)
        normalized_phone = _normalize_phone(phone_plain)
        phone_hash = hash_phone(normalized_phone) if normalized_phone else None
        encrypted_phone = encrypt_value(normalized_phone) if normalized_phone is not None else None

        dob_plain = _maybe_decrypt(row["date_of_birth"], decrypt_value)
        dob_text = _coerce_date_text(dob_plain)
        encrypted_dob = encrypt_value(dob_text) if dob_text else None

        conn.execute(
            sa.text(
                """
                UPDATE cases
                SET email = :email,
                    email_hash = :email_hash,
                    phone = :phone,
                    phone_hash = :phone_hash,
                    date_of_birth = :dob
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "email": encrypted_email,
                "email_hash": email_hash,
                "phone": encrypted_phone,
                "phone_hash": phone_hash,
                "dob": encrypted_dob,
            },
        )

    ip_rows = conn.execute(
        sa.text("SELECT id, email, phone, notes_internal FROM intended_parents")
    ).mappings()
    for row in ip_rows:
        email_plain = _maybe_decrypt(row["email"], decrypt_value)
        normalized_email = _normalize_email(email_plain)
        email_hash = hash_email(normalized_email)
        encrypted_email = encrypt_value(normalized_email)

        phone_plain = _maybe_decrypt(row["phone"], decrypt_value)
        normalized_phone = _normalize_phone(phone_plain)
        phone_hash = hash_phone(normalized_phone) if normalized_phone else None
        encrypted_phone = encrypt_value(normalized_phone) if normalized_phone is not None else None

        notes_plain = _maybe_decrypt(row["notes_internal"], decrypt_value)
        encrypted_notes = encrypt_value(notes_plain) if notes_plain else None

        conn.execute(
            sa.text(
                """
                UPDATE intended_parents
                SET email = :email,
                    email_hash = :email_hash,
                    phone = :phone,
                    phone_hash = :phone_hash,
                    notes_internal = :notes
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "email": encrypted_email,
                "email_hash": email_hash,
                "phone": encrypted_phone,
                "phone_hash": phone_hash,
                "notes": encrypted_notes,
            },
        )

    op.alter_column("cases", "email_hash", nullable=False)
    op.alter_column("intended_parents", "email_hash", nullable=False)

    op.drop_index("uq_case_email_active", table_name="cases")
    op.drop_index("uq_ip_email_active", table_name="intended_parents")
    op.create_index(
        "uq_case_email_hash_active",
        "cases",
        ["organization_id", "email_hash"],
        unique=True,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "uq_ip_email_hash_active",
        "intended_parents",
        ["organization_id", "email_hash"],
        unique=True,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "idx_cases_org_phone_hash",
        "cases",
        ["organization_id", "phone_hash"],
        unique=False,
        postgresql_where=sa.text("phone_hash IS NOT NULL"),
    )
    op.create_index(
        "idx_ip_org_phone_hash",
        "intended_parents",
        ["organization_id", "phone_hash"],
        unique=False,
        postgresql_where=sa.text("phone_hash IS NOT NULL"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION cases_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.case_number, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        UPDATE cases SET search_vector = to_tsvector('simple',
            coalesce(full_name, '') || ' ' || coalesce(case_number, '')
        );
        """
    )
    op.execute(
        """
        UPDATE intended_parents SET search_vector = to_tsvector('simple',
            coalesce(full_name, '')
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    from app.core.encryption import decrypt_value

    case_rows = conn.execute(
        sa.text("SELECT id, email, phone, date_of_birth FROM cases")
    ).mappings()
    for row in case_rows:
        email_plain = _maybe_decrypt(row["email"], decrypt_value)
        phone_plain = _maybe_decrypt(row["phone"], decrypt_value)
        dob_plain = _maybe_decrypt(row["date_of_birth"], decrypt_value)
        dob_value = None
        if isinstance(dob_plain, (date, datetime)):
            dob_value = dob_plain.date() if isinstance(dob_plain, datetime) else dob_plain
        elif dob_plain:
            try:
                dob_value = date.fromisoformat(_safe_str(dob_plain))
            except Exception:
                dob_value = None

        conn.execute(
            sa.text(
                """
                UPDATE cases
                SET email = :email,
                    phone = :phone,
                    date_of_birth = :dob
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "email": email_plain,
                "phone": phone_plain,
                "dob": dob_value,
            },
        )

    ip_rows = conn.execute(
        sa.text("SELECT id, email, phone, notes_internal FROM intended_parents")
    ).mappings()
    for row in ip_rows:
        email_plain = _maybe_decrypt(row["email"], decrypt_value)
        phone_plain = _maybe_decrypt(row["phone"], decrypt_value)
        notes_plain = _maybe_decrypt(row["notes_internal"], decrypt_value)

        conn.execute(
            sa.text(
                """
                UPDATE intended_parents
                SET email = :email,
                    phone = :phone,
                    notes_internal = :notes
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "email": email_plain,
                "phone": phone_plain,
                "notes": notes_plain,
            },
        )

    op.drop_index("idx_ip_org_phone_hash", table_name="intended_parents")
    op.drop_index("idx_cases_org_phone_hash", table_name="cases")
    op.drop_index("uq_ip_email_hash_active", table_name="intended_parents")
    op.drop_index("uq_case_email_hash_active", table_name="cases")

    op.alter_column(
        "cases",
        "email",
        type_=CITEXT(),
        postgresql_using="email::citext",
    )
    op.alter_column(
        "cases",
        "phone",
        type_=sa.String(length=20),
        postgresql_using="phone::varchar",
    )
    op.alter_column(
        "cases",
        "date_of_birth",
        type_=sa.Date(),
        postgresql_using="date_of_birth::date",
    )
    op.alter_column(
        "intended_parents",
        "email",
        type_=CITEXT(),
        postgresql_using="email::citext",
    )
    op.alter_column(
        "intended_parents",
        "phone",
        type_=sa.String(length=50),
        postgresql_using="phone::varchar",
    )

    op.drop_column("intended_parents", "phone_hash")
    op.drop_column("intended_parents", "email_hash")
    op.drop_column("cases", "phone_hash")
    op.drop_column("cases", "email_hash")

    op.create_index(
        "uq_case_email_active",
        "cases",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_archived = FALSE"),
    )
    op.create_index(
        "uq_ip_email_active",
        "intended_parents",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("is_archived = FALSE"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION cases_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.case_number, '') || ' ' ||
                coalesce(NEW.email, '') || ' ' ||
                coalesce(NEW.phone, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION intended_parents_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple',
                coalesce(NEW.full_name, '') || ' ' ||
                coalesce(NEW.email, '') || ' ' ||
                coalesce(NEW.phone, '')
            );
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        UPDATE cases SET search_vector = to_tsvector('simple',
            coalesce(full_name, '') || ' ' ||
            coalesce(case_number, '') || ' ' ||
            coalesce(email, '') || ' ' ||
            coalesce(phone, '')
        );
        """
    )
    op.execute(
        """
        UPDATE intended_parents SET search_vector = to_tsvector('simple',
            coalesce(full_name, '') || ' ' ||
            coalesce(email, '') || ' ' ||
            coalesce(phone, '')
        );
        """
    )
