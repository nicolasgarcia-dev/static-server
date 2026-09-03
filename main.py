import os
import sys
import argparse
import getpass
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def run_server(args):
    """Start the Uvicorn web server."""
    os.environ["PORT"] = str(args.port)
    os.environ["HOST"] = args.host
    os.environ["HTML_STORAGE_DIR"] = str(Path(args.storage_dir).resolve())

    storage_path = Path(os.environ["HTML_STORAGE_DIR"])
    storage_path.mkdir(parents=True, exist_ok=True)

    import uvicorn

    print(f"\n=======================================================")
    print(f" 🚀 HTML Server & Explorer iniciado (Multiusuario)")
    print(f" -------------------------------------------------------")
    print(f" • Panel de Control:     http://{args.host}:{args.port}/")
    print(f" • Inicio de Sesión:     http://{args.host}:{args.port}/login")
    print(f" • Panel Alternativo:    http://{args.host}:{args.port}/_manager")
    print(f" • Carpeta de archivos:  {storage_path}")
    print(f" =======================================================\n")

    uvicorn.run(
        "app.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


def cmd_create_admin(args):
    """Create an administrator account from CLI."""
    from app.services.db import create_user, get_user, init_db

    init_db()

    username = args.username
    if not username:
        try:
            username = input("👤 Nombre de usuario administrador: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            sys.exit(1)

    if not username:
        print("❌ Error: El nombre de usuario no puede estar vacío.")
        sys.exit(1)

    existing = get_user(username)
    if existing:
        print(f"❌ Error: El usuario '{username}' ya existe.")
        sys.exit(1)

    password = args.password
    if not password:
        try:
            p1 = getpass.getpass("🔑 Contraseña: ")
            p2 = getpass.getpass("🔑 Confirma la contraseña: ")
            if p1 != p2:
                print("❌ Error: Las contraseñas no coinciden.")
                sys.exit(1)
            password = p1
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            sys.exit(1)

    try:
        user = create_user(username=username, password=password, is_admin=True, is_active=True)
        print(f"\n✅ Administrador '{user['username']}' creado correctamente.")
        print(f"📁 Directorio asignado: html_storage/{user['username']}")
        print(f"🌐 Inicia sesión en el panel web: http://localhost:{os.getenv('PORT', '5000')}/login\n")
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_create_user(args):
    """Create a user account from CLI."""
    from app.services.db import create_user, get_user, init_db

    init_db()

    username = args.username
    if not username:
        try:
            username = input("👤 Nombre de usuario: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            sys.exit(1)

    if not username:
        print("❌ Error: El nombre de usuario no puede estar vacío.")
        sys.exit(1)

    existing = get_user(username)
    if existing:
        print(f"❌ Error: El usuario '{username}' ya existe.")
        sys.exit(1)

    password = args.password
    if not password:
        try:
            p1 = getpass.getpass("🔑 Contraseña: ")
            p2 = getpass.getpass("🔑 Confirma la contraseña: ")
            if p1 != p2:
                print("❌ Error: Las contraseñas no coinciden.")
                sys.exit(1)
            password = p1
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada.")
            sys.exit(1)

    try:
        user = create_user(username=username, password=password, is_admin=args.admin, is_active=True)
        role_label = "Administrador" if args.admin else "Usuario estándar"
        print(f"\n✅ {role_label} '{user['username']}' creado correctamente.")
        print(f"📁 Directorio asignado: html_storage/{user['username']}")
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def cmd_list_users(args):
    """List all registered users from CLI."""
    from app.services.db import list_users, init_db

    init_db()
    users = list_users()

    if not users:
        print("\nℹ️  No hay usuarios registrados todavía.")
        print("💡 Crea un administrador con: python main.py create-admin\n")
        return

    print("\n=======================================================")
    print(" 👥 Usuarios Registrados en el Servidor")
    print(" -------------------------------------------------------")
    print(f" {'USUARIO':<20} | {'ROL':<14} | {'ESTADO':<14} | {'CREADO'}")
    print(" " + "-" * 64)
    for u in users:
        role = "Administrador" if u["is_admin"] else "Usuario"
        status = "Habilitado" if u["is_active"] else "Deshabilitado"
        date_str = u["created_at"].split("T")[0] if u.get("created_at") else "-"
        print(f" {u['username']:<20} | {role:<14} | {status:<14} | {date_str}")
    print(" =======================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="HTML Server & Explorer - Servidor de HTMLs estáticos con panel web multiusuario.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Comando a ejecutar")

    # Subcommand: run (web server)
    run_parser = subparsers.add_parser("run", help="Iniciar el servidor web")
    run_parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.getenv("PORT", "5000")),
        help="Puerto donde se ejecutará el servidor web"
    )
    run_parser.add_argument(
        "-H", "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Dirección IP de escucha del servidor"
    )
    run_parser.add_argument(
        "-d", "--storage-dir",
        type=str,
        default=os.getenv("HTML_STORAGE_DIR", "html_storage"),
        help="Carpeta base donde se almacenan y sirven los HTMLs"
    )
    run_parser.add_argument(
        "--reload",
        action="store_true",
        help="Activar auto-recarga en desarrollo"
    )

    # Subcommand: create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Crear un usuario administrador")
    admin_parser.add_argument("-u", "--username", type=str, help="Nombre del usuario administrador")
    admin_parser.add_argument("-p", "--password", type=str, help="Contraseña del usuario administrador")

    # Subcommand: create-user
    user_parser = subparsers.add_parser("create-user", help="Crear un nuevo usuario")
    user_parser.add_argument("-u", "--username", type=str, help="Nombre del usuario")
    user_parser.add_argument("-p", "--password", type=str, help="Contraseña del usuario")
    user_parser.add_argument("--admin", action="store_true", help="Crear con privilegios de administrador")

    # Subcommand: list-users
    subparsers.add_parser("list-users", help="Listar usuarios registrados")

    # Compatibility: If first argument is not a known subcommand, default to 'run'
    argv = sys.argv[1:]
    known_commands = {"run", "create-admin", "create-user", "list-users", "-h", "--help"}

    if not argv or (argv[0] not in known_commands and not argv[0].startswith("-h")):
        # Prepend 'run' to arguments so existing commands like python main.py --port 5000 continue working
        argv = ["run"] + argv

    args = parser.parse_args(argv)

    if args.subcommand == "create-admin":
        cmd_create_admin(args)
    elif args.subcommand == "create-user":
        cmd_create_user(args)
    elif args.subcommand == "list-users":
        cmd_list_users(args)
    elif args.subcommand == "run" or args.subcommand is None:
        run_server(args)


if __name__ == "__main__":
    main()
