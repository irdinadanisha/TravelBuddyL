# Google Maps Review Sources

TravelBuddy uses the official Google Places API to attach Google Maps review references, ratings, and opening-hour information to recommendations. It does not scrape Google Maps pages.

## Required Environment Variable

Set one of these before refreshing:

```powershell
$env:GOOGLE_MAPS_API_KEY="your_google_maps_platform_key"
```

or:

```powershell
$env:GOOGLE_PLACES_API_KEY="your_google_maps_platform_key"
```

The key needs access to the Places API.

## Refresh From The CLI

Run from `backend/`:

```powershell
python -m app.services.google_places
```

For a small test:

```powershell
python -m app.services.google_places --limit 3
```

To search Google Maps only for places discovered from Reddit:

```powershell
python -m app.services.google_places --reddit-only --limit 10
```

This writes:

```text
backend/app/data/google_places.json
```

## Refresh Through The API

With FastAPI running:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/google-places/refresh
```

Check cache status:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/google-places/status
```

## User-Facing Source Rules

The app only shows these source types as references:

- Google Maps reviews
- Reddit threads

Starter data is still useful as candidate data, but it is not shown as a source. If a place has no Google Maps or Reddit source yet, the UI asks you to refresh Google Maps or Reddit sources.

## Rating And Hours

After refresh, recommendations can show:

- Google Maps rating
- Google review count
- Google price level when available
- current open/closed status when Google returns it
- weekday opening-hour descriptions
- whether a requested weekday appears closed

If a user asks for a specific day such as `tomorrow`, `today`, or `Monday`, TravelBuddy tries to match that day against Google weekday opening descriptions. If no Google hours are cached, the app displays that a Google Maps refresh is needed.
