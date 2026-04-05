from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.interview import router as interview_router
from app.api.routers.jd import router as jd_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.resume import router as resume_router
from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware

app = FastAPI(
    title=settings.project_name,
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(jd_router, prefix=settings.api_v1_prefix)
app.include_router(resume_router, prefix=settings.api_v1_prefix)
app.include_router(interview_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
