from unittest.mock import MagicMock
from uuid import uuid4
from app.services import surrogate_service
from app.db.models import Surrogate


def test_list_surrogates_optimizes_count_query():
    mock_db = MagicMock()

    # Setup the chain for the main query
    # When db.query(Surrogate) is called
    mock_main_query = MagicMock()

    # When db.query(func.count(Surrogate.id)) is called (optimized path)
    mock_count_query = MagicMock()
    mock_count_query.filter.return_value = mock_count_query
    mock_count_query.scalar.return_value = 42

    def query_side_effect(*args):
        # Current implementation calls db.query(Surrogate)
        if args and args[0] is Surrogate:
            return mock_main_query

        # If we optimize, it will call db.query(func.count(Surrogate.id))
        # We assume any other call is the count query for this test context
        return mock_count_query

    mock_db.query.side_effect = query_side_effect

    # Setup main query chain
    mock_main_query.options.return_value = mock_main_query
    mock_main_query.filter.return_value = mock_main_query
    mock_main_query.order_by.return_value = mock_main_query
    mock_main_query.offset.return_value = mock_main_query
    mock_main_query.limit.return_value = mock_main_query
    mock_main_query.all.return_value = []
    mock_main_query.count.return_value = 100  # Unoptimized path returns this

    # Call
    org_id = uuid4()
    surrogate_service.list_surrogates(db=mock_db, org_id=org_id, include_total=True)

    # Check if unoptimized .count() was called on the main query
    if mock_main_query.count.called:
        print("\nUnoptimized: .count() was called on the main query (potentially with joins).")
    else:
        print("\nOptimized: .count() was NOT called on the main query.")

    if mock_count_query.scalar.called:
        print("Optimized: separate count query was executed.")
    else:
        print("Unoptimized: separate count query was NOT executed.")

    # Assertion for the final state (I want this test to pass ONLY if optimized)
    assert not mock_main_query.count.called, (
        "Should not call .count() on main query with eager loads"
    )
    assert mock_count_query.scalar.called, "Should execute separate optimized count query"
