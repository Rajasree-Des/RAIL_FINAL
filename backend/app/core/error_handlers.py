import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    NotFoundError,
    RateLimitError,
    SummaryNotGeneratedError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class ErrorResponse(BaseModel):
    detail: str
    code: str


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def authentication_handler(_: Request, exc: AuthenticationError) -> JSONResponse:
        logger.warning("Authentication failed: %s", exc.message)
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(_: Request, exc: AuthorizationError) -> JSONResponse:
        logger.warning("Authorization failed: %s", exc.message)
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        logger.warning("Resource not found: %s", exc.message)
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(SummaryNotGeneratedError)
    async def summary_not_generated_handler(
        _: Request, exc: SummaryNotGeneratedError
    ) -> JSONResponse:
        logger.info("Summary not generated: run_id=%s", exc.run_id)
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
        logger.warning("Validation error: %s", exc.message)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(_: Request, exc: RateLimitError) -> JSONResponse:
        logger.warning("Rate limit exceeded: %s", exc.message)
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(DatabaseError)
    async def database_handler(_: Request, exc: DatabaseError) -> JSONResponse:
        logger.error("Database error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail="A database error occurred" if settings.is_production else exc.message,
                code=exc.code,
            ).model_dump(),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        logger.error("Application error: %s", exc.message)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail="An error occurred" if settings.is_production else exc.message,
                code=exc.code,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", str(exc))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail="An unexpected error occurred",
                code="INTERNAL_ERROR",
            ).model_dump(),
        )
