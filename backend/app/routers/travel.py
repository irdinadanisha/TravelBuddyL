from fastapi import APIRouter, HTTPException

from app.schemas.travel import ChatRequest, ChatResponse
from app.services.orchestrator import TravelOrchestrator

router = APIRouter(tags=["travel"])
orchestrator = TravelOrchestrator()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return orchestrator.handle_chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
