"""Tests for MFA service and endpoints.

Tests cover:
- TOTP secret generation and verification
- Recovery code generation and validation
- MFA enrollment flow
"""

from app.services import mfa_service


class TestTOTPGeneration:
    """Tests for TOTP secret and code generation."""

    def test_generate_totp_secret_length(self):
        """Generated secrets should be 32 characters base32."""
        secret = mfa_service.generate_totp_secret()
        assert len(secret) == 32
        # Base32 characters
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_generate_totp_secret_uniqueness(self):
        """Each generated secret should be unique."""
        secrets = [mfa_service.generate_totp_secret() for _ in range(10)]
        assert len(set(secrets)) == 10

    def test_provisioning_uri_format(self):
        """Provisioning URI should have correct format for authenticator apps."""
        secret = "JBSWY3DPEHPK3PXP"  # Test secret
        email = "test@example.com"
        
        uri = mfa_service.get_totp_provisioning_uri(secret, email)
        
        assert uri.startswith("otpauth://totp/")
        assert "SurrogacyCRM" in uri  # Issuer
        assert "test%40example.com" in uri or "test@example.com" in uri  # Email


class TestTOTPVerification:
    """Tests for TOTP code verification."""

    def test_verify_valid_code(self):
        """Valid TOTP code should pass verification."""
        import pyotp
        
        secret = "JBSWY3DPEHPK3PXP"
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        
        assert mfa_service.verify_totp_code(secret, current_code) is True

    def test_verify_invalid_code(self):
        """Invalid TOTP code should fail verification."""
        secret = "JBSWY3DPEHPK3PXP"
        
        assert mfa_service.verify_totp_code(secret, "000000") is False
        assert mfa_service.verify_totp_code(secret, "123456") is False

    def test_verify_empty_inputs(self):
        """Empty secret or code should return False."""
        assert mfa_service.verify_totp_code("", "123456") is False
        assert mfa_service.verify_totp_code("JBSWY3DPEHPK3PXP", "") is False
        assert mfa_service.verify_totp_code(None, "123456") is False

    def test_verify_code_with_spaces(self):
        """Code with spaces should be sanitized and verified."""
        import pyotp
        
        secret = "JBSWY3DPEHPK3PXP"
        totp = pyotp.TOTP(secret)
        code = totp.now()
        code_with_spaces = f"{code[:3]} {code[3:]}"
        
        assert mfa_service.verify_totp_code(secret, code_with_spaces) is True


class TestRecoveryCodes:
    """Tests for recovery code generation and validation."""

    def test_generate_recovery_codes_count(self):
        """Should generate the specified number of codes."""
        codes = mfa_service.generate_recovery_codes(8)
        assert len(codes) == 8

    def test_generate_recovery_codes_format(self):
        """Codes should be 8 uppercase alphanumeric characters."""
        codes = mfa_service.generate_recovery_codes(5)
        for code in codes:
            assert len(code) == 8
            assert code.isupper() or code.isdigit()

    def test_generate_recovery_codes_no_ambiguous_chars(self):
        """Codes should not contain ambiguous characters (0, O, 1, I, L)."""
        # Generate many codes to increase chance of catching issues
        codes = mfa_service.generate_recovery_codes(100)
        for code in codes:
            assert "0" not in code
            assert "O" not in code
            assert "1" not in code
            assert "I" not in code
            assert "L" not in code

    def test_hash_recovery_code(self):
        """Hashing should produce consistent SHA-256 hashes."""
        code = "ABCD1234"
        hash1 = mfa_service.hash_recovery_code(code)
        hash2 = mfa_service.hash_recovery_code(code)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_hash_recovery_code_case_insensitive(self):
        """Hashing should be case-insensitive."""
        hash1 = mfa_service.hash_recovery_code("ABCD1234")
        hash2 = mfa_service.hash_recovery_code("abcd1234")
        
        assert hash1 == hash2

    def test_verify_recovery_code_valid(self):
        """Valid recovery code should be found in hashed list."""
        code = "ABCD1234"
        hashed = mfa_service.hash_recovery_codes([code, "EFGH5678"])
        
        is_valid, index = mfa_service.verify_recovery_code(code, hashed)
        
        assert is_valid is True
        assert index == 0

    def test_verify_recovery_code_invalid(self):
        """Invalid code should not be found."""
        hashed = mfa_service.hash_recovery_codes(["ABCD1234", "EFGH5678"])
        
        is_valid, index = mfa_service.verify_recovery_code("XXXX9999", hashed)
        
        assert is_valid is False
        assert index == -1

    def test_verify_recovery_code_case_insensitive(self):
        """Verification should work regardless of case."""
        hashed = mfa_service.hash_recovery_codes(["ABCD1234"])
        
        is_valid, _ = mfa_service.verify_recovery_code("abcd1234", hashed)
        
        assert is_valid is True


class TestMFAStatus:
    """Tests for MFA status checks."""

    def test_is_mfa_required_always_true(self):
        """MFA should be required for all users currently."""
        # Create a mock user
        class MockUser:
            mfa_enabled = False

        assert mfa_service.is_mfa_required(MockUser()) is True

    def test_has_mfa_setup_with_totp(self):
        """User with TOTP enabled should have MFA setup."""
        from datetime import datetime, timezone

        class MockUser:
            mfa_enabled = True
            totp_enabled_at = datetime.now(timezone.utc)
            duo_enrolled_at = None

        assert mfa_service.has_mfa_setup(MockUser()) is True

    def test_has_mfa_setup_without_enrollment(self):
        """User without enrollment should not have MFA setup."""
        class MockUser:
            mfa_enabled = False
            totp_enabled_at = None
            duo_enrolled_at = None

        assert mfa_service.has_mfa_setup(MockUser()) is False
