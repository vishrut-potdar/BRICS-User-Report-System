"""Maps (place search, complaint points) and the generative AI assist features, with no network calls."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import assist
from app.config import REPO_ROOT, Settings
from app.container import build_container
from app.geocode import Geocoder, GeocodeHit
from app.language import ExtractionError, OfflineProvider
from app.main import create_app
from app.models import CivicRequest
from app.pack import available_packs

DATA = REPO_ROOT / "data"
pytestmark = pytest.mark.skipif(len(available_packs(DATA)) < 10, reason="run scripts.build_indicators --pack all first")


class FakeGeocoder(Geocoder):
    """Knows two places; records what it was asked."""

    PLACES = {"sitabuldi": GeocodeHit(21.1466, 79.0849, True, "Sitabuldi, Nagpur, Maharashtra, India"),
              "jatiúca": GeocodeHit(-9.6435, -35.7072, True, "Jatiúca, Maceió, Alagoas, Brasil")}

    def __init__(self):
        super().__init__("none")
        self.name = "fake"
        self.queries: list[tuple[str, str, str | None]] = []

    def geocode(self, query, country, region=None):
        self.queries.append((query, country, region))
        return next((hit for key, hit in self.PLACES.items() if key in query.casefold()), None)


@pytest.fixture(scope="module")
def app_parts():
    settings = Settings(data_dir=DATA, pack_id="IN", language_provider="offline", repository="memory",
                        phone_hash_salt="t", geocoder="none", google_maps_browser_key=None)
    container = build_container(settings)
    container.geocoder = FakeGeocoder()  # before any region loads, so every resolver uses it
    for pack in ("IN-MH", "BR-AL"):  # the shipped synthetic complaints, so there is something to rank and brief
        path = DATA / "synthetic" / pack / "requests.jsonl"
        with path.open(encoding="utf-8") as fh:
            container.region(pack).repo.add_many(CivicRequest.model_validate_json(line) for line in fh)
        container.region(pack).demand.invalidate()
    return container, TestClient(create_app(settings, container))


def test_config_reports_osm_and_offline_without_keys(app_parts):
    _, client = app_parts
    config = client.get("/config").json()
    assert config["maps"] == {"provider": "osm", "browser_key": None}
    assert config["ai"] == {"provider": "offline", "enabled": False}


def test_geocode_preview_searches_within_the_picked_area(app_parts):
    container, client = app_parts
    hit = client.get("/geocode", params={"q": "Sitabuldi", "pack": "IN", "admin_code": "IN-MH-NAGPUR"}).json()
    assert hit["admin_code"] == "IN-MH-NAGPUR" and hit["district"] == "Nagpur"
    query, country, region = container.geocoder.queries[-1]
    assert country == "IN" and region == "Maharashtra" and "Nagpur" in query  # narrowed to the pilot state and district
    assert client.get("/geocode", params={"q": "Nowhere at all", "pack": "IN"}).status_code == 404


def test_typed_location_gives_an_exact_point(app_parts):
    _, client = app_parts
    body = client.post("/ingest", json={"text": "Buraco na rua", "pack": "BR", "admin_code": "BR-AL-MACEIO",
                                         "location_text": "Jatiúca"}).json()
    assert body["location_confidence"] == "B" and body["h3"] and body["admin_code"] == "BR-AL-MACEIO"


def test_pin_placed_by_citizen_is_confidence_b(app_parts):
    _, client = app_parts
    body = client.post("/ingest", json={"text": "No water", "pack": "IN", "admin_code": "IN-MH-NAGPUR",
                                         "lat": 21.15, "lon": 79.08, "location_confidence": "B"}).json()
    assert body["location_confidence"] == "B" and body["admin_code"] == "IN-MH-NAGPUR"


def test_points_are_rounded_and_filtered(app_parts):
    _, client = app_parts
    data = client.get("/points", params={"pack": "BR-AL", "admin_code": "BR-AL-MACEIO"}).json()
    assert data["fields"] == ["lat", "lon", "sector", "urgency", "status", "admin_code"] and data["points"]
    assert {row[5] for row in data["points"]} == {"BR-AL-MACEIO"}
    for lat, lon, *_ in data["points"][:50]:
        assert round(lat, 3) == lat and round(lon, 3) == lon


def test_understand_reads_a_draft(app_parts):
    _, client = app_parts
    body = client.post("/assist/understand", json={"text": "Não tem água na nossa rua há 5 dias", "pack": "BR"}).json()
    assert body["ai"] is False and body["lang"] == "pt" and body["category"] == "water"


def test_briefs_fall_back_to_templates_without_gemini(app_parts):
    _, client = app_parts
    top = client.get("/rankings", params={"pack": "IN-MH", "limit": 1}).json()["items"][0]
    brief = client.post("/assist/brief", json={"pack": "IN-MH", "cluster_id": top["cluster_id"]}).json()
    assert brief["ai"] is False and brief["scope"] == "cluster" and top["district"] in brief["text"]
    area = client.post("/assist/brief", json={"pack": "IN-MH"}).json()
    assert area["scope"] == "area" and "Maharashtra" in area["text"]
    assert client.post("/assist/brief", json={"pack": "IN-MH", "cluster_id": "nope"}).status_code == 404


class FakeGemini(OfflineProvider):
    name = "gemini"

    def __init__(self, fail=False):
        super().__init__()
        self.fail, self.prompts = fail, []

    def write(self, prompt, *, max_tokens=700):
        self.prompts.append(prompt)
        if self.fail:
            raise ExtractionError("quota")
        return "AI briefing text"


def test_gemini_brief_is_grounded_and_falls_back_on_error(app_parts):
    container, _ = app_parts
    region = container.region("IN-MH")
    view = region.demand.cluster(region.demand.rankings(None, limit=1)[0]["cluster_id"], __import__("app.scoring").scoring.PRESETS["balanced"])
    ai = FakeGemini()
    out = assist.cluster_brief(ai, view, "Maharashtra", "hi")
    assert out == {"ai": True, "provider": "gemini", "lang": "hi", "text": "AI briefing text"}
    prompt = ai.prompts[0]
    assert "Write in Hindi" in prompt and "Do not rank" in prompt and view["district"] in prompt
    assert "requester_hash" not in prompt  # only redacted summaries and score inputs go to the model
    assert assist.cluster_brief(FakeGemini(fail=True), view, "Maharashtra")["ai"] is False


def _mock_client(payload, seen):
    import httpx

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_nominatim_parsing_and_policy_headers():
    seen = []
    payload = [{"lat": "21.148", "lon": "79.084", "addresstype": "historic", "type": "fort", "display_name": "Sitabuldi Fort, Nagpur"}]
    geocoder = Geocoder("nominatim", http=_mock_client(payload, seen))
    hit = geocoder.geocode("Sitabuldi, Nagpur", "IN", "Maharashtra")
    assert hit == GeocodeHit(21.148, 79.084, True, "Sitabuldi Fort, Nagpur")
    params = seen[0].url.params
    assert params["countrycodes"] == "in" and "Maharashtra" in params["q"]
    assert geocoder.geocode("sitabuldi,  nagpur", "IN", "Maharashtra") == hit and len(seen) == 1  # cached
    coarse = Geocoder("nominatim", http=_mock_client([{"lat": "19", "lon": "75", "addresstype": "state", "display_name": "Maharashtra"}], []))
    assert coarse.geocode("Maharashtra", "IN").precise is False


def test_google_parsing_and_auto_selection():
    seen = []
    payload = {"status": "OK", "results": [{"geometry": {"location": {"lat": -9.64, "lng": -35.7}}, "types": ["neighborhood"],
                                            "formatted_address": "Jatiúca, Maceió - AL"}]}
    geocoder = Geocoder("auto", google_key="k", http=_mock_client(payload, seen))
    assert geocoder.name == "google"
    hit = geocoder.geocode("Jatiúca", "BR", "Alagoas")
    assert hit.precise and hit.lat == -9.64 and "administrative_area:Alagoas" in seen[0].url.params["components"]
    assert Geocoder("auto").name == "nominatim" and Geocoder("none").geocode("x", "IN") is None
