from datetime import timedelta

from conftest import make_requests


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_meta_lists_presets(client):
    meta = client.get("/meta").json()
    assert set(meta["presets"]) == {"balanced", "equity_first", "volume_only"}
    assert meta["language_provider"] == "offline"


def test_ingest_resolves_district_from_text(client):
    response = client.post("/ingest", json={"text": "Hamare gaon mein handpump kharab hai, Nandurbar", "sender_id": "u1"})
    assert response.status_code == 201
    body = response.json()
    assert body["admin_code"] == "TS-NANDURBAR"
    assert body["category"] == "water"
    assert body["location_confidence"] == "C"
    assert body["status"] == "received"
    assert "requester_hash" not in body


def test_ingest_with_gps_gets_h3_cell(client):
    body = client.post("/ingest", json={"text": "Road pe gaddhe hain", "lat": 18.53, "lon": 73.85}).json()
    assert body["admin_code"] == "TS-PUNE" and body["h3"] and body["location_confidence"] == "A"


def test_ingest_requires_content(client):
    assert client.post("/ingest", json={}).status_code == 422
    assert client.post("/ingest", json={"audio_base64": "not base64!"}).status_code == 422


def seed(container):
    container.repo.add_many(
        make_requests("TS-PUNE", 18.52, 73.86, n=60, requesters=30, prefix="pune")
        + make_requests("TS-AURANGABAD", 19.88, 75.34, n=10, requesters=8, sector="roads", prefix="aur")
        + make_requests("TS-NANDURBAR", 21.37, 74.24, n=5, requesters=5, urgent=2, prefix="nan")
        + make_requests("TS-PUNE", 18.60, 73.70, n=200, requesters=12, sector="roads",
                        text="Station Road ka kaam turant karo!!", spread=timedelta(minutes=25), prefix="brig")
    )
    container.demand.invalidate()


def test_volume_only_vs_equity(client, container):
    seed(container)
    volume = client.get("/rankings", params={"preset": "volume_only"}).json()["items"]
    assert volume[0]["cluster_id"].startswith("TS-PUNE.roads")  # the brigade wins on raw volume
    balanced = client.get("/rankings").json()["items"]
    assert balanced[0]["admin_code"] == "TS-NANDURBAR"
    brigade = next(i for i in balanced if i["cluster_id"].startswith("TS-PUNE.roads"))
    assert brigade["integrity"]["multiplier"] == 0.5 and "burst" in brigade["integrity"]["flags"]
    assert {"components", "contributions", "integrity_penalty", "robust"} <= set(balanced[0])


def test_weight_overrides_and_validation(client, container):
    seed(container)
    response = client.get("/rankings", params={"preset": "balanced", "demand": 1, "need": 0, "equity": 0, "alignment": 0, "urgency": 0})
    assert response.json()["weights"]["demand"] == 1.0
    assert client.get("/rankings", params={"preset": "nope"}).status_code == 422


def test_compare_and_cluster_detail(client, container):
    seed(container)
    comparison = client.get("/rankings/compare", params={"a": "volume_only", "b": "equity_first", "k": 3}).json()
    assert comparison["b"]["in_poorest_quartile"] >= comparison["a"]["in_poorest_quartile"]
    cluster_id = comparison["b"]["top"][0]["cluster_id"]
    detail = client.get(f"/clusters/{cluster_id}").json()
    assert detail["status"] == "ranked" and len(detail["requests"]) == detail["n_messages"]
    assert client.get("/clusters/does-not-exist").status_code == 404


def test_export_suppresses_small_groups(client, container):
    seed(container)
    response = client.get("/export/aggregates.csv")
    assert response.status_code == 200
    assert "TS-NANDURBAR" in response.text  # 5 requesters meets the threshold of 5
    geojson = client.get("/export/aggregates.geojson", params={"level": "h3"}).json()
    assert geojson["features"] and geojson["features"][0]["geometry"]["type"] == "Polygon"
    container.repo.add_many(make_requests("TS-AURANGABAD", 19.9, 75.3, n=3, requesters=3, sector="health", prefix="tiny"))
    container.demand.invalidate()
    rows = client.get("/export/aggregates.csv").text
    assert "TS-AURANGABAD,Aurangabad,health" not in rows


def test_districts_and_silent(client, container):
    seed(container)
    districts = client.get("/districts").json()
    assert {d["admin_code"] for d in districts} == {"TS-PUNE", "TS-AURANGABAD", "TS-NANDURBAR"}
    silent = client.get("/districts/silent", params={"k": 1}).json()
    assert silent[0]["poverty"] >= 0.15


def test_whatsapp_webhook_verify_and_ingest(client, settings, container):
    assert client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "1"}).status_code == 403
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919800000000", "id": "m1", "type": "text", "text": {"body": "Kachra gaadi nahi aati, Aurangabad"}}
    ]}}]}]}
    assert client.post("/webhooks/whatsapp", json=payload).json() == {"status": "ok"}
    stored = container.repo.all()
    assert len(stored) == 1 and stored[0].channel == "whatsapp" and stored[0].geo.admin_code == "TS-AURANGABAD"
    assert "919800000000" not in stored[0].model_dump_json()


def test_dashboard_served_at_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Vikas Vaani" in response.text


def test_admin_dashboard_served(client):
    response = client.get("/admin")
    assert response.status_code == 200 and "Admin" in response.text
    assert client.get("/static/app.css").status_code == 200
