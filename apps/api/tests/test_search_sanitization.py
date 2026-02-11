from app.utils.normalization import escape_like_string

def test_escape_like_string():
    """
    Unit test for escape_like_string utility.
    """
    assert escape_like_string("foo") == "foo"
    assert escape_like_string("foo%bar") == "foo\\%bar"
    assert escape_like_string("foo_bar") == "foo\\_bar"
    assert escape_like_string("foo\\bar") == "foo\\\\bar"
    assert escape_like_string("%_\\") == "\\%\\_\\\\"
    assert escape_like_string(None) is None
