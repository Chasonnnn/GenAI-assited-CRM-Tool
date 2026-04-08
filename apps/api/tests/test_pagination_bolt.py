import pytest
from app.utils.pagination import paginate_query, PaginationParams

class MockQuery:
    def __init__(self, data):
        self.data = data
        self.count_called = 0
        self.current_offset = 0
        self.current_limit = None

    def count(self):
        self.count_called += 1
        return len(self.data)

    def offset(self, off):
        self.current_offset = off
        return self

    def limit(self, lim):
        self.current_limit = lim
        return self

    def all(self):
        start = self.current_offset
        end = start + self.current_limit if self.current_limit else None
        return self.data[start:end]

def test_pagination_count_optimization_first_page_incomplete():
    # Only 3 items, page size is 10. offset=0, len=3 < 10
    q = MockQuery([1, 2, 3])
    p = PaginationParams(page=1, per_page=10)
    items, total = paginate_query(q, p)
    assert items == [1, 2, 3]
    assert total == 3
    assert q.count_called == 0 # Should NOT be called

def test_pagination_count_optimization_first_page_exact():
    # Exactly 10 items, page size is 10. offset=0, len=10 == 10
    q = MockQuery(list(range(10)))
    p = PaginationParams(page=1, per_page=10)
    items, total = paginate_query(q, p)
    assert len(items) == 10
    assert total == 10
    assert q.count_called == 1 # SHOULD be called, length == per_page

def test_pagination_count_optimization_first_page_empty():
    # 0 items, page size is 10. offset=0, len=0 < 10
    q = MockQuery([])
    p = PaginationParams(page=1, per_page=10)
    items, total = paginate_query(q, p)
    assert items == []
    assert total == 0
    assert q.count_called == 0 # Should NOT be called since offset=0

def test_pagination_count_optimization_middle_page_incomplete():
    # 25 items, page 3, size 10. offset=20, len=5 < 10
    q = MockQuery(list(range(25)))
    p = PaginationParams(page=3, per_page=10)
    items, total = paginate_query(q, p)
    assert len(items) == 5
    assert total == 25
    assert q.count_called == 0 # Should NOT be called

def test_pagination_count_optimization_middle_page_exact():
    # 30 items, page 3, size 10. offset=20, len=10 == 10
    q = MockQuery(list(range(30)))
    p = PaginationParams(page=3, per_page=10)
    items, total = paginate_query(q, p)
    assert len(items) == 10
    assert total == 30
    assert q.count_called == 1 # SHOULD be called

def test_pagination_count_optimization_middle_page_empty():
    # 20 items, page 3, size 10. offset=20, len=0 < 10.
    # offset > 0 and len(items) == 0 means we could be out of bounds, must count.
    q = MockQuery(list(range(20)))
    p = PaginationParams(page=3, per_page=10)
    items, total = paginate_query(q, p)
    assert items == []
    assert total == 20
    assert q.count_called == 1 # SHOULD be called
