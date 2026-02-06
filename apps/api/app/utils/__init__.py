"""Utility modules.

Keep this module lightweight.

`app.utils` is imported implicitly whenever a submodule import like
`app.utils.presentation` is used. Avoid importing optional heavy dependencies
(FastAPI, SQLAlchemy) here so non-server scripts (e.g. `scripts/gen_stage_map.py`)
can run in environments where backend deps are not installed.
"""

from app.utils.normalization import (
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_state,
)

__all__ = [
    # Normalization
    "normalize_email",
    "normalize_name",
    "normalize_phone",
    "normalize_state",
]

try:
    # Optional: only available when FastAPI + SQLAlchemy deps are installed.
    from app.utils.pagination import (  # type: ignore
        PaginatedResponse,
        PaginationParams,
        get_pagination,
        paginate_query,
    )

    __all__ += [
        "PaginationParams",
        "PaginatedResponse",
        "get_pagination",
        "paginate_query",
    ]
except ModuleNotFoundError:
    # Allow importing `app.utils.*` in tooling contexts without backend deps.
    pass
