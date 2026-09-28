"""Groups requests into demand clusters: same district, same sector, same H3 cell.

Requests located only to district level (confidence C) form one district-level cluster per sector.
Embedding-based sub-clustering within a cell is a planned refinement; the cluster ID format stays the same.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import h3

from .integrity import IntegrityReport, assess
from .models import CivicRequest
from .scoring import ClusterInput

INACTIVE_STATUSES = frozenset({"needs_review", "rejected", "resolved"})


def cluster_id_for(admin_code: str, sector: str, h3_cell: str | None) -> str:
    return f"{admin_code}.{sector}.{h3_cell or 'district'}"


def is_active(request: CivicRequest) -> bool:
    return request.status not in INACTIVE_STATUSES and bool(request.geo.admin_code)


@dataclass
class Cluster:
    cluster_id: str
    admin_code: str
    sector: str
    h3: str | None
    requests: list[CivicRequest]
    integrity: IntegrityReport = field(default_factory=IntegrityReport)

    @property
    def n_messages(self) -> int:
        return len(self.requests)

    @property
    def n_requesters(self) -> int:
        return len({r.requester_hash for r in self.requests})

    @property
    def n_urgent(self) -> int:
        return sum(r.urgency == "high" for r in self.requests)

    @property
    def synthetic_share(self) -> float:
        return sum(r.synthetic for r in self.requests) / len(self.requests) if self.requests else 0.0

    def centroid(self, fallback: tuple[float, float] | None = None) -> tuple[float, float] | None:
        if self.h3:
            return h3.cell_to_latlng(self.h3)
        return fallback

    def to_input(self) -> ClusterInput:
        return ClusterInput(
            cluster_id=self.cluster_id,
            admin_code=self.admin_code,
            sector=self.sector,
            n_messages=self.n_messages,
            n_requesters=self.n_requesters,
            n_urgent=self.n_urgent,
            integrity=self.integrity.multiplier,
        )


def build_clusters(requests: Iterable[CivicRequest]) -> list[Cluster]:
    groups: dict[tuple[str, str, str | None], list[CivicRequest]] = defaultdict(list)
    for request in requests:
        if not is_active(request):
            continue
        cell = request.geo.h3 if request.geo.confidence in ("A", "B") else None
        groups[(request.geo.admin_code, request.category, cell)].append(request)

    clusters = []
    for (admin_code, sector, cell), items in groups.items():
        items.sort(key=lambda r: r.created_at)
        report = assess(
            [r.requester_hash for r in items],
            [r.created_at for r in items],
            [r.text_original for r in items],
        )
        clusters.append(Cluster(cluster_id_for(admin_code, sector, cell), admin_code, sector, cell, items, report))
    return clusters
