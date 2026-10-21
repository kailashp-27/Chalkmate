from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from chalkmate.assessment_routes import router as assessment_router
from chalkmate.assignment_routes import router as assignment_router
from chalkmate.campaign_routes import router as campaign_router
from chalkmate.config import get_settings
from chalkmate.intelligence_routes import router as intelligence_router
from chalkmate.mail_webhooks import router as mail_webhook_router
from chalkmate.planning_routes import router as planning_router
from chalkmate.reporting_routes import router as reporting_router
from chalkmate.review_routes import router as review_router
from chalkmate.routes import router
from chalkmate.support_routes import router as support_router


@asynccontextmanager
async def lifespan(app):
    # Pool only the stateless HTTP transport; credentials are supplied per request.
    async with httpx.AsyncClient(
        timeout=10,
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=10, keepalive_expiry=30),
    ) as client:
        app.state.auth_http = client
        yield


app = FastAPI(title="Chalkmate API", version="1.0.0", lifespan=lifespan)
settings = get_settings()
origins = [settings.web_origin]
if settings.app_env == "development":
    origins.append("http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(assessment_router)
app.include_router(review_router)
app.include_router(assignment_router)
app.include_router(campaign_router)
app.include_router(mail_webhook_router)
app.include_router(intelligence_router)
app.include_router(planning_router)
app.include_router(reporting_router)
app.include_router(support_router)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "These records conflict with existing data. Refresh and review, then retry."
        },
    )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Process liveness only; does not claim database or broker readiness."""
    return {"status": "ok", "service": "chalkmate-api"}
