# OpenStreetMap POI Ingestion

This ingestion expands the TravelBuddy dataset without Google Maps or Reddit credentials by using the OpenStreetMap Overpass API.

## What It Collects

For each configured city, it collects named POIs such as:

- Restaurants, cafes, bars, food courts, and marketplaces.
- Museums and galleries.
- Parks and gardens.
- Bakeries, coffee shops, cheese shops, bookshops, and delis.

The output is normalized into the same place shape used by the chatbot.

## Refresh From CLI

Run from `backend/`:

```powershell
python -m app.services.osm_poi_ingestion --cities Paris,Lyon,Marseille,Nice,Bordeaux,Strasbourg,Lille --city-limit 120 --delay-seconds 2
```

This writes:

```text
backend/app/data/osm_poi_places.json
```

## Refresh Through API

With FastAPI running:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/osm-poi/refresh?cities=Paris,Lyon,Marseille,Nice,Bordeaux,Strasbourg,Lille&city_limit=120"
```

Check status:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/osm-poi/status
```

## Practical Limits

This uses a public Overpass instance, so keep limits modest and avoid rapid repeated runs. For larger research datasets, run it less often, use delays, or host/use a dedicated Overpass provider.

## Current Test Run

A run with 7 cities and 120 places per city produced 840 OSM POI candidates:

```text
Paris: 120
Lyon: 120
Marseille: 120
Nice: 120
Bordeaux: 120
Strasbourg: 120
Lille: 120
```
