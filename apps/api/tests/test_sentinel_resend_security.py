
import base64
import hashlib
import hmac
import time
import pytest
from app.services.webhooks.resend import _verify_svix_signature

def _generate_signature_with_raw_secret(body: bytes, secret: str, timestamp: str) -> str:
    """
    Generate signature using the raw secret string bytes, mimicking the fallback behavior.
    """
    msg_id = "msg_test"
    signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

    # Intentionally use the raw secret string as bytes
    secret_bytes = secret.encode("utf-8")

    signature = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return msg_id, f"v1,{signature_b64}"

def test_verify_svix_signature_fallback_vulnerability():
    """
    This test demonstrates that the current implementation accepts a signature
    generated with the RAW secret string even if it has a 'whsec_' prefix
    but is invalid Base64 (contains non-ascii characters).
    """
    # A secret that starts with whsec_ and contains non-ascii characters
    # This will fail base64 decoding (ValueError) and trigger the fallback.
    secret = "whsec_secret_with_emoji_😊"

    body = b'{"test": "data"}'
    timestamp = str(int(time.time()))

    # Generate signature using the WHOLE secret string (including prefix if fallback uses it? No, wait)

    # Wait, the code:
    # 1. secret.startswith("whsec_") -> Yes.
    # 2. secret = secret[6:] -> "secret_with_emoji_😊"
    # 3. tries to decode "secret_with_emoji_😊" -> ValueError
    # 4. secret_bytes = secret.encode("utf-8") -> "secret_with_emoji_😊".encode("utf-8")

    stripped_secret = secret[6:]
    msg_id, signature = _generate_signature_with_raw_secret(body, stripped_secret, timestamp)

    headers = {
        "svix-id": msg_id,
        "svix-timestamp": timestamp,
        "svix-signature": signature,
    }

    # This should return False now that we've fixed the vulnerability.
    is_valid = _verify_svix_signature(body, headers, secret)

    print(f"Is valid (should be False): {is_valid}")
    assert is_valid is False

if __name__ == "__main__":
    test_verify_svix_signature_fallback_vulnerability()
