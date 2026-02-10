
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.dashboard_service import get_attention_items
from app.db.enums import Role

def test_get_attention_items_optimization():
    """
    Verify that get_attention_items uses NOT EXISTS and avoids GROUP BY
    for performance optimization.
    """
    db = MagicMock()

    # Setup chain to handle fluent API
    # db.query(...) -> query
    # query.join(...) -> query
    # query.filter(...) -> query
    # ...
    query_mock = MagicMock()
    db.query.return_value = query_mock
    query_mock.join.return_value = query_mock
    query_mock.outerjoin.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.limit.return_value = query_mock

    # Mock return values for execution methods
    query_mock.all.return_value = []
    query_mock.scalar.return_value = 0

    org_id = uuid4()
    user_id = uuid4()

    # Call the function
    get_attention_items(db, org_id, user_id, Role.CASE_MANAGER)

    # 1. Verify GROUP BY is NOT called (this was the bottleneck)
    assert not query_mock.group_by.called, "Should not use GROUP BY for stuck surrogates"

    # 2. Verify EXISTS is used in filter
    found_exists = False

    # We inspect all calls to .filter()
    # The arguments are SQLAlchemy BinaryExpressions or similar.
    # Converting them to string usually produces SQL-like output representation.
    for call in query_mock.filter.call_args_list:
        args, _ = call
        for arg in args:
            arg_str = str(arg)
            # The optimized query uses ~exists(...) which renders as "NOT EXISTS"
            if "EXISTS" in arg_str:
                found_exists = True
                print(f"Found EXISTS clause: {arg_str}")

    assert found_exists, "Expected NOT EXISTS clause in query filters"
