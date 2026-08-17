import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field, field_validator

from app.services.storage import StorageService, sanitize_and_validate_name

router = APIRouter(prefix="/api/explorer", tags=["Explorer"])
storage = StorageService()

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB max per file


class CreateFolderRequest(BaseModel):
    path: str = Field(default="", description="Ruta relativa del directorio padre")
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la nueva carpeta")

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        return sanitize_and_validate_name(v)


class DeleteItemRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Ruta relativa del archivo o carpeta a eliminar")


class RenameItemRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Ruta relativa original del elemento")
    new_name: str = Field(..., min_length=1, max_length=255, description="Nuevo nombre para el elemento")

    @field_validator("new_name")
    def validate_new_name(cls, v: str) -> str:
        return sanitize_and_validate_name(v)


@router.get("/list")
async def list_directory(path: str = ""):
    """Lista el contenido de un directorio con metadatos."""
    try:
        data = storage.list_directory(path)
        return {"success": True, "data": data}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {str(e)}")


@router.get("/tree")
async def get_tree(path: str = ""):
    """Devuelve la jerarquía de carpetas."""
    try:
        tree = storage.get_tree(path)
        return {"success": True, "tree": tree}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Devuelve estadísticas de uso de almacenamiento."""
    try:
        stats = storage.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/folders")
async def create_folder(req: CreateFolderRequest):
    """Crea una nueva carpeta en la ruta indicada."""
    try:
        result = storage.create_folder(req.path, req.name)
        return {"success": True, "data": result}
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/upload")
async def upload_files(
    path: str = Form(""),
    files: List[UploadFile] = File(...)
):
    """Sube uno o varios archivos a la carpeta especificada con validación de tamaño."""
    saved_files = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise ValueError(f"El archivo '{file.filename}' excede el límite máximo de 100 MB.")

            result = storage.save_file(path, file.filename, content)
            saved_files.append(result)
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "saved_files": saved_files,
        "errors": errors,
        "message": f"Se subieron {len(saved_files)} archivo(s) correctamente." + (f" ({len(errors)} errores)" if errors else "")
    }


@router.delete("/items")
async def delete_item(req: DeleteItemRequest):
    """Elimina un archivo o directorio de forma segura."""
    try:
        result = storage.delete_item(req.path)
        return {"success": True, "data": result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/rename")
async def rename_item(req: RenameItemRequest):
    """Renombra un archivo o carpeta."""
    try:
        result = storage.rename_item(req.path, req.new_name)
        return {"success": True, "data": result}
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/file-content")
async def get_file_content(path: str):
    """Obtiene el contenido de texto/código de un archivo."""
    try:
        data = storage.get_file_content(path)
        return {"success": True, "data": data}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
