"""Integrity multiplier (0.5-1.0): down-weights clusters that look coordinated rather than organic.

Three signals, each mapped to a 0-1 suspicion; the strongest one sets the penalty:
- sender concentration: few phone numbers sending many messages
- burstiness: most of the cluster arriving inside one 30-minute window
- near-duplicate text: copy-pasted messages
Nothing is deleted: the cluster stays visible with its flags, and a human decides.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

_WORD = re.compile(r"\w+")
MAX_PAIRWISE_TEXTS = 600


@dataclass(frozen=True)
class IntegrityReport:
    multiplier: float = 1.0
    sender_diversity: float = 1.0
    burst_share: float = 0.0
    duplicate_share: float = 0.0
    flags: tuple[str, ...] = ()


def _normalise(text: str) -> str:
    return " ".join(_WORD.findall(text.casefold()))


def _shingles(text: str, k: int = 3) -> frozenset[str]:
    return frozenset(text[i : i + k] for i in range(max(1, len(text) - k + 1)))


def duplicate_share(texts: Sequence[str], threshold: float = 0.85) -> float:
    """Share of messages whose text equals, or nearly equals (char-3gram Jaccard ≥ threshold), another's."""
    if not texts:
        return 0.0
    counts = Counter(_normalise(t) for t in texts)
    uniques = list(counts)
    duplicated = {u for u in uniques if counts[u] > 1}
    candidates = uniques[:MAX_PAIRWISE_TEXTS]
    shingles = {u: _shingles(u) for u in candidates}
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            if a in duplicated and b in duplicated:
                continue
            sa, sb = shingles[a], shingles[b]
            if len(sa & sb) / len(sa | sb) >= threshold:
                duplicated.update((a, b))
    return sum(counts[u] for u in duplicated) / len(texts)


def max_window_share(timestamps: Sequence[datetime], window: timedelta) -> float:
    times = sorted(timestamps)
    best, start = 0, 0
    for end, t in enumerate(times):
        while t - times[start] > window:
            start += 1
        best = max(best, end - start + 1)
    return best / len(times) if times else 0.0


def assess(
    requesters: Sequence[str],
    timestamps: Sequence[datetime],
    texts: Sequence[str],
    *,
    window: timedelta = timedelta(minutes=30),
    min_messages: int = 5,
) -> IntegrityReport:
    n = len(texts)
    if n < min_messages:
        return IntegrityReport()
    diversity = len(set(requesters)) / n
    burst = max_window_share(timestamps, window)
    dup = duplicate_share(texts)

    signals = {
        "low_sender_diversity": max(0.0, (0.7 - diversity) / 0.7),
        "burst": max(0.0, (burst - 0.5) / 0.5) if n >= 10 else 0.0,
        "near_duplicate_text": max(0.0, (dup - 0.5) / 0.5),
    }
    suspicion = min(1.0, max(signals.values()))
    return IntegrityReport(
        multiplier=round(1.0 - 0.5 * suspicion, 4),
        sender_diversity=round(diversity, 4),
        burst_share=round(burst, 4),
        duplicate_share=round(dup, 4),
        flags=tuple(name for name, value in signals.items() if value > 0),
    )
