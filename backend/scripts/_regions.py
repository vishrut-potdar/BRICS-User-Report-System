"""Curated unit tables for the BRICS packs, used by scripts/build_reference.py.

Boundaries come from geoBoundaries, whose names are inconsistent ("Nothern Cape", Guangdong labelled
"Guangzhou Province", dated Chinese county names), so every unit is listed here with a clean English name, a
local-script name and aliases. Source features are matched by ISO code where geoBoundaries has one, otherwise by
the exact source name.

Aliases feed the gazetteer. `weak` names are also ordinary words or directions ("Pará" folds to "para",
"North West", "Pilar"), so they only match place mentions and district guesses, never free text.

Unit tuple: (code, name, local name, aliases, weak aliases, priority area)
"""

from __future__ import annotations

Unit = tuple[str, str, str, tuple[str, ...], tuple[str, ...], bool]


def u(code: str, name: str, local: str = "", aliases: str = "", weak: str = "", priority: bool = False) -> Unit:
    split = lambda s: tuple(a.strip() for a in s.split(";") if a.strip())  # noqa: E731
    return code, name, local or name, split(aliases), split(weak), priority


# --- country level: states / provinces (ADM1) --------------------------------------------------------

BR_STATES = [
    u("BR-AC", "Acre", "Acre", "Rio Branco"),
    u("BR-AL", "Alagoas", "Alagoas", "Maceió"),
    u("BR-AP", "Amapá", "Amapá", "Macapá"),
    u("BR-AM", "Amazonas", "Amazonas", "Manaus"),
    u("BR-BA", "Bahia", "Bahia", "Salvador"),
    u("BR-CE", "Ceará", "Ceará", "Fortaleza"),
    u("BR-DF", "Distrito Federal", "Distrito Federal", "Brasília"),
    u("BR-ES", "Espírito Santo", "Espírito Santo", "Vitória"),
    u("BR-GO", "Goiás", "Goiás", "Goiânia"),
    u("BR-MA", "Maranhão", "Maranhão", "São Luís"),
    u("BR-MT", "Mato Grosso", "Mato Grosso", "Cuiabá"),
    u("BR-MS", "Mato Grosso do Sul", "Mato Grosso do Sul", "", "Campo Grande"),
    u("BR-MG", "Minas Gerais", "Minas Gerais", "Belo Horizonte"),
    u("BR-PA", "Pará", "Pará", "", "Pará;Belém"),
    u("BR-PB", "Paraíba", "Paraíba", "João Pessoa"),
    u("BR-PR", "Paraná", "Paraná", "Curitiba"),
    u("BR-PE", "Pernambuco", "Pernambuco", "Recife"),
    u("BR-PI", "Piauí", "Piauí", "Teresina"),
    u("BR-RJ", "Rio de Janeiro", "Rio de Janeiro"),
    u("BR-RN", "Rio Grande do Norte", "Rio Grande do Norte", "", "Natal"),
    u("BR-RS", "Rio Grande do Sul", "Rio Grande do Sul", "Porto Alegre"),
    u("BR-RO", "Rondônia", "Rondônia", "Porto Velho"),
    u("BR-RR", "Roraima", "Roraima", "Boa Vista"),
    u("BR-SC", "Santa Catarina", "Santa Catarina", "Florianópolis"),
    u("BR-SP", "São Paulo", "São Paulo"),
    u("BR-SE", "Sergipe", "Sergipe", "Aracaju"),
    u("BR-TO", "Tocantins", "Tocantins", "", "Palmas"),
]

RU_SUBJECTS = [
    u("RU-AD", "Adygea", "Адыгея", "Maykop;Майкоп"),
    u("RU-AL", "Altai Republic", "Республика Алтай", "Gorno-Altaysk;Горно-Алтайск"),
    u("RU-ALT", "Altai Krai", "Алтайский край", "Barnaul;Барнаул"),
    u("RU-AMU", "Amur Oblast", "Амурская область", "Blagoveshchensk;Благовещенск"),
    u("RU-ARK", "Arkhangelsk Oblast", "Архангельская область", "Arkhangelsk;Архангельск"),
    u("RU-AST", "Astrakhan Oblast", "Астраханская область", "Astrakhan;Астрахань"),
    u("RU-BA", "Bashkortostan", "Башкортостан", "Ufa;Уфа"),
    u("RU-BEL", "Belgorod Oblast", "Белгородская область", "Belgorod;Белгород"),
    u("RU-BRY", "Bryansk Oblast", "Брянская область", "Bryansk;Брянск"),
    u("RU-BU", "Buryatia", "Бурятия", "Ulan-Ude;Улан-Удэ"),
    u("RU-CE", "Chechnya", "Чечня", "Grozny;Грозный"),
    u("RU-CHE", "Chelyabinsk Oblast", "Челябинская область", "Chelyabinsk;Челябинск"),
    u("RU-CHU", "Chukotka Autonomous Okrug", "Чукотский автономный округ", "Anadyr;Анадырь"),
    u("RU-CU", "Chuvashia", "Чувашия", "Cheboksary;Чебоксары"),
    u("RU-DA", "Dagestan", "Дагестан", "Makhachkala;Махачкала"),
    u("RU-IN", "Ingushetia", "Ингушетия", "Magas;Магас"),
    u("RU-IRK", "Irkutsk Oblast", "Иркутская область", "Irkutsk;Иркутск"),
    u("RU-IVA", "Ivanovo Oblast", "Ивановская область", "Ivanovo;Иваново"),
    u("RU-KAM", "Kamchatka Krai", "Камчатский край", "Petropavlovsk-Kamchatsky;Петропавловск-Камчатский"),
    u("RU-KB", "Kabardino-Balkaria", "Кабардино-Балкария", "Nalchik;Нальчик"),
    u("RU-KC", "Karachay-Cherkessia", "Карачаево-Черкесия", "Cherkessk;Черкесск"),
    u("RU-KDA", "Krasnodar Krai", "Краснодарский край", "Krasnodar;Краснодар;Sochi;Сочи"),
    u("RU-KEM", "Kemerovo Oblast", "Кемеровская область", "Kemerovo;Кемерово;Kuzbass;Кузбасс"),
    u("RU-KGD", "Kaliningrad Oblast", "Калининградская область", "Kaliningrad;Калининград"),
    u("RU-KGN", "Kurgan Oblast", "Курганская область", "Kurgan;Курган"),
    u("RU-KHA", "Khabarovsk Krai", "Хабаровский край", "Khabarovsk;Хабаровск"),
    u("RU-KHM", "Khanty-Mansi Autonomous Okrug", "Ханты-Мансийский автономный округ", "Yugra;Югра;Khanty-Mansiysk;Ханты-Мансийск;Surgut;Сургут"),
    u("RU-KIR", "Kirov Oblast", "Кировская область", "Kirov;Киров"),
    u("RU-KK", "Khakassia", "Хакасия", "Abakan;Абакан"),
    u("RU-KL", "Kalmykia", "Калмыкия", "Elista;Элиста"),
    u("RU-KLU", "Kaluga Oblast", "Калужская область", "Kaluga;Калуга"),
    u("RU-KO", "Komi Republic", "Республика Коми", "Syktyvkar;Сыктывкар"),
    u("RU-KOS", "Kostroma Oblast", "Костромская область", "Kostroma;Кострома"),
    u("RU-KR", "Republic of Karelia", "Карелия", "Petrozavodsk;Петрозаводск"),
    u("RU-KRS", "Kursk Oblast", "Курская область", "Kursk;Курск"),
    u("RU-KYA", "Krasnoyarsk Krai", "Красноярский край", "Krasnoyarsk;Красноярск"),
    u("RU-LEN", "Leningrad Oblast", "Ленинградская область"),
    u("RU-LIP", "Lipetsk Oblast", "Липецкая область", "Lipetsk;Липецк"),
    u("RU-MAG", "Magadan Oblast", "Магаданская область", "Magadan;Магадан"),
    u("RU-ME", "Mari El", "Марий Эл", "Yoshkar-Ola;Йошкар-Ола"),
    u("RU-MO", "Mordovia", "Мордовия", "Saransk;Саранск"),
    u("RU-MOS", "Moscow Oblast", "Московская область", "Подмосковье"),
    u("RU-MOW", "Moscow", "Москва"),
    u("RU-MUR", "Murmansk Oblast", "Мурманская область", "Murmansk;Мурманск"),
    u("RU-NEN", "Nenets Autonomous Okrug", "Ненецкий автономный округ", "Naryan-Mar;Нарьян-Мар"),
    u("RU-NGR", "Novgorod Oblast", "Новгородская область", "Veliky Novgorod;Великий Новгород"),
    u("RU-NIZ", "Nizhny Novgorod Oblast", "Нижегородская область", "Nizhny Novgorod;Нижний Новгород"),
    u("RU-NVS", "Novosibirsk Oblast", "Новосибирская область", "Novosibirsk;Новосибирск"),
    u("RU-OMS", "Omsk Oblast", "Омская область", "Omsk;Омск"),
    u("RU-ORE", "Orenburg Oblast", "Оренбургская область", "Orenburg;Оренбург"),
    u("RU-ORL", "Oryol Oblast", "Орловская область", "Oryol;Орёл;Орел"),
    u("RU-PER", "Perm Krai", "Пермский край", "Perm;Пермь"),
    u("RU-PNZ", "Penza Oblast", "Пензенская область", "Penza;Пенза"),
    u("RU-PRI", "Primorsky Krai", "Приморский край", "Vladivostok;Владивосток"),
    u("RU-PSK", "Pskov Oblast", "Псковская область", "Pskov;Псков"),
    u("RU-ROS", "Rostov Oblast", "Ростовская область", "Rostov-on-Don;Ростов-на-Дону"),
    u("RU-RYA", "Ryazan Oblast", "Рязанская область", "Ryazan;Рязань"),
    u("RU-SA", "Sakha (Yakutia)", "Республика Саха (Якутия)", "Yakutia;Якутия;Yakutsk;Якутск"),
    u("RU-SAK", "Sakhalin Oblast", "Сахалинская область", "Yuzhno-Sakhalinsk;Южно-Сахалинск"),
    u("RU-SAM", "Samara Oblast", "Самарская область", "Samara;Самара;Tolyatti;Тольятти"),
    u("RU-SAR", "Saratov Oblast", "Саратовская область", "Saratov;Саратов"),
    u("RU-SE", "North Ossetia–Alania", "Северная Осетия — Алания", "North Ossetia;Северная Осетия;Vladikavkaz;Владикавказ"),
    u("RU-SMO", "Smolensk Oblast", "Смоленская область", "Smolensk;Смоленск"),
    u("RU-SPE", "Saint Petersburg", "Санкт-Петербург", "St Petersburg;St. Petersburg;Петербург"),
    u("RU-STA", "Stavropol Krai", "Ставропольский край", "Stavropol;Ставрополь"),
    u("RU-SVE", "Sverdlovsk Oblast", "Свердловская область", "Yekaterinburg;Екатеринбург"),
    u("RU-TA", "Tatarstan", "Татарстан", "Kazan;Казань"),
    u("RU-TAM", "Tambov Oblast", "Тамбовская область", "Tambov;Тамбов"),
    u("RU-TOM", "Tomsk Oblast", "Томская область", "Tomsk;Томск"),
    u("RU-TUL", "Tula Oblast", "Тульская область", "Tula;Тула"),
    u("RU-TVE", "Tver Oblast", "Тверская область", "Tver;Тверь"),
    u("RU-TY", "Tuva", "Тыва", "Tyva;Тува"),
    u("RU-TYU", "Tyumen Oblast", "Тюменская область", "Tyumen;Тюмень"),
    u("RU-UD", "Udmurtia", "Удмуртия", "Izhevsk;Ижевск"),
    u("RU-ULY", "Ulyanovsk Oblast", "Ульяновская область", "Ulyanovsk;Ульяновск"),
    u("RU-VGG", "Volgograd Oblast", "Волгоградская область", "Volgograd;Волгоград"),
    u("RU-VLA", "Vladimir Oblast", "Владимирская область", "Vladimir;Владимир"),
    u("RU-VLG", "Vologda Oblast", "Вологодская область", "Vologda;Вологда"),
    u("RU-VOR", "Voronezh Oblast", "Воронежская область", "Voronezh;Воронеж"),
    u("RU-YAN", "Yamalo-Nenets Autonomous Okrug", "Ямало-Ненецкий автономный округ", "Yamal;Ямал;Salekhard;Салехард"),
    u("RU-YAR", "Yaroslavl Oblast", "Ярославская область", "Yaroslavl;Ярославль"),
    u("RU-YEV", "Jewish Autonomous Oblast", "Еврейская автономная область", "Birobidzhan;Биробиджан"),
    u("RU-ZAB", "Zabaykalsky Krai", "Забайкальский край", "Chita;Чита"),
]

IN_STATES = [
    u("IN-AN", "Andaman and Nicobar Islands", "अंडमान और निकोबार द्वीपसमूह", "Port Blair"),
    u("IN-AP", "Andhra Pradesh", "आंध्र प्रदेश", "Amaravati;Visakhapatnam;Vijayawada"),
    u("IN-AR", "Arunachal Pradesh", "अरुणाचल प्रदेश", "Itanagar"),
    u("IN-AS", "Assam", "असम", "Guwahati;Dispur"),
    u("IN-BR", "Bihar", "बिहार", "Patna;पटना"),
    u("IN-CH", "Chandigarh", "चंडीगढ़"),
    u("IN-CT", "Chhattisgarh", "छत्तीसगढ़", "Raipur;रायपुर"),
    u("IN-DH", "Dadra and Nagar Haveli and Daman and Diu", "दादरा और नगर हवेली और दमन और दीव", "Silvassa;Daman"),
    u("IN-DL", "Delhi", "दिल्ली", "New Delhi"),
    u("IN-GA", "Goa", "गोवा", "Panaji"),
    u("IN-GJ", "Gujarat", "गुजरात", "Ahmedabad;Gandhinagar;Surat"),
    u("IN-HP", "Himachal Pradesh", "हिमाचल प्रदेश", "Shimla"),
    u("IN-HR", "Haryana", "हरियाणा", "Gurugram;Gurgaon;Faridabad"),
    u("IN-JH", "Jharkhand", "झारखंड", "Ranchi;रांची"),
    u("IN-JK", "Jammu and Kashmir", "जम्मू और कश्मीर", "Srinagar;Jammu"),
    u("IN-KA", "Karnataka", "कर्नाटक", "Bengaluru;Bangalore"),
    u("IN-KL", "Kerala", "केरल", "Thiruvananthapuram;Kochi"),
    u("IN-LA", "Ladakh", "लद्दाख", "Leh"),
    u("IN-LD", "Lakshadweep", "लक्षद्वीप", "Kavaratti"),
    u("IN-MH", "Maharashtra", "महाराष्ट्र", "Mumbai;मुंबई"),
    u("IN-ML", "Meghalaya", "मेघालय", "Shillong"),
    u("IN-MN", "Manipur", "मणिपुर", "Imphal"),
    u("IN-MP", "Madhya Pradesh", "मध्य प्रदेश", "Bhopal;Indore;भोपाल"),
    u("IN-MZ", "Mizoram", "मिज़ोरम", "Aizawl"),
    u("IN-NL", "Nagaland", "नागालैंड", "Kohima"),
    u("IN-OR", "Odisha", "ओडिशा", "Orissa;Bhubaneswar"),
    u("IN-PB", "Punjab", "पंजाब", "Ludhiana;Amritsar"),
    u("IN-PY", "Puducherry", "पुडुचेरी", "Pondicherry"),
    u("IN-RJ", "Rajasthan", "राजस्थान", "Jaipur;जयपुर"),
    u("IN-SK", "Sikkim", "सिक्किम", "Gangtok"),
    u("IN-TG", "Telangana", "तेलंगाना", "Hyderabad"),
    u("IN-TN", "Tamil Nadu", "तमिलनाडु", "Chennai"),
    u("IN-TR", "Tripura", "त्रिपुरा", "Agartala"),
    u("IN-UP", "Uttar Pradesh", "उत्तर प्रदेश", "Lucknow;Kanpur;लखनऊ"),
    u("IN-UT", "Uttarakhand", "उत्तराखंड", "Dehradun"),
    u("IN-WB", "West Bengal", "पश्चिम बंगाल", "Kolkata;Calcutta"),
]

# geoBoundaries' China ADM1 has no ISO codes and mislabels Guangdong, so these match on its shapeName.
# Hong Kong, Macau and Taiwan are left out: the pack covers the 31 mainland divisions that national
# statistics (NBS, MWR, NHC) report on.
CN_PROVINCES = [
    (u("CN-BJ", "Beijing", "北京市", "北京"), "Beijing Municipality"),
    (u("CN-TJ", "Tianjin", "天津市", "天津"), "Tianjin Municipality"),
    (u("CN-HE", "Hebei", "河北省", "河北;Shijiazhuang;石家庄"), "Hebei Province"),
    (u("CN-SX", "Shanxi", "山西省", "山西;Taiyuan;太原"), "Shanxi Province"),
    (u("CN-NM", "Inner Mongolia", "内蒙古自治区", "内蒙古;Hohhot;呼和浩特"), "Inner Mongolia Autonomous Region"),
    (u("CN-LN", "Liaoning", "辽宁省", "辽宁;Shenyang;沈阳"), "Liaoning Province"),
    (u("CN-JL", "Jilin", "吉林省", "吉林;Changchun;长春"), "Jilin Province"),
    (u("CN-HL", "Heilongjiang", "黑龙江省", "黑龙江;Harbin;哈尔滨"), "Heilongjiang Province"),
    (u("CN-SH", "Shanghai", "上海市", "上海"), "Shanghai Municipality"),
    (u("CN-JS", "Jiangsu", "江苏省", "江苏;Nanjing;南京"), "Jiangsu Province"),
    (u("CN-ZJ", "Zhejiang", "浙江省", "浙江;Hangzhou;杭州"), "Zhejiang Province"),
    (u("CN-AH", "Anhui", "安徽省", "安徽;Hefei;合肥"), "Anhui Province"),
    (u("CN-FJ", "Fujian", "福建省", "福建;Fuzhou;福州"), "Fujian Province"),
    (u("CN-JX", "Jiangxi", "江西省", "江西;Nanchang;南昌"), "Jiangxi Province"),
    (u("CN-SD", "Shandong", "山东省", "山东;Jinan;济南"), "Shandong Province"),
    (u("CN-HA", "Henan", "河南省", "河南;Zhengzhou;郑州"), "Henan Province"),
    (u("CN-HB", "Hubei", "湖北省", "湖北;Wuhan;武汉"), "Hubei Province"),
    (u("CN-HN", "Hunan", "湖南省", "湖南;Changsha;长沙"), "Hunan Province"),
    (u("CN-GD", "Guangdong", "广东省", "广东;Guangzhou;广州;Shenzhen;深圳"), "Guangzhou Province"),
    (u("CN-GX", "Guangxi", "广西壮族自治区", "广西;Nanning;南宁"), "Guangxi Zhuang Autonomous Region"),
    (u("CN-HI", "Hainan", "海南省", "海南;Haikou;海口"), "Hainan Province"),
    (u("CN-CQ", "Chongqing", "重庆市", "重庆"), "Chongqing Municipality"),
    (u("CN-SC", "Sichuan", "四川省", "四川;Chengdu;成都"), "Sichuan Province"),
    (u("CN-GZ", "Guizhou", "贵州省", "贵州;Guiyang;贵阳"), "Guizhou Province"),
    (u("CN-YN", "Yunnan", "云南省", "云南;Kunming;昆明"), "Yunnan Province"),
    (u("CN-XZ", "Tibet", "西藏自治区", "西藏;Xizang;Lhasa;拉萨"), "Tibet Autonomous Region"),
    (u("CN-SN", "Shaanxi", "陕西省", "陕西;Xi'an;西安"), "Shaanxi Province"),
    (u("CN-GS", "Gansu", "甘肃省", "甘肃;Lanzhou;兰州"), "Gansu Province"),
    (u("CN-QH", "Qinghai", "青海省", "青海;Xining;西宁"), "Qinghai Province"),
    (u("CN-NX", "Ningxia", "宁夏回族自治区", "宁夏"), "Ningxia Ningxia Hui Autonomous Region"),
    (u("CN-XJ", "Xinjiang", "新疆维吾尔自治区", "新疆;Urumqi;乌鲁木齐"), "Xinjiang Uyghur Autonomous Region"),
]

# geoBoundaries short codes for South Africa (EC, GT, KZ, LI...) mapped to ISO 3166-2.
ZA_PROVINCES = [
    (u("ZA-EC", "Eastern Cape", "Oos-Kaap", "Bhisho;Gqeberha;Port Elizabeth;East London"), "EC"),
    (u("ZA-FS", "Free State", "Vrystaat", "Bloemfontein", "Free State"), "FS"),
    (u("ZA-GP", "Gauteng", "Gauteng", "Johannesburg;Joburg;Pretoria;Tshwane;Soweto"), "GT"),
    (u("ZA-KZN", "KwaZulu-Natal", "KwaZulu-Natal", "KZN;Durban;eThekwini;Pietermaritzburg"), "KZ"),
    (u("ZA-LP", "Limpopo", "Limpopo", "Polokwane"), "LI"),
    (u("ZA-MP", "Mpumalanga", "Mpumalanga", "Mbombela;Nelspruit"), "MP"),
    (u("ZA-NC", "Northern Cape", "Noord-Kaap", "Kimberley"), "NC"),
    (u("ZA-NW", "North West", "Noordwes", "Mahikeng;Mafikeng;Rustenburg", "North West"), "NW"),
    (u("ZA-WC", "Western Cape", "Wes-Kaap", "Cape Town;Kaapstad"), "WC"),
]

# --- pilot regions: districts / municipalities (ADM2), matched on geoBoundaries shapeName -----------

# Russia, Tuva (Tyva): 17 kozhuuns and 2 urban okrugs. Russia's poorest federal subject by Rosstat's poverty rate.
RU_TY_UNITS = [
    (u("RU-TY-KYZYL_CITY", "Kyzyl", "Кызыл", "Kyzyl city"), ["городской округ Кызыл"]),
    (u("RU-TY-AK_DOVURAK", "Ak-Dovurak", "Ак-Довурак"), ["городской округ Ак-Довурак"]),
    (u("RU-TY-KYZYL_KOZHUUN", "Kyzyl kozhuun", "Кызылский кожуун", "Kaa-Khem settlement;Каа-Хем"), ["Кызылский кожуун"]),
    (u("RU-TY-BAI_TAIGA", "Bai-Taiga kozhuun", "Бай-Тайгинский кожуун", "Teeli;Тээли"), ["Bay-Tayginsky Kozhuun"]),
    (u("RU-TY-BARUN_KHEMCHIK", "Barun-Khemchik kozhuun", "Барун-Хемчикский кожуун", "Kyzyl-Mazhalyk;Кызыл-Мажалык"), ["Barun-Khemchiksky Kozhuun"]),
    (u("RU-TY-CHAA_KHOL", "Chaa-Khol kozhuun", "Чаа-Хольский кожуун", "Чаа-Холь"), ["Chaa-Kholsky Kozhuun"]),
    (u("RU-TY-CHEDI_KHOL", "Chedi-Khol kozhuun", "Чеди-Хольский кожуун", "Khovu-Aksy;Хову-Аксы"), ["Chedi-Kholsky Kozhuun"]),
    (u("RU-TY-DZUN_KHEMCHIK", "Dzun-Khemchik kozhuun", "Дзун-Хемчикский кожуун", "Chadan;Чадан"), ["Dzun-Khemchiksky Kozhuun"]),
    (u("RU-TY-ERZIN", "Erzin kozhuun", "Эрзинский кожуун", "Erzin;Эрзин"), ["Erzinsky Kozhuun"]),
    (u("RU-TY-KAA_KHEM", "Kaa-Khem kozhuun", "Каа-Хемский кожуун", "Saryg-Sep;Сарыг-Сеп"), ["Kaa-Khemsky District"]),
    (u("RU-TY-MONGUN_TAIGA", "Mongun-Taiga kozhuun", "Монгун-Тайгинский кожуун", "Mugur-Aksy;Мугур-Аксы"), ["Mongun-Tayginsky Kozhuun"]),
    (u("RU-TY-OVYUR", "Ovyur kozhuun", "Овюрский кожуун", "Khandagayty;Хандагайты"), ["Ovyursky Kozhuun"]),
    (u("RU-TY-PIY_KHEM", "Piy-Khem kozhuun", "Пий-Хемский кожуун", "Turan;Туран"), ["Piy-Khemsky Kozhuun"]),
    (u("RU-TY-SUT_KHOL", "Sut-Khol kozhuun", "Сут-Хольский кожуун", "Sug-Aksy;Суг-Аксы"), ["Sut-Kholsky Kozhuun"]),
    (u("RU-TY-TANDY", "Tandy kozhuun", "Тандинский кожуун", "Bai-Khaak;Бай-Хаак"), ["Tandinsky Kozhuun"]),
    (u("RU-TY-TERE_KHOL", "Tere-Khol kozhuun", "Тере-Хольский кожуун", "Kungurtug;Кунгуртуг"), ["Tere-Kholsky Kozhuun"]),
    (u("RU-TY-TES_KHEM", "Tes-Khem kozhuun", "Тес-Хемский кожуун", "Samagaltai;Самагалтай"), ["Tes-Khemsky Kozhuun"]),
    (u("RU-TY-TODZHA", "Todzha kozhuun", "Тоджинский кожуун", "Toora-Khem;Тоора-Хем"), ["Todzhinsky Kozhuun"]),
    (u("RU-TY-ULUG_KHEM", "Ulug-Khem kozhuun", "Улуг-Хемский кожуун", "Shagonar;Шагонар"), ["Ulug-Khemsky Kozhuun"]),
]

# China, Ningxia: county-level units. geoBoundaries' county layer predates several reforms, so units are
# merged to today's names (Taole county into Pingluo; Hongsibu is inside Tongxin's old boundary).
# Priority = the former national poverty-alleviation counties of Xihaigu and the central arid zone.
CN_NX_UNITS = [
    (u("CN-NX-YINCHUAN", "Yinchuan (city districts)", "银川市区", "Yinchuan;银川;Xingqing;兴庆区;Jinfeng;金凤区;Xixia;西夏区"), ["Yinchuanshi"]),
    (u("CN-NX-YONGNING", "Yongning County", "永宁县", "Yongning;永宁"), ["Yongningxian"]),
    (u("CN-NX-HELAN", "Helan County", "贺兰县", "Helan;贺兰"), ["Helanxian"]),
    (u("CN-NX-LINGWU", "Lingwu", "灵武市", "灵武"), ["Lingwuxian"]),
    (u("CN-NX-DAWUKOU", "Dawukou District", "大武口区", "Dawukou;Shizuishan;石嘴山"), ["Shizhuishanshi"]),
    (u("CN-NX-HUINONG", "Huinong District", "惠农区", "Huinong;惠农"), ["Huinongxian"]),
    (u("CN-NX-PINGLUO", "Pingluo County", "平罗县", "Pingluo;平罗"), ["Pingluoxian", "Taolexian"]),
    (u("CN-NX-LITONG", "Litong District", "利通区", "Litong;Wuzhong;吴忠"), ["Wuzhongshi"]),
    (u("CN-NX-QINGTONGXIA", "Qingtongxia", "青铜峡市", "青铜峡"), ["Qingtongxiashi"]),
    (u("CN-NX-YANCHI", "Yanchi County", "盐池县", "Yanchi;盐池", priority=True), ["Yanchixian"]),
    (u("CN-NX-TONGXIN", "Tongxin County", "同心县", "Tongxin;同心;Hongsibu;红寺堡", priority=True), ["Tongxinxian"]),
    (u("CN-NX-SHAPOTOU", "Shapotou District", "沙坡头区", "Shapotou;Zhongwei;中卫"), ["Zhongweixian"]),
    (u("CN-NX-ZHONGNING", "Zhongning County", "中宁县", "Zhongning;中宁"), ["Zhongningxian"]),
    (u("CN-NX-HAIYUAN", "Haiyuan County", "海原县", "Haiyuan;海原", priority=True), ["Haiyuanxian"]),
    (u("CN-NX-YUANZHOU", "Yuanzhou District", "原州区", "Yuanzhou;Guyuan;固原", priority=True), ["Guyuanxian"]),
    (u("CN-NX-XIJI", "Xiji County", "西吉县", "Xiji;西吉", priority=True), ["Xijixian"]),
    (u("CN-NX-LONGDE", "Longde County", "隆德县", "Longde;隆德", priority=True), ["Longdexian"]),
    (u("CN-NX-JINGYUAN", "Jingyuan County", "泾源县", "Jingyuan;泾源", priority=True), ["Jingyuanxian"]),
    (u("CN-NX-PENGYANG", "Pengyang County", "彭阳县", "Pengyang;彭阳", priority=True), ["Pengyangxian"]),
]

# South Africa, Eastern Cape: 6 district municipalities and 2 metros.
# Priority = the Eastern Cape nodes of the Integrated Sustainable Rural Development Programme (2001).
ZA_EC_UNITS = [
    (u("ZA-EC-NELSON_MANDELA_BAY", "Nelson Mandela Bay", "Nelson Mandela Bay", "Gqeberha;Port Elizabeth;Kariega;Uitenhage"), ["Nelson Mandela Bay"]),
    (u("ZA-EC-BUFFALO_CITY", "Buffalo City", "Buffalo City", "East London;Qonce;King William's Town;Mdantsane"), ["Buffalo City"]),
    (u("ZA-EC-SARAH_BAARTMAN", "Sarah Baartman", "Sarah Baartman", "Cacadu;Makhanda;Grahamstown;Graaff-Reinet"), ["Cacadu"]),
    (u("ZA-EC-AMATHOLE", "Amathole", "Amathole", "Butterworth;Komani"), ["Amathole"]),
    (u("ZA-EC-CHRIS_HANI", "Chris Hani", "Chris Hani", "Queenstown", priority=True), ["Chris Hani"]),
    (u("ZA-EC-JOE_GQABI", "Joe Gqabi", "Joe Gqabi", "Ukhahlamba;Aliwal North", priority=True), ["Joe Gqabi"]),
    (u("ZA-EC-OR_TAMBO", "OR Tambo", "OR Tambo", "O.R. Tambo;O.R.Tambo;Mthatha;Umtata;Lusikisiki", priority=True), ["O.R.Tambo"]),
    (u("ZA-EC-ALFRED_NZO", "Alfred Nzo", "Alfred Nzo", "Mount Ayliff;Matatiele", priority=True), ["Alfred Nzo"]),
]

# India, Maharashtra: names in the existing reference file; geoBoundaries (LGD 2021) spells a few differently.
IN_MH_SOURCE_NAMES = {
    "Ahmadnagar": "IN-MH-AHMEDNAGAR", "Bid": "IN-MH-BEED", "Buldana": "IN-MH-BULDHANA",
    "Gondiya": "IN-MH-GONDIA", "Mumbai": "IN-MH-MUMBAI_CITY", "Raigarh": "IN-MH-RAIGAD",
}

# Brazil, Alagoas: all 102 municipalities come from the IBGE localities API (official names and codes).
# These municipality names are also everyday Portuguese words or common place names elsewhere.
BR_AL_WEAK = {
    "Anadia", "Atalaia", "Batalha", "Belém", "Belo Monte", "Cajueiro", "Campestre", "Campo Alegre", "Campo Grande",
    "Capela", "Carneiros", "Estrela de Alagoas", "Feliz Deserto", "Flexeiras", "Jundiá", "Maravilha", "Messias",
    "Olivença", "Ouro Branco", "Palestina", "Pilar", "Pindoba", "Roteiro", "São Brás", "São Sebastião", "Satuba",
    "Viçosa",
}
