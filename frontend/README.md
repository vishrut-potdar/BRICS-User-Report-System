# frontend (owner: frontend and design)

React/Vite dashboard on Firebase Hosting. The API contract it builds on (interactive docs at `/docs` on the backend):

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
