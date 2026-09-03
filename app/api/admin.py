from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.api.auth import require_admin
from app.services.db import (
    create_user,
    get_user,
    list_users,
    update_user_status,
    update_user_password,
    delete_user
)

from app.services.storage import StorageService
from app.config import STORAGE_DIR

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, description="Nombre de usuario único")
    password: str = Field(..., min_length=4, description="Contraseña")
    is_admin: bool = Field(default=False, description="¿Es administrador?")


class UpdateUserStatusRequest(BaseModel):
    is_active: bool = Field(..., description="Estado activo/inactivo de la cuenta")


class MoveItemRequest(BaseModel):
    source_path: str = Field(..., min_length=1, description="Ruta relativa del elemento en storage")
    target_username: str = Field(..., min_length=2, description="Nombre del usuario destinatario")
    dest_subpath: str = Field(default="", description="Subcarpeta de destino opcional")


@router.get("/users")
async def get_all_users(admin: Dict[str, Any] = Depends(require_admin)):
    """Listar todos los usuarios registrados en el servidor."""
    users = list_users()
    return {"success": True, "users": users}


@router.post("/users")
async def admin_create_user(req: CreateUserRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """Crear un nuevo usuario con carpeta propia."""
    try:
        new_user = create_user(
            username=req.username,
            password=req.password,
            is_admin=req.is_admin,
            is_active=True
        )
        return {
            "success": True,
            "user": new_user,
            "message": f"Usuario '{new_user['username']}' creado con éxito."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.patch("/users/{username}/status")
async def toggle_user_status(
    username: str,
    req: UpdateUserStatusRequest,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Habilitar o deshabilitar una cuenta de usuario."""
    clean_user = username.strip().lower()
    if clean_user == admin["username"] and not req.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes deshabilitar tu propia cuenta de administrador."
        )

    try:
        updated = update_user_status(clean_user, req.is_active)
        state_str = "habilitado" if req.is_active else "deshabilitado"
        return {
            "success": True,
            "user": updated,
            "message": f"Usuario '{clean_user}' {state_str} correctamente."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/users/{username}")
async def admin_delete_user(username: str, admin: Dict[str, Any] = Depends(require_admin)):
    """Eliminar un usuario del sistema."""
    clean_user = username.strip().lower()
    if clean_user == admin["username"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta de administrador."
        )

    try:
        delete_user(clean_user)
        return {
            "success": True,
            "message": f"Usuario '{clean_user}' eliminado correctamente del sistema."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


class AdminResetPasswordRequest(BaseModel):

    new_password: str


@router.post("/users/{username}/password")
async def admin_reset_password(
    username: str,
    req: AdminResetPasswordRequest,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """Permite al administrador restablecer la contraseña de cualquier usuario."""
    clean_user = username.strip().lower()
    if len(req.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener al menos 4 caracteres."
        )

    try:
        update_user_password(clean_user, req.new_password)
        return {
            "success": True,
            "message": f"Contraseña actualizada correctamente para el usuario '{clean_user}'."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/move-item")
async def admin_move_item(req: MoveItemRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """Mover carpetas o archivos existentes a la carpeta de un usuario determinado."""

    target_user = get_user(req.target_username)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El usuario destino '{req.target_username}' no existe."
        )

    storage = StorageService(base_dir=STORAGE_DIR, url_prefix="")
    try:
        result = storage.move_item_to_user(
            source_rel_path=req.source_path,
            target_username=req.target_username,
            dest_subpath=req.dest_subpath
        )
        return {"success": True, "data": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
