"""Read side: clusters, rankings, comparisons, district views and anonymised open-data aggregates."""

from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import h3

from .clustering import Cluster, build_clusters, is_active
from .models import CivicRequest, public_view
from .pack import PackContext
from .repository import RequestRepository
from .scoring import PRESETS, VOLUME_ONLY, ScoredCluster, Weights, rank_clusters


@dataclass
class _State:
    requests: list[CivicRequest]
    clusters: list[Cluster]
    by_id: dict[str, Cluster]


class DemandService:
    def __init__(self, repo: RequestRepository, ctx: PackContext, *, cache_seconds: float = 10.0):
        self._repo = repo
        self._ctx = ctx
        self._ttl = cache_seconds
        self._lock = threading.Lock()
        self._state: _State | None = None
        self._state_at = 0.0

    def invalidate(self) -> None:
        with self._lock:
            self._state = None

    def _current(self) -> _State:
        with self._lock:
            if self._state is None or time.monotonic() - self._state_at > self._ttl:
                requests = self._repo.all()
                clusters = build_clusters(requests)
                self._state = _State(requests, clusters, {c.cluster_id: c for c in clusters})
                self._state_at = time.monotonic()
            return self._state

    # --- views -----------------------------------------------------------------------------------

    def _view(self, cluster: Cluster, *, rank: int, score: float, scored: ScoredCluster | None, detail: bool = False) -> dict[str, Any]:
        info = self._ctx.info.get(cluster.admin_code)
        centroid = cluster.centroid((info.lat, info.lon) if info else None)
        view: dict[str, Any] = {
            "rank": rank,
            "cluster_id": cluster.cluster_id,
            "admin_code": cluster.admin_code,
            "district": info.name if info else cluster.admin_code,
            "sector": cluster.sector,
            "level": "h3" if cluster.h3 else "district",
            "h3": cluster.h3,
            "centroid": {"lat": centroid[0], "lon": centroid[1]} if centroid else None,
            "score": score,
            "n_messages": cluster.n_messages,
            "n_requesters": cluster.n_requesters,
            "n_urgent": cluster.n_urgent,
            "synthetic_share": round(cluster.synthetic_share, 3),
            "integrity": {
                "multiplier": cluster.integrity.multiplier,
                "sender_diversity": cluster.integrity.sender_diversity,
                "burst_share": cluster.integrity.burst_share,
                "duplicate_share": cluster.integrity.duplicate_share,
                "flags": list(cluster.integrity.flags),
            },
            "sample_summaries": [r.summary_redacted for r in cluster.requests[:3]],
        }
        if scored is not None:
            view.update(
                components=dict(scored.components),
                contributions=dict(scored.contributions),
                integrity_penalty=scored.integrity_penalty,
                alignment_status=scored.alignment_status,
                robust=scored.robust,
            )
        if detail:
            view["requests"] = [public_view(r) for r in cluster.requests]
        return view

    def _ranked_views(self, weights: Weights | None, *, sensitivity: bool) -> list[dict[str, Any]]:
        state = self._current()
        if weights is None:  # volume-only baseline: what most intake systems implicitly do
            ordered = sorted(state.clusters, key=lambda c: (-c.n_messages, c.cluster_id))
            return [self._view(c, rank=i, score=float(c.n_messages), scored=None) for i, c in enumerate(ordered, start=1)]
        scored = rank_clusters(
            [c.to_input() for c in state.clusters],
            self._ctx.districts,
            self._ctx.planned,
            weights,
            sensitivity_top_k=10 if sensitivity else 0,
        )
        return [self._view(state.by_id[s.cluster_id], rank=s.rank, score=s.score, scored=s) for s in scored]

    def rankings(
        self,
        weights: Weights | None,
        *,
        sector: str | None = None,
        admin_code: str | None = None,
        limit: int = 20,
        sensitivity: bool = True,
    ) -> list[dict[str, Any]]:
        """`rank` is state-wide; the sector/district filters only narrow what is returned."""
        items = self._ranked_views(weights, sensitivity=sensitivity)
        if sector:
            items = [i for i in items if i["sector"] == sector]
        if admin_code:
            items = [i for i in items if i["admin_code"] == admin_code]
        return items[:limit]

    def cluster(self, cluster_id: str, weights: Weights) -> dict[str, Any] | None:
        state = self._current()
        cluster = state.by_id.get(cluster_id)
        if cluster is None:
            return None
        scored = next((s for s in self._scored(weights) if s.cluster_id == cluster_id), None)
        if scored is None:  # emerging: below the minimum-requesters threshold, so unranked
            return self._view(cluster, rank=0, score=0.0, scored=None, detail=True) | {"status": "emerging"}
        return self._view(cluster, rank=scored.rank, score=scored.score, scored=scored, detail=True) | {"status": "ranked"}

    def _scored(self, weights: Weights) -> list[ScoredCluster]:
        state = self._current()
        return rank_clusters([c.to_input() for c in state.clusters], self._ctx.districts, self._ctx.planned, weights, sensitivity_top_k=0)

    def compare(self, preset_a: str, preset_b: str, k: int = 10) -> dict[str, Any]:
        """Headline numbers for the equity story: where does each preset send the top k?"""
        poverty = sorted(d.poverty for d in self._ctx.districts.values())
        q75 = poverty[int(0.75 * (len(poverty) - 1))] if poverty else 0.0
        poorest_quartile = {c for c, d in self._ctx.districts.items() if d.poverty >= q75}
        least_poor_3 = {c for c, _ in sorted(self._ctx.districts.items(), key=lambda kv: kv[1].poverty)[:3]}

        def summarise(preset: str) -> dict[str, Any]:
            weights = None if preset == VOLUME_ONLY else PRESETS[preset]
            top = self._ranked_views(weights, sensitivity=False)[:k]
            codes = [item["admin_code"] for item in top]
            return {
                "preset": preset,
                "top": [{k2: item[k2] for k2 in ("rank", "cluster_id", "district", "sector", "score", "n_messages", "n_requesters")} for item in top],
                "in_poorest_quartile": sum(c in poorest_quartile for c in codes),
                "in_least_poor_3": sum(c in least_poor_3 for c in codes),
                "distinct_districts": len(set(codes)),
            }

        a, b = summarise(preset_a), summarise(preset_b)
        overlap = {i["cluster_id"] for i in a["top"]} & {i["cluster_id"] for i in b["top"]}
        return {
            "k": k,
            "a": a,
            "b": b,
            "overlap": len(overlap),
            "poorest_quartile_districts": sorted(self._ctx.info[c].name for c in poorest_quartile),
            "least_poor_3_districts": sorted(self._ctx.info[c].name for c in least_poor_3),
            "synthetic_indicators": self._ctx.synthetic_indicators,
        }

    def districts(self) -> list[dict[str, Any]]:
        state = self._current()
        counts = Counter(r.geo.admin_code for r in state.requests if is_active(r))
        rows = []
        for code, d in sorted(self._ctx.districts.items()):
            info = self._ctx.info[code]
            n = counts.get(code, 0)
            rows.append(
                {
                    "admin_code": code,
                    "district": d.name,
                    "name_local": info.name_local,
                    "lgd_code": info.lgd_code,
                    "centroid": {"lat": info.lat, "lon": info.lon},
                    "population": d.population,
                    "poverty": d.poverty,
                    "aspirational": d.aspirational,
                    "need": dict(d.need),
                    "n_requests": n,
                    "requests_per_100k": round(n / d.population * 100_000, 3) if d.population else None,
                    "placeholder_metrics": list(self._ctx.placeholder_metrics.get(code, ())),
                }
            )
        return rows

    def silent_districts(self, k: int = 5) -> list[dict[str, Any]]:
        """Poorer-than-median districts with the fewest requests per capita: where outreach should go."""
        rows = self.districts()
        poverty = sorted(r["poverty"] for r in rows)
        median = poverty[len(poverty) // 2] if poverty else 0.0
        poor = [r for r in rows if r["poverty"] >= median]
        return sorted(poor, key=lambda r: (r["requests_per_100k"] or 0.0, -r["poverty"]))[:k]

    def aggregates(self, level: str = "district", min_requesters: int = 5) -> tuple[list[dict[str, Any]], int]:
        """Counts per (district|h3, sector). Groups with fewer than `min_requesters` people are suppressed."""
        state = self._current()
        groups: dict[tuple[str, str, str | None], list[CivicRequest]] = defaultdict(list)
        for r in state.requests:
            if not is_active(r):
                continue
            if level == "h3":
                if r.geo.h3 and r.geo.confidence in ("A", "B"):
                    groups[(r.geo.admin_code, r.category, r.geo.h3)].append(r)
            else:
                groups[(r.geo.admin_code, r.category, None)].append(r)

        rows, suppressed = [], 0
        for (code, sector, cell), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "")):
            requesters = len({r.requester_hash for r in items})
            if requesters < min_requesters:
                suppressed += 1
                continue
            info = self._ctx.info.get(code)
            lat, lon = h3.cell_to_latlng(cell) if cell else ((info.lat, info.lon) if info else (None, None))
            rows.append(
                {
                    "admin_code": code,
                    "district": info.name if info else code,
                    "sector": sector,
                    "h3": cell,
                    "lat": round(lat, 5) if lat is not None else None,
                    "lon": round(lon, 5) if lon is not None else None,
                    "n_requests": len(items),
                    "n_requesters": requesters,
                    "share_urgent": round(sum(r.urgency == "high" for r in items) / len(items), 3),
                    "synthetic_share": round(sum(r.synthetic for r in items) / len(items), 3),
                }
            )
        return rows, suppressed

    def summary(self) -> dict[str, Any]:
        state = self._current()
        statuses = Counter(r.status for r in state.requests)
        return {
            "n_requests": len(state.requests),
            "n_synthetic": sum(r.synthetic for r in state.requests),
            "by_status": dict(statuses),
            "n_clusters": len(state.clusters),
        }
