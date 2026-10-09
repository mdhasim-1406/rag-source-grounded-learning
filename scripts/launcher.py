#!/usr/bin/env python3
"""
Scholar Studio - Cross-Platform Server Launcher
Single-user safe startup with LAN security checks and provider awareness.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env without overriding explicitly exported environment variables
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)


def main():
    parser = argparse.ArgumentParser(
        description="Launch Scholar Studio RAG Application"
    )
    # Default to 127.0.0.1 for safe single-user local access
    default_host = os.getenv("HOST", "127.0.0.1")
    default_port_str = os.getenv("PORT", "8000")
    try:
        default_port = int(default_port_str)
    except ValueError:
        default_port = 8000

    parser.add_argument(
        "--host",
        "-H",
        dest="host",
        default=default_host,
        help=f"Host interface to bind to (default: {default_host})",
    )
    parser.add_argument(
        "--port",
        "-p",
        dest="port",
        type=int,
        default=default_port,
        help=f"Port number to listen on (default: {default_port})",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable uvicorn auto-reload for development",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of uvicorn worker processes (default: 1)",
    )

    args = parser.parse_args()
    host = args.host
    port = args.port

    print("=" * 66)
    print(" Scholar Studio - Source-Grounded Learning System")
    print("=" * 66)

    # Opt-in LAN check and security warning
    if host in ("0.0.0.0", "::", "0"):
        print("[WARNING] Binding to 0.0.0.0 exposes Scholar Studio to your local network (LAN).")
        print("[WARNING] This application is single-user with no built-in authentication.")
        print("[WARNING] Anyone on your local network can access the API, upload files, and query data.")
        print("[WARNING] Ensure your host firewall is configured manually. No automatic public tunnel is created.")
        print(f"Local Access URL:  http://127.0.0.1:{port}")
    else:
        print(f"Local Access URL:  http://{host}:{port}")

    print(f"Health Endpoint:   http://127.0.0.1:{port}/health")
    print(f"System Info:       http://127.0.0.1:{port}/api/v1/system")
    print("=" * 66)

    try:
        import uvicorn
    except ImportError:
        print("[ERROR] uvicorn is not installed in the active environment.")
        print("Please run ./setup.sh (Linux/macOS) or .\\setup.ps1 (Windows) first.")
        sys.exit(1)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )


if __name__ == "__main__":
    main()
