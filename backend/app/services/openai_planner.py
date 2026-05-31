import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from app.schemas.travel import ChatRequest, ChatResponse, Place, TravelIntent

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")


class OpenAITravelPlanner:
    def __init__(self) -> None:
        self.client = OpenAI() if os.getenv("OPENAI_API_KEY") else None
        self.model = DEFAULT_MODEL

    def plan(
        self,
        request: ChatRequest,
        intent: TravelIntent,
        candidates: list[Place],
    ) -> ChatResponse:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "You are TravelBuddy France, a practical travel-planning assistant. "
                "Build France-only itineraries that favor local-feeling places, realistic pacing, "
                "and clear avoidance of tourist traps. Use only the provided candidate places for "
                "itinerary stops so coordinates remain accurate. If the user does not clearly state "
                "what they want to do, default to a balanced 1-day mixed itinerary with walks, "
                "culture, parks/markets/cafes, and meal stops instead of a restaurant-only answer. "
                "Assume every itinerary starts at 09:00. Include lunch around 12:30 and dinner "
                "around 19:00 between the other places whenever candidate food stops are available. "
                "When the user asks for a 2-day, "
                "3-day, or multi-day itinerary, split the plan into itinerary.days with the matching "
                "number of day sections and assign stops to each day, using the same 09:00 start, "
                "lunch, afternoon, and dinner rhythm for each day. Do not repeat the same stop on "
                "multiple days. Give each day a clear theme when candidates allow it, such as "
                "sightseeing day, shopping day, museum hopping day, neighborhood wandering day, "
                "food market day, or cafe day. Also keep itinerary.stops as "
                "the full ordered flattened route. If the user asks for a non-France "
                "destination, politely redirect to France and choose the closest useful French plan. "
                "If the user asks for Asian food, Japanese, ramen, Vietnamese, pho, Chinese, Thai, "
                "Korean, or sushi, recommend matching restaurant candidates only; do not replace "
                "restaurant requests with markets, museums, walks, or cafes unless no restaurant "
                "candidate exists. "
                "If the user asks for cafes or coffee, recommend cafes or coffee shops only, prefer "
                "candidate places with source_type reddit or another explicit source_url, and preserve "
                "each stop's source_type, source_title, source_url, google_rating, "
                "google_user_rating_count, google_price_level, google_price_label, map_source, "
                "map_url, price_label, opening_hours, open_now, and open_status_label fields for "
                "display. Do not claim a place is open unless the provided map fields support it. "
                "If the user asks for shopping, souvenirs, affordable shopping, vintage, thrift, "
                "luxury brands, boutiques, department stores, skincare, or gifts, prioritize matching "
                "shopping candidates and explain the shopping style for each stop. "
                "If the user is a first-time visitor or asks for must-go/iconic landmarks, build the "
                "day around must-go attractions but still include lunch around 12:30 and dinner around "
                "19:00 using provided restaurant, market, or food candidates. Do not make first-timer "
                "plans attraction-only. "
                "For official_open_data stops, treat them as events or activities and preserve "
                "their official schedule/source fields. "
                "Return only valid JSON matching the schema."
            ),
            input=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": request.message,
                            "history": request.history[-8:],
                            "initial_intent": intent.model_dump(),
                            "candidate_places": [
                                place.model_dump() for place in candidates
                            ],
                        }
                    ),
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "travelbuddy_chat_response",
                    "schema": ChatResponse.model_json_schema(),
                    "strict": False,
                }
            },
        )

        return ChatResponse.model_validate_json(response.output_text)
