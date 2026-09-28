from datetime import datetime, timedelta, timezone

from app.integrity import assess, duplicate_share

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_brigade_is_down_weighted_with_all_flags():
    n = 200
    report = assess(
        [f"s{i % 12}" for i in range(n)],
        [T0 + timedelta(seconds=i * 9) for i in range(n)],  # all inside 30 minutes
        ["Station Road ka widening kaam turant shuru karo" + ("!!" if i % 2 else " please") for i in range(n)],
    )
    assert report.multiplier == 0.5
    assert set(report.flags) == {"low_sender_diversity", "burst", "near_duplicate_text"}


def test_organic_cluster_is_not_penalised():
    texts = [
        "No water in our ward for five days", "Handpump broken near the school", "Tanker has not come this week",
        "Tap water is dirty and smells", "Borewell dried up in our lane", "Pipeline leak near the temple",
        "Water comes only at 3am for ten minutes", "Our tank is empty since Monday", "Please fix the village well",
        "Kids are falling sick from the water", "Supply stopped after the road work", "Only one tap for forty homes",
    ]
    report = assess([f"p{i}" for i in range(len(texts))], [T0 + timedelta(days=i) for i in range(len(texts))], texts)
    assert report.multiplier == 1.0 and report.flags == ()


def test_small_clusters_are_exempt():
    assert assess(["a", "a"], [T0, T0], ["same", "same"]).multiplier == 1.0


def test_duplicate_share_detects_near_copies():
    assert duplicate_share(["fix the road now!!", "fix the road now", "a completely different message"]) == 2 / 3
