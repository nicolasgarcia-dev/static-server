import os
import re
import shutil
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import STORAGE_DIR

# Common web mimetypes
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("text/html", ".htm")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")

# Invalid character pattern for file and directory names
# Disallows control chars, slashes, null bytes, HTML tags, shell special chars
INVALID_NAME_CHARS_REGEX = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


def sanitize_and_validate_name(name: str) -> str:
    """
    Validates and sanitizes a file or folder name.
    Rejects path traversal, control characters, null bytes, and dangerous characters.
    """
    clean = name.strip()
    if not clean:
        raise ValueError("El nombre no puede estar vacío.")

    if len(clean) > 255:
        raise ValueError("El nombre excede la longitud máxima permitida (255 caracteres).")

    # Reject null bytes and control characters
    if INVALID_NAME_CHARS_REGEX.search(clean):
        raise ValueError("El nombre contiene caracteres no permitidos (< > : \" / \\ | ? * o caracteres de control).")

    # Reject path traversal names
    if clean in [".", ".."] or clean.startswith(".."):
        raise ValueError("Nombre de archivo o carpeta no válido.")

    # Reject Windows reserved names
    base_upper = Path(clean).stem.upper()
    if base_upper in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"'{clean}' es un nombre reservado del sistema.")

    return clean


class StorageService:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe_resolve(self, relative_path: str = "") -> Path:
        """
        Safely resolve a relative path inside the storage directory.
        Raises ValueError if path attempts to escape base_dir (Path Traversal).
        """
        # Remove null bytes
        if "\x00" in relative_path:
            raise ValueError("Ruta inválida: contiene bytes nulos.")

        # Normalize path string
        clean_path = relative_path.strip().lstrip("/\\")
        target_path = (self.base_dir / clean_path).resolve()

        if not target_path.is_relative_to(self.base_dir):
            raise ValueError(f"Acceso denegado: La ruta '{relative_path}' se encuentra fuera del directorio de almacenamiento.")

        return target_path

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size to human readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def list_directory(self, relative_path: str = "") -> Dict[str, Any]:
        """
        List items inside a relative directory with metadata.
        """
        target_dir = self._safe_resolve(relative_path)

        if not target_dir.exists():
            raise FileNotFoundError(f"La carpeta '{relative_path}' no existe.")
        if not target_dir.is_dir():
            raise NotADirectoryError(f"'{relative_path}' no es un directorio.")

        # Compute relative path from base_dir
        rel_from_base = "" if target_dir == self.base_dir else str(target_dir.relative_to(self.base_dir)).replace("\\", "/")

        items: List[Dict[str, Any]] = []

        for entry in os.scandir(target_dir):
            # Ignore hidden files
            if entry.name.startswith("."):
                continue

            entry_path = Path(entry.path)
            item_rel_path = str(entry_path.relative_to(self.base_dir)).replace("\\", "/")
            stat = entry.stat()
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            if entry.is_dir():
                try:
                    children_count = sum(1 for e in os.scandir(entry.path) if not e.name.startswith("."))
                except Exception:
                    children_count = 0

                items.append({
                    "name": entry.name,
                    "path": item_rel_path,
                    "is_dir": True,
                    "size": 0,
                    "size_formatted": f"{children_count} elementos",
                    "modified": modified,
                    "url": f"/{item_rel_path}",
                    "extension": "",
                    "children_count": children_count
                })
            else:
                ext = entry_path.suffix.lower()
                mime_type, _ = mimetypes.guess_type(entry.name)
                items.append({
                    "name": entry.name,
                    "path": item_rel_path,
                    "is_dir": False,
                    "size": stat.st_size,
                    "size_formatted": self._format_size(stat.st_size),
                    "modified": modified,
                    "url": f"/{item_rel_path}",
                    "extension": ext,
                    "is_html": ext in [".html", ".htm"],
                    "mime_type": mime_type or "application/octet-stream"
                })

        # Sort: directories first (alphabetical), then files (alphabetical)
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        # Build breadcrumbs
        breadcrumbs = [{"name": "html_storage", "path": ""}]
        if rel_from_base:
            parts = rel_from_base.split("/")
            accum = ""
            for p in parts:
                accum = f"{accum}/{p}" if accum else p
                breadcrumbs.append({"name": p, "path": accum})

        return {
            "current_path": rel_from_base,
            "absolute_path": str(target_dir),
            "breadcrumbs": breadcrumbs,
            "items": items,
            "total_items": len(items)
        }

    def get_tree(self, relative_path: str = "") -> List[Dict[str, Any]]:
        """
        Recursively get folder hierarchy tree.
        """
        target_dir = self._safe_resolve(relative_path)
        if not target_dir.exists() or not target_dir.is_dir():
            return []

        tree = []
        for entry in os.scandir(target_dir):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                entry_path = Path(entry.path)
                item_rel_path = str(entry_path.relative_to(self.base_dir)).replace("\\", "/")
                tree.append({
                    "name": entry.name,
                    "path": item_rel_path,
                    "is_dir": True,
                    "children": self.get_tree(item_rel_path)
                })

        tree.sort(key=lambda x: x["name"].lower())
        return tree

    def create_folder(self, parent_path: str, folder_name: str) -> Dict[str, Any]:
        """
        Create a new folder inside parent_path with strict sanitization.
        """
        clean_name = sanitize_and_validate_name(folder_name)
        parent_dir = self._safe_resolve(parent_path)
        new_dir = (parent_dir / clean_name).resolve()

        if not new_dir.is_relative_to(self.base_dir):
            raise ValueError("Ruta de destino no válida.")

        if new_dir.exists():
            raise FileExistsError(f"La carpeta '{clean_name}' ya existe en esta ubicación.")

        new_dir.mkdir(parents=True, exist_ok=True)
        rel_path = str(new_dir.relative_to(self.base_dir)).replace("\\", "/")

        return {
            "name": clean_name,
            "path": rel_path,
            "url": f"/{rel_path}",
            "message": f"Carpeta '{clean_name}' creada correctamente."
        }

    def save_file(self, target_folder_path: str, filename: str, content_bytes: bytes) -> Dict[str, Any]:
        """
        Save uploaded file bytes into target_folder_path with security validation.
        """
        raw_name = Path(filename).name.strip()
        clean_filename = sanitize_and_validate_name(raw_name)

        target_dir = self._safe_resolve(target_folder_path)
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        destination_path = (target_dir / clean_filename).resolve()
        if not destination_path.is_relative_to(self.base_dir):
            raise ValueError("Ruta de archivo no autorizada.")

        with open(destination_path, "wb") as f:
            f.write(content_bytes)

        rel_path = str(destination_path.relative_to(self.base_dir)).replace("\\", "/")
        ext = destination_path.suffix.lower()

        return {
            "filename": clean_filename,
            "path": rel_path,
            "size": len(content_bytes),
            "size_formatted": self._format_size(len(content_bytes)),
            "url": f"/{rel_path}",
            "is_html": ext in [".html", ".htm"],
            "message": f"Archivo '{clean_filename}' guardado correctamente."
        }

    def delete_item(self, relative_path: str) -> Dict[str, Any]:
        """
        Delete file or directory inside storage safely.
        """
        if not relative_path.strip():
            raise ValueError("No se puede eliminar la carpeta raíz de almacenamiento.")

        target_path = self._safe_resolve(relative_path)
        if not target_path.exists():
            raise FileNotFoundError("El elemento especificado no existe.")

        name = target_path.name
        is_dir = target_path.is_dir()

        if is_dir:
            shutil.rmtree(target_path)
        else:
            target_path.unlink()

        return {
            "name": name,
            "path": relative_path,
            "is_dir": is_dir,
            "message": f"{'Carpeta' if is_dir else 'Archivo'} '{name}' eliminado correctamente."
        }

    def rename_item(self, relative_path: str, new_name: str) -> Dict[str, Any]:
        """
        Rename file or directory with validation.
        """
        if not relative_path.strip():
            raise ValueError("No se puede renombrar la carpeta raíz.")

        clean_new_name = sanitize_and_validate_name(new_name)
        target_path = self._safe_resolve(relative_path)
        if not target_path.exists():
            raise FileNotFoundError("El elemento original no existe.")

        new_path = target_path.parent / clean_new_name
        if new_path.exists():
            raise FileExistsError(f"Ya existe un elemento con el nombre '{clean_new_name}'.")

        target_path.rename(new_path)
        new_rel_path = str(new_path.relative_to(self.base_dir)).replace("\\", "/")

        return {
            "old_path": relative_path,
            "new_path": new_rel_path,
            "new_name": clean_new_name,
            "url": f"/{new_rel_path}",
            "message": f"Renombrado a '{clean_new_name}' con éxito."
        }

    def get_file_content(self, relative_path: str) -> Dict[str, Any]:
        """
        Read text/html content of a file.
        """
        target_path = self._safe_resolve(relative_path)
        if not target_path.exists() or target_path.is_dir():
            raise FileNotFoundError("El archivo no existe o es un directorio.")

        # Limit to 5MB for text preview
        stat = target_path.stat()
        if stat.st_size > 5 * 1024 * 1024:
            raise ValueError("El archivo es demasiado grande para previsualizar texto (máximo 5MB).")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(target_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                content = "<!-- Archivo binario o codificación no soportada -->"

        ext = target_path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(target_path.name)

        return {
            "name": target_path.name,
            "path": relative_path,
            "size": stat.st_size,
            "size_formatted": self._format_size(stat.st_size),
            "content": content,
            "url": f"/{relative_path}",
            "mime_type": mime_type or "text/plain",
            "is_html": ext in [".html", ".htm"]
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculate global statistics of html_storage.
        """
        total_size = 0
        total_files = 0
        total_folders = 0
        total_html = 0

        for root, dirs, files in os.walk(self.base_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            total_folders += len(dirs)

            for file in files:
                if file.startswith("."):
                    continue
                file_path = Path(root) / file
                try:
                    sz = file_path.stat().st_size
                    total_size += sz
                    total_files += 1
                    if file.lower().endswith((".html", ".htm")):
                        total_html += 1
                except Exception:
                    pass

        return {
            "total_size": total_size,
            "total_size_formatted": self._format_size(total_size),
            "total_files": total_files,
            "total_folders": total_folders,
            "total_html": total_html,
            "storage_path": str(self.base_dir)
        }
