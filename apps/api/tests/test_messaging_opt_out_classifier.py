import pytest

from app.services.messaging_opt_out_classifier import classify_consent_instruction


def test_stop_keyword_is_a_global_opt_out() -> None:
    assert classify_consent_instruction("STOP") == "global_opt_out"


@pytest.mark.parametrize("keyword", ["STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"])
def test_standard_stop_keywords_are_global_opt_outs(keyword: str) -> None:
    assert classify_consent_instruction(keyword) == "global_opt_out"


@pytest.mark.parametrize("keyword", ["START", "UNSTOP"])
def test_restore_keywords_are_classified_for_purpose_restoration(keyword: str) -> None:
    assert classify_consent_instruction(keyword) == "restore"


@pytest.mark.parametrize(
    "message_text",
    [
        "Stop promotional messages",
        "Please unsubscribe me from marketing offers",
        "Do not send referral bonus ads",
    ],
)
def test_explicit_marketing_revocations_are_promotional_only(message_text: str) -> None:
    assert classify_consent_instruction(message_text) == "promotional_opt_out"


@pytest.mark.parametrize(
    "message_text",
    ["Please stop texting me", "Don't send me any more texts", "Remove me from all messages"],
)
def test_clear_natural_language_revocations_are_global(message_text: str) -> None:
    assert classify_consent_instruction(message_text) == "global_opt_out"


@pytest.mark.parametrize(
    "message_text",
    [
        "Stop all messages, including promotional offers",
        "Do not contact me again",
        "Please don't text this number anymore",
    ],
)
def test_explicit_all_channel_revocations_take_priority_over_promotional_terms(
    message_text: str,
) -> None:
    assert classify_consent_instruction(message_text) == "global_opt_out"


@pytest.mark.parametrize("message_text", ["Stop this", "I don't want these updates"])
def test_unclear_revocation_scope_creates_a_provisional_hold(message_text: str) -> None:
    assert classify_consent_instruction(message_text) == "ambiguous_hold"


def test_unrelated_reply_does_not_change_consent() -> None:
    assert classify_consent_instruction("Can we talk tomorrow?") == "none"


def test_incidental_stop_word_does_not_change_consent() -> None:
    assert classify_consent_instruction("Can you stop by tomorrow?") == "none"
