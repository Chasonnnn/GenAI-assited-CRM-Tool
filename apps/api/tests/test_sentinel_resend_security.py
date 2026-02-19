"""Tests for Sentinel Security Fixes - Resend Signature Verification."""

import base64
import hashlib
import hmac
import time
import uuid

import pytest


def _generate_signature_with_raw_bytes(body: bytes, secret: str, timestamp: str) -> str:
    """Generate a valid Svix signature using the raw bytes of the secret, even if it has whsec_ prefix."""
    msg_id = str(uuid.uuid4())
    signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

    # Use raw bytes regardless of prefix
    if secret.startswith("whsec_"):
        secret_bytes = secret[6:].encode("utf-8")
    else:
        secret_bytes = secret.encode("utf-8")

    signature = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return msg_id, f"v1,{signature_b64}"

def _generate_signature_correctly(body: bytes, secret: str, timestamp: str) -> str:
    """Generate a valid Svix signature using proper decoding for whsec_ prefix."""
    msg_id = str(uuid.uuid4())
    signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

    def _pad_b64(value: str) -> str:
        return value + "=" * (-len(value) % 4)

    if secret.startswith("whsec_"):
        # Correctly decode base64
        secret_bytes = base64.urlsafe_b64decode(_pad_b64(secret[6:]))
    else:
        secret_bytes = secret.encode("utf-8")

    signature = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return msg_id, f"v1,{signature_b64}"


class TestResendSecurity:
    """Test security fixes for Resend webhook verification."""

    def test_verify_svix_signature_fail_invalid_base64_whsec(self):
        """
        Test that verification fails immediately if a whsec_ secret is not valid base64.

        The vulnerability was that it would fall back to using the raw bytes of the secret string,
        which could lead to unexpected behavior or key confusion.
        """
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        # "INVALIDBASE64" is 13 chars, all valid base64 chars.
        # Length 13 is invalid (1 mod 4). Even with padding, it fails because 1 sextet is left over.
        # This forces both urlsafe_b64decode and b64decode to fail.
        # This will trigger the fallback to raw bytes in vulnerable code.
        secret = "whsec_INVALIDBASE64"
        timestamp = str(int(time.time()))

        # Generate a signature using the raw bytes of the invalid base64 string
        # This simulates what the vulnerable code would accept as valid (using fallback key)
        msg_id, signature = _generate_signature_with_raw_bytes(body, secret, timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        }

        # Verify should return False because the secret is invalid base64.
        # It should NOT fall back to using the raw bytes.
        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is False

    def test_verify_svix_signature_pass_valid_whsec(self):
        """Test that verification passes for a valid base64 whsec_ secret."""
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        # Construct a valid whsec_ secret
        raw_secret = b"valid_secret_bytes_123"
        secret = "whsec_" + base64.urlsafe_b64encode(raw_secret).decode("utf-8")
        timestamp = str(int(time.time()))

        # Generate signature correctly
        msg_id, signature = _generate_signature_correctly(body, secret, timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        }

        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is True
