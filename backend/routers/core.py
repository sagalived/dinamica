from fastapi import APIRouter, Request

from backend.config import APP_NAME

router = APIRouter(prefix="/api", tags=["core"])


@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "message": f"{APP_NAME} online com PostgreSQL, JWT e Pandas.",
        "database_ready": getattr(request.app.state, "database_ready", False),
        "database_error": getattr(request.app.state, "database_error", None),
    }
