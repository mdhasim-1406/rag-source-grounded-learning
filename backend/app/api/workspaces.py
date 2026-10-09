from fastapi import APIRouter, HTTPException
from typing import List
from ..models.schemas import Workspace, WorkspaceCreate
from ..services.storage import storage

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces"])


@router.post("", response_model=Workspace)
def create_workspace(payload: WorkspaceCreate):
    return storage.create_workspace(title=payload.title, description=payload.description or "")


@router.get("", response_model=List[Workspace])
def list_workspaces():
    return storage.list_workspaces()


@router.get("/{workspace_id}", response_model=Workspace)
def get_workspace(workspace_id: str):
    ws = storage.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return ws


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str):
    success = storage.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return {"message": "Workspace deleted successfully."}
