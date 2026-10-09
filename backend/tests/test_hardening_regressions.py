import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.models.schemas import SourceChunk, QuizDeck, QuizQuestion, Citation
from app.services.quiz_engine import QuizEngineService, quiz_engine
from app.services.storage import Storage
from app.services.ingestion import DocumentIngestionService
from app.services.llm_client import LLMClient
from app.main import app


@pytest.fixture
def temp_storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    st = Storage(db_path=db_path)
    yield st
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def sample_chunk():
    return SourceChunk(
        id="valid-chunk-123",
        source_id="src-1",
        workspace_id="ws-1",
        source_title="Deep Learning Foundations",
        chunk_index=0,
        content="Backpropagation computes gradients of the loss function with respect to weights using the chain rule.",
        page_number=4,
        token_count=15
    )


# ==============================================================================
# Priority 1 & 2: Quiz Normalization & Citation Grounding
# ==============================================================================

def test_quiz_normalization_rejects_unknown_chunk_id(sample_chunk):
    service = QuizEngineService()
    raw = {
        "type": "mcq_single",
        "question": "What does backpropagation compute?",
        "options": ["A) Weights", "B) Gradients of loss function", "C) Learning rate"],
        "correct_answer": 1,
        "chunk_id": "non-existent-chunk-999",
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule.",
        "explanation": "Calculates gradients."
    }
    result = service._normalize_and_verify_question(raw, [sample_chunk])
    assert result is None, "Should reject question with unknown chunk ID instead of substituting candidate_chunks[0]"


def test_quiz_normalization_rejects_non_verbatim_quote(sample_chunk):
    service = QuizEngineService()
    raw = {
        "type": "mcq_single",
        "question": "What does backpropagation compute?",
        "options": ["A) Weights", "B) Gradients of loss function", "C) Learning rate"],
        "correct_answer": 1,
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "This is a hallucinated quote that does not appear in the text.",
        "explanation": "Calculates gradients."
    }
    result = service._normalize_and_verify_question(raw, [sample_chunk])
    assert result is None, "Should reject question with non-verbatim quote instead of fabricating citation"


def test_quiz_normalization_rejects_empty_quote(sample_chunk):
    service = QuizEngineService()
    raw = {
        "type": "mcq_single",
        "question": "What does backpropagation compute?",
        "options": ["A) Weights", "B) Gradients of loss function", "C) Learning rate"],
        "correct_answer": 1,
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "",
        "explanation": "Calculates gradients."
    }
    result = service._normalize_and_verify_question(raw, [sample_chunk])
    assert result is None, "Should reject question with empty quote"


def test_quiz_normalization_rejects_unsupported_short_answer_type(sample_chunk):
    service = QuizEngineService()
    raw = {
        "type": "short_answer",
        "question": "Explain backpropagation.",
        "correct_answer": "Chain rule",
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule.",
        "explanation": "Calculates gradients."
    }
    result = service._normalize_and_verify_question(raw, [sample_chunk])
    assert result is None, "Should reject short_answer type as unsupported"


def test_quiz_normalization_validates_mcq_options_and_index(sample_chunk):
    service = QuizEngineService()
    # Out of range index
    raw_invalid_idx = {
        "type": "mcq_single",
        "question": "What does backpropagation compute?",
        "options": ["A) Weights", "B) Gradients"],
        "correct_answer": 5,
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule."
    }
    assert service._normalize_and_verify_question(raw_invalid_idx, [sample_chunk]) is None

    # Insufficient options (< 2)
    raw_insufficient = {
        "type": "mcq_single",
        "question": "What does backpropagation compute?",
        "options": ["Only one option"],
        "correct_answer": 0,
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule."
    }
    assert service._normalize_and_verify_question(raw_insufficient, [sample_chunk]) is None


def test_quiz_normalization_validates_multi_select(sample_chunk):
    service = QuizEngineService()
    # Out of range index in list
    raw_bad_indices = {
        "type": "multi_select",
        "question": "Select all applicable properties.",
        "options": ["Option A", "Option B"],
        "correct_answer": [0, 99],
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule."
    }
    assert service._normalize_and_verify_question(raw_bad_indices, [sample_chunk]) is None

    # Empty correct_answer list
    raw_empty_ans = {
        "type": "multi_select",
        "question": "Select all applicable properties.",
        "options": ["Option A", "Option B"],
        "correct_answer": [],
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule."
    }
    assert service._normalize_and_verify_question(raw_empty_ans, [sample_chunk]) is None


def test_quiz_normalization_validates_flashcard(sample_chunk):
    service = QuizEngineService()
    raw_empty_card = {
        "type": "flashcard",
        "question": "What is backprop?",
        "options": [],
        "correct_answer": "",
        "chunk_id": sample_chunk.id,
        "verbatim_quote": "Backpropagation computes gradients of the loss function with respect to weights using the chain rule."
    }
    assert service._normalize_and_verify_question(raw_empty_card, [sample_chunk]) is None


@pytest.mark.anyio
async def test_quiz_generation_fails_explicitly_if_zero_verified(sample_chunk):
    service = QuizEngineService()
    # Mock LLM returning invalid questions that fail verification
    with patch("app.services.quiz_engine.llm_client.generate_json", new_callable=AsyncMock) as mock_json:
        mock_json.return_value = [
            {
                "type": "mcq_single",
                "question": "Fake question",
                "options": ["A", "B"],
                "correct_answer": 0,
                "chunk_id": "non-existent-chunk",
                "verbatim_quote": "Not in text"
            }
        ]
        with pytest.raises(RuntimeError, match="(?i)(no valid|failed to generate any valid)"):
            await service.generate_quiz_deck(
                workspace_id="ws-1",
                workspace_title="Test",
                chunks=[sample_chunk],
                num_questions=1
            )


# ==============================================================================
# Priority 4: Source Selection [] Must Return None Not All
# ==============================================================================

def test_source_selection_empty_list_returns_none(temp_storage):
    ws = temp_storage.create_workspace("Test WS")
    src1 = temp_storage.add_source(ws.id, "Doc 1", "txt")
    src2 = temp_storage.add_source(ws.id, "Doc 2", "txt")
    chunk1 = SourceChunk(
        id="c1", source_id=src1.id, workspace_id=ws.id, source_title=src1.title,
        chunk_index=0, content="Content 1", page_number=1, token_count=5
    )
    chunk2 = SourceChunk(
        id="c2", source_id=src2.id, workspace_id=ws.id, source_title=src2.title,
        chunk_index=0, content="Content 2", page_number=1, token_count=5
    )
    temp_storage.save_chunks([chunk1, chunk2])

    # Passing None should return all chunks
    all_chunks = temp_storage.get_source_chunks(ws.id, source_ids=None)
    assert len(all_chunks) == 2

    # Passing empty list [] must return EMPTY list, NOT all chunks!
    empty_selection_chunks = temp_storage.get_source_chunks(ws.id, source_ids=[])
    assert empty_selection_chunks == [], "source_ids=[] must return empty list, not all workspace chunks!"


def test_api_endpoints_reject_empty_source_selection(temp_storage):
    with patch("app.api.chat.storage", temp_storage), \
         patch("app.api.quizzes.storage", temp_storage), \
         patch("app.api.study.storage", temp_storage):
        client = TestClient(app)
        ws = temp_storage.create_workspace("Scope WS")
        src = temp_storage.add_source(ws.id, "Doc", "txt")
        chunk = SourceChunk(
            id="c1", source_id=src.id, workspace_id=ws.id, source_title=src.title,
            chunk_index=0, content="Some content here", page_number=1, token_count=4
        )
        temp_storage.save_chunks([chunk])

        # Chat with source_ids=[]
        chat_res = client.post("/api/v1/chat", json={
            "workspace_id": ws.id,
            "query": "What is this?",
            "source_ids": []
        })
        assert chat_res.status_code == 400
        assert "No source documents selected" in chat_res.json()["detail"]

        # Quiz generate with source_ids=[]
        quiz_res = client.post("/api/v1/quizzes/generate", json={
            "workspace_id": ws.id,
            "source_ids": [],
            "num_questions": 2
        })
        assert quiz_res.status_code == 400
        assert "No source documents selected" in quiz_res.json()["detail"]

        # Study guide generate with source_ids=[]
        study_res = client.post("/api/v1/study/guide", json={
            "workspace_id": ws.id,
            "source_ids": []
        })
        assert study_res.status_code == 400
        assert "No source documents selected" in study_res.json()["detail"]


# ==============================================================================
# Priority 6: Bounded Chunk Lengths for Long Paragraphs
# ==============================================================================

def test_ingestion_bounds_oversized_paragraphs():
    chunk_size = 50
    overlap = 10
    ingestion = DocumentIngestionService(chunk_size=chunk_size, chunk_overlap=overlap)
    
    # 200 words in a single continuous paragraph without newlines
    long_paragraph = "word " * 200
    pages = ingestion.parse_text_or_markdown(long_paragraph)
    chunks = ingestion.chunk_document(
        source_id="src-1",
        workspace_id="ws-1",
        source_title="Long Para",
        pages=pages
    )
    
    assert len(chunks) > 1, "A 200-word single paragraph with chunk_size=50 must be split into multiple chunks"
    for c in chunks:
        assert c.token_count <= chunk_size, f"Chunk token count {c.token_count} exceeds chunk_size {chunk_size}"


# ==============================================================================
# Priority 7: Actionable Sanitized LLM Errors & Timeout
# ==============================================================================

@pytest.mark.anyio
async def test_llm_client_sanitizes_timeout_error():
    import openai
    import httpx
    req = httpx.Request("POST", "http://test")
    client = LLMClient()
    with patch.object(client.client.chat.completions, "create", side_effect=openai.APITimeoutError(request=req)):
        with pytest.raises(RuntimeError, match="timed out"):
            await client.generate_completion([{"role": "user", "content": "hi"}])


@pytest.mark.anyio
async def test_llm_client_sanitizes_connection_error():
    import openai
    import httpx
    req = httpx.Request("POST", "http://test")
    client = LLMClient()
    with patch.object(client.client.chat.completions, "create", side_effect=openai.APIConnectionError(request=req)):
        with pytest.raises(RuntimeError, match="Cannot connect to LLM gateway"):
            await client.generate_completion([{"role": "user", "content": "hi"}])


# ==============================================================================
# Priority 5: Upload Validation & Security
# ==============================================================================

def test_upload_prevents_directory_traversal(temp_storage, tmp_path):
    with patch("app.api.sources.storage", temp_storage):
        client = TestClient(app)
        ws = temp_storage.create_workspace("Traversal WS")
        
        # Attempt directory traversal via malicious filename
        traversal_filename = "../../../../etc/passwd.txt"
        response = client.post(
            "/api/v1/sources/upload",
            data={"workspace_id": ws.id},
            files={"file": (traversal_filename, b"valid note text for test", "text/plain")}
        )
        assert response.status_code == 200
        source_data = response.json()
        saved_file_path = Path(source_data["file_path"])
        
        # Ensure it was saved strictly within uploads dir under UUID name, not in /etc or parent dirs
        uploads_dir = (Path("data/uploads")).resolve()
        assert saved_file_path.resolve().is_relative_to(uploads_dir) or "uploads" in str(saved_file_path)
        assert ".." not in str(saved_file_path)
        assert saved_file_path.name.startswith(ws.id)


def test_upload_rejects_disallowed_file_types(temp_storage):
    with patch("app.api.sources.storage", temp_storage):
        client = TestClient(app)
        ws = temp_storage.create_workspace("Upload WS")
        
        # Try uploading a disallowed file type
        response = client.post(
            "/api/v1/sources/upload",
            data={"workspace_id": ws.id},
            files={"file": ("malicious.exe", b"binarycontent", "application/x-msdownload")}
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_empty_or_scanned_pdf_with_no_text(temp_storage, tmp_path):
    with patch("app.api.sources.storage", temp_storage):
        client = TestClient(app)
        ws = temp_storage.create_workspace("PDF WS")
        
        # Create a minimal empty/invalid PDF
        corrupt_pdf = b"%PDF-1.4 empty pdf without text objects %%EOF"
        response = client.post(
            "/api/v1/sources/upload",
            data={"workspace_id": ws.id},
            files={"file": ("blank.pdf", corrupt_pdf, "application/pdf")}
        )
        assert response.status_code == 400
        assert "text" in response.json()["detail"].lower() or "pdf" in response.json()["detail"].lower()
