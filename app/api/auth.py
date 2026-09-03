from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.services.db import (
    verify_password,
    create_session,
    get_session_user,
    delete_session
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="Nombre de usuario")
    password: str = Field(..., min_length=1, description="Contraseña")
    remember: bool = Field(default=True, description="Mantener la sesión iniciada")


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract session token from cookie or Authorization header."""
    # 1. Cookie
    token = request.cookies.get("session_id")
    if token:
        return token

    # 2. Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get authenticated user if session exists, else None."""
    token = extract_token_from_request(request)
    if not token:
        return None
    return get_session_user(token)


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Dependency: require authenticated user or raise 401."""
    user = await get_optional_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Por favor, inicia sesión."
        )
    return user


async def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency: require administrator privileges or raise 403."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requieren permisos de administrador."
        )
    return current_user


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    """Iniciar sesión con usuario y contraseña."""
    try:
        user = verify_password(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos."
        )

    duration_days = 30 if req.remember else 1
    token = create_session(user["username"], duration_days=duration_days)

    # Set secure HttpOnly cookie
    max_age = (duration_days * 86400) if req.remember else None
    response.set_cookie(
        key="session_id",
        value=token,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False  # Allow HTTP on local/private networks
    )

    return {
        "success": True,
        "token": token,
        "user": {
            "username": user["username"],
            "is_admin": user["is_admin"]
        },
        "message": "Inicio de sesión correcto."
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Cerrar la sesión actual e invalidar el token."""
    token = extract_token_from_request(request)
    if token:
        delete_session(token)

    response.delete_cookie(key="session_id", path="/")
    return {"success": True, "message": "Sesión cerrada correctamente."}


@router.get("/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Obtener datos del usuario conectado actualmente."""
    return {
        "success": True,
        "user": {
            "username": current_user["username"],
            "is_admin": current_user["is_admin"]
        }
    }
