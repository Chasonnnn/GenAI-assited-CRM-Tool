"""Utility modules."""

from app.utils.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_state,
)
from app.utils.pagination import (
    PaginatedResponse,
    PaginationParams,
    get_pagination,
    paginate_query,
)

__all__ = [
    # Normalization
    "normalize_email",
    "normalize_name",
    "normalize_phone",
    "normalize_state",
    # Pagination
    "PaginationParams",
    "PaginatedResponse",
    "get_pagination",
    "paginate_query",
]
