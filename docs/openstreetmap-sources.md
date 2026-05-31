# OpenStreetMap Sources

TravelBuddy can use OpenStreetMap through the public Nominatim search API when a Google Maps API key is not available.

## What OpenStreetMap Can Provide

- Place coordinates.
- OpenStreetMap place page links.
- Address and category details.
- `opening_hours` when local mappers have added the tag.
- Price or fee hints when tags such as `fee`, `charge`, or `price` exist.

## What OpenStreetMap Does Not Provide

- Google-style star ratings.
- Google review counts.
- Guaranteed business prices or menus.
- Guaranteed opening hours for every business.

If those fields are missing, the frontend will say that the data is not available from OpenStreetMap instead of pretending it was found.

## Required Environment Variables

No API key is required. Set a clear user agent so Nominatim can identify your app:

```powershell
$env:OSM_USER_AGENT="travelbuddy-france-local-recs/0.1 your-email-or-name"
```

## Reddit Then OpenStreetMap Pipeline

Run from `backend/`:

```powershell
python -m app.services.reddit_osm_pipeline --subreddits france,paris,AskFrance --limit-per-query 5 --comment-limit 8 --osm-limit 20
```

This writes:

```text
backend/app/data/reddit_places.json
backend/app/data/osm_places.json
```

## OpenStreetMap-Only Refresh

If `reddit_places.json` already exists, refresh only the OSM lookup:

```powershell
python -m app.services.osm_places --limit 20
```

## API Refresh

With FastAPI running:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/osm-places/refresh
```

Check cache status:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/osm-places/status
```

## Usage Note

The public Nominatim service is suitable for small development refreshes, not heavy production scraping. The implementation waits between requests and sends a custom User-Agent. For production, use your own Nominatim instance or a hosted OSM provider.
