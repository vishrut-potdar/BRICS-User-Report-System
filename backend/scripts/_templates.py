"""Phrase bank for the offline synthetic generator: (text, English gloss, urgency) per sector and language.

{n} is filled with a small number so messages vary. Keep entries short and plausible; every generated record
is labelled synthetic. A Gemini-generated set can replace this for more natural variety.
"""

from __future__ import annotations

Template = tuple[str, str | None, str]  # text, English (None = same as text), urgency

TEMPLATES: dict[str, dict[str, list[Template]]] = {
    "water": {
        "hi": [
            ("हमारे गाँव में {n} दिन से हैंडपंप खराब है, पीने का पानी नहीं मिल रहा।", "The handpump in our village has been broken for {n} days; we are not getting drinking water.", "medium"),
            ("नल में {n} दिन से गंदा पानी आ रहा है, बच्चे बीमार हो रहे हैं।", "Dirty water has been coming from the tap for {n} days; children are falling ill.", "high"),
        ],
        "mr": [
            ("आमच्या गावात {n} दिवसांपासून नळाला पाणी येत नाही.", "There has been no water in the taps in our village for {n} days.", "medium"),
            ("टँकर आठवड्यातून एकदाच येतो, पिण्याच्या पाण्याची मोठी टंचाई आहे.", "The tanker comes only once a week; there is a severe drinking-water shortage.", "medium"),
        ],
        "hi-Latn": [
            ("Hamare mohalle mein {n} din se paani nahi aa raha, tanker bhi nahi aata", "No water in our neighbourhood for {n} days, and no tanker comes either.", "medium"),
            ("Handpump {n} hafte se kharab hai, auraton ko door se paani laana padta hai", "The handpump has been broken for {n} weeks; women have to fetch water from far away.", "medium"),
        ],
        "en": [
            ("No piped water supply in our ward for {n} days.", None, "medium"),
            ("The only borewell in our hamlet has dried up and there is no tanker.", None, "medium"),
        ],
    },
    "sanitation": {
        "hi": [
            ("हमारी बस्ती में सार्वजनिक शौचालय नहीं है, महिलाओं को बहुत परेशानी होती है।", "There is no public toilet in our settlement; women face great difficulty.", "medium"),
            ("नाली {n} दिन से जाम है और गंदा पानी घरों में घुस रहा है।", "The drain has been blocked for {n} days and dirty water is entering homes.", "high"),
        ],
        "mr": [
            ("आमच्या वस्तीतील गटार उघडे आहे आणि सगळीकडे दुर्गंधी पसरली आहे.", "The drain in our settlement is open and the stench has spread everywhere.", "medium"),
            ("सार्वजनिक स्वच्छतागृह {n} महिन्यांपासून बंद आहे.", "The public toilet has been closed for {n} months.", "medium"),
        ],
        "hi-Latn": [
            ("Gutter {n} din se overflow ho raha hai, bachche beemar pad rahe hain", "The drain has been overflowing for {n} days; children are falling sick.", "high"),
            ("Basti mein ek bhi public toilet nahi hai", "There is not a single public toilet in the settlement.", "medium"),
        ],
        "en": [
            ("The drain near the market is blocked and overflowing onto the road.", None, "medium"),
            ("Sewage has been flowing in the open near our homes for {n} days.", None, "high"),
        ],
    },
    "roads": {
        "hi": [
            ("गाँव से मुख्य सड़क तक पक्की सड़क नहीं है, बारिश में रास्ता बंद हो जाता है।", "There is no paved road from the village to the main road; it gets cut off in the rains.", "medium"),
            ("सड़क पर इतने गड्ढे हैं कि {n} हादसे हो चुके हैं।", "There are so many potholes on the road that {n} accidents have already happened.", "high"),
        ],
        "mr": [
            ("गावाकडे जाणारा रस्ता पूर्णपणे खड्ड्यांनी भरला आहे.", "The road to the village is completely full of potholes.", "medium"),
            ("पावसाळ्यात पूल पाण्याखाली जातो आणि गावाचा संपर्क {n} दिवस तुटतो.", "In the monsoon the bridge goes under water and the village is cut off for {n} days.", "high"),
        ],
        "hi-Latn": [
            ("Road pe itne gaddhe hain ki ambulance bhi nahi aa pati", "There are so many potholes on the road that even an ambulance can't get through.", "high"),
            ("Gaon tak pakki sadak nahi hai, {n} km kachcha rasta hai", "There is no paved road to the village; {n} km is a dirt track.", "medium"),
        ],
        "en": [
            ("The bridge on the village road collapsed during the monsoon.", None, "high"),
            ("The road to the school has been dug up and left unfinished for {n} months.", None, "medium"),
        ],
    },
    "health": {
        "hi": [
            ("प्राथमिक स्वास्थ्य केंद्र में डॉक्टर हफ्ते में सिर्फ एक दिन आते हैं।", "The doctor comes to the primary health centre only one day a week.", "medium"),
            ("अस्पताल {n} किलोमीटर दूर है और एम्बुलेंस नहीं आती।", "The hospital is {n} km away and no ambulance comes.", "high"),
        ],
        "mr": [
            ("आमच्या गावाजवळ आरोग्य केंद्र नाही, दवाखान्यासाठी {n} किमी जावे लागते.", "There is no health centre near our village; we have to travel {n} km to a clinic.", "medium"),
            ("आरोग्य केंद्रात {n} दिवसांपासून औषधे नाहीत.", "The health centre has had no medicines for {n} days.", "medium"),
        ],
        "hi-Latn": [
            ("PHC mein {n} din se dawai khatam hai, sab ko private clinic jana pad raha hai", "The PHC has been out of medicines for {n} days; everyone has to go to a private clinic.", "medium"),
            ("Raat ko koi doctor nahi hota, delivery ke liye {n} km jaana padta hai", "There is no doctor at night; for a delivery we have to travel {n} km.", "high"),
        ],
        "en": [
            ("The nearest health centre has no ambulance.", None, "high"),
            ("The sub-centre has been locked for {n} weeks and the nurse has not come.", None, "medium"),
        ],
    },
    "education": {
        "hi": [
            ("सरकारी स्कूल में लड़कियों के लिए अलग शौचालय नहीं है।", "The government school has no separate toilet for girls.", "medium"),
            ("स्कूल की छत टूटी है, बारिश में कक्षाएं बंद रहती हैं।", "The school roof is broken; classes stop when it rains.", "medium"),
        ],
        "mr": [
            ("शाळेच्या इमारतीचे छप्पर गळते, मुलांना बसायला जागा नाही.", "The school building roof leaks; the children have no place to sit.", "medium"),
            ("शाळेत {n} वर्गांसाठी फक्त एक शिक्षक आहे.", "The school has only one teacher for {n} classes.", "low"),
        ],
        "hi-Latn": [
            ("School mein sirf ek teacher hai {n} classes ke liye", "The school has only one teacher for {n} classes.", "low"),
            ("School mein peene ka paani aur bijli dono nahi hain", "The school has neither drinking water nor electricity.", "low"),
        ],
        "en": [
            ("The primary school has no electricity or drinking water.", None, "low"),
            ("The anganwadi building has cracks in the walls and is unsafe for the children.", None, "high"),
        ],
    },
    "electricity": {
        "hi": [
            ("हमारे गाँव में रोज़ {n} घंटे बिजली कटौती होती है।", "Our village has {n} hours of power cuts every day.", "low"),
            ("ट्रांसफार्मर {n} दिन से जला हुआ है, पूरा मोहल्ला अंधेरे में है।", "The transformer has been burnt out for {n} days; the whole neighbourhood is in darkness.", "medium"),
        ],
        "mr": [
            ("आमच्या वस्तीत अजूनही वीज जोडणी मिळालेली नाही.", "Our settlement still has not received an electricity connection.", "medium"),
            ("रस्त्यावरचे दिवे {n} महिन्यांपासून बंद आहेत, रात्री भीती वाटते.", "The street lights have been off for {n} months; it feels unsafe at night.", "high"),
        ],
        "hi-Latn": [
            ("Transformer jal gaya hai {n} din se, light nahi hai", "The transformer burnt out {n} days ago; there is no power.", "medium"),
            ("Bijli ke taar neeche latak rahe hain, kabhi bhi current lag sakta hai", "Electric wires are hanging low; someone could get a shock any time.", "high"),
        ],
        "en": [
            ("Street lights on the main road have not worked for months; it is unsafe at night.", None, "high"),
            ("Our hamlet gets power for only {n} hours a day.", None, "low"),
        ],
    },
    "waste": {
        "hi": [
            ("मोहल्ले में कचरा {n} दिन से नहीं उठाया गया है।", "Garbage in the neighbourhood has not been collected for {n} days.", "low"),
            ("खुले में कचरा जलाया जा रहा है, सांस लेना मुश्किल है।", "Garbage is being burnt in the open; it is hard to breathe.", "medium"),
        ],
        "mr": [
            ("रस्त्यावर कचऱ्याचे ढीग साचले आहेत, घंटागाडी येत नाही.", "Heaps of garbage have piled up on the road; the garbage van doesn't come.", "low"),
            ("घंटागाडी {n} दिवसांपासून आलेली नाही.", "The garbage van has not come for {n} days.", "low"),
        ],
        "hi-Latn": [
            ("Kachra gaadi aati hi nahi, sab log naale mein kachra daal rahe hain", "The garbage van never comes; everyone is dumping waste in the drain.", "low"),
            ("{n} din se kachra nahi utha, badbu aur machhar badh gaye hain", "Garbage hasn't been picked up for {n} days; the smell and mosquitoes have increased.", "medium"),
        ],
        "en": [
            ("Garbage has not been collected in our lane for {n} days.", None, "low"),
            ("An open dump next to the school is attracting stray dogs.", None, "medium"),
        ],
    },
}

OPENERS: dict[str, list[str]] = {
    "en": ["", "", "Sir,", "Respected officer,", "Hello,"],
    "hi": ["", "", "नमस्ते,", "सर,", "महोदय,"],
    "mr": ["", "", "नमस्कार,", "साहेब,", "महोदय,"],
    "hi-Latn": ["", "", "Namaste sir,", "Sir ji,", "Hello,"],
}
CLOSERS: dict[str, list[str]] = {
    "en": ["", "Please help.", "Kindly take action soon.", "This is a long-pending issue.", "Many families are affected."],
    "hi": ["", "कृपया मदद करें।", "जल्दी कार्रवाई करें।", "यह समस्या बहुत पुरानी है।", "कई परिवार परेशान हैं।"],
    "mr": ["", "कृपया मदत करा.", "लवकर कारवाई करावी.", "ही समस्या खूप जुनी आहे.", "अनेक कुटुंबांना त्रास होत आहे."],
    "hi-Latn": ["", "please help karo", "jaldi kuch karo", "bahut purani problem hai", "plz dekhiye", "sab pareshan hain"],
}
LANDMARKS: dict[str, list[tuple[str, str]]] = {
    "en": [("near the old bus stand", "near the old bus stand"), ("behind the gram panchayat office", "behind the gram panchayat office"),
           ("next to the primary school", "next to the primary school"), ("on the market road", "on the market road")],
    "hi": [("पुराने बस स्टैंड के पास", "near the old bus stand"), ("ग्राम पंचायत कार्यालय के पीछे", "behind the gram panchayat office"),
           ("प्राथमिक स्कूल के बगल में", "next to the primary school"), ("मंडी रोड पर", "on the market road")],
    "mr": [("जुन्या बस स्थानकाजवळ", "near the old bus stand"), ("ग्रामपंचायत कार्यालयामागे", "behind the gram panchayat office"),
           ("प्राथमिक शाळेशेजारी", "next to the primary school"), ("बाजार रस्त्यावर", "on the market road")],
    "hi-Latn": [("purane bus stand ke paas", "near the old bus stand"), ("panchayat office ke peeche", "behind the gram panchayat office"),
                ("primary school ke bagal mein", "next to the primary school"), ("mandi road pe", "on the market road")],
}
DISTRICT_ONLY: dict[str, str] = {"en": "({d})", "hi": "({d})", "mr": "({d})", "hi-Latn": "({d})"}

# The planted brigading attack: near-identical messages from a handful of numbers in 30 minutes.
BRIGADE: dict[str, tuple[str, str]] = {
    "hi-Latn": ("Station Road ka widening kaam turant shuru karo, yeh sabse zaroori kaam hai",
                "Start the Station Road widening work immediately; this is the most important work."),
}
BRIGADE_SUFFIXES = ["", "!!", "!!!", " please", " sir please", " 🙏"]

# Brazil, Russia, China and South Africa phrases live in their own file; merge them in.
from scripts import _templates_brics as _brics  # noqa: E402

for _sector, _by_lang in _brics.TEMPLATES.items():
    TEMPLATES[_sector].update(_by_lang)
OPENERS.update(_brics.OPENERS)
CLOSERS.update(_brics.CLOSERS)
LANDMARKS.update(_brics.LANDMARKS)
DISTRICT_ONLY.update(_brics.DISTRICT_ONLY)
BRIGADE.update(_brics.BRIGADE)
DETAILS = _brics.DETAILS
