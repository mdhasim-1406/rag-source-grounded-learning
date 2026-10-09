import math
import re
from typing import List, Dict, Tuple, Optional
import numpy as np
from ..models.schemas import SourceChunk, Citation


class HybridRetrievalService:
    """
    Dual-Path Lexical Search Engine (BM25 Okapi + Lexical Phrase/N-gram Coverage + Reciprocal Rank Fusion).
    Note: Retrieval is purely lexical (BM25 and phrase-overlap matching) and does not use
    dense neural vector embeddings. Deterministic, zero external daemon requirements, and robust under all conditions.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def tokenize(self, text: str) -> List[str]:
        """Low-latency tokenization and normalization."""
        return [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', text)]

    def search_hybrid(
        self,
        query: str,
        chunks: List[SourceChunk],
        top_k: int = 5
    ) -> List[Tuple[SourceChunk, float]]:
        if not chunks:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return [(c, 1.0) for c in chunks[:top_k]]

        # 1. BM25 Lexical Ranking
        bm25_scores = self._score_bm25(query_tokens, chunks)
        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)
        bm25_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(bm25_ranked)}

        # 2. Lexical Phrase Coverage & N-gram Proximity Scoring
        phrase_scores = self._score_phrase_coverage(query_tokens, chunks)
        phrase_ranked = sorted(enumerate(phrase_scores), key=lambda x: x[1], reverse=True)
        phrase_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(phrase_ranked)}

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF formula: RRF_score(d) = sum(1 / (k + rank_i(d))) with constant k=60
        k_const = 60
        rrf_scores = []
        for idx in range(len(chunks)):
            r_bm25 = bm25_ranks.get(idx, 1000)
            r_phrase = phrase_ranks.get(idx, 1000)
            rrf_score = (1.0 / (k_const + r_bm25)) + (1.0 / (k_const + r_phrase))
            rrf_scores.append((chunks[idx], rrf_score))

        # Sort by final RRF score descending
        rrf_scores.sort(key=lambda x: x[1], reverse=True)
        return rrf_scores[:top_k]

    def _score_bm25(self, query_tokens: List[str], chunks: List[SourceChunk]) -> List[float]:
        N = len(chunks)
        doc_tokens = [self.tokenize(c.content) for c in chunks]
        doc_lens = [len(dt) for dt in doc_tokens]
        avg_doc_len = sum(doc_lens) / max(N, 1)

        # Document frequency for query terms
        df: Dict[str, int] = {}
        for q in set(query_tokens):
            df[q] = sum(1 for dt in doc_tokens if q in dt)

        scores = []
        for i, dt in enumerate(doc_tokens):
            score = 0.0
            dl = doc_lens[i]
            # Term counts in document
            tc: Dict[str, int] = {}
            for t in dt:
                tc[t] = tc.get(t, 0) + 1

            for q in query_tokens:
                if q in tc:
                    f = tc[q]
                    # IDF with Robertson-Spärck Jones formula
                    idf = math.log((N - df[q] + 0.5) / (df[q] + 0.5) + 1.0)
                    numerator = f * (self.k1 + 1)
                    denominator = f + self.k1 * (1 - self.b + self.b * (dl / max(avg_doc_len, 1e-5)))
                    score += idf * (numerator / max(denominator, 1e-5))
            scores.append(score)
        return scores

    def _score_phrase_coverage(self, query_tokens: List[str], chunks: List[SourceChunk]) -> List[float]:
        """
        N-gram and subphrase lexical matching score.
        Complements BM25 by scoring exact phrase proximity and term coverage.
        """
        scores = []
        query_set = set(query_tokens)
        query_text = " ".join(query_tokens)

        for c in chunks:
            content_lower = c.content.lower()
            overlap = sum(1 for token in query_set if token in content_lower)
            coverage = overlap / max(len(query_set), 1)

            # Bonus for exact contiguous subphrases
            phrase_bonus = 0.5 if query_text in content_lower else 0.0

            # Title match bonus
            title_bonus = 0.3 if any(token in c.source_title.lower() for token in query_set) else 0.0

            scores.append(coverage + phrase_bonus + title_bonus)
        return scores

    # Backwards compatibility alias
    _score_semantic = _score_phrase_coverage

    def build_citations(self, scored_chunks: List[Tuple[SourceChunk, float]]) -> List[Citation]:
        citations = []
        for idx, (chunk, score) in enumerate(scored_chunks):
            # Extract a punchy verbatim quote (first 200 chars or first two sentences)
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', chunk.content) if s.strip()]
            quote = sentences[0] if sentences else chunk.content[:160]
            if len(quote) > 220:
                quote = quote[:217] + "..."

            citations.append(Citation(
                citation_index=idx + 1,
                source_id=chunk.source_id,
                source_title=chunk.source_title,
                chunk_id=chunk.id,
                page_number=chunk.page_number or 1,
                quote=quote
            ))
        return citations


retrieval_service = HybridRetrievalService()
