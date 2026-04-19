"""Pagination utilities for list endpoints."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query
from sqlalchemy.orm import Query as SQLAlchemyQuery


T = TypeVar("T")

# Pagination limits
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


@dataclass
class PaginationParams:
    """Pagination parameters from query string."""

    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


def get_pagination(
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(
        DEFAULT_PER_PAGE,
        ge=1,
        le=MAX_PER_PAGE,
        description=f"Items per page (max {MAX_PER_PAGE})",
    ),
) -> PaginationParams:
    """
    Pagination dependency.

    Usage:
        @router.get("/items")
        def list_items(pagination: PaginationParams = Depends(get_pagination)):
            ...
    """
    return PaginationParams(page=page, per_page=per_page)


@dataclass
class PaginatedResponse(Generic[T]):
    """Standard paginated response structure."""

    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int

    @classmethod
    def create(
        cls, items: list[T], total: int, pagination: PaginationParams
    ) -> "PaginatedResponse[T]":
        pages = (
            (total + pagination.per_page - 1) // pagination.per_page
            if pagination.per_page > 0
            else 0
        )
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
            pages=pages,
        )


def _resolve_total(
    items: list,
    *,
    offset: int,
    limit: int,
    count_query: SQLAlchemyQuery,
) -> int:
    if len(items) < limit:
        if offset == 0:
            return len(items)
        if items:
            return offset + len(items)
    return count_query.count()


def paginate_query(
    query: SQLAlchemyQuery,
    pagination: PaginationParams,
    *,
    count_query: SQLAlchemyQuery | None = None,
) -> tuple[list, int]:
    """
    Apply pagination to a SQLAlchemy query.

    Returns:
        (items, total_count)
    """
    items = query.offset(pagination.offset).limit(pagination.per_page).all()
    total = _resolve_total(
        items,
        offset=pagination.offset,
        limit=pagination.per_page,
        count_query=count_query or query,
    )
    return items, total


def paginate_query_by_offset(
    query: SQLAlchemyQuery,
    *,
    offset: int,
    limit: int,
    count_query: SQLAlchemyQuery | None = None,
) -> tuple[list, int]:
    items = query.offset(offset).limit(limit).all()
    total = _resolve_total(
        items,
        offset=offset,
        limit=limit,
        count_query=count_query or query,
    )
    return items, total
