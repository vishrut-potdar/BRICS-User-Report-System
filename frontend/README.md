# frontend (owner: frontend and design)

`index.html` is a single-file dashboard with no build step. The FastAPI app serves it at `/`, so it calls the
API from the same origin (and the Cloud Run image ships both). Opened straight from disk, it tries
`http://127.0.0.1:8000` and falls back to built-in demo data if the API is not running.

What is live: rankings and score breakdowns, the heat map (cluster centroids), top issue per district, silent
districts, headline counts, and the citizen-app preview, which files real requests through `POST /ingest` (text, or a
recorded voice note, which needs Gemini). What is still on-screen only: "Simulate request", the spam-burst test,
and status/approve/notify, because the API has no endpoints for them yet. The "Volume" preset uses client-side
weights (demand-heavy) rather than the API's `volume_only` message count.

The API contract it builds on (interactive docs at `/docs` on the backend):

| Screen | Endpoint |
|---|---|
| Ranked list and map | `GET /rankings?preset=balanced\|equity_first\|volume_only&limit=20` (+ `demand`, `need`, `equity`, `alignment`, `urgency` weight overrides) |
| Weight slider / presets | same endpoint; `GET /meta` → `presets`, `components` |
| Score waterfall | each ranking item: `contributions` (weight × component), `integrity_penalty`, `score` |
| "Robust" badge | `robust: true` (stays top-10 under ±20% weight changes) |
| Project detail | `GET /clusters/{cluster_id}` → redacted request summaries, integrity flags |
| Volume vs equity headline | `GET /rankings/compare?a=volume_only&b=equity_first&k=10` |
| Silent districts panel | `GET /districts/silent?k=5` |
| District layer | `GET /districts`, `GET /export/aggregates.geojson?level=district\|h3` |
| Synthetic labels | `synthetic_share` on items; `GET /meta` → `synthetic_indicators`, `placeholder_metrics` |

Every record in the demo dataset is synthetic. Show that on screen.
