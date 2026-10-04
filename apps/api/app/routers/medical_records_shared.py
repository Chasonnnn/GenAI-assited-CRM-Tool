"""Shared HTTP mapping for medical record routes."""

from typing import NoReturn

from fastapi import HTTPException

from app.services import medical_record_service


def raise_medical_record_error(exc: medical_record_service.MedicalRecordError) -> NoReturn:
    if isinstance(exc, medical_record_service.MedicalRecordNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, medical_record_service.MedicalRecordConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc
