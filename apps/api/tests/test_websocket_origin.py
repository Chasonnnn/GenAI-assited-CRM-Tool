from app.routers.websocket import _origin_is_allowed


def test_origin_allowed_in_dev_even_if_not_listed():
    allowed = {"http://localhost:3000"}
    assert _origin_is_allowed("http://evil.com", allowed=allowed, is_dev=True)


def test_origin_allowed_in_dev_when_missing():
    allowed = {"http://localhost:3000"}
    assert _origin_is_allowed(None, allowed=allowed, is_dev=True)


def test_origin_allows_listed_origin_in_prod():
    allowed = {"http://localhost:3000"}
    assert _origin_is_allowed("http://localhost:3000", allowed=allowed, is_dev=False)


def test_origin_rejects_unlisted_origin_in_prod():
    allowed = {"http://localhost:3000"}
    assert not _origin_is_allowed("http://evil.com", allowed=allowed, is_dev=False)


def test_origin_rejects_missing_origin_in_prod():
    allowed = {"http://localhost:3000"}
    assert not _origin_is_allowed(None, allowed=allowed, is_dev=False)
