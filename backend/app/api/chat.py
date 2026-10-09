import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..models.schemas import ChatRequest, ChatResponse
from ..services.storage import storage
from ..services.retrieval import retrieval_service
from ..services.llm_client import llm_client

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

from contextlib import asynccontextmanager

_active_sessions = set()

@asynccontextmanager
async def session_guard(session_id):
    # Single-process deployment: no await between membership check and insert.
    if session_id in _active_sessions:
        raise HTTPException(409, "A response is already being generated for this session")
    _active_sessions.add(session_id)
    try:
        yield
    finally:
        _active_sessions.discard(session_id)

from pydantic import BaseModel, Field
class SessionCreate(BaseModel):
    workspace_id: str
    title: str = Field(min_length=1, max_length=160)
class SessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=160)

@router.get("/sessions")
async def list_sessions(workspace_id: str):
    if not storage.get_workspace(workspace_id): raise HTTPException(404, "Workspace not found")
    return storage.list_chat_sessions(workspace_id)
@router.post("/sessions", status_code=201)
async def create_session(request: SessionCreate):
    if not storage.get_workspace(request.workspace_id): raise HTTPException(404, "Workspace not found")
    return storage.create_chat_session(request.workspace_id, request.title)
@router.get("/sessions/{session_id}")
async def get_session(session_id: str, workspace_id: str):
    result = storage.get_chat_session(workspace_id, session_id)
    if not result: raise HTTPException(404, "Session not found")
    return {"session": {k:v for k,v in result.items() if k != "messages"}, "messages": result["messages"]}
@router.patch("/sessions/{session_id}")
async def patch_session(session_id: str, workspace_id: str, request: SessionRename):
    result = storage.rename_chat_session(workspace_id, session_id, request.title)
    if not result: raise HTTPException(404, "Session not found")
    return result
@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(session_id: str, workspace_id: str):
    if not storage.delete_chat_session(workspace_id, session_id): raise HTTPException(404, "Session not found")


def _build_chat_prompt(query: str, scored_chunks) -> list[dict]:
    context_lines = []
    for idx, (chunk, score) in enumerate(scored_chunks):
        context_lines.append(
            f"[{idx+1}] Source: \"{chunk.source_title}\" (Page {chunk.page_number}):\n{chunk.content}"
        )
    context_str = "\n\n".join(context_lines)

    system_prompt = """You are an academic research and learning assistant. Your responses must be STRICTLY grounded in the provided sources.
Rules:
1. Always base your response directly on the provided source chunks.
2. Embed numbered inline citation badges like [1], [2] immediately following claims or facts derived from the corresponding source chunk.
3. If the user's question cannot be answered using the provided sources, explicitly state: "This information is not found in the selected source documents."
4. Be clear, rigorous, and intellectually precise."""

    user_prompt = f"""SOURCE DOCUMENTS:
{context_str}

USER QUESTION:
{query}

Provide a comprehensive, source-grounded answer with inline citation chips [1], [2] wherever appropriate:"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    async with session_guard(request.session_id or f"workspace:{request.workspace_id}"):
        return await _generate_chat(request)

async def _generate_chat(request: ChatRequest):
    if request.source_ids is not None and not request.source_ids:
        raise HTTPException(400, "No source documents selected. Please select at least one source.")
    if not storage.get_workspace(request.workspace_id):
        raise HTTPException(404, "Workspace not found")
    session = storage.get_chat_session(request.workspace_id, request.session_id) if request.session_id else storage.create_chat_session(request.workspace_id, "New chat")
    if not session:
        raise HTTPException(404, "Session not found")
    chunks = storage.get_source_chunks(request.workspace_id, request.source_ids)
    if not chunks:
        raise HTTPException(400, "No source documents found in this workspace. Upload a PDF or add notes first.")
    scored_chunks = retrieval_service.search_hybrid(request.query, chunks, top_k=5)
    citations = retrieval_service.build_citations(scored_chunks)
    messages = _build_chat_prompt(request.query, scored_chunks)
    history = storage.chat_context(session["id"], limit=12)
    messages[-1:-1] = history
    try:
        answer = await llm_client.generate_completion(messages, temperature=0.2)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")
    try:
        storage.append_chat_turn(session["id"], request.workspace_id, request.query, answer,
                                 [c.model_dump() for c in citations], request.source_ids or [],
                                 [c.model_dump() for c, _ in scored_chunks])
    except ValueError:
        raise HTTPException(409, "Concurrent or invalid session turn")
    return ChatResponse(answer=answer, citations=citations,
                        used_chunks=[c for c, _ in scored_chunks], session_id=session["id"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    async with session_guard(request.session_id or f"workspace:{request.workspace_id}"):
        return await _chat_stream_response(request)

async def _chat_stream_response(request: ChatRequest):
    if request.source_ids is not None and not request.source_ids:
        raise HTTPException(400, "No source documents selected. Please select at least one source.")
    if not storage.get_workspace(request.workspace_id):
        raise HTTPException(404, "Workspace not found")
    session = storage.get_chat_session(request.workspace_id, request.session_id) if request.session_id else storage.create_chat_session(request.workspace_id, "New chat")
    if not session:
        raise HTTPException(404, "Session not found")
    chunks = storage.get_source_chunks(request.workspace_id, request.source_ids)
    if not chunks:
        raise HTTPException(400, "No source documents found in this workspace.")
    scored_chunks = retrieval_service.search_hybrid(request.query, chunks, top_k=5)
    citations = retrieval_service.build_citations(scored_chunks)
    messages = _build_chat_prompt(request.query, scored_chunks)
    messages[-1:-1] = storage.chat_context(session["id"], limit=12)
    async def event_generator():
        answer_parts = []
        yield f"event: meta\\ndata: {json.dumps({'session_id': session['id']})}\\n\\n"
        yield f"event: citations\\ndata: {json.dumps([c.model_dump() for c in citations])}\\n\\n"
        try:
            async for token in llm_client.stream_completion(messages, temperature=0.2):
                answer_parts.append(token)
                yield f"event: message\\ndata: {json.dumps({'token': token})}\\n\\n"
            answer = ''.join(answer_parts)
            storage.append_chat_turn(session['id'], request.workspace_id, request.query, answer,
                [c.model_dump() for c in citations], request.source_ids or [], [c.model_dump() for c, _ in scored_chunks])
            yield "event: done\\ndata: {}\\n\\n"
        except Exception as e:
            yield f"event: error\\ndata: {json.dumps({'detail': str(e)})}\\n\\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
