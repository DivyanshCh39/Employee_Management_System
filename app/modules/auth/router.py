from fastapi import APIRouter, Request

from app.dependencies import CurrentUser, DBSession
from app.modules.auth import service
from app.modules.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    MeResponse,
    MessageResponse,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="Login with email and password")
def login(payload: LoginRequest, request: Request, db: DBSession):
    ip = request.client.host if request.client else None
    return service.login(email=payload.email, password=payload.password, db=db, ip_address=ip)


@router.post("/refresh", response_model=AccessTokenResponse, summary="Refresh an expired access token")
def refresh(payload: RefreshRequest, db: DBSession):
    return service.refresh_access_token(refresh_token=payload.refresh_token, db=db)


@router.get("/me", response_model=MeResponse, summary="Get current user profile")
def get_me(current_user: CurrentUser):
    return service.get_me(current_user)


@router.post("/change-password", response_model=MessageResponse, summary="Change own password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
):
    ip = request.client.host if request.client else None
    return service.change_password(
        employee=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        db=db,
        ip_address=ip,
    )