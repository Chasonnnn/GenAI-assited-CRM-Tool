"""New case writes stay fenced while API and worker revisions are mixed."""

import uuid

import pytest

from app.core.config import settings
from app.db.models import Attachment, EntityNote, Match, MatchAttempt, Task
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _accept, _case, _donor


@pytest.mark.asyncio
async def test_disabled_expansion_preserves_legacy_match_operations(authed_client, db, monkeypatch):
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    case = await _case(authed_client, ip, surrogate=surrogate)
    accepted = await _accept(authed_client, case)
    assert accepted["status"] == "accepted"
    assert (await authed_client.get(f"/matches/{case['id']}")).status_code == 200
    before = db.query(Match).count()
    donor = await _donor(authed_client)
    response = await authed_client.post(
        "/matches/", json={"donor_id": donor["id"], "intended_parent_id": ip["id"]}
    )
    assert response.status_code == 503
    assert db.query(Match).count() == before
    response = await authed_client.post(
        f"/matches/{case['id']}/attempts", json={"attempt_type": "embryo_transfer"}
    )
    assert response.status_code == 503
    assert db.query(MatchAttempt).count() == 0
    response = await authed_client.put(
        f"/matches/{case['id']}/complete", json={"outcome": "Completed"}
    )
    assert response.status_code == 503
    db.expire_all()
    assert db.get(Match, uuid.UUID(case["id"])).status == "accepted"


@pytest.mark.asyncio
async def test_disabled_expansion_rejects_repeat_pairs(authed_client, db, monkeypatch):
    ip = await _create_intended_parent(authed_client)
    surrogate = await _create_surrogate(authed_client)
    case = await _case(authed_client, ip, surrogate=surrogate)
    response = await authed_client.put(
        f"/matches/{case['id']}/reject", json={"rejection_reason": "Not proceeding"}
    )
    assert response.status_code == 200
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    response = await authed_client.post(
        "/matches/", json={"surrogate_id": surrogate["id"], "intended_parent_id": ip["id"]}
    )
    assert response.status_code == 503
    assert db.query(Match).count() == 1


@pytest.mark.asyncio
async def test_disabled_expansion_rejects_parallel_ip_commitment(authed_client, monkeypatch):
    ip = await _create_intended_parent(authed_client)
    first = await _create_surrogate(authed_client)
    second = await _create_surrogate(authed_client)
    await _accept(authed_client, await _case(authed_client, ip, surrogate=first))
    second_case = await _case(authed_client, ip, surrogate=second)
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    response = await authed_client.put(f"/matches/{second_case['id']}/accept", json={})
    assert response.status_code == 503


def test_expansion_requires_explicit_activation(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("MATCH_CASE_EXPANSION_ENABLED", raising=False)
    assert Settings(_env_file=None).MATCH_CASE_EXPANSION_ENABLED is False


@pytest.mark.asyncio
async def test_disabling_expansion_keeps_history_readable_and_blocks_new_work(
    authed_client, db, monkeypatch
):
    import io

    from PIL import Image

    donor = await _donor(authed_client)
    ip = await _create_intended_parent(authed_client)
    case = await _accept(authed_client, await _case(authed_client, ip, donor=donor))
    attempt = await authed_client.post(
        f"/matches/{case['id']}/attempts", json={"attempt_type": "retrieval"}
    )
    assert attempt.status_code == 201
    monkeypatch.setattr(settings, "MATCH_CASE_EXPANSION_ENABLED", False)
    assert (await authed_client.get(f"/matches/{case['id']}")).status_code == 200
    assert len((await authed_client.get(f"/matches/{case['id']}/attempts")).json()) == 1
    assert (await authed_client.get(f"/matches/{case['id']}/work")).status_code == 200
    updated = await authed_client.patch(
        f"/matches/{case['id']}/attempts/{attempt.json()['id']}", json={"status": "completed"}
    )
    assert updated.status_code == 503
    before = [db.query(model).count() for model in (Task, EntityNote, Attachment)]
    note = await authed_client.post(f"/matches/{case['id']}/notes", json={"content": "Blocked"})
    assert note.status_code == 503
    task = await authed_client.post("/tasks", json={"title": "Blocked", "match_id": case["id"]})
    assert task.status_code == 503
    content = io.BytesIO()
    Image.new("RGB", (1, 1)).save(content, format="PNG")
    file = await authed_client.post(
        f"/matches/{case['id']}/attachments",
        files={"file": ("blocked.png", content.getvalue(), "image/png")},
    )
    assert file.status_code == 503
    assert [db.query(model).count() for model in (Task, EntityNote, Attachment)] == before
