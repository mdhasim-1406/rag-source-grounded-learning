from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings
from .api import workspaces, sources, chat, quizzes, study

app = FastAPI(
    title="Scholar Studio API",
    description="RAG-Based Intelligent Quiz Generation and Source-Grounded Learning System",
    version=settings.version
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(workspaces.router)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(quizzes.router)
app.include_router(study.router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version,
        "provider": settings.llm_provider,
        "model": settings.llm_model
    }


@app.get("/api/v1/system")
def system_info():
    return {
        "provider": settings.llm_provider,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k_chunks": settings.top_k_chunks,
        "data_dir": str(settings.data_dir)
    }


# Static Frontend Mounting
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_frontend_root():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Scholar Studio API is running."}
