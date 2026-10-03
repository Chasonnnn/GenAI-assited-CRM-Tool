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


@pytest.mark.parametrize("symbol", ["%", "_", "\\"])
def test_surrogate_fallback_matches_literal_metacharacters(
    db, test_org, test_user, default_stage, symbol
):
    from app.core.encryption import hash_email
    from app.db.models import Organization, Surrogate
    from app.services import search_service

    other = Organization(name="Other search tenant", slug=f"search-other-{symbol.encode().hex()}")
    db.add(other)
    db.flush()
    rows = []
    for index, (org_id, name) in enumerate(
        [
            (test_org.id, f"Mark{symbol}tail"),
            (test_org.id, "MarkXtail"),
            (other.id, f"Mark{symbol}tail"),
        ]
    ):
        row = Surrogate(
            organization_id=org_id,
            stage_id=default_stage.id,
            full_name=name,
            full_name_normalized=name.lower(),
            email=f"search-{index}@example.test",
            email_hash=hash_email(f"search-{index}@example.test"),
            surrogate_number=f"S9900{index}",
            surrogate_number_normalized=f"s9900{index}",
            status_label=default_stage.label,
            source="manual",
            owner_type="user",
            owner_id=test_user.id,
            created_by_user_id=test_user.id,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    results = search_service._search_surrogates(
        db, test_org.id, f"ark{symbol}ta", 20, 0, "developer", test_user.id, True
    )
    assert {result["entity_id"] for result in results} == {str(rows[0].id)}
    # Identifier fallback must not interpret wildcard-only queries as all record numbers.
    results = search_service._search_surrogates(
        db, test_org.id, f"990{symbol}", 20, 0, "developer", test_user.id, True
    )
    assert results == []


@pytest.mark.parametrize("symbol", ["%", "_", "\\"])
@pytest.mark.parametrize("field", ["subject", "requester_email", "ticket_code"])
def test_ticket_search_matches_literal_metacharacters(db, test_org, symbol, field):
    from app.db.models import Organization, Ticket
    from app.services import ticketing_service

    other = Organization(name="Other ticket tenant", slug="ticket-other")
    db.add(other)
    db.flush()
    rows = []
    for index, (org_id, value) in enumerate(
        [
            (test_org.id, f"mark{symbol}tail"),
            (test_org.id, "markXtail"),
            (other.id, f"mark{symbol}tail"),
        ]
    ):
        values = {
            "subject": "Unrelated",
            "requester_email": "other@example.test",
            "ticket_code": f"T{index:05d}",
        }
        values[field] = value
        row = Ticket(organization_id=org_id, **values)
        db.add(row)
        rows.append(row)
    db.flush()
    result = ticketing_service.list_tickets(
        db, org_id=test_org.id, limit=20, cursor=None, q=f"ark{symbol}ta"
    )
    assert {item.id for item in result.items} == {rows[0].id}
