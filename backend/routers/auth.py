from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user, require_database_ready
from backend.models import AppUser
from backend.schemas import AuthResponse, LoginRequest, MeResponse, RegisterRequest, UserResponse
from backend.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(
    payload: RegisterRequest,
    _: None = Depends(require_database_ready),
    db: Session = Depends(get_db),
) -> AppUser:
    existing = db.scalar(select(AppUser).where(AppUser.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email ja cadastrado.")

    user = AppUser(
        email=payload.email,
        full_name=payload.full_name,
        department=payload.department,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    _: None = Depends(require_database_ready),
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(AppUser).where(AppUser.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")

    token = create_access_token(user.email)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=MeResponse)
def auth_me(
    _: None = Depends(require_database_ready),
    current_user: AppUser = Depends(get_current_user),
) -> dict:
    return {"user": UserResponse.model_validate(current_user)}
