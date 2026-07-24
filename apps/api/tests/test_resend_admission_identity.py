"""Public-contract tests for secret-safe Resend admission identities."""

import pytest


def _identity_module():
    from app.services import resend_admission_identity

    return resend_admission_identity


def test_identical_credentials_share_one_admission_identity_across_logical_routes():
    identity = _identity_module()
    api_key = "re_shared_route_secret_7Dk9"

    platform_route_identity = identity.resolve_resend_admission_identity(
        api_key=api_key,
        group_fingerprint=None,
    )
    organization_route_identity = identity.resolve_resend_admission_identity(
        api_key=api_key,
        group_fingerprint=None,
    )

    assert platform_route_identity == organization_route_identity
    assert platform_route_identity == (
        "credential:4b21d5938bbed221eaf3ebc5551d16c3494d327c18ab54d36e312c3e00d29ff8"
    )
    assert api_key not in platform_route_identity


def test_distinct_credentials_receive_isolated_admission_identities():
    identity = _identity_module()
    first_key = "re_distinct_secret_alpha_7Dk9"
    second_key = "re_distinct_secret_beta_7Dk9"

    first = identity.resolve_resend_admission_identity(
        api_key=first_key,
        group_fingerprint=None,
    )
    second = identity.resolve_resend_admission_identity(
        api_key=second_key,
        group_fingerprint=None,
    )

    assert first == ("credential:8dff5c3f8d436b3c64216d41f68364ea1f6f5e1b2241ff7414031eef096825d5")
    assert second == ("credential:c9d88757749c17b5b6e69d8a6b55a904353a0a83288c998d1b762c0b0c7c1312")
    assert first != second
    assert first_key not in first
    assert second_key not in second


def test_distinct_credentials_with_same_group_fingerprint_share_team_identity():
    identity = _identity_module()
    group_token = "team-token-Alpha-0123456789-abcdef"
    group_fingerprint = identity.admission_group_fingerprint(group_token)

    first = identity.resolve_resend_admission_identity(
        api_key="re_distinct_secret_alpha_7Dk9",
        group_fingerprint=group_fingerprint,
    )
    second = identity.resolve_resend_admission_identity(
        api_key="re_distinct_secret_beta_7Dk9",
        group_fingerprint=group_fingerprint,
    )

    assert group_fingerprint == ("b8989520646473e2db32a491196383a78cabb0b59661d996ee2f518f8cfafb26")
    assert first == f"team:{group_fingerprint}"
    assert second == first
    assert group_token not in first
    assert "re_distinct_secret_alpha_7Dk9" not in first
    assert "re_distinct_secret_beta_7Dk9" not in second


def test_group_fingerprints_are_domain_separated_and_case_sensitive():
    identity = _identity_module()

    upper = identity.admission_group_fingerprint("team-token-Alpha-0123456789-abcdef")
    lower = identity.admission_group_fingerprint("team-token-alpha-0123456789-abcdef")

    assert upper == "b8989520646473e2db32a491196383a78cabb0b59661d996ee2f518f8cfafb26"
    assert lower == "23a211a28da640255ee4de11e3d4eb20b3d4b746d82e1761df2dc82c3a6a28cf"
    assert upper != lower


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        " ",
        " re_valid_but_surrounded_by_whitespace ",
    ],
)
def test_credential_fingerprint_rejects_blank_or_untrimmed_keys(api_key):
    identity = _identity_module()

    with pytest.raises(ValueError):
        identity.credential_fingerprint(api_key)


@pytest.mark.parametrize(
    "group_token",
    [
        "too-short",
        " xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx ",
        "x" * 257,
    ],
)
def test_group_fingerprint_rejects_untrimmed_or_out_of_bounds_tokens(group_token):
    identity = _identity_module()

    with pytest.raises(ValueError):
        identity.admission_group_fingerprint(group_token)


@pytest.mark.parametrize(
    "group_fingerprint",
    [
        "",
        "abc123",
        "B8989520646473E2DB32A491196383A78CABB0B59661D996EE2F518F8CFAFB26",
        "g" * 64,
        "b8989520646473e2db32a491196383a78cabb0b59661d996ee2f518f8cfafb26 ",
    ],
)
def test_resolver_rejects_noncanonical_group_fingerprints(group_fingerprint):
    identity = _identity_module()

    with pytest.raises(ValueError):
        identity.resolve_resend_admission_identity(
            api_key="re_distinct_secret_alpha_7Dk9",
            group_fingerprint=group_fingerprint,
        )
