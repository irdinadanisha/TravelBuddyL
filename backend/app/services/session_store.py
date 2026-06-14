"""Session persistence using DynamoDB with a local JSON fallback."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.schemas.travel import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

SESSION_DIR = Path(
    os.getenv("SESSION_DIR", "/tmp/travelbuddy-sessions")
)
DYNAMO_TABLE = os.getenv("SESSION_TABLE", "").strip()
DYNAMO_REGION = (
    os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "us-east-1"
)

_table = None
_table_checked = False


def _get_table():
    """Return the configured DynamoDB table, or None when unavailable."""
    global _table, _table_checked

    if _table_checked:
        return _table
    _table_checked = True

    if not DYNAMO_TABLE:
        logger.info("SESSION_TABLE is not configured; using file session storage.")
        return None

    try:
        import boto3

        dynamodb = boto3.resource("dynamodb", region_name=DYNAMO_REGION)
        table = dynamodb.Table(DYNAMO_TABLE)
        table.load()
        _table = table
        logger.info("DynamoDB session store ready (table=%s)", DYNAMO_TABLE)
    except Exception as exc:
        logger.warning("DynamoDB unavailable, using file fallback: %s", exc)
        _table = None

    return _table


def ensure_session_id(session_id: str = "") -> str:
    return session_id.strip() or str(uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_session(session_id: str) -> dict:
    now = _now_iso()
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "turns": [],
        "latest_itinerary": None,
    }


def _file_path(session_id: str) -> Path:
    safe_id = "".join(
        character
        for character in session_id
        if character.isalnum() or character in {"-", "_"}
    )
    return SESSION_DIR / f"{safe_id}.json"


def _file_read(session_id: str) -> dict:
    path = _file_path(session_id)
    if not path.exists():
        return _new_session(session_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _file_write(session: dict) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    _file_path(session["session_id"]).write_text(
        json.dumps(session, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def _dynamo_read(session_id: str) -> dict | None:
    table = _get_table()
    if table is None:
        return None

    try:
        response = table.get_item(Key={"session_id": session_id})
        item = response.get("Item")
        return json.loads(item["data"]) if item else None
    except Exception as exc:
        logger.warning("DynamoDB read failed: %s", exc)
        return None


def _dynamo_write(session: dict) -> bool:
    table = _get_table()
    if table is None:
        return False

    try:
        table.put_item(
            Item={
                "session_id": session["session_id"],
                "updated_at": session.get("updated_at", _now_iso()),
                "data": json.dumps(session, ensure_ascii=True),
            }
        )
        return True
    except Exception as exc:
        logger.warning("DynamoDB write failed: %s", exc)
        return False


def _session_summary(session: dict) -> dict:
    return {
        "session_id": session.get("session_id", ""),
        "created_at": session.get("created_at", ""),
        "updated_at": session.get("updated_at", ""),
        "turn_count": len(session.get("turns", [])),
        "latest_destination": (session.get("latest_itinerary") or {}).get(
            "destination", ""
        ),
    }


def _dynamo_list() -> list[dict] | None:
    table = _get_table()
    if table is None:
        return None

    try:
        items = []
        scan_kwargs = {
            "ProjectionExpression": "session_id, updated_at, #data",
            "ExpressionAttributeNames": {"#data": "data"},
        }

        while True:
            response = table.scan(**scan_kwargs)
            for item in response.get("Items", []):
                session = json.loads(item.get("data", "{}"))
                session.setdefault("session_id", item.get("session_id", ""))
                session["updated_at"] = item.get(
                    "updated_at", session.get("updated_at", "")
                )
                items.append(_session_summary(session))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

        return sorted(items, key=lambda item: item["updated_at"], reverse=True)
    except Exception as exc:
        logger.warning("DynamoDB scan failed: %s", exc)
        return None


def _read_session(session_id: str) -> dict:
    return _dynamo_read(session_id) or _file_read(session_id)


def save_chat_turn(request: ChatRequest, response: ChatResponse) -> None:
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

    if not _dynamo_write(session):
        _file_write(session)


def list_sessions() -> list[dict]:
    dynamo_sessions = _dynamo_list()
    if dynamo_sessions is not None:
        return dynamo_sessions

    if not SESSION_DIR.exists():
        return []

    sessions = [
        _session_summary(json.loads(path.read_text(encoding="utf-8")))
        for path in SESSION_DIR.glob("*.json")
    ]
    return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)


def get_session(session_id: str) -> dict:
    dynamo_session = _dynamo_read(session_id)
    if dynamo_session is not None:
        return dynamo_session

    path = _file_path(session_id)
    if not path.exists():
        raise FileNotFoundError(session_id)
    return json.loads(path.read_text(encoding="utf-8"))
