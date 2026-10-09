import uuid
from typing import List, Dict, Any, Optional
from ..models.schemas import (
    SourceChunk, QuizQuestion, QuizDeck, Citation, QuizSubmitRequest,
    QuizResult, QuestionFeedback
)
from .llm_client import llm_client
from .retrieval import retrieval_service


class QuizEngineService:
    async def generate_quiz_deck(
        self,
        workspace_id: str,
        workspace_title: str,
        chunks: List[SourceChunk],
        num_questions: int = 5,
        difficulty: str = "medium",
        question_types: Optional[List[str]] = None
    ) -> QuizDeck:
        if not chunks:
            raise ValueError("No source documents available to generate quiz questions.")

        q_types = question_types or ["mcq_single", "multi_select", "flashcard"]
        
        # Select representative chunks across the document corpus
        sampled_chunks = self._sample_chunks(chunks, max_chunks=min(len(chunks), max(num_questions * 2, 8)))
        
        # Build context prompt
        context_blocks = []
        for idx, c in enumerate(sampled_chunks):
            context_blocks.append(
                f"[Chunk {idx+1} | Source: {c.source_title} | Page {c.page_number} | ID: {c.id}]\n{c.content}"
            )
        context_str = "\n\n".join(context_blocks)

        prompt = f"""You are a master academic educator and assessment design specialist.
Your task is to generate {num_questions} pedagogically sound, high-fidelity quiz questions grounded STRICTLY in the provided text chunks.

DIFFICULTY LEVEL: {difficulty}
ALLOWED QUESTION TYPES: {', '.join(q_types)}

RULES:
1. STRICT SOURCE GROUNDING: Every question, answer, and distractor must be derived directly from the provided source chunks.
2. VERBATIM CITATION: Every question MUST cite an exact sentence from the source chunk as `verbatim_quote`, specifying `chunk_id`, `source_title`, and `page_number`.
3. HIGH-QUALITY DISTRACTORS: For MCQs, incorrect options (distractors) must reflect common student misconceptions or plausible inversions discussed in the text, NOT obvious nonsense.
4. DETAILED EXPLANATIONS: Provide an explanation explaining WHY the right answer is correct, plus a dictionary of distractor explanations explaining why each wrong option is incorrect.
5. BLOOM TAXONOMY: Label each question's cognitive depth ('remember', 'understand', 'apply', or 'analyze').
6. CONCEPT TAGS: Assign a concise 2-4 word concept category (e.g. 'Backpropagation Mechanics', 'Gradient Descent').

OUTPUT FORMAT:
Return a JSON array of question objects matching this exact structure:
[
  {{
    "type": "mcq_single",
    "question": "What is the primary role of the attention mechanism in Transformers?",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_answer": 0,
    "explanation": "Option A is correct because...",
    "distractor_explanations": {{
      "1": "Option B is incorrect because...",
      "2": "Option C confuses X with Y...",
      "3": "Option D..."
    }},
    "verbatim_quote": "Exact sentence extracted word-for-word from the chunk.",
    "source_title": "Title of Source",
    "chunk_id": "chunk_uuid_from_header",
    "page_number": 1,
    "bloom_level": "understand",
    "concept_tag": "Attention Mechanism"
  }}
]

For 'flashcard' type:
- "options" should be empty array `[]`.
- "question" is the Front prompt/question.
- "correct_answer" is the Back key takeaway/definition.
- "explanation" is a memory hook or elaboration.

SOURCE CONTEXT:
{context_str}
"""

        messages = [
            {"role": "system", "content": "You are a source-grounded academic assessment generator. Always output valid JSON."},
            {"role": "user", "content": prompt}
        ]

        raw_questions = await llm_client.generate_json(messages, temperature=0.2)
        if isinstance(raw_questions, dict) and "questions" in raw_questions:
            raw_questions = raw_questions["questions"]

        if not isinstance(raw_questions, list):
            raise RuntimeError("LLM did not return a valid list of questions.")

        # Stage 2: Verification and Normalization
        verified_questions: List[QuizQuestion] = []
        for q in raw_questions:
            norm_q = self._normalize_and_verify_question(q, sampled_chunks)
            if norm_q:
                verified_questions.append(norm_q)

        if not verified_questions:
            raise RuntimeError("Failed to generate any valid source-grounded quiz questions. All generated questions failed citation grounding or validation.")

        deck_id = str(uuid.uuid4())
        return QuizDeck(
            id=deck_id,
            workspace_id=workspace_id,
            title=f"{workspace_title} - {difficulty.capitalize()} Diagnostic Deck",
            difficulty=difficulty,
            total_questions=len(verified_questions),
            questions=verified_questions,
            created_at=uuid.uuid1().hex[:8]
        )

    def evaluate_quiz(self, deck: QuizDeck, submissions: QuizSubmitRequest) -> QuizResult:
        """
        Evaluates student responses against ground truth, computes scores,
        concept breakdowns, and feedback cards with citations.
        """
        user_answers = {s.question_id: s.answer for s in submissions.submissions}
        feedback_list: List[QuestionFeedback] = []
        total_score = 0.0
        correct_count = 0
        concept_breakdown: Dict[str, Dict[str, Any]] = {}

        for q in deck.questions:
            user_ans = user_answers.get(q.id)
            is_correct = False
            score = 0.0
            eval_feedback = ""

            if q.type == "mcq_single":
                try:
                    if int(user_ans) == int(q.correct_answer):  # type: ignore
                        is_correct = True
                        score = 1.0
                except (ValueError, TypeError):
                    is_correct = False

            elif q.type == "multi_select":
                try:
                    correct_set = set(q.correct_answer) if isinstance(q.correct_answer, list) else {int(q.correct_answer)}
                    if isinstance(user_ans, list):
                        user_set = {int(x) for x in user_ans}
                    elif user_ans is not None:
                        user_set = {int(user_ans)}
                    else:
                        user_set = set()
                    if user_set == correct_set:
                        is_correct = True
                        score = 1.0
                    else:
                        # Partial credit for partially correct selections without false positives
                        intersection = user_set.intersection(correct_set)
                        if intersection and not user_set.difference(correct_set):
                            score = len(intersection) / len(correct_set)
                except (ValueError, TypeError):
                    is_correct = False

            elif q.type == "flashcard":
                # Flashcard self-grading or match
                if user_ans in (1, "1", True, "correct", "mastered"):
                    is_correct = True
                    score = 1.0
                else:
                    is_correct = False
                    score = 0.0

            if is_correct:
                correct_count += 1
            total_score += score

            # Update concept breakdown
            tag = q.concept_tag or "General"
            if tag not in concept_breakdown:
                concept_breakdown[tag] = {"total": 0, "correct": 0, "mastery": 0.0}
            concept_breakdown[tag]["total"] += 1
            if is_correct:
                concept_breakdown[tag]["correct"] += 1

            feedback_list.append(QuestionFeedback(
                question_id=q.id,
                is_correct=is_correct,
                score=score,
                user_answer=user_ans,
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                citation=q.citation,
                concept_tag=tag,
                evaluator_feedback=eval_feedback
            ))

        # Compute percentage and mastery levels
        total_questions = len(deck.questions)
        percentage = round((total_score / max(total_questions, 1)) * 100, 1)

        for tag, data in concept_breakdown.items():
            data["mastery"] = round((data["correct"] / max(data["total"], 1)) * 100, 1)

        return QuizResult(
            deck_id=deck.id,
            total_questions=total_questions,
            correct_count=correct_count,
            total_score=round(total_score, 2),
            percentage=percentage,
            concept_breakdown=concept_breakdown,
            feedback=feedback_list
        )

    def _sample_chunks(self, chunks: List[SourceChunk], max_chunks: int) -> List[SourceChunk]:
        """Samples chunks evenly across sources and document progression."""
        if len(chunks) <= max_chunks:
            return chunks
        step = len(chunks) / max_chunks
        return [chunks[int(i * step)] for i in range(max_chunks)]

    def _normalize_and_verify_question(self, q: Dict[str, Any], candidate_chunks: List[SourceChunk]) -> Optional[QuizQuestion]:
        q_type = str(q.get("type", "mcq_single")).strip()
        ALLOWED_TYPES = {"mcq_single", "multi_select", "flashcard"}
        if q_type not in ALLOWED_TYPES:
            return None

        question_text = str(q.get("question", "")).strip()
        if not question_text:
            return None

        chunk_id = str(q.get("chunk_id", "")).strip()
        matching_chunk = next((c for c in candidate_chunks if c.id == chunk_id), None)
        if matching_chunk is None:
            return None

        quote = str(q.get("verbatim_quote", "")).strip()
        if not quote or quote not in matching_chunk.content:
            return None

        if q_type == "mcq_single":
            options = [str(opt).strip() for opt in q.get("options", []) if str(opt).strip()]
            if len(options) < 2:
                return None
            try:
                ans_idx = int(q.get("correct_answer"))
            except (ValueError, TypeError):
                return None
            if not (0 <= ans_idx < len(options)):
                return None
            correct_answer = ans_idx

        elif q_type == "multi_select":
            options = [str(opt).strip() for opt in q.get("options", []) if str(opt).strip()]
            if len(options) < 2:
                return None
            raw_ans = q.get("correct_answer")
            if isinstance(raw_ans, list):
                ans_indices = raw_ans
            elif isinstance(raw_ans, (int, str)):
                ans_indices = [raw_ans]
            else:
                return None

            try:
                parsed_indices = [int(idx) for idx in ans_indices]
            except (ValueError, TypeError):
                return None

            if not parsed_indices:
                return None

            if not all(0 <= idx < len(options) for idx in parsed_indices):
                return None
            correct_answer = sorted(list(set(parsed_indices)))

        elif q_type == "flashcard":
            options = []
            ans_str = str(q.get("correct_answer", "")).strip()
            if not ans_str:
                return None
            correct_answer = ans_str
        else:
            return None

        explanation = str(q.get("explanation", "")).strip() or f"Verified directly from {matching_chunk.source_title}."
        raw_distractors = q.get("distractor_explanations")
        distractor_exps = raw_distractors if isinstance(raw_distractors, dict) else {}
        bloom = str(q.get("bloom_level", "understand")).strip()
        concept = str(q.get("concept_tag", "Core Concept")).strip()

        citation = Citation(
            citation_index=1,
            source_id=matching_chunk.source_id,
            source_title=matching_chunk.source_title,
            chunk_id=matching_chunk.id,
            page_number=matching_chunk.page_number or 1,
            quote=quote
        )

        q_id = str(uuid.uuid4())
        return QuizQuestion(
            id=q_id,
            type=q_type,
            question=question_text,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            distractor_explanations=distractor_exps,
            citation=citation,
            bloom_level=bloom,
            concept_tag=concept
        )


quiz_engine = QuizEngineService()
