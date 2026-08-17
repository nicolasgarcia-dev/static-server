import os
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.server import app
from app.config import STORAGE_DIR

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_storage():
    """Ensure clean test environment before each test."""
    test_subfolder = STORAGE_DIR / "TEST_CIM"
    if test_subfolder.exists():
        shutil.rmtree(test_subfolder)
    yield
    if test_subfolder.exists():
        shutil.rmtree(test_subfolder)


def test_index_dashboard_returns_200():
    """Verify that root dashboard renders correctly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "HTML Server" in response.text


def test_manager_alias_returns_200():
    """Verify that /_manager always opens the dashboard."""
    response = client.get("/_manager")
    assert response.status_code == 200
    assert "HTML Server" in response.text


def test_create_folder_and_list():
    """Test folder creation and listing via API."""
    res_create = client.post("/api/explorer/folders", json={"path": "", "name": "TEST_CIM"})
    assert res_create.status_code == 200
    data = res_create.json()
    assert data["success"] is True
    assert data["data"]["name"] == "TEST_CIM"

    res_list = client.get("/api/explorer/list?path=")
    assert res_list.status_code == 200
    items = res_list.json()["data"]["items"]
    assert any(item["name"] == "TEST_CIM" and item["is_dir"] for item in items)


def test_upload_html_and_direct_serve():
    """
    Test uploading an HTML file to a folder and accessing it directly
    via GET /<folder>/<filename>.html
    """
    client.post("/api/explorer/folders", json={"path": "", "name": "TEST_CIM"})

    html_content = "<html><body><h1>Hola CIM Test</h1></body></html>"
    files = {"files": ("test-cim.html", html_content.encode("utf-8"), "text/html")}
    res_upload = client.post("/api/explorer/upload", data={"path": "TEST_CIM"}, files=files)
    assert res_upload.status_code == 200
    assert res_upload.json()["success"] is True

    res_serve = client.get("/TEST_CIM/test-cim.html")
    assert res_serve.status_code == 200
    assert "text/html" in res_serve.headers.get("content-type", "")
    assert "Hola CIM Test" in res_serve.text


def test_user_example_route():
    """Verify that the user's explicit example route /CIM/fichajes-cim.html works."""
    response = client.get("/CIM/fichajes-cim.html")
    assert response.status_code == 200
    assert "CIM" in response.text
    assert "text/html" in response.headers.get("content-type", "")


def test_path_traversal_prevention():
    """Verify that path traversal attempts are safely rejected."""
    res = client.get("/../../../etc/passwd")
    assert res.status_code in [403, 404]

    res_api = client.get("/api/explorer/list?path=../../")
    assert res_api.status_code == 400


def test_rename_and_delete_item():
    """Test renaming and deleting items."""
    client.post("/api/explorer/folders", json={"path": "", "name": "TEST_CIM"})

    res_rename = client.post("/api/explorer/rename", json={"path": "TEST_CIM", "new_name": "TEST_CIM_RENAMED"})
    assert res_rename.status_code == 200

    res_del = client.request("DELETE", "/api/explorer/items", json={"path": "TEST_CIM_RENAMED"})
    assert res_del.status_code == 200


# ==============================================================================
# SECURITY & XSS TESTS
# ==============================================================================

def test_reflected_xss_in_404_is_escaped():
    """Verify that malicious script tags in URLs are safely escaped in 404 responses."""
    payload = "<script>alert('xss')</script>"
    response = client.get(f"/{payload}")
    assert response.status_code == 404
    # The raw unescaped payload MUST NOT appear in the HTML
    assert "<script>alert('xss')</script>" not in response.text
    # The properly escaped HTML entity MUST appear instead
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in response.text or "&lt;script&gt;" in response.text


def test_xss_folder_name_is_rejected():
    """Verify that folder names with XSS or illegal characters are rejected with 422 or 400."""
    payload = "<img src=x onerror=alert(1)>"
    res = client.post("/api/explorer/folders", json={"path": "", "name": payload})
    assert res.status_code in [400, 422]


def test_security_headers_present():
    """Verify that standard HTTP security headers are present in all responses."""
    response = client.get("/")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
