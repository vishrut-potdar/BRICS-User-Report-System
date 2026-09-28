# Schema

All data is UTF-8. Timestamps are ISO-8601 with an offset. Codes: BCP-47 languages, ISO 3166-2 regions,
H3 v4 cells (resolution 7 by default, about 5 km²).

## CivicRequest (stored; one JSON object per line in JSONL, one document in Firestore)

| Field | Type | Notes |
|---|---|---|
| `id` | string | 12 hex chars; `syn-NNNNN` for synthetic |
| `channel` | `whatsapp` \| `telegram` \| `web` \| `ivr` \| `sms` | |
| `lang` | string | `mr`, `hi`, `en`, `hi-Latn` (Hindi in Roman script), `und` if extraction failed |
| `code_mixed` | bool | |
| `text_original` | string | Transcript or text, regex-redacted (phones, emails, ID numbers). Never returned by the API |
| `text_en` | string | English translation |
| `category` | sector | `water` `sanitation` `roads` `health` `education` `electricity` `waste` `other` |
| `sub_type` | string | snake_case, e.g. `handpump_broken` |
| `urgency` | `low` \| `medium` \| `high` | `high` = immediate risk to life, health or safety |
| `summary_redacted` | string | One English sentence without names, numbers or addresses |
| `geo.lat`, `geo.lon` | float? | Only for confidence A/B |
| `geo.h3` | string? | Only for confidence A/B |
| `geo.admin_code` | string? | `IN-MH-<DISTRICT>`; null → `needs_review` |
| `geo.district` | string? | English name |
| `geo.location_text` | string? | Place mentions as written |
| `geo.confidence` | `A` \| `B` \| `C` | A = GPS, B = geocoded locality or finer, C = district only |
| `geo.method` | `gps` \| `geocode` \| `gazetteer` \| `none` | |
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

`data/processed/indicators_long.csv`: one row per value, which gives provenance:

`admin_code, district_name, metric, value (0-1), year, source, licence, placeholder (true/false)`

`data/processed/district_indicators.csv`: what the scorer reads:

`admin_code, district_name, population, poverty (equity metric, 0-1), aspirational, need_<sector> (0-1, higher = worse),
placeholder_metrics (;-separated), synthetic`

The pack's `need` block maps each sector to a metric, inverting coverage metrics (need = 1 − coverage).

## PlannedProject

`project_id, admin_code, sector, name, budget_inr_lakh, status, source, synthetic`. Collapsed per
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

`data/packs/<PACK_ID>.json` declares: `country`, `region_name`, `languages`, `h3_resolution`, file paths, the
`metrics` it expects (with sources), the `equity_metric`, and the sector → metric `need` mapping. For Brazil or
South Africa, add a pack with HDX COD-AB boundaries, a national or OPHI MPI, and the same need mapping to local
coverage indicators. No code changes are needed.
