from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.core.auth import get_current_user
from app.core.config import settings
from app.routers import (
    capital_calls,
    commitments,
    dashboard,
    fund_groups,
    fund_team_members,
    funds,
    investor_contacts,
    investors,
    organizations,
    users,
)

app = FastAPI(
    title=settings.APP_DOMAIN,
    version="0.0.1",
    openapi_url="/openapi.json" if settings.GENERATE_OPENAPI_DOCS else None,
    docs_url="/docs" if settings.GENERATE_OPENAPI_DOCS else None,
    redoc_url="/redoc" if settings.GENERATE_OPENAPI_DOCS else None,
)


@app.middleware("http")
async def options_handler(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin", "*")
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400",
            },
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,  # type: ignore[invalid-argument-type]
    allow_origins=["http://localhost:3000", f"https://{settings.APP_DOMAIN}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    dashboard.router, prefix="/dashboard", dependencies=[Depends(get_current_user)]
)
app.include_router(
    users.router,
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    organizations.router,
    prefix="/organizations",
    tags=["organizations"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    fund_groups.router,
    prefix="/fund-groups",
    tags=["fund-groups"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    funds.router,
    prefix="/funds",
    tags=["funds"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    fund_team_members.router,
    prefix="/funds",
    tags=["fund-team-members"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    investors.router,
    prefix="/investors",
    tags=["investors"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    investor_contacts.router,
    prefix="/investors",
    tags=["investor-contacts"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    commitments.router,
    prefix="/commitments",
    tags=["commitments"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    commitments.fund_commitments_router,
    prefix="/funds",
    tags=["commitments"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    commitments.investor_commitments_router,
    prefix="/investors",
    tags=["commitments"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    capital_calls.router,
    prefix="/capital-calls",
    tags=["capital-calls"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    capital_calls.fund_capital_calls_router,
    prefix="/funds",
    tags=["capital-calls"],
    dependencies=[Depends(get_current_user)],
)


@app.get("/")
async def root():
    return {
        "message": settings.APP_DOMAIN,
        "status": "running",
    }
