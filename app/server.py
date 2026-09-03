import html
import mimetypes
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from jinja2 import Environment, FileSystemLoader

from app.config import STORAGE_DIR, TEMPLATES_DIR, STATIC_DIR
from app.services.storage import StorageService
from app.api.explorer import router as explorer_router
from app.api.auth import router as auth_router, get_optional_user
from app.api.admin import router as admin_router

# Initialize Jinja2 templates
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# Initialize storage service (root storage for system operations)
storage = StorageService()

app = FastAPI(
    title="HTML Server & Explorer",
    description="Servidor de archivos HTML estáticos con panel de gestión interactivo y multiusuario.",
    version="2.0.0",
    docs_url="/_docs",
    redoc_url="/_redoc",
    openapi_url="/_openapi.json"
)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent Clickjacking on external sites while allowing iframe preview on same origin
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        # Enable XSS filter
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Strict Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # No-cache for app assets to ensure instant updates
        if request.url.path.startswith(("/_static", "/_manager", "/_admin", "/api", "/login")) or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware for open accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount app static files under /_static to avoid conflict with user-stored files
if STATIC_DIR.exists():
    app.mount("/_static", StaticFiles(directory=str(STATIC_DIR)), name="app_static")

# Include Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(explorer_router)


def render_dashboard(request: Request, user: dict = None):
    """Render the main management dashboard scoped to current user."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    template = jinja_env.get_template("index.html")
    rendered = template.render(
        request=request,
        current_user=user,
        storage_dir_name="html_storage" if user.get("is_admin") else user.get("username", "html_storage")
    )
    return HTMLResponse(content=rendered, status_code=200)



@app.api_route("/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_login_page(request: Request):
    """Render the login page if not already authenticated."""
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    template = jinja_env.get_template("login.html")
    rendered = template.render(request=request)
    return HTMLResponse(content=rendered, status_code=200)


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_index(request: Request):
    """
    Main entry point: Requires login. Displays the interactive dashboard.
    """
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return render_dashboard(request, user)


@app.api_route("/_manager", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/_admin", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def get_manager(request: Request):
    """
    Guaranteed entry point for the dashboard even if a root index.html is served.
    """
    user = await get_optional_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return render_dashboard(request, user)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def serve_stored_file(full_path: str, request: Request):
    """
    Directly serve stored HTML files and assets based on relative URL path without password.
    Example: GET /CIM/fichajes-cim.html -> serves html_storage/CIM/fichajes-cim.html
    Example: GET /juan/index.html -> serves html_storage/juan/index.html
    """
    # Exclude internal routes
    if full_path.startswith(("_static", "_docs", "_redoc", "_openapi", "api", "login")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ruta no encontrada.")

    try:
        target_path = storage._safe_resolve(full_path)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso no permitido.")

    if not target_path.exists():
        safe_path = html.escape(full_path)
        return HTMLResponse(
            status_code=404,
            content=f"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>404 - Archivo no encontrado</title>
                <style>
                    body {{
                        background: #09090b;
                        color: #f4f4f5;
                        font-family: system-ui, -apple-system, sans-serif;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        min-height: 100vh;
                        margin: 0;
                        text-align: center;
                        padding: 1.5rem;
                    }}
                    .card {{
                        background: #141417;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 12px;
                        padding: 2.5rem;
                        max-width: 480px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    }}
                    h1 {{ font-size: 2.5rem; margin: 0 0 0.5rem 0; color: #ef4444; }}
                    p {{ color: #a1a1aa; font-size: 0.95rem; line-height: 1.6; margin-bottom: 1.5rem; }}
                    code {{ background: rgba(255, 255, 255, 0.06); padding: 0.2rem 0.5rem; border-radius: 4px; color: #3b82f6; font-family: monospace; }}
                    a.btn {{
                        display: inline-block;
                        background: #3b82f6;
                        color: #ffffff;
                        padding: 0.6rem 1.25rem;
                        border-radius: 6px;
                        text-decoration: none;
                        font-weight: 500;
                        font-size: 0.85rem;
                        transition: all 0.15s;
                    }}
                    a.btn:hover {{ background: #2563eb; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>404</h1>
                    <p>El archivo <code>/{safe_path}</code> no existe en el servidor.</p>
                    <a href="/_manager" class="btn">Abrir Panel de Gestión</a>
                </div>
            </body>
            </html>
            """
        )

    # If it's a directory, check for index.html inside
    if target_path.is_dir():
        index_file = target_path / "index.html"
        if index_file.exists():
            target_path = index_file
        else:
            # Check authentication before exposing directory manager
            user = await get_optional_user(request)
            if not user:
                # Unauthenticated: don't reveal directory structure
                safe_path = html.escape(full_path)
                return HTMLResponse(
                    status_code=404,
                    content=f"""
                    <!DOCTYPE html>
                    <html lang="es">
                    <head>
                        <meta charset="UTF-8">
                        <title>404 - Directorio no disponible</title>
                        <style>
                            body {{ background: #09090b; color: #f4f4f5; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
                            .card {{ background: #141417; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 2.5rem; max-width: 480px; text-align: center; }}
                            h1 {{ color: #ef4444; margin-top: 0; }}
                            a {{ color: #3b82f6; text-decoration: none; }}
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <h1>404</h1>
                            <p>No se encontró ningún archivo <code>index.html</code> en <code>/{safe_path}</code>.</p>
                            <p><a href="/login">Iniciar sesión</a> para gestionar archivos.</p>
                        </div>
                    </body>
                    </html>
                    """
                )
            # Authenticated user: if admin or inside their folder, open dashboard
            if user.get("is_admin") or target_path.is_relative_to(STORAGE_DIR / user["username"]):
                return render_dashboard(request, user)
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a este directorio.")

    mime_type, _ = mimetypes.guess_type(target_path.name)
    if not mime_type:
        mime_type = "application/octet-stream"

    headers = {}
    if mime_type.startswith("text/html"):
        headers["Content-Type"] = "text/html; charset=utf-8"

    return FileResponse(
        path=str(target_path),
        media_type=mime_type,
        headers=headers
    )
