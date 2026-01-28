from app.services.pii_anonymizer import PIIMapping, anonymize_text, rehydrate_text


def test_anonymize_text_redacts_sensitive_fields():
    mapping = PIIMapping()
    text = "DOB: 01/02/1990, SSN: 123-45-6789, Address: 123 Main St"

    anonymized = anonymize_text(text, mapping)

    assert "01/02/1990" not in anonymized
    assert "123-45-6789" not in anonymized
    assert "123 Main St" not in anonymized

    rehydrated = rehydrate_text(anonymized, mapping)
    assert "01/02/1990" in rehydrated
    assert "123-45-6789" in rehydrated
    assert "123 Main St" in rehydrated
