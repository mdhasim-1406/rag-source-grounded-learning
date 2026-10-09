from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..models.schemas import QuizGenerateRequest, QuizDeck, QuizSubmitRequest, QuizResult
from ..services.storage import storage
from ..services.quiz_engine import quiz_engine

router = APIRouter(prefix="/api/v1/quizzes", tags=["Quizzes"])


@router.post("/generate", response_model=QuizDeck)
async def generate_quiz(request: QuizGenerateRequest):
    ws = storage.get_workspace(request.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    if request.source_ids is not None and len(request.source_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="No source documents selected. Please select at least one source."
        )

    chunks = storage.get_source_chunks(request.workspace_id, request.source_ids)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No source documents available in this workspace. Upload documents first."
        )

    try:
        deck = await quiz_engine.generate_quiz_deck(
            workspace_id=request.workspace_id,
            workspace_title=ws.title,
            chunks=chunks,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            question_types=request.question_types
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {str(e)}")

    storage.save_quiz_deck(deck)
    return deck


@router.get("/{deck_id}", response_model=QuizDeck)
def get_quiz_deck(deck_id: str):
    deck = storage.get_quiz_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Quiz deck not found.")
    return deck


@router.get("/workspace/{workspace_id}", response_model=List[QuizDeck])
def list_quiz_decks(workspace_id: str):
    return storage.list_quiz_decks(workspace_id)


@router.post("/submit", response_model=QuizResult)
def submit_quiz(submission: QuizSubmitRequest):
    deck = storage.get_quiz_deck(submission.deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Quiz deck not found.")

    result = quiz_engine.evaluate_quiz(deck, submission)
    storage.record_quiz_result(result, deck.workspace_id)
    return result


@router.get("/mastery/{workspace_id}")
def get_concept_mastery(workspace_id: str) -> Dict[str, Any]:
    return storage.get_mastery_stats(workspace_id)
