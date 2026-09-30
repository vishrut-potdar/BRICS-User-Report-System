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
    "pt": ("Envie um texto ou áudio sobre um problema no seu bairro (água, ruas, saúde, escola, energia...). "
           "Diga o bairro ou povoado e o município. Seu número é guardado só como um código anônimo."),
    "ru": ("Отправьте текст или голосовое сообщение о проблеме в вашем районе (вода, дороги, здоровье, школа, свет...). "
           "Укажите населённый пункт и район. Ваш номер хранится только как анонимный код."),
    "zh": "请发送文字或语音，说明您所在地区的问题（饮水、道路、医疗、学校、电力等），并注明村或社区及所在县区。您的号码仅以匿名代码保存。",
    "af": ("Stuur 'n teks- of stemboodskap oor 'n probleem in jou gebied (water, paaie, gesondheid, skool, krag...). "
           "Noem jou dorp of wyk en munisipaliteit. Jou nommer word slegs as 'n anonieme kode gestoor."),
    "zu": ("Thumela umlayezo noma inothi lezwi mayelana nenkinga endaweni yakho (amanzi, imigwaqo, ezempilo, isikole, ugesi...). "
           "Sho igama lendawo nomasipala. Inombolo yakho igcinwa njengekhodi engaziwa kuphela."),
    "xh": ("Thumela umyalezo okanye inqaku lelizwi malunga nengxaki kwindawo yakho (amanzi, iindlela, impilo, isikolo, umbane...). "
           "Chaza igama lendawo nomasipala. Inombolo yakho igcinwa njengekhowudi engaziwayo kuphela."),
}
ACK = {
    "en": "Your request has been recorded. Tracking ID: {id}",
    "hi": "आपका अनुरोध दर्ज हो गया है। ट्रैकिंग आईडी: {id}",
    "hi-Latn": "Aapki request darj ho gayi hai. Tracking ID: {id}",
    "mr": "तुमची विनंती नोंदवली गेली आहे. ट्रॅकिंग आयडी: {id}",
    "pt": "Sua solicitação foi registrada. Número de acompanhamento: {id}",
    "ru": "Ваше обращение зарегистрировано. Номер для отслеживания: {id}",
    "zh": "您的诉求已登记。查询编号：{id}",
    "af": "Jou versoek is aangeteken. Opsporingsnommer: {id}",
    "zu": "Isicelo sakho sirekhodiwe. Inombolo yokulandelela: {id}",
    "xh": "Isicelo sakho sirekhodiwe. Inombolo yokulandelela: {id}",
}
ASK_LOCATION = {
    "en": "Which village or ward, and which district, is this about?",
    "hi": "यह किस गाँव या वार्ड और किस जिले के बारे में है?",
    "hi-Latn": "Yeh kis gaon ya ward, aur kis district ke baare mein hai?",
    "mr": "हे कोणत्या गावाबद्दल किंवा वॉर्डबद्दल आणि कोणत्या जिल्ह्याबद्दल आहे?",
    "pt": "Em qual bairro ou povoado, e em qual município, fica isso?",
    "ru": "В каком населённом пункте и районе это находится?",
    "zh": "请问这是在哪个村或社区、哪个县区？",
    "af": "In watter dorp of wyk, en watter munisipaliteit, is dit?",
    "zu": "Lokhu kukuphi, endaweni noma esigodini esiphi, kumasipala muphi?",
    "xh": "Oku kweyiphi indawo okanye ilali, kowuphi umasipala?",
}


def _pick(table: dict[str, str], lang: str) -> str:
    return table.get(lang) or table.get(lang.split("-")[0]) or table["en"]


def welcome_message(lang: str = "en") -> str:
    if lang == "en":
        return "\n\n".join(WELCOME[k] for k in ("mr", "hi", "en"))
    return _pick(WELCOME, lang)


def ack_message(request: CivicRequest, local_lang: str | None = None) -> str:
    """Reply in the citizen's language. An English (or unreadable) message also gets the country's main language,
    so a citizen in India who wrote in English sees the Hindi confirmation too."""
    langs = [request.lang]
    if request.lang in ("en", "und") and local_lang and local_lang.split("-")[0] != "en":
        langs.append(local_lang)
    lines = [_pick(ACK, lang).format(id=request.id) for lang in langs]
    if not request.geo.admin_code:
        lines += [_pick(ASK_LOCATION, lang) for lang in langs]
    return "\n".join(dict.fromkeys(lines))
