# Official Open Data Sources

TravelBuddy can ingest official event/activity records from Paris Open Data through the Opendatasoft Explore API.

## Paris Open Data

Opendatasoft Explore API v2.1 uses JSON `GET` endpoints:

```text
https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/{dataset_id}/records
```

The current implementation uses:

```text
que-faire-a-paris-
```

This is the official `Que Faire a Paris?` events and activities dataset. It provides titles, official URLs, descriptions, schedules, venues, coordinates, tags, access links, and price details when available.

Refresh from `backend/`:

```powershell
python -m app.services.open_data_sources --limit 50
```

Search-focused refresh:

```powershell
python -m app.services.open_data_sources --limit 50 --search "balade"
```

With FastAPI running:

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/open-data/refresh?limit=50&search=balade"
```

The cache is written to:

```text
backend/app/data/open_data_places.json
```

## Ile-de-France Open Data

The Ile-de-France portal also uses open-data APIs, but the useful dataset depends on the exact event/activity category you want. Add the dataset ID to the same Opendatasoft pattern once selected:

```text
https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/{dataset_id}/records
```

Recommended use: add this after deciding which regional event or facility dataset best supports the product scope.

## OpenAgenda

OpenAgenda has a REST API for event content, but reading some agendas can require authentication or an access token. It is useful later for broader event coverage, but Paris Open Data is simpler and more defensible for the current prototype.

## Current App Behavior

Official open-data records are normalized into the same `Place` schema as Reddit and OpenStreetMap places:

- `source_type`: `official_open_data`
- `source_title`: official dataset name
- `source_url`: official event page
- `opening_hours`: event date/schedule text when provided
- `price_label`: free/paid/detail when provided
- `tags`: event/activity/official/open-data plus dataset tags
