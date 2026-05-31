from app.schemas.travel import ChatRequest, ChatResponse
from app.services.extractor import extract_travel_intent
from app.services.evidence import build_evidence
from app.services.openai_planner import OpenAITravelPlanner
from app.services.planner import build_itinerary, split_stops_by_day
from app.services.retriever import retrieve_places
from app.services.session_store import ensure_session_id, save_chat_turn

CONTEXT_DESTINATIONS = {
    "paris",
    "lyon",
    "marseille",
    "nice",
    "bordeaux",
    "strasbourg",
    "lille",
}


def _is_mixed_default(interests: list[str]) -> bool:
    return "mixed" in {interest.lower() for interest in interests}


def _needs_day_normalization(interests: list[str], duration_days: int) -> bool:
    normalized = {interest.lower() for interest in interests}
    return (
        duration_days > 1
        or "mixed" in normalized
        or bool({"must_go", "first_time", "iconic", "landmarks"}.intersection(normalized))
    )


def _current_message_has_destination(message: str) -> bool:
    lowered = message.lower()
    return any(destination in lowered for destination in CONTEXT_DESTINATIONS)


def _message_with_context(request: ChatRequest) -> str:
    if not request.history or _current_message_has_destination(request.message):
        return request.message

    recent_history = request.history[-6:]
    context_lines = []
    for item in recent_history:
        role = item.get("role", "user")
        content = item.get("content", "").strip()
        if content:
            context_lines.append(f"{role}: {content}")

    if not context_lines:
        return request.message

    return (
        "Previous same-chat context:\n"
        + "\n".join(context_lines)
        + f"\nCurrent user request: {request.message}"
    )


class TravelOrchestrator:
    def __init__(self) -> None:
        self.ai_planner = OpenAITravelPlanner()

    def handle_chat(self, request: ChatRequest) -> ChatResponse:
        if not request.message.strip():
            raise ValueError("Message cannot be empty.")

        session_id = ensure_session_id(request.session_id)
        intent = extract_travel_intent(_message_with_context(request))
        places = retrieve_places(intent)

        try:
            response = self.ai_planner.plan(request, intent, places)
            response.session_id = session_id
            if _needs_day_normalization(
                response.extracted_intent.interests,
                response.extracted_intent.duration_days,
            ):
                response.itinerary.days = split_stops_by_day(
                    response.itinerary.stops,
                    response.extracted_intent.duration_days,
                    force_full_day=_is_mixed_default(response.extracted_intent.interests),
                )
                response.itinerary.stops = [
                    stop for day in response.itinerary.days for stop in day.stops
                ]
            elif not response.itinerary.days:
                response.itinerary.days = split_stops_by_day(
                    response.itinerary.stops, response.extracted_intent.duration_days
                )
            response.evidence = build_evidence(response.itinerary.stops)
            save_chat_turn(request, response)
            return response
        except Exception:
            itinerary = build_itinerary(intent, places)
            assistant_message = (
                f"I built a {intent.destination}-focused plan from the local France dataset. "
                "The AI planner was unavailable, so this response uses the deterministic fallback."
            )

            response = ChatResponse(
                assistant_message=assistant_message,
                extracted_intent=intent,
                itinerary=itinerary,
                session_id=session_id,
                evidence=build_evidence(itinerary.stops),
            )
            save_chat_turn(request, response)
            return response
