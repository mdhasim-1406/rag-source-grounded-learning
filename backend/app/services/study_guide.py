from datetime import datetime
from typing import List
from ..models.schemas import SourceChunk, StudyGuide, KeyConcept
from .llm_client import llm_client


class StudyGuideService:
    async def generate_study_guide(
        self,
        workspace_id: str,
        workspace_title: str,
        chunks: List[SourceChunk]
    ) -> StudyGuide:
        if not chunks:
            raise ValueError("No source documents available to generate a study guide.")

        # Take representative sample of chunks
        sample_size = min(len(chunks), 12)
        step = len(chunks) / sample_size
        sampled = [chunks[int(i * step)] for i in range(sample_size)]

        context_blocks = []
        for idx, c in enumerate(sampled):
            context_blocks.append(f"[{c.source_title} - Page {c.page_number}]:\n{c.content}")
        context_str = "\n\n".join(context_blocks)

        prompt = f"""You are an elite academic tutor creating a definitive Study Guide for '{workspace_title}'.
Synthesize the provided source excerpts into a structured study guide.

OUTPUT FORMAT:
Return a JSON object matching this structure:
{{
  "title": "{workspace_title} - Comprehensive Study Guide",
  "executive_summary": "Crisp 2-3 paragraph academic synthesis of the primary arguments, methodologies, or findings.",
  "key_concepts": [
    {{
      "concept": "Concept Name",
      "definition": "Precise, source-grounded definition.",
      "source_reference": "Source Name (Page X)"
    }}
  ],
  "core_takeaways": [
    "Takeaway 1...",
    "Takeaway 2...",
    "Takeaway 3..."
  ],
  "practice_prompts": [
    "Essay or discussion prompt 1...",
    "Active recall reflection prompt 2..."
  ]
}}

SOURCE MATERIAL:
{context_str}
"""

        messages = [
            {"role": "system", "content": "You are an expert academic curriculum designer. Always output valid JSON."},
            {"role": "user", "content": prompt}
        ]

        data = await llm_client.generate_json(messages, temperature=0.2)
        if not isinstance(data, dict):
            data = {}

        now = datetime.utcnow().isoformat()
        key_concepts = [
            KeyConcept(
                concept=kc.get("concept", "Key Term"),
                definition=kc.get("definition", "Definition extracted from sources."),
                source_reference=kc.get("source_reference", "")
            )
            for kc in data.get("key_concepts", [])
        ]

        return StudyGuide(
            workspace_id=workspace_id,
            title=data.get("title", f"{workspace_title} - Study Guide"),
            executive_summary=data.get("executive_summary", "No summary generated."),
            key_concepts=key_concepts,
            core_takeaways=data.get("core_takeaways", []),
            practice_prompts=data.get("practice_prompts", []),
            created_at=now
        )


study_guide_service = StudyGuideService()
