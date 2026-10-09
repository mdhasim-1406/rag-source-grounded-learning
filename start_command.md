# Scholar Studio - Exact Start Commands Reference

This reference documents the exact start commands, arguments, accessible endpoints, and networking rules for Scholar Studio across Linux, macOS, WSL, and Windows.

---

## 1. Prerequisites & Initial Setup

Before starting the server for the first time, ensure the environment is initialized:

### Linux / macOS / WSL
```bash
./setup.sh
```

### Windows (PowerShell)
```powershell
.\setup.ps1
```

Both setup scripts detect Python >= 3.11 (or `uv`), create the `.venv` virtual environment, install the backend package in editable mode (`-e backend`), copy `.env.example` to `.env` if `.env` does not exist (preserving existing configurations and databases without printing credentials), and verify backend imports.

---

## 2. Standard Start Commands (Default: Safe Single-User Localhost)

By default, Scholar Studio binds to `127.0.0.1:8000`. This is the safe, single-user configuration suitable for local development and private study. No authentication is enforced.

### Linux / macOS / WSL
```bash
./start.sh
```
*Or explicitly with bash:*
```bash
bash start.sh
```

### Windows (PowerShell)
```powershell
.\start.ps1
```

### Direct Python / Uvicorn Alternative
```bash
# Linux / macOS / WSL:
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Windows (PowerShell):
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

---

## 3. Custom Host & Port Overrides

### Changing the Port
```bash
# Linux / macOS / WSL:
./start.sh --port 8080
# Or via environment variable:
PORT=8080 ./start.sh

# Windows (PowerShell):
.\start.ps1 -Port 8080
# Or via environment variable:
$env:PORT="8080"; .\start.ps1
```

### Opt-in Local Area Network (LAN) Binding
To allow access from other devices on your local Wi-Fi or LAN, bind to `0.0.0.0`:

```bash
# Linux / macOS / WSL:
./start.sh --host 0.0.0.0 --port 8000

# Windows (PowerShell):
.\start.ps1 -HostName 0.0.0.0 -Port 8000
```

> **SECURITY NOTICE ON LAN BINDING (`0.0.0.0`):**
> - Scholar Studio is a single-user system designed without authentication.
> - Binding to `0.0.0.0` exposes your uploaded documents, API routes, and SQLite database to any device on the same local network.
> - Configure firewall rules manually before doing so.
> - No public or automatic tunnel is created by this software.

---

## 4. Accessible URLs & Verifications

Once the server is running, the following endpoints are accessible:

| Resource | URL | Purpose |
|----------|-----|---------|
| **Web Interface** | `http://127.0.0.1:8000/` or `http://localhost:8000/` | Interactive 3-column academic workspace |
| **Health Check** | `http://127.0.0.1:8000/health` | Service status, active LLM provider and model |
| **System Info** | `http://127.0.0.1:8000/api/v1/system` | Retrieval parameters, chunk sizes, data paths |

### Quick Verification via cURL:
```bash
curl -s http://127.0.0.1:8000/health
```
Expected response:
```json
{"status":"healthy","app":"Scholar Studio - RAG Quiz & Learning System","version":"0.1.0","provider":"omniroute","model":"agy/gemini-3.8-flash-tiered"}
```
