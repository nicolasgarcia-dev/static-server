import sqlite3
import hashlib
import hmac
import secrets
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.config import DB_PATH, STORAGE_DIR

# Username validation regex: lowercase letters, digits, hyphens, underscores, dots
# Length 2-64
USERNAME_REGEX = re.compile(r'^[a-z0-9_\-\.]+$')

# Reserved names that cannot be used as usernames because they collide with system endpoints
RESERVED_USERNAMES = {
    "_static", "_manager", "_admin", "_docs", "_redoc", "_openapi", "api",
    "login", "logout", "favicon.ico", "robots.txt", "static", "public"
}


def get_db_connection() -> sqlite3.Connection:
    """Create a SQLite connection with row factory and WAL mode."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db():
    """Initialize database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );
        """)
        conn.commit()


def validate_username(username: str) -> str:
    """
    Validates username format.
    Accepts lowercase alphanumeric characters, hyphens, underscores, and dots.
    """
    if not username:
        raise ValueError("El nombre de usuario no puede estar vacío.")

    clean_user = username.strip().lower()

    if len(clean_user) < 2:
        raise ValueError("El nombre de usuario debe tener al menos 2 caracteres.")
    if len(clean_user) > 64:
        raise ValueError("El nombre de usuario no puede superar los 64 caracteres.")

    if not USERNAME_REGEX.match(clean_user):
        raise ValueError(
            "El nombre de usuario solo puede contener letras minúsculas, números, guiones (-), "
            "guiones bajos (_) y puntos (.)."
        )

    if clean_user in RESERVED_USERNAMES:
        raise ValueError(f"'{clean_user}' es un nombre reservado del sistema.")

    return clean_user


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hashes a password using hashlib.scrypt with a random salt.
    Returns (password_hash_hex, salt_hex).
    """
    if not password or len(password) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")

    if not salt:
        salt = secrets.token_hex(16)

    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1
    )
    return derived.hex(), salt


def create_user(
    username: str,
    password: str,
    is_admin: bool = False,
    is_active: bool = True
) -> Dict[str, Any]:
    """
    Creates a new user and ensures their storage folder exists.
    """
    clean_user = validate_username(username)
    pwd_hash, salt = hash_password(password)

    now = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, salt, is_admin, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (clean_user, pwd_hash, salt, 1 if is_admin else 0, 1 if is_active else 0, now, now)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"El usuario '{clean_user}' ya existe.")

    # Ensure user storage folder exists in html_storage/<username>
    user_storage = STORAGE_DIR / clean_user
    user_storage.mkdir(parents=True, exist_ok=True)

    return {
        "username": clean_user,
        "is_admin": is_admin,
        "is_active": is_active,
        "created_at": now
    }


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by username."""
    clean_user = username.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, password_hash, salt, is_admin, is_active, created_at, updated_at
            FROM users
            WHERE username = ?
            """,
            (clean_user,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "password_hash": row["password_hash"],
            "salt": row["salt"],
            "is_admin": bool(row["is_admin"]),
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }


def list_users() -> List[Dict[str, Any]]:
    """List all registered users without sensitive password hashes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, is_admin, is_active, created_at, updated_at
            FROM users
            ORDER BY is_admin DESC, username ASC
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "username": r["username"],
                "is_admin": bool(r["is_admin"]),
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            }
            for r in rows
        ]


def update_user_status(username: str, is_active: bool) -> Dict[str, Any]:
    """Enable or disable a user account."""
    clean_user = username.strip().lower()
    user = get_user(clean_user)
    if not user:
        raise ValueError(f"El usuario '{clean_user}' no existe.")

    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET is_active = ?, updated_at = ?
            WHERE username = ?
            """,
            (1 if is_active else 0, now, clean_user)
        )
        # If disabled, also invalidate active sessions for security
        if not is_active:
            cursor.execute("DELETE FROM sessions WHERE username = ?", (clean_user,))
        conn.commit()

    return {
        "username": clean_user,
        "is_active": is_active,
        "updated_at": now
    }


def update_user_password(username: str, new_password: str) -> bool:
    """Updates the password hash and salt for a user."""
    clean_user = username.strip().lower()
    user = get_user(clean_user)
    if not user:
        raise ValueError(f"El usuario '{clean_user}' no existe.")

    pwd_hash, salt = hash_password(new_password)
    now = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, salt = ?, updated_at = ?
            WHERE username = ?
            """,
            (pwd_hash, salt, now, clean_user)
        )
        conn.commit()

    return True


def delete_user(username: str) -> bool:

    """Delete a user account and associated sessions."""
    clean_user = username.strip().lower()
    user = get_user(clean_user)
    if not user:
        raise ValueError(f"El usuario '{clean_user}' no existe.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE username = ?", (clean_user,))
        cursor.execute("DELETE FROM users WHERE username = ?", (clean_user,))
        conn.commit()

    return True


def verify_password(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Verifies user credentials.
    Returns safe user dict if verified, None if invalid.
    Raises ValueError if account is disabled.
    """
    user = get_user(username)
    if not user:
        return None

    if not user["is_active"]:
        raise ValueError("Cuenta deshabilitada. Contacte con el administrador.")

    calc_hash, _ = hash_password(password, salt=user["salt"])
    if hmac.compare_digest(calc_hash, user["password_hash"]):
        return {
            "username": user["username"],
            "is_admin": user["is_admin"],
            "is_active": user["is_active"]
        }

    return None


def change_password(username: str, new_password: str) -> bool:
    """Change a user's password."""
    clean_user = username.strip().lower()
    user = get_user(clean_user)
    if not user:
        raise ValueError(f"El usuario '{clean_user}' no existe.")

    pwd_hash, salt = hash_password(new_password)
    now = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET password_hash = ?, salt = ?, updated_at = ?
            WHERE username = ?
            """,
            (pwd_hash, salt, now, clean_user)
        )
        # Invalidate sessions on password change
        cursor.execute("DELETE FROM sessions WHERE username = ?", (clean_user,))
        conn.commit()

    return True


def count_users() -> int:
    """Count total registered users."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]


# ==============================================================================
# SESSIONS MANAGEMENT
# ==============================================================================

def create_session(username: str, duration_days: int = 30) -> str:
    """Generate and store a new secure session token."""
    clean_user = username.strip().lower()
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=duration_days)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (token, username, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, clean_user, now.isoformat(), expires.isoformat())
        )
        conn.commit()

    return token


def get_session_user(token: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user for given session token if not expired and user is active.
    """
    if not token or not isinstance(token, str):
        return None

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.token, s.username, s.expires_at, u.is_admin, u.is_active
            FROM sessions s
            JOIN users u ON s.username = u.username
            WHERE s.token = ?
            """,
            (token,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Check expiration
        if row["expires_at"] < now_iso:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None

        # Check if user is enabled
        if not bool(row["is_active"]):
            return None

        return {
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
            "is_active": True
        }


def delete_session(token: str) -> bool:
    """Delete a session token on logout."""
    if not token:
        return False

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    return True


def cleanup_expired_sessions() -> int:
    """Remove all expired sessions from database."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (now_iso,))
        deleted = cursor.rowcount
        conn.commit()
    return deleted


# Auto-initialize database schema when module is imported
init_db()
