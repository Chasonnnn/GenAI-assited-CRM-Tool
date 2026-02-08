from app.core.security import hash_user_agent, verify_oauth_state, verify_secret


def test_verify_secret():
    assert verify_secret("abc", "abc") is True
    assert verify_secret("abc", "def") is False
    assert verify_secret(None, "abc") is False
    assert verify_secret("abc", None) is False
    assert verify_secret("", "abc") is False


def test_verify_oauth_state_uses_compare_digest_and_behaves_correctly():
    user_agent = "test-agent"
    payload = {
        "state": "state-123",
        "ua_hash": hash_user_agent(user_agent),
        "nonce": "nonce-xyz",
    }

    ok, msg = verify_oauth_state(payload, "state-123", user_agent)
    assert ok is True
    assert msg == ""

    ok, msg = verify_oauth_state(payload, "wrong", user_agent)
    assert ok is False
    assert "State mismatch" in msg

    ok, msg = verify_oauth_state(payload, "state-123", "other-agent")
    assert ok is False
    assert "User-agent mismatch" in msg
