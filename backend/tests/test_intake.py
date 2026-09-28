import pytest

from app.channels import telegram, whatsapp
from app.channels.messages import ack_message
from app.language.offline import OfflineProvider, classify, detect_lang
from app.privacy import hash_requester, redact


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("आमच्या गावात दोन आठवड्यांपासून नळाला पाणी येत नाही.", "mr"),
        ("हमारे गाँव में हैंडपंप खराब है", "hi"),
        ("Hamare gaon mein teen mahine se handpump kharab hai", "hi-Latn"),
        ("No piped water supply in our ward", "en"),
    ],
)
def test_detect_lang(text, lang):
    assert detect_lang(text) == lang


@pytest.mark.parametrize(
    ("text", "sector"),
    [
        ("Hamare gaon mein handpump kharab hai", "water"),
        ("गावाकडे जाणारा रस्ता पूर्णपणे खड्ड्यांनी भरला आहे", "roads"),
        ("Transformer jal gaya hai, light nahi hai", "electricity"),
        ("Kachra gaadi aati hi nahi", "waste"),
        ("Something unrelated entirely", "other"),
    ],
)
def test_classify(text, sector):
    assert classify(text) == sector


def test_offline_provider_marks_untranslated_and_urgent():
    extraction = OfflineProvider().extract(text="Road pe gaddhe hain, ambulance nahi aa pati")
    assert extraction.text_en.startswith("[untranslated")
    assert extraction.urgency == "high"


def test_hash_is_stable_and_salted():
    assert hash_requester("whatsapp", "919800000000", "a") == hash_requester("whatsapp", " 919800000000 ", "a")
    assert hash_requester("whatsapp", "919800000000", "a") != hash_requester("whatsapp", "919800000000", "b")


def test_redact_removes_phone_email_and_id_numbers():
    text = redact("Call +91 98765 43210 or mail a.b@example.com, Aadhaar 1234 5678 9012. Road broken 5 days.")
    assert "98765" not in text and "example.com" not in text and "5678" not in text
    assert "Road broken 5 days" in text


def test_whatsapp_parse_and_signature():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "919800000000", "id": "m1", "type": "text", "text": {"body": "paani nahi hai"}},
        {"from": "919800000001", "id": "m2", "type": "audio", "audio": {"id": "media-1", "mime_type": "audio/ogg; codecs=opus"}},
        {"from": "919800000002", "id": "m3", "type": "sticker"},
    ]}}]}]}
    messages = whatsapp.parse_webhook(payload)
    assert [m.message_id for m in messages] == ["m1", "m2"]
    assert messages[1].media_id == "media-1"
    import hashlib, hmac
    body = b'{"x":1}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert whatsapp.verify_signature("secret", body, signature)
    assert not whatsapp.verify_signature("secret", body, "sha256=bad")


def test_telegram_parse_voice():
    message = telegram.parse_update({"message": {"message_id": 5, "from": {"id": 42}, "chat": {"id": 42},
                                                 "voice": {"file_id": "f1", "mime_type": "audio/ogg"}}})
    assert message and message.media_id == "f1" and message.reply_to == "42"


def test_ack_asks_for_location_when_unresolved(container):
    request = container.ingest.ingest(channel="web", sender_id="u1", text="Paani nahi aa raha hai 5 din se")
    assert request.status == "needs_review"
    assert "district" in ack_message(request)
