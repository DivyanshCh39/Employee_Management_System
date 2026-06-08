from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableException,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import SessionLocal
    from app.db.init_db import seed_first_admin

    db = SessionLocal()
    try:
        seed_first_admin(db)
    except Exception as exc:
        print(f"[startup] seed_first_admin skipped — {exc}")
    finally:
        db.close()

    yield

    print("[shutdown] Application shutting down cleanly")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production-style Employee Management System. "
            "Authenticate via POST /api/v1/auth/login, then use the "
            "returned `access_token` as a Bearer token on all protected routes."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    _add_middleware(app)
    _add_exception_handlers(app)
    _register_routers(app)

    return app


def _add_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _add_exception_handlers(app: FastAPI) -> None:
    handled = (
        BadRequestException,
        UnauthorizedException,
        ForbiddenException,
        NotFoundException,
        ConflictException,
        UnprocessableException,
    )

    async def _handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=exc.status_code,   # type: ignore[attr-defined]
            content={"detail": exc.detail},  # type: ignore[attr-defined]
        )

    for exc_class in handled:
        app.add_exception_handler(exc_class, _handler)


def _register_routers(app: FastAPI) -> None:
    from app.modules.auth.router       import router as auth_router
    from app.modules.employee.router   import router as employee_router
    from app.modules.department.router import router as dept_router
    from app.modules.leave.router      import router as leave_router
    from app.modules.audit.router      import router as audit_router

    API_V1 = "/api/v1"

    app.include_router(auth_router,     prefix=API_V1)
    app.include_router(employee_router, prefix=API_V1)
    app.include_router(dept_router,     prefix=API_V1)
    app.include_router(leave_router,    prefix=API_V1)
    app.include_router(audit_router,    prefix=API_V1)

    @app.get("/health", tags=["Health"], include_in_schema=True)
    def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}


app = create_app()