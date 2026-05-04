from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user, require_database_ready
from backend.models import AppUser
from backend.schemas import UserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserResponse])
def list_admin_users(
    __: None = Depends(require_database_ready),
    _: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AppUser]:
    return db.scalars(select(AppUser).order_by(AppUser.full_name)).all()


@router.post("/backup/drive")
def backup_to_google_drive(
    __: None = Depends(require_database_ready),
    _: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "status": "pending",
        "message": "Backup Google Drive em desenvolvimento",
        "error": "Feature nao disponivel nesta versao",
    }
