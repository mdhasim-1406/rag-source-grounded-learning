import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Find root directory containing .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    app_name: str = "Scholar Studio - RAG Quiz & Learning System"
    version: str = "0.1.0"
    
    # LLM Settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "omniroute")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "omniroute_keyless")
    llm_model: str = os.getenv("LLM_MODEL", "agy/gemini-3.8-flash-tiered")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "60.0"))
    
    # Server & Data
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    data_dir: Path = BASE_DIR / os.getenv("DATA_DIR", "./data")
    
    # Chunking & Retrieval Parameters (OpenNotebook Standards)
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "400"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "60"))
    top_k_chunks: int = int(os.getenv("TOP_K_CHUNKS", "5"))
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.25"))

    def ensure_directories(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
