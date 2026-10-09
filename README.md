# Scholar Studio: RAG-Based Intelligent Quiz Generation & Source-Grounded Learning System

Scholar Studio is an academic workspace and intelligent learning platform inspired by Google NotebookLM and OpenNotebook. It transforms static documents (PDFs, lectures, research papers, notes) into an active-recall cognitive sandbox featuring rigorous source grounding, interactive diagnostic quizzes, automated study guides, and concept mastery analytics.

---

## Key Features

1. **Academic Cockpit Layout (Google Stitch Design System)**
   - **Sources & Index (Left Pane):** Multi-source ingestion with support for PDFs, markdown, and text notes. Hierarchical chunking (400 tokens / 60 token overlap) with exact page number tracking and chunk references. Checkbox-level source filtering.
   - **Studio Inquiry & Synthesis (Center Pane):** Conversational Q&A strictly constrained to selected sources. Responses embed interactive, clickable citation pill badges (`[1]`, `[2]`) that open source excerpts with verbatim quotes and page numbers.
   - **Active Mastery Arena (Right Pane):** Multi-modal diagnostic quiz generator, dynamic study guide synthesizer, and student concept mastery tracking.

2. **Pedagogical Quiz Engine**
   - **Multiple Question Types:** Single-choice MCQs, multi-select, and active-recall flashcards.
   - **Cognitive Bloom Taxonomy:** Questions categorized by depth (*remember*, *understand*, *apply*, *analyze*).
   - **Verbatim Grounding & Plausible Distractors:** Every question includes an exact quote from the source chunk. Distractors represent common misconceptions rather than random text.
   - **Pedagogical Explanations:** Explains why the correct choice is valid and provides granular breakdowns for each distractor.

3. **Closed-Loop Concept Mastery Analytics**
   - Tracks individual concept mastery percentages based on quiz attempts.
   - Highlights weak areas and surfaces targeted study flashcards.

4. **Multi-Provider Architecture**
   - **Local OmniRoute Gateway (Default):** Connects to `http://localhost:20128/v1` using `agy/gemini-3.8-flash-tiered`.
     > **Gateway Note:** The local OmniRoute endpoint **only works if the OmniRoute gateway is installed and running on your host system**. The gateway daemon is **not bundled** with this client repository.
   - **Turnkey Cloud & Local Providers:** Ready-to-use configurations in `.env` for Google Gemini AI Studio, Groq, NVIDIA NIM, OpenAI, and OpenCode CLI proxies.

---

## Architecture & Technology Stack

- **Backend:** Python 3.11+ / FastAPI, Pydantic v2, PyMuPDF (`fitz`), Uvicorn.
- **Retrieval Engine:** Dual-Path Lexical Retrieval combining BM25 Okapi keyword ranking and contiguous subphrase/term coverage scoring with Reciprocal Rank Fusion (RRF). Retrieval is deterministic and purely lexical without neural vector embeddings or vector databases.
- **Storage:** Embedded SQLite database (`data/scholar_studio.db`) with zero external daemon dependencies.
- **Frontend:** Modern Vanilla JavaScript (SPA), Google Stitch Design System CSS tokens, zero heavy framework dependencies.

---

## Quick Start

### 1. Prerequisites
- Python >= 3.11 (or `uv`)
- Local OmniRoute gateway on `http://localhost:20128/v1`, OR an API key for Gemini / Groq / NVIDIA / OpenAI.

### 2. Environment Setup
Run the repeatable native setup script for your platform. This script detects Python >= 3.11 or `uv`, provisions `.venv`, installs the backend in editable mode, copies `.env.example` to `.env` if `.env` does not exist (never overwriting existing secrets or databases), and validates imports:

```bash
# Linux / macOS / WSL:
./setup.sh

# Windows (PowerShell):
.\setup.ps1
```

### 3. Configure Provider (.env)
If you are not using a local OmniRoute gateway, edit `.env` and configure your preferred provider credentials. Setup never prints credentials to stdout.

### 4. Start the Application
Launch Scholar Studio with the native start script:

```bash
# Linux / macOS / WSL:
./start.sh

# Windows (PowerShell):
.\start.ps1
```

- **Default Safe Binding:** Runs on `127.0.0.1:8000` (safe single-user localhost access; no authentication).
- **Custom Port:**
  ```bash
  PORT=8080 ./start.sh
  # or: ./start.sh --port 8080
  # Windows: .\start.ps1 -Port 8080
  ```
- **Opt-in LAN Binding (`0.0.0.0`):**
  ```bash
  ./start.sh --host 0.0.0.0 --port 8000
  # Windows: .\start.ps1 -HostName 0.0.0.0 -Port 8000
  ```
  > **Network Security Warning:** Binding to `0.0.0.0` exposes Scholar Studio to your local network without authentication. Ensure your host firewall is configured manually. No automatic public tunnel is created.

See [start_command.md](start_command.md) for full start command syntax and options.

### 5. Access Endpoints
- **Web Interface:** `http://127.0.0.1:8000/` (or `http://localhost:8000/`)
- **Health Check:** `http://127.0.0.1:8000/health`
- **System Info:** `http://127.0.0.1:8000/api/v1/system`

---

## Instructions for Automated Coding Agents (Antigravity / Codex / OpenCode)

Autonomous coding harnesses and subagents operating on this workspace must follow this workflow:

1. **Run Setup:**
   Execute `./setup.sh` (Linux/macOS) or `.\setup.ps1` (Windows). The setup script is fully idempotent and safe to re-run; existing `.env` secrets and database files are preserved.
2. **Select Provider:**
   Check `.env`. Note that the default OmniRoute endpoint (`http://localhost:20128/v1`) functions only if the OmniRoute gateway is active on the host machine. Otherwise, configure an alternative key (e.g. Gemini, Groq, NVIDIA, OpenAI). Never print secrets or echo `.env` to outputs.
3. **Launch Server & Process Discipline:**
   Execute `./start.sh` or `start.ps1`.
   **CRITICAL RULE (`no killotherprocesses`):** Track the PID of your owned server process and keep its logs. **Never kill other processes** or restart shared system daemons (such as shared port 8000 listeners or background proxy gateways). Terminate only the process spawned by your own session.
4. **Verify Health:**
   Run `curl -s -f http://127.0.0.1:8000/health` and verify the JSON response contains `{"status": "healthy", ...}`.
5. **Report URLs:**
   Output the accessible localhost URL (`http://127.0.0.1:8000`) and the exact startup command.

---

## Running Automated Tests

Run the backend test suite verifying ingestion, lexical retrieval, SQLite persistence, and quiz evaluation:

```bash
.venv/bin/pytest backend/tests/ -v
```

---

## Project Structure

```
rag-source-grounded-learning/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── chat.py           # Grounded chat & SSE streaming
│   │   │   ├── quizzes.py        # Quiz generation & evaluation
│   │   │   ├── sources.py        # PDF & document upload / chunking
│   │   │   ├── study.py          # Study guide generation
│   │   │   └── workspaces.py     # Workspace management
│   │   ├── models/
│   │   │   └── schemas.py        # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── ingestion.py      # PyMuPDF parser & hierarchical chunker
│   │   │   ├── llm_client.py     # OpenAI-compatible multi-provider client
│   │   │   ├── quiz_engine.py    # Generator & strict citation verification engine
│   │   │   ├── retrieval.py      # BM25 + phrase coverage + RRF lexical engine
│   │   │   ├── storage.py        # SQLite persistence layer
│   │   │   └── study_guide.py    # Study guide synthesis engine
│   │   ├── config.py             # App settings & environment loading
│   │   └── main.py               # FastAPI entrypoint & static mounting
│   ├── tests/
│   │   ├── test_chat_lock.py
│   │   ├── test_hardening_regressions.py
│   │   ├── test_ingestion_and_retrieval.py
│   │   └── test_quiz_and_storage.py
│   └── pyproject.toml
├── frontend/
│   ├── css/
│   │   └── style.css             # Google Stitch design system tokens
│   ├── js/
│   │   ├── app.js                # Vanilla JS state & interaction engine
│   │   └── persistence.js        # Local persistence layer
│   └── index.html                # 3-column academic cockpit
├── scripts/
│   └── launcher.py               # Cross-platform safe startup launcher
├── .env.example                  # Template with OmniRoute, Groq, NIM, Gemini, OpenAI
├── setup.sh                      # Linux / macOS / WSL repeatable setup
├── setup.ps1                     # Windows PowerShell repeatable setup
├── start.sh                      # Linux / macOS / WSL safe launch script
├── start.ps1                     # Windows PowerShell safe launch script
├── start_command.md              # Exact startup commands and network reference
├── run.sh                        # Backwards-compatible launch wrapper
├── STITCH_DESIGN_SYSTEM.md       # Extracted Google Stitch guidelines
└── README.md
```

---

## License
No project license has been selected.
