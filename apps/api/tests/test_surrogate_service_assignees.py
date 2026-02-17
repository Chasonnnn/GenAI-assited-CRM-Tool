from unittest.mock import MagicMock
from app.services.surrogate_service import list_assignees
from app.db.models import User, Membership

def test_list_assignees_query_optimization():
    # Mock DB session
    db = MagicMock()

    # Mock query chain
    mock_query = db.query.return_value
    mock_join = mock_query.join.return_value
    mock_filter = mock_join.filter.return_value

    # Mock results
    # The optimized query will return tuples of (User.id, User.display_name, Membership.role)
    mock_filter.all.return_value = [
        ("user_id_1", "User 1", "case_manager"),
        ("user_id_2", "User 2", "admin"),
    ]

    org_id = "some-uuid"

    # Execute
    result = list_assignees(db, org_id)

    # Verification
    # Assert that db.query was called with specific columns, NOT full models
    args, _ = db.query.call_args
    assert len(args) == 3
    # Check that we selected the right columns (User.id, User.display_name, Membership.role)
    # Since these are SQLAlchemy InstrumentedAttributes, we can compare them directly or by string
    assert str(args[0]) == str(User.id)
    assert str(args[1]) == str(User.display_name)
    assert str(args[2]) == str(Membership.role)

    # Check result structure
    assert len(result) == 2
    assert result[0]["id"] == "user_id_1"
    assert result[0]["name"] == "User 1"
    assert result[0]["role"] == "case_manager"

    assert result[1]["id"] == "user_id_2"
    assert result[1]["name"] == "User 2"
    assert result[1]["role"] == "admin"
