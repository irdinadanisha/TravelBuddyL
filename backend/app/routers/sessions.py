from fastapi import APIRouter, HTTPException

from app.services.session_store import get_session, list_sessions

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
def sessions() -> list[dict]:
    return list_sessions()


@router.get("/sessions/{session_id}")
def session_detail(session_id: str) -> dict:
    try:
        return get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc
