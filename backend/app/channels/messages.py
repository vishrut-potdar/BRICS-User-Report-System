"""Citizen-facing replies in the requester's language. Keep them short: they are read on a phone."""

from __future__ import annotations

from ..models import CivicRequest

WELCOME = {
    "en": ("Send a text or voice note about a problem in your area (water, roads, health, school, power...). "
           "Mention your village or ward and district. Your number is stored only as an anonymous code, "
           "and messages are used to plan public works."),
    "hi": ("अपने इलाके की समस्या (पानी, सड़क, स्वास्थ्य, स्कूल, बिजली...) के बारे में टेक्स्ट या वॉइस नोट भेजें। "
           "गाँव या वार्ड और जिले का नाम बताएं। आपका नंबर केवल एक गुमनाम कोड के रूप में रखा जाता है।"),
    "mr": ("तुमच्या भागातील समस्येबद्दल (पाणी, रस्ते, आरोग्य, शाळा, वीज...) मजकूर किंवा व्हॉइस नोट पाठवा. "
           "गाव किंवा वॉर्ड आणि जिल्ह्याचे नाव सांगा. तुमचा नंबर फक्त निनावी कोड म्हणून ठेवला जातो."),
}
ACK = {
    "en": "Your request has been recorded. Tracking ID: {id}",
    "hi": "आपका अनुरोध दर्ज हो गया है। ट्रैकिंग आईडी: {id}",
    "hi-Latn": "Aapki request darj ho gayi hai. Tracking ID: {id}",
    "mr": "तुमची विनंती नोंदवली गेली आहे. ट्रॅकिंग आयडी: {id}",
}
ASK_LOCATION = {
    "en": "Which village or ward, and which district, is this about?",
    "hi": "यह किस गाँव या वार्ड और किस जिले के बारे में है?",
    "hi-Latn": "Yeh kis gaon ya ward, aur kis district ke baare mein hai?",
    "mr": "हे कोणत्या गावाबद्दल किंवा वॉर्डबद्दल आणि कोणत्या जिल्ह्याबद्दल आहे?",
}


def _pick(table: dict[str, str], lang: str) -> str:
    return table.get(lang) or table.get(lang.split("-")[0]) or table["en"]


def welcome_message(lang: str = "en") -> str:
    if lang == "en":
        return "\n\n".join(WELCOME[k] for k in ("mr", "hi", "en"))
    return _pick(WELCOME, lang)


def ack_message(request: CivicRequest) -> str:
    message = _pick(ACK, request.lang).format(id=request.id)
    if not request.geo.admin_code:
        message += "\n" + _pick(ASK_LOCATION, request.lang)
    return message
