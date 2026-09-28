import pytest

from app.scoring import (
    PRESETS, ClusterInput, DistrictContext, Weights, compute_components, rank_clusters,
)

DISTRICTS = {
    "RICH": DistrictContext("RICH", "Rich", 5_000_000, 0.05, False, {"water": 0.1, "roads": 0.1}),
    "MID": DistrictContext("MID", "Mid", 2_000_000, 0.15, False, {"water": 0.4, "roads": 0.3}),
    "POOR": DistrictContext("POOR", "Poor", 1_000_000, 0.35, True, {"water": 0.7, "roads": 0.6}),
}


def cluster(cid, code, sector="water", messages=10, requesters=10, urgent=0, integrity=1.0):
    return ClusterInput(cid, code, sector, messages, requesters, urgent, integrity)


def test_weights_normalise_and_validate():
    w = Weights(demand=2, need=2, equity=0, alignment=0, urgency=0).normalised()
    assert w.demand == pytest.approx(0.5) and w.need == pytest.approx(0.5)
    with pytest.raises(ValueError):
        Weights(demand=-1).normalised()
    with pytest.raises(ValueError):
        Weights(0, 0, 0, 0, 0).normalised()


def test_demand_counts_people_not_messages():
    # 500 messages from 10 phones must count for less than 50 messages from 50 phones.
    comps = compute_components(
        [cluster("spam", "MID", messages=500, requesters=10), cluster("real", "MID", messages=50, requesters=50)],
        DISTRICTS, {},
    )
    assert comps["real"]["demand"] > comps["spam"]["demand"]


def test_demand_is_per_capita():
    comps = compute_components(
        [cluster("big", "RICH", requesters=40), cluster("small", "POOR", requesters=40)], DISTRICTS, {}
    )
    assert comps["small"]["demand"] > comps["big"]["demand"]


def test_alignment_values():
    planned = {("RICH", "water"): "funded", ("MID", "water"): "delayed"}
    comps = compute_components(
        [cluster("a", "RICH"), cluster("b", "MID"), cluster("c", "POOR")], DISTRICTS, planned
    )
    assert (comps["a"]["alignment"], comps["b"]["alignment"], comps["c"]["alignment"]) == (0.0, 0.5, 1.0)


def test_equity_gets_aspirational_bonus_capped_at_one():
    comps = compute_components([cluster("p", "POOR")], DISTRICTS, {})
    assert comps["p"]["equity"] == 1.0  # max poverty (1.0) + bonus, capped


def test_integrity_scales_score_and_reports_penalty():
    clean = rank_clusters([cluster("x", "MID")], DISTRICTS, {}, Weights())[0]
    dirty = rank_clusters([cluster("x", "MID", integrity=0.5)], DISTRICTS, {}, Weights())[0]
    assert dirty.score == pytest.approx(clean.score / 2, abs=0.01)
    assert dirty.integrity_penalty == pytest.approx(sum(dirty.contributions.values()) / 2, abs=1e-3)


def test_waterfall_adds_up_to_score():
    for s in rank_clusters([cluster("a", "RICH"), cluster("b", "POOR", integrity=0.8)], DISTRICTS, {}, Weights()):
        assert s.score == pytest.approx(100 * (sum(s.contributions.values()) - s.integrity_penalty), abs=0.05)


def test_min_requesters_threshold_excludes_single_messages():
    ranked = rank_clusters([cluster("lone", "POOR", messages=1, requesters=1), cluster("ok", "MID")], DISTRICTS, {}, Weights())
    assert [s.cluster_id for s in ranked] == ["ok"]


def test_deterministic_and_tie_broken_by_id():
    clusters = [cluster("b", "MID"), cluster("a", "MID")]
    first = rank_clusters(clusters, DISTRICTS, {}, Weights())
    second = rank_clusters(list(reversed(clusters)), DISTRICTS, {}, Weights())
    assert [s.cluster_id for s in first] == [s.cluster_id for s in second] == ["a", "b"]


def test_equity_first_favours_poorer_district():
    clusters = [cluster("rich", "RICH", requesters=200, messages=200), cluster("poor", "POOR", requesters=5, messages=5)]
    ranked = rank_clusters(clusters, DISTRICTS, {}, PRESETS["equity_first"])
    assert ranked[0].cluster_id == "poor"


def test_sensitivity_marks_dominant_cluster_robust():
    clusters = [cluster(f"c{i}", "RICH", requesters=3) for i in range(12)] + [cluster("top", "POOR", requesters=50, urgent=10)]
    ranked = rank_clusters(clusters, DISTRICTS, {}, Weights(), sensitivity_top_k=10)
    assert ranked[0].cluster_id == "top" and ranked[0].robust is True
    assert all(s.robust is None for s in ranked[10:])
