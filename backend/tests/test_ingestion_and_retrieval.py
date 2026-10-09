import pytest
from app.services.ingestion import ingestion_service
from app.services.retrieval import retrieval_service
from app.models.schemas import SourceChunk


def test_text_parsing_and_chunking():
    sample_text = """
    The Transformer architecture relies entirely on an attention mechanism to draw global dependencies between input and output.
    Unlike recurrence, attention allows for significantly more parallelization during training.
    
    Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions.
    With a single attention head, averaging inhibits this.
    """
    pages = ingestion_service.parse_text_or_markdown(sample_text)
    assert len(pages) == 1
    assert pages[0][0] == 1  # Page 1

    chunks = ingestion_service.chunk_document(
        source_id="test-source-1",
        workspace_id="test-ws-1",
        source_title="Attention Paper",
        pages=pages
    )
    assert len(chunks) >= 1
    assert chunks[0].source_id == "test-source-1"
    assert "Multi-Head Attention" in chunks[0].content


def test_hybrid_retrieval_and_rrf():
    chunk1 = SourceChunk(
        id="c1",
        source_id="s1",
        source_title="Deep Learning",
        chunk_index=0,
        content="Convolutional Neural Networks are designed to process grid-structured data such as images through convolutional filters.",
        page_number=1,
        token_count=18
    )
    chunk2 = SourceChunk(
        id="c2",
        source_id="s1",
        source_title="Deep Learning",
        chunk_index=1,
        content="Recurrent Neural Networks use recurrent loops to process sequential data like time series and natural language tokens.",
        page_number=2,
        token_count=18
    )
    chunk3 = SourceChunk(
        id="c3",
        source_id="s2",
        source_title="Transformers Guide",
        chunk_index=0,
        content="Transformers replace recurrence with self-attention mechanisms, computing dot-product attention across all tokens in parallel.",
        page_number=1,
        token_count=17
    )

    chunks = [chunk1, chunk2, chunk3]

    # Query targeting Transformers
    results = retrieval_service.search_hybrid("self-attention mechanism transformers", chunks, top_k=2)
    assert len(results) == 2
    top_chunk, score = results[0]
    assert top_chunk.id == "c3"
    assert "Transformers" in top_chunk.content

    # Citation building
    citations = retrieval_service.build_citations(results)
    assert len(citations) == 2
    assert citations[0].source_title == "Transformers Guide"
    assert citations[0].page_number == 1
    assert len(citations[0].quote) > 10
