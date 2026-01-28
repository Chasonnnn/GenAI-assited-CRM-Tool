def test_surrogates_router_modules_exist():
    from app.routers import (
        surrogates_contact_attempts,
        surrogates_email,
        surrogates_read,
        surrogates_status,
        surrogates_write,
    )

    assert hasattr(surrogates_read, "router")
    assert hasattr(surrogates_write, "router")
    assert hasattr(surrogates_status, "router")
    assert hasattr(surrogates_email, "router")
    assert hasattr(surrogates_contact_attempts, "router")
