import os
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.server import app
from app.config import STORAGE_DIR, DB_PATH
from app.services.db import init_db, create_user, delete_user, get_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_clean_environment():
    """Ensure clean test database and storage folders before each test."""
    init_db()

    test_users = ["testuser", "testadmin", "user_a", "user_b", "nuevo-empleado", "disabled_user"]
    for u in test_users:
        try:
            delete_user(u)
        except Exception:
            pass

    test_folders = ["TEST_CIM", "testuser", "testadmin", "user_a", "user_b", "nuevo-empleado", "disabled_user", "admin", "cliadmin"]
    for f in test_folders:
        p = STORAGE_DIR / f
        if p.exists():
            shutil.rmtree(p)

    yield

    for u in test_users:
        try:
            delete_user(u)
        except Exception:
            pass

    for f in test_folders:
        p = STORAGE_DIR / f
        if p.exists():
            shutil.rmtree(p)



def get_authenticated_client(username: str = "testuser", password: str = "pass123", is_admin: bool = False):
    """Helper to create and log in a user, returning an authenticated TestClient."""
    try:
        create_user(username=username, password=password, is_admin=is_admin, is_active=True)
    except ValueError:
        pass  # Already created

    auth_client = TestClient(app)
    res = auth_client.post("/api/auth/login", json={"username": username, "password": password, "remember": True})
    assert res.status_code == 200
    token = res.json()["token"]
    auth_client.headers["Authorization"] = f"Bearer {token}"
    return auth_client


# ==============================================================================
# PUBLIC DIRECT ACCESS & UNAUTHENTICATED BEHAVIOR
# ==============================================================================

def test_unauthenticated_dashboard_redirects_to_login():
    """Verify that visiting root / or /_manager without auth redirects to /login."""
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code == 302
    assert res_root.headers["location"] == "/login"

    res_mgr = client.get("/_manager", follow_redirects=False)
    assert res_mgr.status_code == 302
    assert res_mgr.headers["location"] == "/login"


def test_login_page_renders_200():
    """Verify that /login renders the HTML login card."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "Iniciar Sesión" in response.text or "HTML Server" in response.text


def test_public_static_direct_serve_without_password():
    """
    CRITICAL REQUIREMENT:
    Static files remain directly accessible via URL without authentication.
    """
    # 1. Existing root file
    res_existing = client.get("/CIM/fichajes-cim.html")
    assert res_existing.status_code == 200
    assert "text/html" in res_existing.headers.get("content-type", "")

    # 2. Upload a file inside a user folder and access it directly
    user_client = get_authenticated_client(username="testuser", password="secretpassword", is_admin=False)
    html_content = "<html><body><h1>Reporte Privado de TestUser</h1></body></html>"
    files = {"files": ("reporte.html", html_content.encode("utf-8"), "text/html")}
    res_upload = user_client.post("/api/explorer/upload", data={"path": ""}, files=files)
    assert res_upload.status_code == 200

    # Direct access from completely unauthenticated client
    res_direct = client.get("/testuser/reporte.html")
    assert res_direct.status_code == 200
    assert "text/html" in res_direct.headers.get("content-type", "")
    assert "Reporte Privado de TestUser" in res_direct.text


def test_unauthenticated_directory_does_not_leak_explorer():
    """Verify that requesting a directory without index.html does not reveal file tree to anonymous users."""
    res = client.get("/CIM/")
    # If no index.html, anonymous gets 404
    assert res.status_code in [404, 302]


# ==============================================================================
# AUTHENTICATION & LOGIN FLOW
# ==============================================================================

def test_login_failure_invalid_credentials():
    """Verify that wrong password returns 401."""
    create_user("user_a", "correctpass")
    res = client.post("/api/auth/login", json={"username": "user_a", "password": "wrongpassword"})
    assert res.status_code == 401


def test_disabled_user_cannot_login():
    """Verify that disabled users are blocked from logging in."""
    from app.services.db import update_user_status
    create_user("disabled_user", "password123")
    update_user_status("disabled_user", is_active=False)

    res = client.post("/api/auth/login", json={"username": "disabled_user", "password": "password123"})
    assert res.status_code in [401, 403]


def test_authenticated_dashboard_returns_200():
    """Verify that authenticated user can access the dashboard."""
    auth_client = get_authenticated_client(username="testuser", password="secretpassword")
    res = auth_client.get("/")
    assert res.status_code == 200
    assert "HTML Server" in res.text
    assert "testuser" in res.text


def test_logout_invalidates_session():
    """Verify that logout clears cookie and invalidates session token."""
    auth_client = get_authenticated_client(username="testuser", password="secretpassword")
    res_logout = auth_client.post("/api/auth/logout")
    assert res_logout.status_code == 200

    # Subsequent /api/auth/me should return 401
    res_me = auth_client.get("/api/auth/me")
    assert res_me.status_code == 401


# ==============================================================================
# USER ISOLATION & STORAGE SCOPING
# ==============================================================================

def test_regular_user_isolation():
    """
    Verify that regular users are scoped strictly to html_storage/<username>,
    and cannot see or access other users' folders or root files.
    """
    user_a = get_authenticated_client(username="user_a", password="password_a", is_admin=False)
    user_b = get_authenticated_client(username="user_b", password="password_b", is_admin=False)

    # User A creates a folder
    res_create = user_a.post("/api/explorer/folders", json={"path": "", "name": "carpeta_de_a"})
    assert res_create.status_code == 200

    # User A sees their folder
    list_a = user_a.get("/api/explorer/list?path=").json()
    items_a = [i["name"] for i in list_a["data"]["items"]]
    assert "carpeta_de_a" in items_a

    # User B cannot see User A's folder
    list_b = user_b.get("/api/explorer/list?path=").json()
    items_b = [i["name"] for i in list_b["data"]["items"]]
    assert "carpeta_de_a" not in items_b

    # User B cannot delete User A's folder via path traversal
    res_hack = user_b.request("DELETE", "/api/explorer/items", json={"path": "../user_a/carpeta_de_a"})
    assert res_hack.status_code in [400, 404, 403]


def test_admin_sees_all_and_can_manage():
    """Verify that admin user sees root storage with all folders."""
    admin_client = get_authenticated_client(username="testadmin", password="adminpassword", is_admin=True)

    # Admin lists root
    res = admin_client.get("/api/explorer/list?path=")
    assert res.status_code == 200
    items = [i["name"] for i in res.json()["data"]["items"]]
    # Should see CIM (existing root folder)
    assert "CIM" in items


# ==============================================================================
# ADMIN MANAGEMENT API
# ==============================================================================

def test_admin_user_crud_and_status():
    """Test admin creating, enabling/disabling, and listing users."""
    admin_client = get_authenticated_client(username="testadmin", password="adminpassword", is_admin=True)

    # 1. Create new user via admin API
    res_create = admin_client.post("/api/admin/users", json={
        "username": "nuevo-empleado",
        "password": "password123",
        "is_admin": False
    })
    assert res_create.status_code == 200
    assert res_create.json()["user"]["username"] == "nuevo-empleado"

    # 2. List users
    res_list = admin_client.get("/api/admin/users")
    assert res_list.status_code == 200
    usernames = [u["username"] for u in res_list.json()["users"]]
    assert "nuevo-empleado" in usernames

    # 3. Disable user
    res_disable = admin_client.patch("/api/admin/users/nuevo-empleado/status", json={"is_active": False})
    assert res_disable.status_code == 200

    # 4. Try logging in as disabled user -> fails
    res_login_disabled = client.post("/api/auth/login", json={"username": "nuevo-empleado", "password": "password123"})
    assert res_login_disabled.status_code in [401, 403]

    # 5. Re-enable user
    res_enable = admin_client.patch("/api/admin/users/nuevo-empleado/status", json={"is_active": True})
    assert res_enable.status_code == 200

    # 6. Delete user
    res_del = admin_client.delete("/api/admin/users/nuevo-empleado")
    assert res_del.status_code == 200


def test_regular_user_cannot_access_admin_endpoints():
    """Verify that regular non-admin users get 403 Forbidden on admin APIs."""
    user_client = get_authenticated_client(username="testuser", password="secretpassword", is_admin=False)
    res = user_client.get("/api/admin/users")
    assert res.status_code == 403

    res_move = user_client.post("/api/admin/move-item", json={
        "source_path": "CIM",
        "target_username": "testuser"
    })
    assert res_move.status_code == 403


def test_admin_move_item_to_user():
    """
    CRITICAL REQUIREMENT:
    Admin can move existing folders/files to a determined user.
    """
    admin_client = get_authenticated_client(username="testadmin", password="adminpassword", is_admin=True)
    user_client = get_authenticated_client(username="user_a", password="password_a", is_admin=False)

    # Create a temporary folder in root
    admin_client.post("/api/explorer/folders", json={"path": "", "name": "TEST_CIM"})

    # Admin moves TEST_CIM to user_a
    res_move = admin_client.post("/api/admin/move-item", json={
        "source_path": "TEST_CIM",
        "target_username": "user_a",
        "dest_subpath": ""
    })
    assert res_move.status_code == 200
    assert res_move.json()["success"] is True

    # User A now sees TEST_CIM in their scoped storage
    res_user_list = user_client.get("/api/explorer/list?path=")
    assert res_user_list.status_code == 200
    items = [i["name"] for i in res_user_list.json()["data"]["items"]]
    assert "TEST_CIM" in items


def test_user_change_own_password():
    """Verify that a user can change their own password."""
    user_client = get_authenticated_client(username="user_a", password="oldpassword123", is_admin=False)

    # 1. Wrong current password fails
    res_wrong = user_client.post("/api/auth/change-password", json={
        "current_password": "wrongpassword",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456"
    })
    assert res_wrong.status_code == 400

    # 2. Mismatched confirm password fails
    res_mismatch = user_client.post("/api/auth/change-password", json={
        "current_password": "oldpassword123",
        "new_password": "newpassword456",
        "confirm_password": "differentpassword"
    })
    assert res_mismatch.status_code == 400

    # 3. Successful password change
    res_success = user_client.post("/api/auth/change-password", json={
        "current_password": "oldpassword123",
        "new_password": "newpassword456",
        "confirm_password": "newpassword456"
    })
    assert res_success.status_code == 200

    # 4. Old password can no longer log in
    res_login_old = client.post("/api/auth/login", json={"username": "user_a", "password": "oldpassword123"})
    assert res_login_old.status_code == 401

    # 5. New password logs in successfully
    res_login_new = client.post("/api/auth/login", json={"username": "user_a", "password": "newpassword456"})
    assert res_login_new.status_code == 200


def test_admin_reset_user_password():
    """Verify that admin can set a new password for any user."""
    admin_client = get_authenticated_client(username="testadmin", password="adminpassword", is_admin=True)
    user_client = get_authenticated_client(username="user_b", password="userbpassword", is_admin=False)

    # Regular user cannot call admin password reset
    res_forbidden = user_client.post("/api/admin/users/testadmin/password", json={"new_password": "hackedpassword"})
    assert res_forbidden.status_code == 403

    # Admin resets user_b password
    res_reset = admin_client.post("/api/admin/users/user_b/password", json={"new_password": "brandnewpassword"})
    assert res_reset.status_code == 200

    # user_b can log in with brand new password
    res_login = client.post("/api/auth/login", json={"username": "user_b", "password": "brandnewpassword"})
    assert res_login.status_code == 200


# ==============================================================================
# SECURITY & XSS TESTS
# ==============================================================================


def test_reflected_xss_in_404_is_escaped():
    """Verify that malicious script tags in URLs are safely escaped in 404 responses."""
    payload = "<script>alert('xss')</script>"
    response = client.get(f"/{payload}")
    assert response.status_code == 404
    assert "<script>alert('xss')</script>" not in response.text
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in response.text or "&lt;script&gt;" in response.text


def test_xss_folder_name_is_rejected():
    """Verify that folder names with XSS or illegal characters are rejected."""
    admin_client = get_authenticated_client(username="testadmin", password="adminpassword", is_admin=True)
    payload = "<img src=x onerror=alert(1)>"
    res = admin_client.post("/api/explorer/folders", json={"path": "", "name": payload})
    assert res.status_code in [400, 422]


def test_security_headers_present():
    """Verify that standard HTTP security headers are present in all responses."""
    response = client.get("/login")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


# ==============================================================================
# CLI COMMANDS TESTS
# ==============================================================================

def test_cli_create_admin_and_list():
    """Verify CLI admin creation and listing commands."""
    from main import cmd_create_admin, cmd_list_users
    from app.services.db import get_user
    from unittest.mock import Mock

    args = Mock()
    args.username = "cliadmin"
    args.password = "clipassword123"

    cmd_create_admin(args)

    user = get_user("cliadmin")
    assert user is not None
    assert user["is_admin"] is True
    assert (STORAGE_DIR / "cliadmin").exists()

    # Clean up cliadmin
    delete_user("cliadmin")
    if (STORAGE_DIR / "cliadmin").exists():
        shutil.rmtree(STORAGE_DIR / "cliadmin")

