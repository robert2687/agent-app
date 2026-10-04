"""Domain exception hierarchy and FastAPI error envelopes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class NexusError(Exception):
    """Base class for all Nexus domain errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "nexus_internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class NotFoundError(NexusError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationError(NexusError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class VaultLockedError(NexusError):
    status_code = status.HTTP_423_LOCKED
    error_code = "vault_locked"


class VaultUnlockError(NexusError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "vault_unlock_failed"


class ProviderError(NexusError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "provider_error"


class ProviderExhaustedError(ProviderError):
    """Every candidate provider failed / was unavailable."""

    error_code = "provider_exhausted"


class BudgetExceededError(NexusError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "token_budget_exceeded"


class RepositoryIngestError(NexusError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "repository_ingestion_failed"


class ExecutionError(NexusError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "execution_failed"


class JobStateError(NexusError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "invalid_job_state"


def register_error_handlers(app: FastAPI) -> None:
    """Attach uniform JSON error handling to the application."""

    @app.exception_handler(NexusError)
    async def _nexus_handler(_: Request, exc: NexusError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("nexus.errors").exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected internal error occurred.",
                "details": {"exception_type": type(exc).__name__},
            },
        )
