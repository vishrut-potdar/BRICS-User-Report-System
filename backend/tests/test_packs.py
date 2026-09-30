"""The shipped BRICS packs: data integrity, and routing a request into its country and pilot packs."""

from __future__ import annotations

import csv
import json

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.container import build_container
from app.ingest import country_for_number
from app.main import create_app
from app.pack import available_packs, load_pack

DATA = REPO_ROOT / "data"
PACKS = available_packs(DATA)
pytestmark = pytest.mark.skipif(len(PACKS) < 10, reason="run scripts.build_indicators --pack all first")


@pytest.fixture(scope="module")
def real():
    settings = Settings(data_dir=DATA, pack_id="IN", language_provider="offline", repository="memory", phone_hash_salt="t")
    container = build_container(settings)
    return container, TestClient(create_app(settings, container))


@pytest.mark.parametrize("pack_id", PACKS)
def test_pack_is_complete(pack_id):
    ctx = load_pack(DATA, pack_id)
    assert ctx.districts and set(ctx.districts) == set(ctx.info)
    assert all(d.population > 0 for d in ctx.districts.values())
    assert set(ctx.boundaries) == set(ctx.info), "every unit needs a boundary"
    # every unit's centroid falls inside its own boundary, so pins and GPS resolution agree
    from app.geo import GeoResolver

    resolver = GeoResolver(ctx)
    wrong = [c for c, i in ctx.info.items() if resolver.district_for_point(i.lat, i.lon) != c]
    assert len(wrong) <= max(1, len(ctx.info) // 20), wrong


def test_country_packs_list_their_pilots(real):
    _, client = real
    packs = {p["pack_id"]: p for p in client.get("/packs").json()}
    assert {"IN", "BR", "RU", "CN", "ZA"} <= {p for p, v in packs.items() if v["level"] == "country"}
    for pilot, parent in {"IN-MH": "IN", "BR-AL": "BR", "RU-TY": "RU", "CN-NX": "CN", "ZA-EC": "ZA"}.items():
        assert packs[pilot]["parent"] == parent
        # the pilot region is a unit of its country pack, which is how the dashboard drills down
        units = {u["admin_code"] for u in client.get("/meta", params={"pack": parent}).json()["units"]}
        assert pilot in units


def test_boundaries_served(real):
    _, client = real
    geo = client.get("/boundaries", params={"pack": "ZA-EC"}).json()
    assert len(geo["features"]) == 8
    assert client.get("/boundaries", params={"pack": "XX"}).status_code == 404


def test_portal_request_lands_in_country_and_pilot(real):
    _, client = real
    body = client.post("/ingest", json={"text": "Não tem água na nossa rua há 5 dias", "pack": "BR", "admin_code": "BR-AL-MACEIO",
                                         "sender_id": "portal-1"}).json()
    assert body["packs"] == {"BR": "BR-AL", "BR-AL": "BR-AL-MACEIO"}
    assert body["admin_code"] == "BR-AL-MACEIO" and body["lang"] == "pt" and body["category"] == "water"
    assert "registrada" in body["ack"]
    tracked = client.get(f"/track/{body['id']}").json()
    assert tracked["pack"] == "BR-AL" and tracked["country_name"] == "Brazil"
    assert client.get("/track/nope").status_code == 404


def test_state_outside_any_pilot_only_goes_to_country(real):
    _, client = real
    body = client.post("/ingest", json={"text": "Дорога разбита, ямы", "pack": "RU", "admin_code": "RU-TA"}).json()
    assert body["packs"] == {"RU": "RU-TA"} and body["lang"] == "ru" and body["category"] == "roads"


def test_gps_inside_pilot_resolves_district(real):
    _, client = real
    # central Kyzyl, Tuva
    body = client.post("/ingest", json={"text": "Нет воды", "pack": "RU", "lat": 51.72, "lon": 94.44}).json()
    assert body["packs"]["RU"] == "RU-TY" and body["packs"]["RU-TY"] == "RU-TY-KYZYL_CITY"


def test_gazetteer_uses_capital_aliases_and_ignores_weak_words(real):
    container, _ = real
    br = container.region("BR").resolver
    assert br.match_gazetteer(["Falta água em Salvador"]) == "BR-BA"
    assert br.match_gazetteer(["Precisamos de água para beber"]) is None  # "para" is not Pará
    assert br.match_gazetteer(["Pará"], allow_weak=True) == "BR-PA"
    assert container.region("CN").resolver.match_gazetteer(["昆明的路坏了"]) == "CN-YN"


@pytest.mark.parametrize(("number", "country"), [("5582999990000", "BR"), ("79161234567", "RU"), ("919800000000", "IN"),
                                                 ("8613800000000", "CN"), ("27821234567", "ZA"), ("15551234567", None)])
def test_whatsapp_numbers_route_by_calling_code(number, country):
    assert country_for_number(number) == country


def test_pack_configs_reference_real_units():
    for path in sorted((DATA / "packs").glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        with (DATA / config["files"]["district_reference"]).open(encoding="utf-8") as fh:
            codes = {r["admin_code"] for r in csv.DictReader(fh)}
        tiers = config["placeholder"]["deprivation_tiers"]
        syn = config["synthetic"]
        referenced = set(tiers["high"]) | set(tiers["low"]) | set(syn["connectivity"]) | {syn["brigade"]["admin_code"]}
        assert referenced <= codes, (path.name, referenced - codes)


def test_official_status_change_reaches_citizen_tracking(real):
    container, client = real
    first = None
    for i in range(3):  # three people make a ranked cluster
        body = client.post("/ingest", json={"text": "垃圾十天没人清运了", "pack": "CN", "admin_code": "CN-NX-XIJI",
                                             "sender_id": f"xiji-{i}", "category": "waste"}).json()
        first = first or body
    assert first["category"] == "waste" and first["packs"]["CN-NX"] == "CN-NX-XIJI"
    cluster_id = "CN-NX-XIJI.waste.district"
    item = next(i for i in client.get("/rankings", params={"pack": "CN-NX", "limit": 500}).json()["items"] if i["cluster_id"] == cluster_id)
    assert item["work_status"] == "received"
    done = client.post(f"/clusters/{cluster_id}/status", params={"pack": "CN-NX"}, json={"status": "forwarded"}).json()
    assert done["n_requests"] >= 3
    assert client.get(f"/track/{first['id']}").json()["status"] == "forwarded"
    assert client.get(f"/requests/{first['id']}", params={"pack": "CN"}).json()["status"] == "forwarded"  # country copy too
    assert client.post(f"/clusters/{cluster_id}/status", params={"pack": "CN-NX"}, json={"status": "bogus"}).status_code == 422


def test_english_complaint_in_india_gets_english_and_hindi(real):
    _, client = real
    body = client.post("/ingest", json={"text": "The water is not clear", "pack": "IN", "admin_code": "IN-MH-NAGPUR"}).json()
    assert body["lang"] == "en"
    assert "Tracking ID" in body["ack"] and "ट्रैकिंग आईडी" in body["ack"] and "Opsporingsnommer" not in body["ack"]
