# frontend

Two static pages with no build step, served by the FastAPI app, so they call the API from the same origin. The Cloud
Run image ships them with the API.

| File | Route | For |
|---|---|---|
| `index.html` | `/` | Citizen complaint portal |
| `admin.html` | `/admin` | Government dashboard |
| `app.css` | `/static/app.css` | Shared tokens and components |

## Citizen portal

- First visit: pick a country. The portal is locked to it (browser storage) until the citizen presses "Change country".
- Pick the state, and the district or city where the country has district data. The choice is remembered as
  "Your area" for next time.
- Optional category, a description (text, or voice when the server runs Gemini) and optional GPS →
  `POST /ingest {pack, admin_code, category, text | audio_base64, lat, lon, sender_id}`.
- Shows the tracking ID and the acknowledgement in the citizen's language. `GET /track/{id}` shows status.
- "Administrative side" in the header opens `/admin` for the same country.

## Government dashboard

- Country picker, then locked, as on the portal. State and district selections are remembered.
- Picking a state zooms to it. When a pilot pack covers that state (`parent` in `/packs`), the map switches to its
  district boundaries. Picking a district zooms again. Other units are dimmed; the heat map, pins, ranking and
  counters show only the selected area. Clicking the map or the breadcrumb does the same.
- Rankings are recomputed in the browser from each cluster's `components` with the same linear formula as the API,
  so switching presets is instant. "Volume" uses demand-heavy weights for the comparison arrows.
- Status and "Approve and forward" call `POST /clusters/{id}/status`, which updates every request in the cluster.

| Screen | Endpoint |
|---|---|
| Country list, drill-down | `GET /packs` (`level`, `parent`), `GET /meta?pack=` → `units` |
| Map | `GET /boundaries?pack=` (GeoJSON), `GET /rankings?pack=&preset=volume_only` for heat |
| Ranking, score breakdown | `GET /rankings?pack=&preset=balanced&limit=5000&sensitivity=false` |
| Counters | `GET /districts?pack=` (`n_requests`, `n_requesters`, `n_resolved`) |
| Silent areas | `GET /districts/silent?pack=` |
| Open data | `GET /export/aggregates.csv?pack=` |

Every record in the demo dataset is synthetic, and the pages say so.
