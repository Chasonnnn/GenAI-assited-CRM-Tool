import pytest

from app.db.enums import AlertType
from app.db.models import SystemAlert


@pytest.mark.anyio
async def test_gcp_alert_webhook_creates_alert(client, db, test_user, test_org, monkeypatch):
    from app.core.config import settings

    settings.INTERNAL_SECRET = "test-internal-secret"

    payload = {
        "incident": {
            "state": "open",
            "policy_display_name": "WS send failed",
            "summary": "Websocket send failures detected",
            "metric": {
                "labels": {
                    "event": "ws_send_failed",
                    "user_id": str(test_user.id),
                }
            },
        }
    }

    res = await client.post(
        "/internal/alerts/gcp",
        headers={"X-Internal-Secret": "test-internal-secret"},
        json=payload,
    )

    assert res.status_code == 200

    alert = db.query(SystemAlert).filter(SystemAlert.organization_id == test_org.id).first()
    assert alert is not None
    assert alert.alert_type == AlertType.NOTIFICATION_PUSH_FAILED.value
