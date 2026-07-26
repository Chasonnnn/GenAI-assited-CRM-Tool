from pathlib import Path


def test_only_durable_dispatcher_calls_resend_transport() -> None:
    app_root = Path(__file__).parents[1] / "app"
    callers = []
    for path in app_root.rglob("*.py"):
        if "resend_transport.send_email(" in path.read_text(encoding="utf-8"):
            callers.append(path.relative_to(app_root).as_posix())

    assert callers == ["services/email_delivery_dispatch.py"]
