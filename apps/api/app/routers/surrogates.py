"""Surrogates router - aggregated sub-routers."""

from fastapi import APIRouter, Depends

from app.core.deps import require_csrf_header, require_permission
from app.core.policies import POLICIES
from app.routers import (
    surrogates_contact_attempts,
    surrogates_email,
    surrogates_read,
    surrogates_status,
    surrogates_write,
)
from app.schemas.surrogate import SurrogateListResponse, SurrogateRead

router = APIRouter(dependencies=[Depends(require_permission(POLICIES["surrogates"].default))])

router.add_api_route(
    "",
    surrogates_read.list_surrogates,
    methods=["GET"],
    response_model=SurrogateListResponse,
)
router.add_api_route(
    "",
    surrogates_write.create_surrogate,
    methods=["POST"],
    response_model=SurrogateRead,
    status_code=201,
    dependencies=[Depends(require_csrf_header)],
)

router.include_router(surrogates_read.router)
router.include_router(surrogates_write.router)
router.include_router(surrogates_status.router)
router.include_router(surrogates_email.router)
router.include_router(surrogates_contact_attempts.router)
