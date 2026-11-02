"""Match accept eligibility for each participant kind and stage.

Split from test_match_participant_stages.py.
"""

import uuid

import pytest

from app.db.enums import Role
from app.db.models import (
    Donor,
    IntendedParent,
    Surrogate,
)
from app.services import (
    match_lifecycle,
)
from tests.test_match_cancel_request import _create_intended_parent, _create_surrogate
from tests.test_match_cases import _case, _donor
from tests.test_match_lifecycle_characterization import (
    _match_row,
)
from tests.test_match_participant_stages import (
    _stage,
)
from tests.test_match_permissions_v2_characterization import _activate_v2


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_accept_eligibility_warning_names_ineligible_party_and_stage(
    authed_client, db, test_auth, policy, subtests
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    for kind, blocked, stage in [
        ("surrogate", "party", "new_unread"),
        ("surrogate", "party", "approved"),
        ("surrogate", "party", "matched"),
        ("egg", "party", "new"),
        ("egg", "party", "approved"),
        ("egg", "party", "matched"),
        ("sperm", "party", "new"),
        ("sperm", "party", "approved"),
        ("sperm", "party", "matched"),
        ("surrogate", "ip", "new"),
        ("egg", "ip", "delivered"),
        ("sperm", "ip", "new"),
    ]:
        with subtests.test(kind=kind, blocked=blocked, stage=stage):
            donor = kind != "surrogate"
            party = (
                await _donor(authed_client, donor_type=kind)
                if donor
                else await _create_surrogate(authed_client)
            )
            ip = await _create_intended_parent(authed_client)
            record = db.get(
                IntendedParent if blocked == "ip" else Donor if donor else Surrogate,
                uuid.UUID(ip["id"] if blocked == "ip" else party["id"]),
            )
            target = _stage(db, record, stage)
            match = await _case(authed_client, ip, **{"donor" if donor else "surrogate": party})
            label = "Intended parent" if blocked == "ip" else "Donor" if donor else "Surrogate"
            expected = f"{label} at {target.label} is not eligible to accept"
            assert match["status"] == "under_review"
            assert match["accept_eligibility_warnings"] == [expected]
            assert "accept" not in match["allowed_actions"]
            assert match["blocked_reasons"]["accept"] == expected
            assert match["surrogate_has_accepted_match"] is False
            response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
            assert response.status_code == 400, response.text
            assert response.json()["detail"] == expected
            assert _match_row(db, match["id"]).status == "under_review"
            assert db.get(type(record), record.id).stage_id == target.id
            with pytest.raises(match_lifecycle.TransitionError, match="is not eligible to accept"):
                match_lifecycle.transition(
                    db,
                    _match_row(db, match["id"]),
                    "accept",
                    actor_user_id=test_auth.user.id,
                    actor_role=Role.DEVELOPER,
                )


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [1, 2])
async def test_accept_reports_all_ineligible_parties_in_preview_and_http(
    authed_client, db, test_auth, policy, subtests
):
    if policy == 2:
        _activate_v2(db, test_auth.org.id)
    for kind in ["surrogate", "egg", "sperm"]:
        with subtests.test(kind=repr(kind)):
            is_donor = kind != "surrogate"
            party = (
                await _donor(authed_client, donor_type=kind)
                if is_donor
                else await _create_surrogate(authed_client)
            )
            ip = await _create_intended_parent(authed_client)
            primary = db.get(Donor if is_donor else Surrogate, uuid.UUID(party["id"]))
            intended_parent = db.get(IntendedParent, uuid.UUID(ip["id"]))
            primary_stage = _stage(db, primary, "new" if is_donor else "new_unread")
            ip_stage = _stage(db, intended_parent, "new")
            match = await _case(authed_client, ip, **{"donor" if is_donor else "surrogate": party})
            warnings = match["accept_eligibility_warnings"]
            assert len(warnings) == 2
            assert warnings[0].startswith("Donor at" if is_donor else "Surrogate at")
            assert warnings[1].startswith("Intended parent at")
            expected = "; ".join(warnings)
            assert match["blocked_reasons"]["accept"] == expected
            assert "accept" not in match["allowed_actions"]
            response = await authed_client.put(f"/matches/{match['id']}/accept", json={})
            assert response.status_code == 400
            assert response.json()["detail"] == expected
            assert _match_row(db, match["id"]).status == "under_review"
            assert primary.stage_id == primary_stage.id
            assert intended_parent.stage_id == ip_stage.id
