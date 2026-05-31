import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas.travel import ChatRequest, ChatResponse

SESSION_DIR = Path(__file__).resolve().parents[1] / "data" / "sessions"


def ensure_session_id(session_id: str = "") -> str:
    return session_id.strip() or str(uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_path(session_id: str) -> Path:
    safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in {"-", "_"})
    return SESSION_DIR / f"{safe_id}.json"


def _read_session(session_id: str) -> dict:
    path = _session_path(session_id)
    if not path.exists():
        now = _now_iso()
        return {
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "turns": [],
            "latest_itinerary": None,
        }

    return json.loads(path.read_text(encoding="utf-8"))


def save_chat_turn(request: ChatRequest, response: ChatResponse) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session = _read_session(response.session_id)
    session["updated_at"] = _now_iso()
    session["latest_itinerary"] = response.itinerary.model_dump()
    session["turns"].append(
        {
            "user_message": request.message,
            "assistant_message": response.assistant_message,
            "intent": response.extracted_intent.model_dump(),
            "evidence": [item.model_dump() for item in response.evidence],
        }
    )
    _session_path(response.session_id).write_text(
        json.dumps(session, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def list_sessions() -> list[dict]:
    if not SESSION_DIR.exists():
        return []

    sessions = []
    for path in SESSION_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        sessions.append(
            {
                "session_id": data.get("session_id", path.stem),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "turn_count": len(data.get("turns", [])),
                "latest_destination": (data.get("latest_itinerary") or {}).get(
                    "destination", ""
                ),
            }
        )

    return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)


def get_session(session_id: str) -> dict:
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(session_id)
    return json.loads(path.read_text(encoding="utf-8"))
