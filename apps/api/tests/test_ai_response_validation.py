from app.services.ai_prompt_schemas import AIDraftEmailOutput
from app.services.ai_response_validation import (
    parse_json_array,
    parse_json_object,
    validate_model,
    validate_model_list,
)


def test_parse_json_object_handles_code_fence():
    payload = parse_json_object('```json\n{"subject":"Hello","body":"World"}\n```')
    assert payload == {"subject": "Hello", "body": "World"}


def test_parse_json_array_handles_code_fence():
    payload = parse_json_array('```json\n[{"a":1},{"a":2}]\n```')
    assert payload == [{"a": 1}, {"a": 2}]


def test_validate_model_returns_instance():
    model = validate_model(AIDraftEmailOutput, {"subject": "Hi", "body": "There"})
    assert model is not None
    assert model.subject == "Hi"


def test_validate_model_list_filters_invalid_items():
    items = validate_model_list(
        AIDraftEmailOutput,
        [
            {"subject": "Hi", "body": "There"},
            {"subject": "Missing body"},
        ],
    )
    assert len(items) == 1
    assert items[0].subject == "Hi"
