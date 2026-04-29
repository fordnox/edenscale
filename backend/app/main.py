from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.core.auth import get_current_user
from app.core.config import settings
from app.routers import dashboard, users

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


@app.get("/")
async def root():
    return {
        "message": settings.APP_DOMAIN,
        "status": "running",
    }
