"""MFA service - TOTP and recovery code management.

Provides:
- TOTP secret generation and verification (pyotp)
- Recovery code generation and validation
- MFA enrollment and verification state management
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Tuple

import pyotp
from sqlalchemy.orm import Session

from app.db.models import User


# =============================================================================
# Configuration
# =============================================================================

MFA_ISSUER = "Surrogacy Force"
RECOVERY_CODE_COUNT = 8
RECOVERY_CODE_LENGTH = 8  # Characters per code


# =============================================================================
# TOTP Functions
# =============================================================================


def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret (32 characters)."""
    return pyotp.random_base32()


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    """
    Generate the provisioning URI for authenticator apps.

    This creates a URI that can be encoded as a QR code for apps
    like Google Authenticator, Authy, or 1Password.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=MFA_ISSUER)


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a 6-digit TOTP code.

    Allows 1 time step tolerance (±30 seconds) for clock drift.
    """
    if not secret or not code:
        return False

    # Sanitize input
    code = code.strip().replace(" ", "").replace("-", "")
    if len(code) != 6 or not code.isdigit():
        return False

    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# =============================================================================
# Recovery Codes
# =============================================================================


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """
    Generate a list of random recovery codes.

    Format: 8 alphanumeric characters (uppercase + digits, no ambiguous chars)
    """
    # Avoid ambiguous characters: 0, O, 1, I, L
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    codes = []
    for _ in range(count):
        code = "".join(secrets.choice(alphabet) for _ in range(RECOVERY_CODE_LENGTH))
        codes.append(code)
    return codes


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage using SHA-256."""
    normalized = code.upper().strip().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def hash_recovery_codes(codes: list[str]) -> list[str]:
    """Hash all recovery codes for storage."""
    return [hash_recovery_code(code) for code in codes]


def verify_recovery_code(code: str, hashed_codes: list[str]) -> Tuple[bool, int]:
    """
    Check if a recovery code matches any stored hash.

    Returns:
        (is_valid, index) - index of matching code, or -1 if not found
    """
    hashed_input = hash_recovery_code(code)
    for i, stored_hash in enumerate(hashed_codes):
        if hmac.compare_digest(hashed_input, stored_hash):
            return True, i
    return False, -1


# =============================================================================
# MFA Enrollment
# =============================================================================


def setup_totp_for_user(db: Session, user: User) -> Tuple[str, str]:
    """
    Start TOTP setup for a user.

    Returns:
        (secret, provisioning_uri) - secret to store, URI for QR code
    """
    secret = generate_totp_secret()
    uri = get_totp_provisioning_uri(secret, user.email)

    # Store secret but don't enable yet (user must verify first)
    user.totp_secret = secret
    db.commit()

    return secret, uri


def complete_totp_setup(db: Session, user: User, code: str) -> Tuple[bool, list[str] | None]:
    """
    Complete TOTP setup by verifying the initial code.

    If successful:
    - Enables MFA for the user
    - Generates and returns recovery codes (plaintext, one-time display)

    Returns:
        (success, recovery_codes or None)
    """
    if not user.totp_secret:
        return False, None

    if not verify_totp_code(user.totp_secret, code):
        return False, None

    # Generate recovery codes
    plaintext_codes = generate_recovery_codes(RECOVERY_CODE_COUNT)
    hashed_codes = hash_recovery_codes(plaintext_codes)

    # Enable MFA
    now = datetime.now(timezone.utc)
    user.mfa_enabled = True
    user.totp_enabled_at = now
    user.mfa_recovery_codes = hashed_codes
    user.mfa_required_at = now
    db.commit()

    return True, plaintext_codes


def disable_mfa(db: Session, user: User) -> None:
    """Disable MFA for a user (admin action or user re-setup)."""
    user.mfa_enabled = False
    user.totp_secret = None
    user.totp_enabled_at = None
    user.duo_user_id = None
    user.duo_enrolled_at = None
    user.mfa_recovery_codes = None
    # Keep mfa_required_at to track when enforcement started
    db.commit()


# =============================================================================
# MFA Verification
# =============================================================================


def verify_mfa_code(user: User, code: str) -> Tuple[bool, str]:
    """
    Verify an MFA code (TOTP or recovery).

    Returns:
        (is_valid, method) - method is "totp" or "recovery"
    """
    if not user.mfa_enabled:
        return False, ""

    # Try TOTP first
    if user.totp_secret and verify_totp_code(user.totp_secret, code):
        return True, "totp"

    # Try recovery codes
    if user.mfa_recovery_codes:
        is_valid, idx = verify_recovery_code(code, user.mfa_recovery_codes)
        if is_valid:
            return True, "recovery"

    return False, ""


def consume_recovery_code(db: Session, user: User, code: str) -> bool:
    """
    Use a recovery code (one-time use).

    Removes the code from the user's list after successful verification.
    Returns True if code was valid and consumed.
    """
    if not user.mfa_recovery_codes:
        return False

    is_valid, idx = verify_recovery_code(code, user.mfa_recovery_codes)
    if not is_valid:
        return False

    # Remove the used code
    codes = list(user.mfa_recovery_codes)
    codes.pop(idx)
    user.mfa_recovery_codes = codes
    db.commit()

    return True


def regenerate_recovery_codes(db: Session, user: User) -> list[str]:
    """
    Generate new recovery codes, replacing existing ones.

    Requires MFA to be enabled. Returns plaintext codes for display.
    """
    if not user.mfa_enabled:
        raise ValueError("MFA must be enabled to regenerate recovery codes")

    plaintext_codes = generate_recovery_codes(RECOVERY_CODE_COUNT)
    hashed_codes = hash_recovery_codes(plaintext_codes)
    user.mfa_recovery_codes = hashed_codes
    db.commit()

    return plaintext_codes


# =============================================================================
# MFA Status
# =============================================================================


def get_mfa_status(user: User) -> dict:
    """Get MFA enrollment status for a user."""
    return {
        "mfa_enabled": user.mfa_enabled,
        "totp_enabled": user.totp_enabled_at is not None,
        "totp_enabled_at": user.totp_enabled_at.isoformat() if user.totp_enabled_at else None,
        "duo_enabled": user.duo_enrolled_at is not None,
        "duo_enrolled_at": user.duo_enrolled_at.isoformat() if user.duo_enrolled_at else None,
        "recovery_codes_remaining": len(user.mfa_recovery_codes) if user.mfa_recovery_codes else 0,
        "mfa_required": True,  # Global requirement
    }


def is_mfa_required(user: User) -> bool:
    """Check if MFA is required for this user."""
    # Currently MFA is required for all users
    return True


def has_mfa_setup(user: User) -> bool:
    """Check if user has set up MFA."""
    return user.mfa_enabled and (
        user.totp_enabled_at is not None or user.duo_enrolled_at is not None
    )
