
import json
import base64
from app.core.security import create_oauth_state_payload, parse_oauth_state_payload

def test_oauth_state_cookie_encoding():
    state = "test-state"
    nonce = "test-nonce"
    user_agent = "test-agent"
    return_to = "app"

    # Create payload
    encoded_payload = create_oauth_state_payload(state, nonce, user_agent, return_to)

    # Verify it's not JSON (no curly braces or double quotes)
    assert "{" not in encoded_payload
    assert '"' not in encoded_payload
    assert "}" not in encoded_payload

    # Verify it's valid base64
    decoded_bytes = base64.urlsafe_b64decode(encoded_payload)
    decoded_str = decoded_bytes.decode()
    decoded_json = json.loads(decoded_str)

    assert decoded_json["state"] == state
    assert decoded_json["nonce"] == nonce
    assert decoded_json["return_to"] == return_to

    # Verify parsing works
    parsed_payload = parse_oauth_state_payload(encoded_payload)
    assert parsed_payload["state"] == state
    assert parsed_payload["nonce"] == nonce
    assert parsed_payload["return_to"] == return_to

def test_legacy_cookie_fallback():
    # Simulate a legacy unencoded cookie
    legacy_payload = json.dumps({
        "state": "legacy-state",
        "nonce": "legacy-nonce",
        "ua_hash": "legacy-hash",
        "return_to": "app"
    })

    parsed_payload = parse_oauth_state_payload(legacy_payload)
    assert parsed_payload["state"] == "legacy-state"
    assert parsed_payload["nonce"] == "legacy-nonce"
