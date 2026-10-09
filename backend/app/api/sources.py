import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from ..config import settings
from ..models.schemas import Source, SourceCreateText, SourceChunk
from ..services.storage import storage
from ..services.ingestion import ingestion_service

router = APIRouter(prefix="/api/v1/sources", tags=["Sources"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


@router.post("/upload", response_model=Source)
async def upload_source(
    workspace_id: str = Form(...),
    file: UploadFile = File(...)
):
    ws = storage.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    raw_filename = file.filename or "uploaded_document"
    safe_title = Path(raw_filename).name.strip() or "uploaded_document"
    suffix = Path(safe_title).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed types are: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    uploads_dir = (settings.data_dir / "uploads").resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Secure UUID basename path preventing path traversal
    file_uuid = uuid.uuid4().hex
    secure_filename = f"{workspace_id}_{file_uuid}{suffix}"
    save_path = (uploads_dir / secure_filename).resolve()

    # Verify path confinement
    if not str(save_path).startswith(str(uploads_dir)):
        raise HTTPException(status_code=400, detail="Invalid file destination path.")

    # Stream to disk with size bounds
    total_bytes = 0
    try:
        with open(save_path, "wb") as buffer:
            while chunk := await file.read(64 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File size exceeds maximum allowed limit (25 MB)."
                    )
                buffer.write(chunk)
    except HTTPException:
        if save_path.exists():
            save_path.unlink()
        raise
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {str(e)}")

    source_type = "pdf" if suffix == ".pdf" else "txt"

    # Ingestion & parsing with robust error handling
    try:
        if source_type == "pdf":
            pages = ingestion_service.parse_pdf(save_path)
        else:
            with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            pages = ingestion_service.parse_text_or_markdown(content)
    except ValueError as ve:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted PDF file: {str(ve)}")
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")

    # Check for extractable text (guards against scanned/image-only PDFs and blank files)
    total_text = "".join(text for _, text in pages).strip()
    if not pages or not total_text:
        if save_path.exists():
            save_path.unlink()
        if source_type == "pdf":
            raise HTTPException(
                status_code=400,
                detail="No extractable text found in PDF. Scanned or image-only documents without an embedded text layer are not supported."
            )
        else:
            raise HTTPException(status_code=400, detail="The uploaded file contains no extractable text.")

    source = storage.add_source(
        workspace_id=workspace_id,
        title=safe_title,
        source_type=source_type,
        file_path=str(save_path)
    )

    chunks = ingestion_service.chunk_document(
        source_id=source.id,
        workspace_id=workspace_id,
        source_title=source.title,
        pages=pages
    )
    storage.save_chunks(chunks)

    # Re-fetch updated source with chunk count
    sources = storage.list_sources(workspace_id)
    return next((s for s in sources if s.id == source.id), source)


@router.post("/text", response_model=Source)
def create_text_source(payload: SourceCreateText):
    ws = storage.get_workspace(payload.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="Source content cannot be empty.")

    clean_title = payload.title.strip() or "Untitled Note"

    source = storage.add_source(
        workspace_id=payload.workspace_id,
        title=clean_title,
        source_type=payload.source_type,
        file_path=None
    )

    pages = ingestion_service.parse_text_or_markdown(payload.content)
    chunks = ingestion_service.chunk_document(
        source_id=source.id,
        workspace_id=payload.workspace_id,
        source_title=source.title,
        pages=pages
    )
    storage.save_chunks(chunks)

    sources = storage.list_sources(payload.workspace_id)
    return next((s for s in sources if s.id == source.id), source)


@router.get("/{workspace_id}", response_model=List[Source])
def list_sources(workspace_id: str):
    return storage.list_sources(workspace_id)


@router.get("/{workspace_id}/chunks", response_model=List[SourceChunk])
def get_chunks(workspace_id: str, source_ids: Optional[List[str]] = Query(None)):
    return storage.get_source_chunks(workspace_id, source_ids)


@router.delete("/{source_id}")
def delete_source(source_id: str):
    success = storage.delete_source(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Source not found.")
    return {"message": "Source deleted successfully."}
