import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def main():
    parser = argparse.ArgumentParser(
        description="HTML Server & Explorer - Servidor de HTMLs estáticos con panel web.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.getenv("PORT", "5000")),
        help="Puerto donde se ejecutará el servidor web"
    )
    parser.add_argument(
        "-H", "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Dirección IP de escucha del servidor"
    )
    parser.add_argument(
        "-d", "--storage-dir",
        type=str,
        default=os.getenv("HTML_STORAGE_DIR", "html_storage"),
        help="Carpeta base donde se almacenan y sirven los HTMLs"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Activar auto-recarga en desarrollo"
    )

    args = parser.parse_args()

    # Set environment variables for app/config.py
    os.environ["PORT"] = str(args.port)
    os.environ["HOST"] = args.host
    os.environ["HTML_STORAGE_DIR"] = str(Path(args.storage_dir).resolve())

    # Ensure storage dir exists
    storage_path = Path(os.environ["HTML_STORAGE_DIR"])
    storage_path.mkdir(parents=True, exist_ok=True)

    import uvicorn

    print(f"\n=======================================================")
    print(f" 🚀 HTML Server & Explorer iniciado")
    print(f" -------------------------------------------------------")
    print(f" • Panel de Control:     http://{args.host}:{args.port}/")
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


if __name__ == "__main__":
    main()
