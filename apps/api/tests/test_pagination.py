from __future__ import annotations

from app.utils.pagination import PaginationParams, paginate_query


class MockQuery:
    def __init__(self, items: list[int]) -> None:
        self._items = items
        self._offset = 0
        self._limit: int | None = None
        self.count_calls = 0

    def offset(self, offset: int) -> "MockQuery":
        self._offset = offset
        return self

    def limit(self, limit: int) -> "MockQuery":
        self._limit = limit
        return self

    def all(self) -> list[int]:
        end = None if self._limit is None else self._offset + self._limit
        return self._items[self._offset:end]

    def count(self) -> int:
        self.count_calls += 1
        return len(self._items)


def test_paginate_query_skips_count_for_short_first_page() -> None:
    query = MockQuery([1, 2, 3])

    items, total = paginate_query(query, PaginationParams(page=1, per_page=5))

    assert items == [1, 2, 3]
    assert total == 3
    assert query.count_calls == 0


def test_paginate_query_skips_count_for_short_later_page() -> None:
    query = MockQuery([1, 2, 3, 4, 5, 6, 7])

    items, total = paginate_query(query, PaginationParams(page=2, per_page=5))

    assert items == [6, 7]
    assert total == 7
    assert query.count_calls == 0


def test_paginate_query_counts_for_full_page() -> None:
    query = MockQuery([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    items, total = paginate_query(query, PaginationParams(page=1, per_page=5))

    assert items == [1, 2, 3, 4, 5]
    assert total == 10
    assert query.count_calls == 1


def test_paginate_query_counts_for_empty_out_of_range_page() -> None:
    query = MockQuery([1, 2, 3])

    items, total = paginate_query(query, PaginationParams(page=2, per_page=5))

    assert items == []
    assert total == 3
    assert query.count_calls == 1
