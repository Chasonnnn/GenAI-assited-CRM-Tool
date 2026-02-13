import pytest

from app.utils.normalization import escape_like_string


def test_escape_like_string_escapes_wildcards_and_backslash():
    assert escape_like_string(r"100%_match\path") == r"100\%\_match\\path"


@pytest.mark.asyncio
async def test_task_search_treats_percent_as_literal(authed_client):
    response_normal = await authed_client.post(
        "/tasks",
        json={"title": "Normal task title"},
    )
    assert response_normal.status_code == 201, response_normal.text
    normal_task_id = response_normal.json()["id"]

    response_percent = await authed_client.post(
        "/tasks",
        json={"title": "Task 100% complete"},
    )
    assert response_percent.status_code == 201, response_percent.text
    percent_task_id = response_percent.json()["id"]

    search_response = await authed_client.get("/tasks?q=%")
    assert search_response.status_code == 200, search_response.text

    returned_ids = {item["id"] for item in search_response.json()["items"]}
    assert percent_task_id in returned_ids
    assert normal_task_id not in returned_ids
