from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..models.schemas import StudyGuide
from ..services.storage import storage
from ..services.study_guide import study_guide_service

router = APIRouter(prefix="/api/v1/study", tags=["Study Tools"])


class StudyGuideRequest(BaseModel):
    workspace_id: str
    source_ids: Optional[List[str]] = None


@router.post("/guide")
async def generate_study_guide(request: StudyGuideRequest):
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
        guide = await study_guide_service.generate_study_guide(
            workspace_id=request.workspace_id,
            workspace_title=ws.title,
            chunks=chunks
        )
        return storage.create_saved_guide(request.workspace_id, guide.model_dump(),
            [c.source_id for c in chunks], [c.model_dump() for c in chunks])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Study guide generation failed: {str(e)}")


@router.get("/guides")
async def list_guides(workspace_id: str):
    if not storage.get_workspace(workspace_id): raise HTTPException(404, "Workspace not found")
    return storage.list_saved_guides(workspace_id)


@router.get("/guides/{guide_id}")
async def get_guide(guide_id: str, workspace_id: str):
    guide = storage.get_saved_guide(workspace_id, guide_id)
    if not guide: raise HTTPException(404, "Guide not found")
    return guide


@router.delete("/guides/{guide_id}", status_code=204)
async def delete_guide(guide_id: str, workspace_id: str):
    if not storage.delete_saved_guide(workspace_id, guide_id): raise HTTPException(404, "Guide not found")

