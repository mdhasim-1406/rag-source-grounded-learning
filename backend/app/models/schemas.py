from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


# ==============================================================================
# Workspaces / Notebooks
# ==============================================================================
class WorkspaceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = ""


class Workspace(BaseModel):
    id: str
    title: str
    description: str
    source_count: int = 0
    created_at: str
    updated_at: str


# ==============================================================================
# Sources & Chunks
# ==============================================================================
class SourceChunk(BaseModel):
    id: str
    source_id: str
    workspace_id: str = ""
    source_title: str
    chunk_index: int
    content: str
    page_number: Optional[int] = 1
    token_count: int = 0


class Source(BaseModel):
    id: str
    workspace_id: str
    title: str
    source_type: str  # pdf, txt, md, web, note
    file_path: Optional[str] = None
    token_count: int = 0
    chunk_count: int = 0
    created_at: str


class SourceCreateText(BaseModel):
    workspace_id: str
    title: str
    content: str
    source_type: str = "note"


# ==============================================================================
# Grounding & Citations
# ==============================================================================
class Citation(BaseModel):
    citation_index: int
    source_id: str
    source_title: str
    chunk_id: str
    page_number: Optional[int] = 1
    quote: str


# ==============================================================================
# Chat
# ==============================================================================
class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    citations: Optional[List[Citation]] = []
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    workspace_id: str
    query: str
    source_ids: Optional[List[str]] = None  # None = query all active sources in workspace
    conversation_history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    used_chunks: List[SourceChunk] = []
    session_id: Optional[str] = None


# ==============================================================================
# Intelligent Quiz Engine
# ==============================================================================
class QuizGenerateRequest(BaseModel):
    workspace_id: str
    source_ids: Optional[List[str]] = None
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium")  # easy, medium, hard, adaptive
    question_types: List[str] = Field(default=["mcq_single", "multi_select", "flashcard"])


class QuizQuestion(BaseModel):
    id: str
    type: str  # mcq_single, multi_select, flashcard
    question: str
    options: List[str] = []  # For MCQs and multi-select
    correct_answer: Union[int, List[int], str]  # Index, list of indices, or text
    explanation: str
    distractor_explanations: Dict[str, str] = {}
    citation: Optional[Citation] = None
    bloom_level: str = "understand"  # remember, understand, apply, analyze
    concept_tag: str = "General"


class QuizDeck(BaseModel):
    id: str
    workspace_id: str
    title: str
    difficulty: str
    total_questions: int
    questions: List[QuizQuestion]
    created_at: str


class AnswerSubmission(BaseModel):
    question_id: str
    answer: Union[int, List[int], str]


class QuizSubmitRequest(BaseModel):
    deck_id: str
    submissions: List[AnswerSubmission]


class QuestionFeedback(BaseModel):
    question_id: str
    is_correct: bool
    score: float  # 0.0 to 1.0
    user_answer: Any
    correct_answer: Any
    explanation: str
    citation: Optional[Citation] = None
    concept_tag: str
    evaluator_feedback: Optional[str] = None


class QuizResult(BaseModel):
    deck_id: str
    total_questions: int
    correct_count: int
    total_score: float
    percentage: float
    concept_breakdown: Dict[str, Dict[str, Any]]  # tag -> {total, correct, mastery}
    feedback: List[QuestionFeedback]


# ==============================================================================
# Study Guide & Synthesis
# ==============================================================================
class KeyConcept(BaseModel):
    concept: str
    definition: str
    source_reference: Optional[str] = None


class StudyGuide(BaseModel):
    workspace_id: str
    title: str
    executive_summary: str
    key_concepts: List[KeyConcept]
    id: Optional[str] = None
    source_ids: List[str] = []
    core_takeaways: List[str]
    practice_prompts: List[str]
    created_at: str
