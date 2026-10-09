import tempfile
import os
from app.services.storage import Storage
from app.services.quiz_engine import quiz_engine
from app.models.schemas import (
    QuizDeck, QuizQuestion, Citation, QuizSubmitRequest, AnswerSubmission
)


def test_storage_operations():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        storage = Storage(db_path=db_path)
        ws = storage.create_workspace("Test Notebook", "Description")
        assert ws.title == "Test Notebook"

        source = storage.add_source(ws.id, "Lecture 1.pdf", "pdf")
        assert source.workspace_id == ws.id

        sources = storage.list_sources(ws.id)
        assert len(sources) == 1
        assert sources[0].title == "Lecture 1.pdf"
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_quiz_evaluation_logic():
    q1 = QuizQuestion(
        id="q1",
        type="mcq_single",
        question="What enables parallelization in Transformers?",
        options=["A) Recurrent cells", "B) Self-attention mechanism", "C) Max pooling", "D) LSTMs"],
        correct_answer=1,
        explanation="Self-attention computes connections simultaneously without sequential recurrent state.",
        distractor_explanations={"0": "Recurrent cells enforce sequentiality.", "2": "Pooling is CNN.", "3": "LSTMs are sequential."},
        citation=Citation(
            citation_index=1,
            source_id="s1",
            source_title="Transformer Paper",
            chunk_id="c1",
            page_number=2,
            quote="Self-attention allows for parallel processing of tokens."
        ),
        bloom_level="understand",
        concept_tag="Attention Mechanism"
    )

    deck = QuizDeck(
        id="d1",
        workspace_id="w1",
        title="Diagnostic Quiz",
        difficulty="medium",
        total_questions=1,
        questions=[q1],
        created_at="2026-10-08"
    )

    # Correct submission
    sub = QuizSubmitRequest(
        deck_id="d1",
        submissions=[AnswerSubmission(question_id="q1", answer=1)]
    )
    result = quiz_engine.evaluate_quiz(deck, sub)
    assert result.total_questions == 1
    assert result.correct_count == 1
    assert result.percentage == 100.0
    assert result.concept_breakdown["Attention Mechanism"]["mastery"] == 100.0

    # Wrong submission
    sub_wrong = QuizSubmitRequest(
        deck_id="d1",
        submissions=[AnswerSubmission(question_id="q1", answer=0)]
    )
    result_wrong = quiz_engine.evaluate_quiz(deck, sub_wrong)
    assert result_wrong.correct_count == 0
    assert result_wrong.percentage == 0.0
