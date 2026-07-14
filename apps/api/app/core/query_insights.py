"""Low-cardinality SQLCommenter tags for Cloud SQL Query Insights."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import re
from typing import Iterator
from urllib.parse import quote

from fastapi import Request
from sqlalchemy import event

from app.core.config import settings


@dataclass(frozen=True)
class QueryInsightsContext:
    method: str
    route_template: str
    release: str


_context: ContextVar[QueryInsightsContext | None] = ContextVar(
    "query_insights_context",
    default=None,
)
_QUERY_PREFIX = re.compile(r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|WITH)\b", re.IGNORECASE)
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_RELEASE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _validate_context(*, method: str, route_template: str, release: str) -> QueryInsightsContext:
    normalized_method = method.upper()
    if normalized_method not in _METHODS:
        raise ValueError("Unsupported HTTP method for Query Insights tag")
    if not route_template.startswith("/") or "?" in route_template or len(route_template) > 240:
        raise ValueError("Query Insights route must be a bounded route template")
    if not _RELEASE.fullmatch(release):
        raise ValueError("Query Insights release tag is invalid")
    return QueryInsightsContext(
        method=normalized_method,
        route_template=route_template,
        release=release,
    )


@contextmanager
def set_query_insights_context(
    *,
    method: str,
    route_template: str,
    release: str,
) -> Iterator[None]:
    context = _validate_context(
        method=method,
        route_template=route_template,
        release=release,
    )
    token = _context.set(context)
    try:
        yield
    finally:
        _context.reset(token)


async def query_insights_request_context(request: Request):
    """Bind the matched FastAPI route template for all endpoint database work."""
    route = request.scope.get("route")
    route_template = getattr(route, "path", None)
    if not isinstance(route_template, str):
        yield
        return
    with set_query_insights_context(
        method=request.method,
        route_template=route_template,
        release=settings.VERSION,
    ):
        yield


def add_query_insights_comment(statement: str) -> str:
    """Append route/release tags without including bind values or request identifiers."""
    context = _context.get()
    if context is None or not _QUERY_PREFIX.match(statement):
        return statement
    # Psycopg's pyformat paramstyle treats every literal percent in a statement
    # as formatting syntax. Doubling the encoded route's percent signs preserves
    # a single percent in the SQL sent to PostgreSQL.
    route = quote(f"{context.method} {context.route_template}", safe="").replace("%", "%%")
    release = quote(context.release, safe="")
    return f"{statement} /*application='crm-api',route='{route}',release='{release}'*/"


def install_query_insights_tags(engine) -> None:
    """Install one SQLAlchemy listener on the application engine."""

    @event.listens_for(engine, "before_cursor_execute", retval=True)
    def _tag_query(_conn, _cursor, statement, parameters, _context, _executemany):
        return add_query_insights_comment(str(statement)), parameters
