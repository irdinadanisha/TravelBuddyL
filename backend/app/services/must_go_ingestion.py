import argparse
import json
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "france_must_go_places.json"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

TYPE_GROUPS = [
    {
        "name": "landmarks",
        "types": [
            "wd:Q570116",  # tourist attraction
            "wd:Q4989906",  # monument
            "wd:Q811979",  # architectural structure
            "wd:Q12518",  # tower
            "wd:Q12280",  # bridge
            "wd:Q174782",  # square
        ],
    },
    {
        "name": "museums",
        "types": [
            "wd:Q33506",  # museum
            "wd:Q207694",  # art museum
            "wd:Q17431399",  # national museum
            "wd:Q856584",  # library museum / heritage-ish
        ],
    },
    {
        "name": "castles_palaces",
        "types": [
            "wd:Q23413",  # castle
            "wd:Q751876",  # chateau
            "wd:Q16560",  # palace
            "wd:Q1370598",  # fortified castle
        ],
    },
    {
        "name": "religious_heritage",
        "types": [
            "wd:Q2977",  # cathedral
            "wd:Q16970",  # church building
            "wd:Q44613",  # monastery
            "wd:Q2912397",  # abbey
            "wd:Q32815",  # mosque
            "wd:Q34627",  # synagogue
        ],
    },
    {
        "name": "heritage_archaeology",
        "types": [
            "wd:Q9259",  # UNESCO World Heritage Site
            "wd:Q839954",  # archaeological site
            "wd:Q15642541",  # historic site
            "wd:Q1030034",  # GLAM-ish heritage institution
        ],
    },
    {
        "name": "nature_views",
        "types": [
            "wd:Q22698",  # park
            "wd:Q1107656",  # garden
            "wd:Q8502",  # mountain
            "wd:Q23397",  # lake
            "wd:Q40080",  # beach
            "wd:Q23442",  # island
            "wd:Q46169",  # national park
        ],
    },
    {
        "name": "culture_family",
        "types": [
            "wd:Q24354",  # theatre
            "wd:Q153562",  # opera house
            "wd:Q194195",  # amusement park
            "wd:Q43501",  # zoo
            "wd:Q2281788",  # aquarium
        ],
    },
]

KNOWN_CITY_BOUNDS = [
    ("Paris", 48.80, 48.91, 2.22, 2.48),
    ("Lyon", 45.70, 45.82, 4.75, 4.92),
    ("Marseille", 43.20, 43.40, 5.25, 5.55),
    ("Nice", 43.64, 43.76, 7.18, 7.34),
    ("Bordeaux", 44.78, 44.90, -0.66, -0.48),
    ("Strasbourg", 48.52, 48.64, 7.68, 7.84),
    ("Lille", 50.58, 50.67, 2.98, 3.12),
]

MUST_GO_AREAS = [
    ("Paris", 48.80, 2.22, 48.91, 2.48),
    ("Versailles", 48.77, 2.05, 48.84, 2.18),
    ("Saint-Denis", 48.91, 2.31, 48.96, 2.39),
    ("Fontainebleau", 48.37, 2.62, 48.45, 2.75),
    ("Marne-la-Vallee", 48.84, 2.70, 48.91, 2.86),
    ("Mont Saint-Michel", 48.60, -1.56, 48.66, -1.48),
    ("Saint-Malo", 48.61, -2.08, 48.68, -1.94),
    ("Rennes", 48.07, -1.76, 48.16, -1.60),
    ("Nantes", 47.16, -1.65, 47.28, -1.45),
    ("Tours", 47.34, 0.62, 47.44, 0.76),
    ("Amboise", 47.37, 0.94, 47.45, 1.02),
    ("Blois", 47.55, 1.25, 47.64, 1.39),
    ("Chambord", 47.57, 1.48, 47.64, 1.55),
    ("Bordeaux", 44.78, -0.66, 44.90, -0.48),
    ("Saint-Emilion", 44.86, -0.19, 44.93, -0.12),
    ("Biarritz", 43.44, -1.62, 43.51, -1.49),
    ("Toulouse", 43.55, 1.35, 43.67, 1.52),
    ("Carcassonne", 43.18, 2.30, 43.24, 2.42),
    ("Montpellier", 43.56, 3.80, 43.66, 3.95),
    ("Nimes", 43.79, 4.30, 43.88, 4.42),
    ("Avignon", 43.91, 4.75, 44.00, 4.90),
    ("Arles", 43.64, 4.58, 43.72, 4.68),
    ("Aix-en-Provence", 43.48, 5.36, 43.57, 5.50),
    ("Marseille", 43.20, 5.25, 43.40, 5.55),
    ("Cassis", 43.18, 5.50, 43.25, 5.60),
    ("Nice", 43.64, 7.18, 43.76, 7.34),
    ("Cannes", 43.52, 6.93, 43.59, 7.08),
    ("Antibes", 43.55, 7.05, 43.62, 7.17),
    ("Grasse", 43.62, 6.88, 43.69, 7.00),
    ("Lyon", 45.70, 4.75, 45.82, 4.92),
    ("Annecy", 45.86, 6.08, 45.95, 6.18),
    ("Chamonix", 45.88, 6.80, 46.02, 6.98),
    ("Grenoble", 45.13, 5.65, 45.23, 5.80),
    ("Dijon", 47.28, 4.96, 47.37, 5.08),
    ("Beaune", 46.99, 4.78, 47.06, 4.90),
    ("Strasbourg", 48.52, 7.68, 48.64, 7.84),
    ("Colmar", 48.04, 7.32, 48.12, 7.42),
    ("Nancy", 48.65, 6.12, 48.73, 6.24),
    ("Metz", 49.08, 6.10, 49.15, 6.24),
    ("Reims", 49.20, 3.98, 49.30, 4.10),
    ("Rouen", 49.40, 1.02, 49.48, 1.16),
    ("Honfleur", 49.39, 0.20, 49.44, 0.28),
    ("Caen", 49.14, -0.43, 49.22, -0.30),
    ("Bayeux", 49.24, -0.75, 49.31, -0.65),
    ("Lille", 50.58, 2.98, 50.67, 3.12),
    ("Amiens", 49.86, 2.22, 49.94, 2.36),
    ("Lourdes", 43.06, -0.10, 43.12, 0.02),
    ("Ajaccio", 41.88, 8.68, 41.96, 8.80),
    ("Bastia", 42.65, 9.40, 42.73, 9.48),
]


def _seed_place(
    name: str,
    city: str,
    category: str,
    latitude: float,
    longitude: float,
    source_url: str,
    tags: list[str] | None = None,
) -> dict:
    tags_out = [
        "france",
        "must_go",
        "first_time",
        "iconic",
        "landmark",
        city.lower(),
        category.replace("must-go ", ""),
        *(tags or []),
    ]
    if "nature" in category or "viewpoint" in category:
        best_time = "morning or golden hour"
    elif "museum" in category or "religious" in category:
        best_time = "morning"
    else:
        best_time = "morning or late afternoon"

    return {
        "name": name,
        "city": city,
        "neighborhood": city,
        "address": "",
        "category": category,
        "reason": "A classic France must-go place for first-time visitors and iconic sightseeing routes.",
        "local_tip": "Expect crowds; go early, reserve when possible, and pair it with a calmer nearby stop.",
        "tourist_trap_risk": "high",
        "best_time": best_time,
        "estimated_duration_minutes": 120 if "museum" in category else 90,
        "latitude": latitude,
        "longitude": longitude,
        "map_source": "Curated must-go seed",
        "map_url": source_url,
        "price_label": "",
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query="
            + urllib.parse.quote(f"{name}, {city}, France")
        ),
        "google_rating": None,
        "google_user_rating_count": None,
        "google_price_level": "",
        "google_price_label": "",
        "business_status": "",
        "opening_hours": [],
        "open_now": None,
        "open_status_label": "Opening hours need map-source refresh",
        "tags": list(dict.fromkeys(tags_out)),
        "source_type": "curated_must_go",
        "source_title": f"Curated France must-go: {name}",
        "source_url": source_url,
        "confidence": 1.0,
        "osm_type": "",
        "osm_id": "",
        "wikidata_id": "",
        "wikipedia": source_url,
    }


ICONIC_SEED_PLACES = [
    _seed_place("Eiffel Tower", "Paris", "must-go landmark", 48.8584, 2.2945, "https://en.wikipedia.org/wiki/Eiffel_Tower", ["paris", "tower"]),
    _seed_place("Louvre Museum", "Paris", "must-go museum", 48.8606, 2.3376, "https://en.wikipedia.org/wiki/Louvre", ["art", "museum"]),
    _seed_place("Notre-Dame Cathedral", "Paris", "must-go religious heritage", 48.8530, 2.3499, "https://en.wikipedia.org/wiki/Notre-Dame_de_Paris", ["cathedral"]),
    _seed_place("Arc de Triomphe", "Paris", "must-go landmark", 48.8738, 2.2950, "https://en.wikipedia.org/wiki/Arc_de_Triomphe", ["monument"]),
    _seed_place("Sainte-Chapelle", "Paris", "must-go religious heritage", 48.8554, 2.3450, "https://en.wikipedia.org/wiki/Sainte-Chapelle", ["church", "stained_glass"]),
    _seed_place("Sacré-Cœur Basilica", "Paris", "must-go religious heritage", 48.8867, 2.3431, "https://en.wikipedia.org/wiki/Sacr%C3%A9-C%C5%93ur,_Paris", ["montmartre"]),
    _seed_place("Musée d'Orsay", "Paris", "must-go museum", 48.8600, 2.3266, "https://en.wikipedia.org/wiki/Mus%C3%A9e_d%27Orsay", ["art", "museum"]),
    _seed_place("Palace of Versailles", "Versailles", "must-go castle or palace", 48.8049, 2.1204, "https://en.wikipedia.org/wiki/Palace_of_Versailles", ["palace", "garden"]),
    _seed_place("Mont Saint-Michel", "Mont Saint-Michel", "must-go heritage site", 48.6361, -1.5115, "https://en.wikipedia.org/wiki/Mont-Saint-Michel", ["unesco", "abbey"]),
    _seed_place("Château de Chambord", "Chambord", "must-go castle or palace", 47.6161, 1.5170, "https://en.wikipedia.org/wiki/Ch%C3%A2teau_de_Chambord", ["loire", "chateau"]),
    _seed_place("Château de Chenonceau", "Chenonceaux", "must-go castle or palace", 47.3249, 1.0703, "https://en.wikipedia.org/wiki/Ch%C3%A2teau_de_Chenonceau", ["loire", "chateau"]),
    _seed_place("Palace of Fontainebleau", "Fontainebleau", "must-go castle or palace", 48.4021, 2.6995, "https://en.wikipedia.org/wiki/Palace_of_Fontainebleau", ["palace"]),
    _seed_place("Pont du Gard", "Vers-Pont-du-Gard", "must-go heritage site", 43.9476, 4.5350, "https://en.wikipedia.org/wiki/Pont_du_Gard", ["roman", "unesco"]),
    _seed_place("Cité de Carcassonne", "Carcassonne", "must-go heritage site", 43.2065, 2.3630, "https://en.wikipedia.org/wiki/Cit%C3%A9_de_Carcassonne", ["medieval", "unesco"]),
    _seed_place("Palais des Papes", "Avignon", "must-go heritage site", 43.9509, 4.8075, "https://en.wikipedia.org/wiki/Palais_des_Papes", ["palace", "unesco"]),
    _seed_place("Arles Amphitheatre", "Arles", "must-go heritage site", 43.6776, 4.6308, "https://en.wikipedia.org/wiki/Arles_Amphitheatre", ["roman"]),
    _seed_place("Notre-Dame de la Garde", "Marseille", "must-go religious heritage", 43.2840, 5.3710, "https://en.wikipedia.org/wiki/Notre-Dame_de_la_Garde", ["basilica", "viewpoint"]),
    _seed_place("Vieux-Port de Marseille", "Marseille", "must-go landmark", 43.2950, 5.3740, "https://en.wikipedia.org/wiki/Old_Port_of_Marseille", ["harbor"]),
    _seed_place("Calanques National Park", "Marseille", "must-go nature or viewpoint", 43.2170, 5.4330, "https://en.wikipedia.org/wiki/Calanques_National_Park", ["nature", "coast"]),
    _seed_place("Promenade des Anglais", "Nice", "must-go landmark", 43.6951, 7.2656, "https://en.wikipedia.org/wiki/Promenade_des_Anglais", ["seafront"]),
    _seed_place("Castle Hill of Nice", "Nice", "must-go nature or viewpoint", 43.6958, 7.2795, "https://en.wikipedia.org/wiki/Colline_du_Ch%C3%A2teau", ["viewpoint"]),
    _seed_place("Strasbourg Cathedral", "Strasbourg", "must-go religious heritage", 48.5819, 7.7508, "https://en.wikipedia.org/wiki/Strasbourg_Cathedral", ["cathedral"]),
    _seed_place("Petite France", "Strasbourg", "must-go heritage site", 48.5817, 7.7408, "https://en.wikipedia.org/wiki/Petite_France,_Strasbourg", ["historic_walk"]),
    _seed_place("Place de la Bourse", "Bordeaux", "must-go landmark", 44.8414, -0.5696, "https://en.wikipedia.org/wiki/Place_de_la_Bourse,_Bordeaux", ["square"]),
    _seed_place("Dune of Pilat", "Arcachon", "must-go nature or viewpoint", 44.5892, -1.2133, "https://en.wikipedia.org/wiki/Dune_of_Pilat", ["nature"]),
    _seed_place("Basilica of Notre-Dame de Fourvière", "Lyon", "must-go religious heritage", 45.7623, 4.8220, "https://en.wikipedia.org/wiki/Basilica_of_Notre-Dame_de_Fourvi%C3%A8re", ["basilica", "viewpoint"]),
    _seed_place("Vieux Lyon", "Lyon", "must-go heritage site", 45.7630, 4.8270, "https://en.wikipedia.org/wiki/Vieux_Lyon", ["old_town", "unesco"]),
    _seed_place("Place Stanislas", "Nancy", "must-go heritage site", 48.6936, 6.1834, "https://en.wikipedia.org/wiki/Place_Stanislas", ["square", "unesco"]),
    _seed_place("Reims Cathedral", "Reims", "must-go religious heritage", 49.2539, 4.0340, "https://en.wikipedia.org/wiki/Reims_Cathedral", ["cathedral", "unesco"]),
    _seed_place("Rouen Cathedral", "Rouen", "must-go religious heritage", 49.4402, 1.0950, "https://en.wikipedia.org/wiki/Rouen_Cathedral", ["cathedral"]),
    _seed_place("Aiguille du Midi", "Chamonix", "must-go nature or viewpoint", 45.8793, 6.8870, "https://en.wikipedia.org/wiki/Aiguille_du_Midi", ["mountain", "viewpoint"]),
    _seed_place("Lake Annecy", "Annecy", "must-go nature or viewpoint", 45.8525, 6.1650, "https://en.wikipedia.org/wiki/Lake_Annecy", ["lake", "nature"]),
    _seed_place("Gorges du Verdon", "Provence-Alpes-Côte d'Azur", "must-go nature or viewpoint", 43.7490, 6.3286, "https://en.wikipedia.org/wiki/Verdon_Gorge", ["nature", "canyon"]),
    _seed_place("Rocamadour", "Rocamadour", "must-go heritage site", 44.7995, 1.6180, "https://en.wikipedia.org/wiki/Rocamadour", ["village", "pilgrimage"]),
    _seed_place("Lascaux", "Montignac-Lascaux", "must-go heritage site", 45.0538, 1.1679, "https://en.wikipedia.org/wiki/Lascaux", ["cave", "prehistoric"]),
    _seed_place("Saint-Malo Ramparts", "Saint-Malo", "must-go heritage site", 48.6493, -2.0257, "https://en.wikipedia.org/wiki/Saint-Malo", ["ramparts", "old_town"]),
    _seed_place("Omaha Beach", "Normandy", "must-go heritage site", 49.3706, -0.8712, "https://en.wikipedia.org/wiki/Omaha_Beach", ["wwii", "history"]),
    _seed_place("Panthéon", "Paris", "must-go landmark", 48.8462, 2.3460, "https://en.wikipedia.org/wiki/Panth%C3%A9on", ["monument"]),
    _seed_place("Palais Garnier", "Paris", "must-go culture or family attraction", 48.8719, 2.3316, "https://en.wikipedia.org/wiki/Palais_Garnier", ["opera"]),
    _seed_place("Centre Pompidou", "Paris", "must-go museum", 48.8606, 2.3522, "https://en.wikipedia.org/wiki/Centre_Pompidou", ["art", "museum"]),
    _seed_place("Père Lachaise Cemetery", "Paris", "must-go heritage site", 48.8614, 2.3933, "https://en.wikipedia.org/wiki/P%C3%A8re_Lachaise_Cemetery", ["cemetery", "history"]),
]


def _query_for_group(type_group: dict, limit: int, offset: int) -> str:
    values = " ".join(type_group["types"])
    return f"""
SELECT DISTINCT ?place ?placeLabel ?coord ?classLabel ?adminLabel ?article ?image ?sitelinks WHERE {{
  ?place wdt:P17 wd:Q142;
         wdt:P625 ?coord;
         wdt:P31 ?class.
  VALUES ?class {{ {values} }}
  OPTIONAL {{ ?place wdt:P131 ?admin. }}
  OPTIONAL {{ ?place wdt:P18 ?image. }}
  OPTIONAL {{
    ?article schema:about ?place;
             schema:isPartOf <https://en.wikipedia.org/>.
  }}
  ?place wikibase:sitelinks ?sitelinks.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,fr". }}
}}
ORDER BY DESC(?sitelinks) ?placeLabel
LIMIT {limit}
OFFSET {offset}
"""


def _run_sparql(query: str) -> list[dict]:
    url = WIKIDATA_ENDPOINT + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": "TravelBuddy student project must-go dataset/0.1",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("results", {}).get("bindings", [])
        except (TimeoutError, HTTPError, URLError):
            if attempt == 2:
                return []
            time.sleep(2 + attempt)
    return []


def _parse_point(point: str) -> tuple[float, float]:
    raw = point.removeprefix("Point(").removesuffix(")")
    longitude_text, latitude_text = raw.split(" ")
    return float(latitude_text), float(longitude_text)


def _infer_city(latitude: float, longitude: float, admin_label: str) -> str:
    admin_lower = admin_label.lower()
    for city, min_lat, max_lat, min_lon, max_lon in KNOWN_CITY_BOUNDS:
        if min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon:
            return city
        if city.lower() in admin_lower:
            return city
    return admin_label or "France"


def _category_from_group(group_name: str, class_label: str) -> str:
    cleaned = class_label.lower() if class_label else group_name.replace("_", " ")
    if "museum" in cleaned:
        return "must-go museum"
    if any(term in cleaned for term in ["castle", "chateau", "palace"]):
        return "must-go castle or palace"
    if any(term in cleaned for term in ["cathedral", "church", "abbey", "monastery"]):
        return "must-go religious heritage"
    if any(term in cleaned for term in ["park", "garden", "mountain", "lake", "beach", "island"]):
        return "must-go nature or viewpoint"
    if any(term in cleaned for term in ["theatre", "opera", "zoo", "aquarium", "amusement"]):
        return "must-go culture or family attraction"
    if any(term in cleaned for term in ["archaeological", "historic", "world heritage"]):
        return "must-go heritage site"
    return "must-go landmark"


def _tourist_risk(sitelinks: int) -> str:
    if sitelinks >= 80:
        return "high"
    if sitelinks >= 25:
        return "medium"
    return "medium"


def _best_time(category: str) -> str:
    if "nature" in category or "viewpoint" in category:
        return "morning or golden hour"
    if "museum" in category or "religious" in category:
        return "morning"
    return "morning or late afternoon"


def _place_from_binding(binding: dict, group_name: str) -> dict:
    name = binding.get("placeLabel", {}).get("value", "").strip()
    entity_url = binding.get("place", {}).get("value", "")
    entity_id = entity_url.rsplit("/", 1)[-1]
    latitude, longitude = _parse_point(binding["coord"]["value"])
    class_label = binding.get("classLabel", {}).get("value", group_name)
    admin_label = binding.get("adminLabel", {}).get("value", "")
    city = _infer_city(latitude, longitude, admin_label)
    sitelinks = int(binding.get("sitelinks", {}).get("value", 0) or 0)
    category = _category_from_group(group_name, class_label)
    source_url = binding.get("article", {}).get("value") or entity_url
    tags = [
        "france",
        "must_go",
        "first_time",
        "iconic",
        "landmark",
        group_name,
        category.replace("must-go ", ""),
        class_label.lower(),
        city.lower(),
    ]

    return {
        "name": name,
        "city": city,
        "neighborhood": admin_label,
        "address": "",
        "category": category,
        "reason": (
            f"A widely documented France must-go place for first-time visitors "
            f"({class_label}; {sitelinks} Wikidata sitelinks)."
        ),
        "local_tip": (
            "Expect more visitors than the local-first dataset; go early, book ahead "
            "when needed, and pair it with a nearby quieter stop."
        ),
        "tourist_trap_risk": _tourist_risk(sitelinks),
        "best_time": _best_time(category),
        "estimated_duration_minutes": 90,
        "latitude": latitude,
        "longitude": longitude,
        "map_source": "Wikidata",
        "map_url": entity_url,
        "price_label": "",
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query="
            + urllib.parse.quote(f"{name}, {city}, France")
        ),
        "google_rating": None,
        "google_user_rating_count": None,
        "google_price_level": "",
        "google_price_label": "",
        "business_status": "",
        "opening_hours": [],
        "open_now": None,
        "open_status_label": "Opening hours need map-source refresh",
        "tags": list(dict.fromkeys(tags)),
        "source_type": "wikidata",
        "source_title": f"Wikidata {entity_id}: {name}",
        "source_url": source_url,
        "confidence": min(1.0, max(0.65, sitelinks / 120)),
        "wikidata_id": entity_id,
        "wikidata_sitelinks": sitelinks,
        "wikidata_class": class_label,
        "image_url": binding.get("image", {}).get("value", ""),
    }


def collect_must_go_places(target_count: int = 1000, per_group_limit: int = 220) -> list[dict]:
    deduped: dict[str, dict] = {}
    for group in TYPE_GROUPS:
        offset = 0
        while offset < per_group_limit:
            batch_limit = min(50, per_group_limit - offset)
            rows = _run_sparql(_query_for_group(group, batch_limit, offset))
            if not rows:
                break
            for row in rows:
                try:
                    place = _place_from_binding(row, group["name"])
                except (KeyError, ValueError):
                    continue
                if not place["name"]:
                    continue
                key = place["wikidata_id"]
                current = deduped.get(key)
                if current is None or place["wikidata_sitelinks"] > current.get("wikidata_sitelinks", 0):
                    deduped[key] = place
            offset += batch_limit
            if len(deduped) >= target_count:
                break
            time.sleep(0.5)
        if len(deduped) >= target_count:
            break

    return sorted(
        deduped.values(),
        key=lambda item: item.get("wikidata_sitelinks", 0),
        reverse=True,
    )[:target_count]


def save_must_go_places(places: list[dict]) -> Path:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Wikidata SPARQL: France items with coordinates and tourism/heritage classes",
        "place_count": len(places),
        "places": places,
        "evaluation": evaluate_places(places),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return OUTPUT_PATH


def _overpass_query(area: tuple[str, float, float, float, float], limit: int) -> str:
    _, min_lat, min_lon, max_lat, max_lon = area
    bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
    return f"""
[out:json][timeout:90];
(
  nwr({bbox})["tourism"~"^(attraction|museum|gallery|viewpoint|theme_park|zoo|aquarium)$"]["name"];
  nwr({bbox})["historic"]["name"];
  nwr({bbox})["heritage"]["name"];
  nwr({bbox})["leisure"~"^(park|garden)$"]["name"];
  nwr({bbox})["amenity"~"^(theatre|arts_centre|planetarium)$"]["name"];
);
out center tags {limit};
"""


def _run_overpass(query: str) -> list[dict]:
    request = urllib.request.Request(
        OVERPASS_ENDPOINT,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "TravelBuddy student project must-go dataset/0.1"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=130) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("elements", [])
        except (TimeoutError, HTTPError, URLError):
            if attempt == 2:
                return []
            time.sleep(3 + attempt)
    return []


def _element_coordinates(element: dict) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if center and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def _osm_category(tags: dict) -> str:
    tourism = tags.get("tourism", "")
    historic = tags.get("historic", "")
    leisure = tags.get("leisure", "")
    amenity = tags.get("amenity", "")
    if tourism == "museum":
        return "must-go museum"
    if tourism in {"viewpoint", "attraction"}:
        return "must-go landmark"
    if tourism in {"theme_park", "zoo", "aquarium"}:
        return "must-go culture or family attraction"
    if tourism == "gallery" or amenity in {"theatre", "arts_centre", "planetarium"}:
        return "must-go culture or family attraction"
    if leisure in {"park", "garden"}:
        return "must-go nature or viewpoint"
    if historic in {"castle", "palace", "fort", "manor", "city_gate"}:
        return "must-go castle or palace"
    if historic in {"church", "cathedral", "monastery", "wayside_shrine"}:
        return "must-go religious heritage"
    if historic:
        return "must-go heritage site"
    return "must-go landmark"


def _osm_place_from_element(element: dict, area_name: str) -> dict | None:
    tags = element.get("tags", {})
    name = tags.get("name") or tags.get("name:en") or tags.get("name:fr")
    coordinates = _element_coordinates(element)
    if not name or not coordinates:
        return None

    latitude, longitude = coordinates
    category = _osm_category(tags)
    osm_type = element.get("type", "node")
    osm_id = element.get("id")
    source_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    wikidata_id = tags.get("wikidata", "")
    wikipedia = tags.get("wikipedia", "")
    source_title = (
        f"OpenStreetMap must-go candidate: {name}"
        if not wikidata_id
        else f"OpenStreetMap + Wikidata {wikidata_id}: {name}"
    )
    city = tags.get("addr:city") or area_name
    tags_out = [
        "france",
        "must_go",
        "first_time",
        "iconic",
        "landmark",
        area_name.lower(),
        city.lower(),
        category.replace("must-go ", ""),
    ]
    for key in ["tourism", "historic", "heritage", "leisure", "amenity"]:
        if tags.get(key):
            tags_out.append(tags[key])
    if wikidata_id:
        tags_out.append("wikidata")
    if wikipedia:
        tags_out.append("wikipedia")

    confidence = 0.78
    if wikidata_id:
        confidence += 0.12
    if wikipedia:
        confidence += 0.08

    return {
        "name": name,
        "city": city,
        "neighborhood": area_name,
        "address": tags.get("addr:full", ""),
        "category": category,
        "reason": (
            "A public attraction or heritage place from OpenStreetMap, suitable "
            "for first-time France itineraries and classic sightseeing routes."
        ),
        "local_tip": (
            "This is part of the must-go dataset, so expect more visitors. Go early "
            "or late and combine it with quieter nearby streets or parks."
        ),
        "tourist_trap_risk": "high" if category == "must-go landmark" else "medium",
        "best_time": _best_time(category),
        "estimated_duration_minutes": 90,
        "latitude": latitude,
        "longitude": longitude,
        "map_source": "OpenStreetMap",
        "map_url": source_url,
        "price_label": "",
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query="
            + urllib.parse.quote(f"{name}, {city}, France")
        ),
        "google_rating": None,
        "google_user_rating_count": None,
        "google_price_level": "",
        "google_price_label": "",
        "business_status": "",
        "opening_hours": [tags["opening_hours"]] if tags.get("opening_hours") else [],
        "open_now": None,
        "open_status_label": (
            f"OpenStreetMap hours: {tags['opening_hours']}"
            if tags.get("opening_hours")
            else "Opening hours not mapped in OpenStreetMap"
        ),
        "tags": list(dict.fromkeys(tags_out)),
        "source_type": "openstreetmap",
        "source_title": source_title,
        "source_url": source_url,
        "confidence": min(confidence, 1.0),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "wikidata_id": wikidata_id,
        "wikipedia": wikipedia,
    }


def collect_osm_must_go_places(target_count: int = 1000, per_area_limit: int = 90) -> list[dict]:
    deduped: dict[str, dict] = {
        f"seed::{place['name'].lower()}::{place['city'].lower()}": place
        for place in ICONIC_SEED_PLACES
    }
    for area in MUST_GO_AREAS:
        area_name = area[0]
        elements = _run_overpass(_overpass_query(area, per_area_limit))
        for element in elements:
            place = _osm_place_from_element(element, area_name)
            if not place:
                continue
            key = place.get("wikidata_id") or f"{place['name'].lower()}::{place['city'].lower()}"
            current = deduped.get(key)
            if current is None or place["confidence"] > current.get("confidence", 0):
                deduped[key] = place
        time.sleep(0.7)

    category_weight = {
        "must-go landmark": 0,
        "must-go museum": 1,
        "must-go heritage site": 2,
        "must-go castle or palace": 3,
        "must-go religious heritage": 4,
        "must-go nature or viewpoint": 5,
        "must-go culture or family attraction": 6,
    }
    return sorted(
        deduped.values(),
        key=lambda item: (
            0 if item.get("source_type") == "curated_must_go" else 1,
            -item.get("confidence", 0),
            category_weight.get(item.get("category", ""), 9),
            item.get("city", ""),
            item.get("name", ""),
        ),
    )[:target_count]


def evaluate_places(places: list[dict]) -> dict:
    return {
        "total": len(places),
        "unique_wikidata_ids": len({place.get("wikidata_id") for place in places if place.get("wikidata_id")}),
        "unique_osm_ids": len({f"{place.get('osm_type')}/{place.get('osm_id')}" for place in places if place.get("osm_id")}),
        "with_coordinates": sum(1 for place in places if place.get("latitude") and place.get("longitude")),
        "with_source_url": sum(1 for place in places if place.get("source_url")),
        "with_image_url": sum(1 for place in places if place.get("image_url")),
        "top_cities": Counter(place.get("city", "Unknown") for place in places).most_common(15),
        "top_categories": Counter(place.get("category", "Unknown") for place in places).most_common(15),
        "tourist_risk": Counter(place.get("tourist_trap_risk", "unknown") for place in places),
    }


def refresh_must_go_places(
    target_count: int = 1000,
    per_group_limit: int = 220,
    source: str = "osm",
) -> dict:
    if source == "wikidata":
        places = collect_must_go_places(
            target_count=target_count,
            per_group_limit=per_group_limit,
        )
    else:
        places = collect_osm_must_go_places(
            target_count=target_count,
            per_area_limit=per_group_limit,
        )
    output_path = save_must_go_places(places)
    return {
        "place_count": len(places),
        "output_path": str(output_path),
        "evaluation": evaluate_places(places),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build France must-go attractions dataset.")
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--per-group-limit", type=int, default=90)
    parser.add_argument("--source", choices=["osm", "wikidata"], default="osm")
    args = parser.parse_args()
    print(json.dumps(refresh_must_go_places(args.target_count, args.per_group_limit, args.source), indent=2))


if __name__ == "__main__":
    main()
