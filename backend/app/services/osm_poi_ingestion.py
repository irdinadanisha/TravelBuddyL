import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import parse, request

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "osm_poi_places.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

CITY_BBOXES = {
    "Paris": (48.8156, 2.2241, 48.9022, 2.4699),
    "Lyon": (45.7074, 4.7718, 45.8084, 4.8984),
    "Marseille": (43.2140, 5.2280, 43.3910, 5.5320),
    "Nice": (43.6500, 7.1800, 43.7600, 7.3300),
    "Bordeaux": (44.7900, -0.6500, 44.8900, -0.5000),
    "Strasbourg": (48.5200, 7.6800, 48.6300, 7.8200),
    "Lille": (50.6000, 2.9800, 50.6600, 3.1300),
}


def _overpass_query(bbox: tuple[float, float, float, float], limit: int) -> str:
    south, west, north, east = bbox
    box = f"{south},{west},{north},{east}"
    return f"""
[out:json][timeout:35];
(
  node["amenity"~"restaurant|cafe|bar|pub|food_court|marketplace"]["name"]({box});
  way["amenity"~"restaurant|cafe|bar|pub|food_court|marketplace"]["name"]({box});
  relation["amenity"~"restaurant|cafe|bar|pub|food_court|marketplace"]["name"]({box});
  node["tourism"~"museum|gallery"]["name"]({box});
  way["tourism"~"museum|gallery"]["name"]({box});
  relation["tourism"~"museum|gallery"]["name"]({box});
  node["leisure"~"park|garden"]["name"]({box});
  way["leisure"~"park|garden"]["name"]({box});
  relation["leisure"~"park|garden"]["name"]({box});
  node["shop"~"bakery|coffee|cheese|books|deli"]["name"]({box});
  way["shop"~"bakery|coffee|cheese|books|deli"]["name"]({box});
  relation["shop"~"bakery|coffee|cheese|books|deli"]["name"]({box});
);
out center tags {limit};
"""


def _post_overpass(query: str) -> dict:
    body = parse.urlencode({"data": query}).encode("utf-8")
    req = request.Request(
        OVERPASS_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "travelbuddy-france-local-recs/0.1",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _lat_lon(element: dict) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _category(tags: dict) -> str:
    if tags.get("amenity"):
        value = tags["amenity"].replace("_", " ")
        cuisine = tags.get("cuisine")
        return f"{cuisine} {value}" if cuisine and value == "restaurant" else value
    if tags.get("tourism"):
        return tags["tourism"].replace("_", " ")
    if tags.get("leisure"):
        return tags["leisure"].replace("_", " ")
    if tags.get("shop"):
        return f"{tags['shop'].replace('_', ' ')} shop"
    return "place"


def _poi_tags(city: str, tags: dict) -> list[str]:
    values = [city.lower(), "openstreetmap", "local candidate"]
    for key in ("amenity", "tourism", "leisure", "shop", "cuisine"):
        value = tags.get(key)
        if not value:
            continue
        values.extend(part.strip().lower() for part in str(value).replace(";", ",").split(","))
    if tags.get("amenity") in {"restaurant", "cafe", "food_court", "marketplace"}:
        values.append("food")
    if tags.get("amenity") == "restaurant":
        values.extend(["restaurant", "restaurants"])
    if tags.get("amenity") == "cafe" or tags.get("shop") == "coffee":
        values.extend(["cafes", "coffee"])
    if tags.get("tourism") == "museum":
        values.extend(["museum", "museums"])
    if tags.get("leisure") in {"park", "garden"}:
        values.extend(["park", "parks", "walks", "quiet"])
    return list(dict.fromkeys(value for value in values if value))


def _osm_url(element: dict, lat: float, lon: float) -> str:
    element_type = element.get("type")
    element_id = element.get("id")
    if element_type and element_id:
        return f"https://www.openstreetmap.org/{element_type}/{element_id}"
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"


def _element_to_place(element: dict, city: str) -> dict | None:
    tags = element.get("tags") or {}
    name = tags.get("name")
    coordinates = _lat_lon(element)
    if not name or coordinates is None:
        return None
    lat, lon = coordinates
    source_url = _osm_url(element, lat, lon)
    category = _category(tags)
    opening_hours = tags.get("opening_hours", "")
    address_parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:city", city),
    ]
    address = " ".join(part for part in address_parts if part).strip()
    tags_list = _poi_tags(city, tags)
    return {
        "name": name,
        "city": city,
        "neighborhood": tags.get("addr:suburb", ""),
        "address": address,
        "category": category,
        "reason": f"OpenStreetMap-listed {category} in {city}, added as a broader local candidate.",
        "local_tip": "Use this as a candidate and verify current details before going.",
        "tourist_trap_risk": "medium",
        "best_time": "Flexible",
        "estimated_duration_minutes": 75,
        "latitude": lat,
        "longitude": lon,
        "map_source": "OpenStreetMap",
        "map_url": source_url,
        "price_label": tags.get("fee", "") or tags.get("charge", "") or tags.get("price", ""),
        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={parse.quote(f'{name}, {address or city}, France')}",
        "business_status": "",
        "opening_hours": [opening_hours] if opening_hours else [],
        "open_now": None,
        "tags": tags_list,
        "source_type": "openstreetmap",
        "source_title": "OpenStreetMap POI dataset",
        "source_url": source_url,
        "confidence": 0.72,
    }


def refresh_osm_poi_places(
    cities: list[str] | None = None,
    city_limit: int = 150,
    delay_seconds: float = 2.0,
) -> dict:
    selected_cities = cities or list(CITY_BBOXES)
    all_places: list[dict] = []
    seen: set[str] = set()
    per_city_counts: dict[str, int] = {}

    for index, city in enumerate(selected_cities):
        bbox = CITY_BBOXES.get(city)
        if not bbox:
            continue
        data = _post_overpass(_overpass_query(bbox, city_limit))
        count = 0
        for element in data.get("elements", []):
            place = _element_to_place(element, city)
            if not place:
                continue
            key = f"{place['name'].lower()}::{place['city'].lower()}::{place['latitude']:.5f}::{place['longitude']:.5f}"
            if key in seen:
                continue
            seen.add(key)
            all_places.append(place)
            count += 1
            if count >= city_limit:
                break
        per_city_counts[city] = count
        if index < len(selected_cities) - 1:
            time.sleep(delay_seconds)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap Overpass API POI harvest",
        "place_count": len(all_places),
        "per_city_counts": per_city_counts,
        "places": all_places,
    }
    DATA_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return {
        "place_count": len(all_places),
        "per_city_counts": per_city_counts,
        "output_path": str(DATA_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh broad OpenStreetMap POI dataset.")
    parser.add_argument("--cities", default=",".join(CITY_BBOXES))
    parser.add_argument("--city-limit", type=int, default=150)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    args = parser.parse_args()
    result = refresh_osm_poi_places(
        cities=[city.strip() for city in args.cities.split(",") if city.strip()],
        city_limit=args.city_limit,
        delay_seconds=args.delay_seconds,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
