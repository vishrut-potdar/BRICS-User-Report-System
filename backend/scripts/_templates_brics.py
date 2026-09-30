"""Phrase bank for the Brazil, Russia, China and South Africa packs, in the same shape as _templates.py.

Short, plain sentences a resident might send. Every generated record is labelled synthetic.
"""

from __future__ import annotations

Template = tuple[str, str | None, str]  # text, English (None = same as text), urgency

TEMPLATES: dict[str, dict[str, list[Template]]] = {
    "water": {
        "pt": [
            ("Estamos sem água na torneira há {n} dias.", "We have had no water from the tap for {n} days.", "medium"),
            ("O caminhão-pipa só vem uma vez por semana e a água não dá.", "The water truck only comes once a week and the water is not enough.", "medium"),
        ],
        "ru": [
            ("В нашем посёлке уже {n} дней нет воды.", "Our settlement has had no water for {n} days.", "medium"),
            ("Вода из колонки грязная, дети болеют.", "The water from the standpipe is dirty; the children are falling ill.", "high"),
        ],
        "zh": [
            ("我们村已经停水{n}天了，吃水很困难。", "Our village has had no water for {n} days; drinking water is hard to get.", "medium"),
            ("自来水发黄有异味，孩子们喝了生病。", "The tap water is yellow and smells; children fall ill after drinking it.", "high"),
        ],
        "af": [
            ("Ons het al {n} dae geen water in die krane nie.", "We have had no water in the taps for {n} days.", "medium"),
            ("Die watertenk kom net een keer per week.", "The water tanker comes only once a week.", "medium"),
        ],
        "zu": [
            ("Akukho manzi emapompini ethu izinsuku ezingu-{n}.", "There has been no water in our taps for {n} days.", "medium"),
            ("Amanzi angcolile, izingane ziyagula.", "The water is dirty; the children are getting sick.", "high"),
        ],
        "xh": [
            ("Akukho manzi kwiimpompo zethu iintsuku ezi-{n}.", "There has been no water in our taps for {n} days.", "medium"),
            ("Amanzi amdaka, abantwana bayagula.", "The water is dirty; the children are getting sick.", "high"),
        ],
    },
    "sanitation": {
        "pt": [
            ("O esgoto está correndo a céu aberto na nossa rua.", "Sewage is running in the open on our street.", "high"),
            ("Nossa comunidade não tem banheiro público nem rede de esgoto.", "Our community has no public toilet or sewer network.", "medium"),
        ],
        "ru": [
            ("Канализацию прорвало {n} дней назад, стоки текут по улице.", "The sewer burst {n} days ago; waste water is running down the street.", "high"),
            ("В школе до сих пор туалет на улице.", "The school still has an outdoor toilet.", "medium"),
        ],
        "zh": [
            ("村里没有卫生厕所，污水直接排到路边。", "The village has no sanitary toilets; waste water runs straight onto the roadside.", "medium"),
            ("下水道堵了{n}天，污水流进院子。", "The drain has been blocked for {n} days and sewage is flowing into the yards.", "high"),
        ],
        "af": [
            ("Die riool loop al {n} dae oop in ons straat.", "Sewage has been running open in our street for {n} days.", "high"),
            ("Ons gebruik nog steeds emmertoilette.", "We are still using bucket toilets.", "medium"),
        ],
        "zu": [
            ("Amanzi angcolile agcwele umgwaqo wethu izinsuku ezingu-{n}.", "Sewage has filled our street for {n} days.", "high"),
            ("Asinazo izindlu zangasese ezifanele endaweni yethu.", "We have no proper toilets in our area.", "medium"),
        ],
        "xh": [
            ("Amanzi amdaka aqhuma esitratweni sethu iintsuku ezi-{n}.", "Sewage has been overflowing in our street for {n} days.", "high"),
            ("Asinazo izindlu zangasese ezifanelekileyo kule lali.", "There are no proper toilets in this village.", "medium"),
        ],
    },
    "roads": {
        "pt": [
            ("A estrada para o povoado está cheia de buracos, a ambulância não passa.", "The road to the village is full of potholes; the ambulance cannot get through.", "high"),
            ("Nossa rua não tem calçamento e vira lama quando chove.", "Our street is unpaved and turns to mud when it rains.", "medium"),
        ],
        "ru": [
            ("Дорога до райцентра разбита, ямы глубиной по колено.", "The road to the district centre is broken up, with knee-deep potholes.", "medium"),
            ("Мост через реку аварийный, по нему опасно ездить.", "The bridge over the river is unsafe to drive on.", "high"),
        ],
        "zh": [
            ("村里的路坑坑洼洼，下雨就走不了。", "The village road is full of potholes and impassable when it rains.", "medium"),
            ("桥已经裂开{n}个月了，没人修，很危险。", "The bridge has been cracked for {n} months and nobody fixes it; it is dangerous.", "high"),
        ],
        "af": [
            ("Die pad na ons dorp is vol slaggate.", "The road to our town is full of potholes.", "medium"),
            ("Die grondpad spoel weg elke keer as dit reën.", "The gravel road washes away every time it rains.", "medium"),
        ],
        "zu": [
            ("Umgwaqo oya esigodini sethu unezimbobo eziningi.", "The road to our village has many potholes.", "medium"),
            ("Ibhuloho liwile, izingane azikwazi ukuya esikoleni.", "The bridge has collapsed; the children cannot get to school.", "high"),
        ],
        "xh": [
            ("Indlela eya elalini yethu inemingxuma emininzi.", "The road to our village has many potholes.", "medium"),
            ("Ibhulorho yawa, abantwana abakwazi ukuya esikolweni.", "The bridge collapsed; the children cannot get to school.", "high"),
        ],
    },
    "health": {
        "pt": [
            ("O posto de saúde está sem médico há {n} semanas.", "The health post has had no doctor for {n} weeks.", "medium"),
            ("Falta remédio no posto e o hospital fica a {n} km.", "The health post has no medicine and the hospital is {n} km away.", "high"),
        ],
        "ru": [
            ("ФАП в нашем селе закрыт, до больницы {n} км.", "The medical post in our village is closed; the hospital is {n} km away.", "high"),
            ("Врач приезжает только раз в месяц.", "The doctor comes only once a month.", "medium"),
        ],
        "zh": [
            ("村卫生室没有医生，看病要去{n}公里外的镇上。", "The village clinic has no doctor; we have to go to the town {n} km away.", "medium"),
            ("晚上有急病叫不到救护车。", "At night we cannot get an ambulance for emergencies.", "high"),
        ],
        "af": [
            ("Die kliniek het al {n} weke geen medisyne nie.", "The clinic has had no medicine for {n} weeks.", "medium"),
            ("Die naaste hospitaal is {n} km ver en daar is geen ambulans nie.", "The nearest hospital is {n} km away and there is no ambulance.", "high"),
        ],
        "zu": [
            ("Umtholampilo awunawo amaphilisi izinsuku ezingu-{n}.", "The clinic has had no medicine for {n} days.", "medium"),
            ("I-ambulensi ayifiki endaweni yethu.", "The ambulance does not reach our area.", "high"),
        ],
        "xh": [
            ("Ikliniki ayinamayeza iintsuku ezi-{n}.", "The clinic has had no medicine for {n} days.", "medium"),
            ("I-ambulensi ayifiki kule lali.", "The ambulance does not reach this village.", "high"),
        ],
    },
    "education": {
        "pt": [
            ("A escola está com o telhado caindo e as aulas pararam.", "The school roof is falling in and classes have stopped.", "high"),
            ("A escola não tem água potável nem internet.", "The school has neither drinking water nor internet.", "low"),
        ],
        "ru": [
            ("В школе {n} лет не было капитального ремонта, крыша течёт.", "The school has not had major repairs for {n} years; the roof leaks.", "medium"),
            ("В селе закрыли школу, дети ездят за {n} км.", "The village school was closed; the children travel {n} km.", "medium"),
        ],
        "zh": [
            ("学校只有一位老师教{n}个年级。", "The school has one teacher for {n} grades.", "low"),
            ("教室墙体开裂，孩子们上课不安全。", "The classroom walls are cracked; it is unsafe for the children.", "high"),
        ],
        "af": [
            ("Die skool het nog steeds putlatrines.", "The school still has pit latrines.", "high"),
            ("Daar is {n} leerders in een klaskamer.", "There are {n} learners in one classroom.", "low"),
        ],
        "zu": [
            ("Isikole sisenezindlu zangasese zemigodi.", "The school still has pit toilets.", "high"),
            ("Isikole asinawo amanzi okuphuza.", "The school has no drinking water.", "low"),
        ],
        "xh": [
            ("Isikolo sisenezindlu zangasese zemingxuma.", "The school still has pit toilets.", "high"),
            ("Isikolo asinawo amanzi okusela.", "The school has no drinking water.", "low"),
        ],
    },
    "electricity": {
        "pt": [
            ("Falta luz todo dia por {n} horas no nosso bairro.", "Our neighbourhood loses power for {n} hours every day.", "low"),
            ("O poste da rua está apagado há meses, é perigoso à noite.", "The street light has been out for months; it is dangerous at night.", "high"),
        ],
        "ru": [
            ("Свет отключают каждый день на {n} часов.", "The power is cut for {n} hours every day.", "low"),
            ("На улице не горят фонари, вечером опасно.", "The street lights are out; it is dangerous in the evening.", "high"),
        ],
        "zh": [
            ("村里经常停电，每次停{n}个小时。", "The village often loses power, {n} hours each time.", "low"),
            ("路灯坏了几个月，晚上走路很危险。", "The street lights have been broken for months; walking at night is dangerous.", "high"),
        ],
        "af": [
            ("Ons het al {n} dae geen krag nie, die transformator is gesteel.", "We have had no power for {n} days; the transformer was stolen.", "medium"),
            ("Die straatligte werk nie, dit is onveilig in die aand.", "The street lights do not work; it is unsafe at night.", "high"),
        ],
        "zu": [
            ("Akukho gesi izinsuku ezingu-{n}.", "There has been no electricity for {n} days.", "medium"),
            ("Izibani zasemgwaqweni azisebenzi, kuyingozi ebusuku.", "The street lights do not work; it is dangerous at night.", "high"),
        ],
        "xh": [
            ("Akukho mbane iintsuku ezi-{n}.", "There has been no electricity for {n} days.", "medium"),
            ("Izibane zesitrato azisebenzi, kuyingozi ebusuku.", "The street lights do not work; it is dangerous at night.", "high"),
        ],
    },
    "waste": {
        "pt": [
            ("A coleta de lixo não passa há {n} dias.", "The rubbish collection has not come for {n} days.", "low"),
            ("Tem um lixão perto da escola, cheio de ratos.", "There is a dump near the school, full of rats.", "medium"),
        ],
        "ru": [
            ("Мусор не вывозят уже {n} недели.", "The rubbish has not been collected for {n} weeks.", "low"),
            ("За селом стихийная свалка, мусор жгут.", "There is an illegal dump outside the village and the rubbish is burnt.", "medium"),
        ],
        "zh": [
            ("垃圾{n}天没人清运了，味道很大。", "The rubbish has not been collected for {n} days; it smells terrible.", "low"),
            ("村口有人焚烧垃圾，烟很呛。", "People burn rubbish at the village entrance; the smoke is choking.", "medium"),
        ],
        "af": [
            ("Die vullis is al {n} weke nie verwyder nie.", "The rubbish has not been removed for {n} weeks.", "low"),
            ("Mense stort vullis langs die skool.", "People are dumping rubbish next to the school.", "medium"),
        ],
        "zu": [
            ("Udoti awuqoqwanga amasonto angu-{n}.", "The rubbish has not been collected for {n} weeks.", "low"),
            ("Kunodoti oningi eduze kwesikole.", "There is a lot of rubbish near the school.", "medium"),
        ],
        "xh": [
            ("Inkunkuma ayithathwanga iiveki ezi-{n}.", "The rubbish has not been collected for {n} weeks.", "low"),
            ("Kukho inkunkuma eninzi kufutshane nesikolo.", "There is a lot of rubbish near the school.", "medium"),
        ],
    },
}

OPENERS: dict[str, list[str]] = {
    "pt": ["", "", "Bom dia,", "Prezados,", "Olá,"],
    "ru": ["", "", "Здравствуйте,", "Добрый день,", "Уважаемая администрация,"],
    "zh": ["", "", "您好，", "领导好，", "你好，"],
    "af": ["", "", "Goeiedag,", "Meneer,", "Hallo,"],
    "zu": ["", "", "Sawubona,", "Sanibonani,", "Baba,"],
    "xh": ["", "", "Molo,", "Molweni,", "Tata,"],
}
CLOSERS: dict[str, list[str]] = {
    "pt": ["", "Por favor, ajudem.", "Pedimos providências urgentes.", "Muitas famílias sofrem com isso."],
    "ru": ["", "Просим помочь.", "Примите меры, пожалуйста.", "Страдают многие семьи."],
    "zh": ["", "请尽快解决。", "希望政府帮帮我们。", "很多家庭受影响。"],
    "af": ["", "Help asseblief.", "Doen asseblief gou iets.", "Baie gesinne word geraak."],
    "zu": ["", "Sicela usizo.", "Sicela nisheshe.", "Imindeni eminingi ihlukumezekile."],
    "xh": ["", "Sicela uncedo.", "Sicela nikhawuleze.", "Iintsapho ezininzi zichaphazelekile."],
}
LANDMARKS: dict[str, list[tuple[str, str]]] = {
    "pt": [("perto da rodoviária", "near the bus station"), ("atrás da prefeitura", "behind the town hall"),
           ("ao lado da escola municipal", "next to the municipal school"), ("na rua da feira", "on the market street")],
    "ru": [("возле автостанции", "near the bus station"), ("за зданием администрации", "behind the administration building"),
           ("рядом со школой", "next to the school"), ("на центральной улице", "on the main street")],
    "zh": [("汽车站附近", "near the bus station"), ("村委会后面", "behind the village committee office"),
           ("小学旁边", "next to the primary school"), ("集市路上", "on the market road")],
    "af": [("naby die taxistaanplek", "near the taxi rank"), ("agter die munisipale kantoor", "behind the municipal office"),
           ("langs die laerskool", "next to the primary school"), ("in die hoofstraat", "on the main street")],
    "zu": [("eduze kwerenki yamatekisi", "near the taxi rank"), ("ngemuva kwehhovisi likamasipala", "behind the municipal office"),
           ("eceleni kwesikole", "next to the school"), ("emgwaqeni omkhulu", "on the main road")],
    "xh": [("kufutshane nerenki yeeteksi", "near the taxi rank"), ("emva kweofisi kamasipala", "behind the municipal office"),
           ("ecaleni kwesikolo", "next to the school"), ("kwindlela enkulu", "on the main road")],
}
DISTRICT_ONLY: dict[str, str] = {"pt": "({d})", "ru": "({d})", "zh": "（{d}）", "af": "({d})", "zu": "({d})", "xh": "({d})"}

# The planted brigading attack, per language: near-identical messages from a handful of numbers in 30 minutes.
BRIGADE: dict[str, tuple[str, str]] = {
    "pt": ("Asfaltem a avenida principal agora, é a obra mais importante da cidade",
           "Pave the main avenue now; it is the most important work in the city."),
    "ru": ("Срочно отремонтируйте центральную улицу, это самое важное для города",
           "Repair the main street urgently; it is the most important thing for the city."),
    "zh": ("立刻拓宽主干道，这是全市最重要的工程", "Widen the main road immediately; it is the most important project in the city."),
    "en": ("Resurface the main road now, this is the most important project in the city",
           "Resurface the main road now; this is the most important project in the city."),
}

# Extra clauses mixed into organic messages so they vary the way real ones do. Without them, a one-language
# pack reuses a handful of sentences and honest clusters get flagged as copy-paste campaigns.
DETAILS: dict[str, list[tuple[str, str | None]]] = {
    "pt": [("Já reclamamos na prefeitura.", "We already complained at the town hall."), ("As crianças são as que mais sofrem.", "The children suffer the most."),
           ("Isso começou no mês passado.", "This started last month."), ("Ninguém veio olhar até agora.", "Nobody has come to look so far."),
           ("Moram muitos idosos aqui.", "Many elderly people live here."), ("Quando chove fica pior.", "It gets worse when it rains."),
           ("Somos mais de cem famílias.", "We are more than a hundred families."), ("Mandamos fotos pelo WhatsApp.", "We sent photos on WhatsApp.")],
    "ru": [("Мы уже писали в администрацию.", "We already wrote to the administration."), ("Больше всего страдают дети.", "The children suffer most."),
           ("Это началось в прошлом месяце.", "This started last month."), ("До сих пор никто не приезжал.", "Nobody has come so far."),
           ("Здесь живёт много пенсионеров.", "Many pensioners live here."), ("Зимой становится ещё хуже.", "In winter it gets even worse."),
           ("На улице больше ста домов.", "There are more than a hundred houses on the street."), ("Фотографии можем прислать.", "We can send photos.")],
    "zh": [("我们已经向村委会反映过。", "We already reported it to the village committee."), ("孩子和老人最受影响。", "Children and the elderly are most affected."),
           ("这个问题从上个月开始。", "The problem started last month."), ("到现在还没有人来看。", "Nobody has come to look yet."),
           ("下雨天更严重。", "It is worse on rainy days."), ("全村一百多户都受影响。", "More than a hundred households are affected."),
           ("可以提供照片。", "We can provide photos."), ("希望尽快派人来修。", "We hope someone is sent to fix it soon.")],
    "af": [("Ons het al by die munisipaliteit gekla.", "We already complained to the municipality."), ("Die kinders ly die meeste.", "The children suffer the most."),
           ("Dit het verlede maand begin.", "It started last month."), ("Niemand het nog kom kyk nie.", "Nobody has come to look yet."),
           ("Baie ou mense woon hier.", "Many elderly people live here."), ("Dit is erger as dit reën.", "It is worse when it rains."),
           ("Meer as honderd gesinne word geraak.", "More than a hundred families are affected."), ("Ons kan foto's stuur.", "We can send photos.")],
    "zu": [("Sesikhalile kumasipala.", "We have already complained to the municipality."), ("Izingane yizona ezihlupheka kakhulu.", "The children suffer the most."),
           ("Lokhu kwaqala ngenyanga edlule.", "This started last month."), ("Akekho oseze weza ukuzobheka.", "Nobody has come to look yet."),
           ("Kuhlala abantu abadala abaningi lapha.", "Many elderly people live here."), ("Kuba kubi kakhulu uma lina.", "It gets worse when it rains."),
           ("Imindeni engaphezu kwekhulu ithintekile.", "More than a hundred families are affected."), ("Singathumela izithombe.", "We can send photos.")],
    "xh": [("Sele sikhalazile kumasipala.", "We have already complained to the municipality."), ("Abantwana ngabona basokola kakhulu.", "The children suffer the most."),
           ("Oku kuqale kwinyanga ephelileyo.", "This started last month."), ("Akukho mntu uze kujonga ukuza kuthi ga ngoku.", "Nobody has come to look yet."),
           ("Kuhlala abantu abadala abaninzi apha.", "Many elderly people live here."), ("Kuba mbi ngakumbi xa kunetha.", "It gets worse when it rains."),
           ("Iintsapho ezingaphezu kwekhulu zichaphazelekile.", "More than a hundred families are affected."), ("Singathumela iifoto.", "We can send photos.")],
    "en": [("We have already complained to the office.", None), ("The children suffer the most.", None), ("This started last month.", None),
           ("Nobody has come to check yet.", None), ("Many elderly people live here.", None), ("It gets worse when it rains.", None),
           ("More than a hundred families are affected.", None), ("We can send photos.", None)],
    "hi": [("हमने पहले भी शिकायत की थी।", "We complained before too."), ("सबसे ज़्यादा बच्चे परेशान हैं।", "The children are the most affected."),
           ("यह पिछले महीने से हो रहा है।", "This has been happening since last month."), ("अब तक कोई देखने नहीं आया।", "Nobody has come to look yet."),
           ("बारिश में हालत और खराब हो जाती है।", "It gets worse in the rains."), ("सौ से ज़्यादा परिवार परेशान हैं।", "More than a hundred families are affected.")],
    "hi-Latn": [("Pehle bhi complaint ki thi", "We complained before too."), ("Bachche sabse zyada pareshan hain", "The children are the most affected."),
                ("Pichhle mahine se yahi haal hai", "It has been like this since last month."), ("Abhi tak koi dekhne nahi aaya", "Nobody has come to look yet."),
                ("Baarish mein aur bura ho jaata hai", "It gets worse in the rain."), ("Sau se zyada ghar affected hain", "More than a hundred homes are affected.")],
    "mr": [("आम्ही आधीही तक्रार केली होती.", "We complained before too."), ("सगळ्यात जास्त त्रास मुलांना होतो.", "The children suffer the most."),
           ("हे गेल्या महिन्यापासून सुरू आहे.", "This has been going on since last month."), ("अजून कोणीही पाहायला आलेले नाही.", "Nobody has come to look yet."),
           ("पावसात परिस्थिती आणखी बिघडते.", "It gets worse in the rains."), ("शंभरहून अधिक कुटुंबांना त्रास होत आहे.", "More than a hundred families are affected.")],
}
