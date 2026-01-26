"""Webhook handler interface."""

from __future__ import annotations

from typing import Protocol

from fastapi import Request, Response
from sqlalchemy.orm import Session

WebhookResult = dict | Response


class WebhookHandler(Protocol):
    async def handle(self, request: Request, db: Session, **kwargs) -> WebhookResult:
        """Handle a webhook request."""
