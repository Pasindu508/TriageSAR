"""TriageSAR API. Serves analysis results computed from the prepared fixture; optionally the built web app."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.core.logging import configure_logging, log_requests
from app.core.settings import get_settings
from app.models.errors import ApiError
from app.schemas.responses import ErrorBody, ErrorResponse
from triagesar import __version__

DESCRIPTION = (
    "From NISAR surface motion to an evidence-ranked infrastructure inspection queue. "
    "The inspection priority score is not a probability of damage. All endpoints are read-only."
)


def _error(status: int, code: str, message: str, hint: str | None = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, hint=hint))
    return JSONResponse(status_code=status, content=body.model_dump(), headers={"Cache-Control": "no-store"})


def create_app() -> FastAPI:
    logger = configure_logging()
    settings = get_settings()
    app = FastAPI(title="TriageSAR API", version=__version__, description=DESCRIPTION)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET"], allow_headers=["*"])
    app.middleware("http")(log_requests)

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        if "cache-control" not in response.headers:
            if request.url.path.startswith("/assets/"):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "no-cache"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("api_error", extra={"code": exc.code, "detail": exc.message})
        return _error(exc.status_code, exc.code, exc.message, exc.hint)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []))
        return _error(422, "invalid_request", f"Invalid request parameter {where}: {first.get('msg', 'invalid value')}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, "not_found" if exc.status_code == 404 else "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", extra={"error_type": type(exc).__name__})
        return _error(500, "internal_error", "An unexpected error occurred.")

    app.include_router(router)

    dist = settings.web_dist
    if (dist / "index.html").is_file():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            if path.startswith("api/"):
                return _error(404, "not_found", "Not found")
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
