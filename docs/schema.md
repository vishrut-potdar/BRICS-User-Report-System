# Schema

All data is UTF-8. Timestamps are ISO-8601 with an offset. Codes: BCP-47 languages, ISO 3166-2 regions,
H3 v4 cells (resolution 7 in pilot regions, about 5 km²; resolution 5 in country packs, about 250 km²).

Every stored record belongs to one pack. A message is interpreted once and stored in each pack of its country that it
falls in (the country pack always, a pilot pack when it is inside that region), under the same `id`.

## CivicRequest (stored; one JSON object per line in JSONL, one document in Firestore)

| Field | Type | Notes |
|---|---|---|
| `id` | string | 12 hex chars; `syn-<PACK>-NNNNN` for synthetic. Same value in every pack that holds a copy |
| `channel` | `whatsapp` \| `telegram` \| `web` \| `ivr` \| `sms` | |
| `lang` | string | BCP-47: `mr`, `hi`, `en`, `hi-Latn` (Hindi in Roman script), `pt`, `ru`, `zh`, `af`, `zu`, `xh`; `und` if extraction failed |
| `code_mixed` | bool | |
| `text_original` | string | Transcript or text, regex-redacted (phones, emails, ID numbers). Never returned by the API |
| `text_en` | string | English translation |
| `category` | sector | `water` `sanitation` `roads` `health` `education` `electricity` `waste` `other` |
| `sub_type` | string | snake_case, e.g. `handpump_broken` |
| `urgency` | `low` \| `medium` \| `high` | `high` = immediate risk to life, health or safety |
| `summary_redacted` | string | One English sentence without names, numbers or addresses |
| `geo.lat`, `geo.lon` | float? | Only for confidence A/B |
| `geo.h3` | string? | Only for confidence A/B |
| `geo.admin_code` | string? | The pack's unit: ISO 3166-2 in country packs (`BR-AL`), `<REGION>-<SLUG>` in pilots (`BR-AL-MACEIO`); null → `needs_review` |
| `geo.district` | string? | English name |
| `geo.location_text` | string? | Place mentions as written |
| `geo.confidence` | `A` \| `B` \| `C` | A = GPS, B = geocoded locality or finer, C = district only |
| `geo.method` | `gps` \| `geocode` \| `gazetteer` \| `selected` \| `none` | `selected` = the citizen picked the place in the portal |
| `requester_hash` | string | HMAC-SHA256(salt, `channel:sender_id`)[:24] |
| `created_at` | datetime | |
| `status` | `received` \| `needs_review` \| `forwarded` \| `in_progress` \| `resolved` \| `rejected` | Only active statuses count as demand |
| `provider` | string | `gemini`, `offline` or `synthetic` |
| `synthetic` | bool | Must be shown on screen when true |

## Cluster

`cluster_id = <admin_code>.<sector>.<h3 cell | "district">`, e.g. `IN-MH-PUNE.roads.876088424ffffff`.
Requests with confidence C form one district-level cluster per sector. Embedding-based sub-clustering within a
cell is a planned refinement and will keep this ID format.

## Indicator tables

`data/processed/<PACK>/indicators_long.csv`: one row per value, which gives provenance:

`admin_code, district_name, metric, value (0-1), year, source, licence, placeholder (true/false)`

`data/processed/<PACK>/indicators.csv`: what the scorer reads:

`admin_code, district_name, population, poverty (equity metric, 0-1), aspirational, need_<sector> (0-1, higher = worse),
placeholder_metrics (;-separated), synthetic`

The pack's `need` block maps each sector to a metric, inverting coverage metrics (need = 1 − coverage).

## PlannedProject

`project_id, admin_code, sector, name, budget_m, currency, status, source, synthetic`. Collapsed per
(district, sector): any funded/sanctioned/in-progress/completed → `funded`; else any delayed/stalled → `delayed`.

## Score

```
Priority = 100 × Σ w_i · component_i × integrity
contributions_i = w_i · component_i            (the waterfall bars, 0-1 scale)
integrity_penalty = Σ contributions × (1 − integrity)
score = 100 × (Σ contributions − integrity_penalty)
```

Integrity = 1 − 0.5 × max(concentration, burstiness, duplication), each 0-1:

- concentration = max(0, (0.7 − unique senders / messages) / 0.7)
- burstiness = max(0, (largest 30-minute share − 0.5) / 0.5), only for clusters of 10+ messages
- duplication = max(0, (near-duplicate share − 0.5) / 0.5), where near-duplicate means char-3-gram Jaccard ≥ 0.85

Clusters of fewer than 5 messages are exempt.

## Country packs

A pack is config plus data files; supporting a new region needs no code changes. Ten ship today:

| Pack | Level | Units | Languages |
|---|---|---|---|
| `BR` / `BR-AL` | country / pilot | 27 states / 102 municipalities of Alagoas | pt |
| `RU` / `RU-TY` | country / pilot | 83 federal subjects / 19 districts of Tuva | ru |
| `IN` / `IN-MH` | country / pilot | 36 states and UTs / 36 districts of Maharashtra | hi, mr, en, hi-Latn |
| `CN` / `CN-NX` | country / pilot | 31 mainland provinces / 19 counties of Ningxia | zh |
| `ZA` / `ZA-EC` | country / pilot | 9 provinces / 8 districts of the Eastern Cape | en, zu, xh, af |

`data/packs/<PACK_ID>.json` declares:

- identity: `country`, `country_name`, `level` (`country` | `region`), `parent` (the country pack of a pilot),
  `region_name`, `unit_label(_plural)`, `priority_label` (what the equity bonus flag means locally), `languages`,
  `h3_resolution`, `utc_offset`
- `files`: `reference/<PACK>/units.csv`, `boundaries.geojson`, `settlements.csv`, `processed/<PACK>/…`,
  `synthetic/<PACK>/requests.jsonl`
- `metrics` (with expected official sources), `equity_metric`, and the sector → metric `need` mapping
- `placeholder`: deterministic shaping for placeholder values until `data/raw/<PACK>/` files exist
- `synthetic`: request volume, language mix (overall and per unit), connectivity multipliers and the brigade target

A pilot's `pack_id` equals the country-pack unit code it details (`BR-AL`), which is how the dashboard drills down.

Build order, from `backend/`: `scripts.build_reference` (boundaries, populations; needs network once) →
`scripts.build_indicators --allow-placeholder` → `scripts.generate_synthetic` → `scripts.seed --reset`.
