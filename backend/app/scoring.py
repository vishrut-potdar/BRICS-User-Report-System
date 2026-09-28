"""Deterministic, auditable priority score. The LLM classifies and explains; it never computes or overrides this.

    Priority(c) = 100 × [w_D·Demand + w_N·Need + w_E·Equity + w_A·Alignment + w_U·Urgency] × Integrity(c)

Pure Python with no I/O, so every number on the dashboard can be reproduced from the inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

COMPONENTS: tuple[str, ...] = ("demand", "need", "equity", "alignment", "urgency")
ASPIRATIONAL_BONUS = 0.10
ALIGNMENT_VALUE = {"none": 1.0, "delayed": 0.5, "funded": 0.0}
MIN_REQUESTERS_TO_RANK = 3  # below this a cluster is "emerging", not ranked: one message is not demand
VOLUME_ONLY = "volume_only"


@dataclass(frozen=True)
class Weights:
    demand: float = 0.25
    need: float = 0.30
    equity: float = 0.20
    alignment: float = 0.15
    urgency: float = 0.10

    def as_dict(self) -> dict[str, float]:
        return {name: getattr(self, name) for name in COMPONENTS}

    def normalised(self) -> Weights:
        values = self.as_dict()
        if any(v < 0 or math.isnan(v) for v in values.values()):
            raise ValueError("weights must be non-negative numbers")
        total = sum(values.values())
        if total <= 0:
            raise ValueError("at least one weight must be positive")
        return Weights(**{name: v / total for name, v in values.items()})


PRESETS: dict[str, Weights] = {
    "balanced": Weights(),
    "equity_first": Weights(demand=0.15, need=0.25, equity=0.35, alignment=0.15, urgency=0.10),
}


@dataclass(frozen=True)
class DistrictContext:
    admin_code: str
    name: str
    population: int
    poverty: float  # MPI headcount ratio, 0-1
    aspirational: bool
    need: Mapping[str, float]  # sector -> raw deficit, 0-1 (higher = worse)
    synthetic: bool = False


@dataclass(frozen=True)
class ClusterInput:
    cluster_id: str
    admin_code: str
    sector: str
    n_messages: int
    n_requesters: int
    n_urgent: int
    integrity: float = 1.0


@dataclass(frozen=True)
class ScoredCluster:
    cluster_id: str
    rank: int
    score: float
    components: Mapping[str, float]
    contributions: Mapping[str, float] = field(default_factory=dict)  # weight × component, pre-integrity
    integrity: float = 1.0
    integrity_penalty: float = 0.0  # sum(contributions) × (1 − integrity)
    alignment_status: str = "none"
    robust: bool | None = None  # stays in the top k under ±20% weight changes; None outside the top k


def _minmax(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-12:
        return {key: 0.5 for key in values}
    return {key: (v - lo) / (hi - lo) for key, v in values.items()}


def alignment_status(planned: Mapping[tuple[str, str], str], cluster: ClusterInput) -> str:
    return planned.get((cluster.admin_code, cluster.sector), "none")


def compute_components(
    clusters: Sequence[ClusterInput],
    districts: Mapping[str, DistrictContext],
    planned: Mapping[tuple[str, str], str],
) -> dict[str, dict[str, float]]:
    """Each component is normalised to 0-1 within the state. Clusters in unknown districts are skipped."""
    known = [c for c in clusters if c.admin_code in districts]
    # People, not messages; log-dampened; per 10k residents so big cities don't win by size alone.
    demand = _minmax(
        {
            c.cluster_id: math.log1p(c.n_requesters) / max(districts[c.admin_code].population / 10_000, 1e-9)
            for c in known
        }
    )
    poverty = _minmax({code: d.poverty for code, d in districts.items()})
    need_by_sector: dict[str, dict[str, float]] = {}
    out: dict[str, dict[str, float]] = {}
    for c in known:
        district = districts[c.admin_code]
        if c.sector not in need_by_sector:
            need_by_sector[c.sector] = _minmax({code: d.need.get(c.sector, 0.0) for code, d in districts.items()})
        out[c.cluster_id] = {
            "demand": demand[c.cluster_id],
            "need": need_by_sector[c.sector][c.admin_code],
            "equity": min(1.0, poverty[c.admin_code] + (ASPIRATIONAL_BONUS if district.aspirational else 0.0)),
            "alignment": ALIGNMENT_VALUE[alignment_status(planned, c)],
            "urgency": min(1.0, c.n_urgent / c.n_messages) if c.n_messages else 0.0,
        }
    return out


def _order(components: Mapping[str, Mapping[str, float]], integrity: Mapping[str, float], weights: Weights) -> list[str]:
    w = weights.as_dict()
    score = {cid: sum(w[k] * comp[k] for k in COMPONENTS) * integrity[cid] for cid, comp in components.items()}
    return sorted(score, key=lambda cid: (-score[cid], cid))


def robust_ids(
    components: Mapping[str, Mapping[str, float]],
    integrity: Mapping[str, float],
    weights: Weights,
    top_k: int = 10,
    delta: float = 0.2,
) -> set[str]:
    """Clusters that stay in the top k when any single weight moves by ±delta (then renormalised)."""
    base = set(_order(components, integrity, weights)[:top_k])
    for name in COMPONENTS:
        for factor in (1 - delta, 1 + delta):
            values = weights.as_dict()
            values[name] *= factor
            base &= set(_order(components, integrity, Weights(**values).normalised())[:top_k])
    return base


def rank_clusters(
    clusters: Sequence[ClusterInput],
    districts: Mapping[str, DistrictContext],
    planned: Mapping[tuple[str, str], str],
    weights: Weights,
    *,
    sensitivity_top_k: int = 10,
    min_requesters: int = MIN_REQUESTERS_TO_RANK,
) -> list[ScoredCluster]:
    eligible = [c for c in clusters if c.admin_code in districts and c.n_requesters >= min_requesters]
    by_id = {c.cluster_id: c for c in eligible}
    weights = weights.normalised()
    components = compute_components(eligible, districts, planned)
    integrity = {cid: by_id[cid].integrity for cid in components}
    order = _order(components, integrity, weights)
    robust = robust_ids(components, integrity, weights, sensitivity_top_k) if sensitivity_top_k else None

    w = weights.as_dict()
    results = []
    for rank, cid in enumerate(order, start=1):
        cluster, comp = by_id[cid], components[cid]
        contributions = {k: w[k] * comp[k] for k in COMPONENTS}
        pre_integrity = sum(contributions.values())
        results.append(
            ScoredCluster(
                cluster_id=cid,
                rank=rank,
                score=round(100 * pre_integrity * cluster.integrity, 2),
                components={k: round(v, 4) for k, v in comp.items()},
                contributions={k: round(v, 4) for k, v in contributions.items()},
                integrity=cluster.integrity,
                integrity_penalty=round(pre_integrity * (1 - cluster.integrity), 4),
                alignment_status=alignment_status(planned, cluster),
                robust=(cid in robust) if robust is not None and rank <= sensitivity_top_k else None,
            )
        )
    return results
