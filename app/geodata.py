"""
O'zbekiston viloyat/shahar nomlari lug'ati, xalqaro yo'nalishlar,
dinamik shahar bazasi va Google Maps lokatsiya integratsiyasi.
"""
import functools
import re
import urllib.parse
from app.db import get_session

# region_key -> shu viloyatga tegishli barcha shahar, tuman, bozor va maskan nomlari
BASE_REGION_CITIES: dict[str, list[str]] = {
    "toshkent": [
        "toshkent", "tashkent", "ташкент", "tosh", "tash", "chirchiq", "chirchik", "чирчик",
        "olmaliq", "almalyk", "алмалык", "angren", "ангрен", "yangiyol", "янгиюль",
        "bekobod", "bekabad", "бекабад", "gazalkent", "газалкент", "parkent", "паркент",
        "zangiota", "зангиота", "qibray", "кибрай", "piskent", "пискент",
        "chinoz", "чиназ", "buka", "бука", "ortachirchiq", "quyi chirchiq", "yuqori chirchiq",
        "qoyliq", "quyliq", "куйлюк", "chorsu", "чорсу", "abu saxiy", "абу сахий",
        "bek baraka", "бек барака", "urikzor", "orikzor", "урикзор", "sergeli", "сергели",
        "yunusobod", "юнусабад", "chilonzor", "чиланзар", "rohat", "рохат", "yallama", "яллама",
        "gishtkoprik", "черняевка", "bostonliq", "бостанлык", "yangibozor",
    ],
    "samarqand": [
        "samarqand", "samarkand", "самарканд", "sam", "kattaqorgon", "kattaqurgon", "kattakurgan", "каттакурган",
        "urgut", "ургут", "tayloq", "toyloq", "тайлак", "bulungur", "булунгур", "pastdargom", "пастдаргом",
        "payariq", "паярык", "ishtixon", "иштихан", "jomboy", "джамбай", "narpay", "нарпай",
        "oqdaryo", "акдарья", "qoshrabot", "кошрабад", "chelsk", "chelaka", "chelak", "челак",
        "paxtachi", "пахтачи", "nurobod", "нурабад", "ziyovuddin",
    ],
    "fargona": [
        "fargona", "farg'ona", "fargon", "фаргона", "фергана", "qoqon", "qokan", "коканд",
        "margilon", "marg'ilon", "маргилан", "quva", "кува", "rishton", "риштан",
        "oltiariq", "алтыарык", "bogdod", "багдад", "beshariq", "бешарык", "uchkoprik", "учкуприк",
        "toshloq", "ташлак", "buvayda", "бувайда", "yozyovon", "язяван", "dangara", "дангара",
        "quvasoy", "кувасай", "vodil", "водил", "sox", "сох", "ozbekiston tumani", "yaypan", "яйпан",
    ],
    "andijon": [
        "andijon", "andijan", "андижан", "and", "asaka", "асака", "shahrixon", "шахрихан",
        "xonobod", "ханабад", "qorasuv", "карасу", "marhamat", "мархамат", "baliqchi", "балыкчи",
        "boz", "буз", "boston", "бостон", "buloqboshi", "булакбаши", "jalolquduq", "джалалкудук",
        "izboskan", "избаскан", "qorgontepa", "кургантепа", "paxtaobod", "пахтаабад",
        "oltinkol", "алтынкуль", "ulugnor", "улугнор", "xojaobod", "ходжаабад", "poytug", "пойтуг",
    ],
    "namangan": [
        "namangan", "наманган", "nam", "chust", "чуст", "kosonsoy", "касансай",
        "pop", "пап", "uchqorgon", "учкурган", "chortoq", "чартак", "uychi", "уйчи",
        "yangiqorgon", "янгикурган", "toraqorgon", "туракурган", "mingbuloq", "мингбулак",
        "norin", "нарын", "davlatobod", "давлатабад", "haqkulobod", "хаккулабад",
    ],
    "buxoro": [
        "buxoro", "buhoro", "bukhara", "бухара", "bux", "kogon", "kagan", "каган",
        "gijduvon", "g'ijduvon", "гиждуван", "qarakol", "qorakol", "каракуль", "romitan", "ромитан",
        "shofirkon", "шафиркан", "jondor", "жондор", "vobkent", "вабкент", "olot", "алат",
        "olotchegara", "peshku", "пешку", "qorovulbozor", "караулбазар", "gazli", "газли",
    ],
    "qashqadaryo": [
        "qashqadaryo", "kashkadarya", "кашкадарья", "qarshi", "karshi", "карши",
        "shahrisabz", "shaxrisabz", "шахрисабз", "koson", "касан", "kitob", "китаб",
        "qamashi", "камаши", "yakkabog", "яккабаг", "guzor", "гузар", "dehqonobod", "дехканабад",
        "muborak", "мубарек", "nishon", "нишан", "kasbi", "касби", "mirishkor", "миришкор",
        "chiroqchi", "чиракчи", "kokdala", "кукдала", "tallimarjon",
    ],
    "surxondaryo": [
        "surxondaryo", "surxondaryo", "сурхандарья", "surxon", "termiz", "термез",
        "denov", "денов", "sherobod", "шерабад", "shurchi", "шурчи", "jarqorgon", "джаркурган",
        "boysun", "байсун", "qumqorgon", "кумкурган", "uzun", "узун", "sariosiyo", "сариасия",
        "oltinsoy", "алтынсай", "angor", "ангор", "muzrabot", "музрабад", "bandixon", "бандихан",
        "qiziriq", "кизирик",
    ],
    "jizzax": [
        "jizzax", "jizax", "джизак", "жиззах", "dizzax", "dashtobod", "даштабад",
        "zomin", "зомин", "zaamin", "gallaorol", "галлаарал", "paxtakor", "пахтакор",
        "zarbdor", "зарбдар", "dostlik", "dustlik", "дустлик", "baxmal", "бахмал",
        "mirzachul", "мирзачуль", "forish", "фариш", "sharof rashidov", "arnosoy", "arnasoy",
    ],
    "sirdaryo": [
        "sirdaryo", "сирдарья", "guliston", "гулистан", "yangiyer", "янгиер",
        "shirin", "ширин", "boyovut", "баёвут", "sayxunobod", "сайхунабад",
        "sardoba", "сардоба", "mirzaobod", "мирзаабад", "oqoltin", "акалтын", "xovos", "хаваст",
        "baxt", "бахт",
    ],
    "navoiy": [
        "navoiy", "navoi", "навои", "zarafshon", "зарафшан", "uchquduq", "учкудук",
        "karmana", "кармана", "qiziltepa", "кызылтепа", "xatirchi", "хатырчи",
        "nurota", "нурата", "konimex", "канимех", "tomdi", "тамды", "navbahor", "навбахор",
    ],
    "xorazm": [
        "xorazm", "xorezm", "хорезм", "urganch", "urgench", "ургенч", "xiva", "хива",
        "xonqa", "ханка", "hazorasp", "хазарасп", "shovot", "шават", "gurlan", "гурлен",
        "yangibozor", "янгибазар", "qoshkopir", "кошкупыр", "bogot", "багат", "tuproqqala",
        "yangiariq", "янгиарык",
    ],
    "qoraqalpogiston": [
        "qoraqalpogiston", "karakalpakstan", "каракалпакстан", "nukus", "нукус",
        "tortkol", "турткуль", "beruniy", "беруни", "qongirot", "кунград",
        "xojayli", "ходжейли", "chimboy", "чимбай", "moynoq", "муйнак", "ellikqala", "элликкала",
        "taxtakopir", "тахтакупыр", "qanlikol", "канлыкуль", "shumanay", "шуманай",
        "bozatov", "бозатау", "kegeyli", "кегейли", "qoraozak", "караузяк",
    ],
    "xalqaro": [
        "rossiya", "россия", "moskva", "москва", "piter", "spb", "санкт-петербург",
        "krasnodar", "краснодар", "rostov", "ростов", "novosibirsk", "новосибирск",
        "samara", "самара", "qozon", "казань", "yekaterinburg", "екатеринбург",
        "qozogiston", "казахстан", "olmaota", "almaty", "алматы", "chimkent", "шымкент",
        "ostona", "astana", "астана", "turkiston", "туркестан", "aqtau", "актау",
        "tojikiston", "таджикистан", "dushanbe", "душанбе", "xojand", "ходжент",
        "qirgiziston", "киргизия", "кыргызстан", "bishkek", "бишкек", "osh", "ош",
        "turkiya", "турция", "istanbul", "стамбул", "xitoy", "китай", "urumchi", "урумчи",
        "yiwu", "иу", "guanchjou", "гуанчжоу", "gruziya", "грузия", "poti", "поти",
        "tbilisi", "тбилиси", "eron", "иран", "bandar abbos", "бандар аббас",
    ],
}

MACRO_REGIONS: dict[str, list[str]] = {
    "vodiy": ["fargona", "andijon", "namangan"],
    "voha": ["qashqadaryo", "surxondaryo", "buxoro", "navoiy"],
    "markaz": ["toshkent", "sirdaryo", "jizzax", "samarqand"],
}

_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q",
    "ғ": "g", "ҳ": "h",
}

_SUFFIX_PATTERN = re.compile(
    r"(?:dagi|daka|gacha|kacha|qacha|dan|den|ga|ka|qa|ge|da|de|ni|ning|bozori|bozoriga|markazi|markaziga|tumani|shahri|shahar|viloyati|oblasti)$",
    re.IGNORECASE,
)

# Global in-memory lookup table
CITY_TO_REGION: dict[str, str] = {}


def _rebuild_city_lookup():
    """Barcha shahar va dinamik DB shaharlarini lookup lug'atiga yig'adi."""
    global CITY_TO_REGION
    new_map = {}
    for _region, _cities in BASE_REGION_CITIES.items():
        for _city in _cities:
            norm_c = normalize(_city)
            new_map[norm_c] = _region
            stripped_c = strip_suffix(norm_c)
            if stripped_c:
                new_map[stripped_c] = _region

    # DB dan CustomCity larni yuklash
    try:
        session = get_session()
        try:
            from app.models import CustomCity
            custom_rows = session.query(CustomCity).filter_by(is_active=True).all()
            for row in custom_rows:
                norm_name = normalize(row.name)
                norm_reg = normalize(row.region)
                new_map[norm_name] = norm_reg
                stripped_name = strip_suffix(norm_name)
                if stripped_name:
                    new_map[stripped_name] = norm_reg
        finally:
            session.close()
    except Exception:
        pass

    CITY_TO_REGION = new_map


@functools.lru_cache(maxsize=4096)
def normalize(text: str) -> str:
    """Shahar/matn taqqoslash uchun tezkor keshlangan normalizatsiya."""
    if not text:
        return ""
    t = text.lower().strip()
    t = "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in t)
    t = t.replace("’", "'").replace("`", "'").replace("‘", "'").replace("ʻ", "'").replace("ʼ", "'")
    t = t.replace("'", "")
    t = re.sub(r"[^a-z0-9\s-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


@functools.lru_cache(maxsize=4096)
def strip_suffix(word: str) -> str:
    """So'z oxiridagi grammatik qo'shimchalarni tozalaydi (masalan: toshkentdan -> toshkent)."""
    clean = normalize(word)
    if not clean or len(clean) <= 3:
        return clean
    stripped = _SUFFIX_PATTERN.sub("", clean).strip()
    return stripped if len(stripped) >= 3 else clean


_rebuild_city_lookup()


def reload_geodata():
    """Admin yangi shahar qo'shganda yoki o'chirganda keshni yangilaydi."""
    normalize.cache_clear()
    strip_suffix.cache_clear()
    _rebuild_city_lookup()


def region_of(city_text: str) -> str | None:
    """Berilgan shahar/joy nomiga mos viloyatni topadi (topilmasa None)."""
    if not city_text:
        return None
    norm = normalize(city_text)
    if not norm:
        return None

    if norm in CITY_TO_REGION:
        return CITY_TO_REGION[norm]

    if norm in MACRO_REGIONS:
        return norm

    stripped = strip_suffix(norm)
    if stripped in CITY_TO_REGION:
        return CITY_TO_REGION[stripped]

    for word in norm.split():
        if word in CITY_TO_REGION:
            return CITY_TO_REGION[word]
        st_word = strip_suffix(word)
        if st_word in CITY_TO_REGION:
            return CITY_TO_REGION[st_word]

    for known_city, reg in CITY_TO_REGION.items():
        if len(known_city) >= 4 and (known_city in norm or norm in known_city):
            return reg

    return None


CANONICAL_REGION_NAMES: dict[str, str] = {
    "toshkent": "Toshkent",
    "samarqand": "Samarqand",
    "fargona": "Farg'ona",
    "andijon": "Andijon",
    "namangan": "Namangan",
    "buxoro": "Buxoro",
    "qashqadaryo": "Qashqadaryo",
    "surxondaryo": "Surxondaryo",
    "jizzax": "Jizzax",
    "sirdaryo": "Sirdaryo",
    "navoiy": "Navoiy",
    "xorazm": "Xorazm",
    "qoraqalpogiston": "Qoraqalpog'iston",
    "vodiy": "Vodiy",
    "voha": "Voha",
    "markaz": "Markaz",
}


def canonical_city_name(city_text: str) -> str | None:
    """Foydalanuvchi kiritgan yoki parse qilingan matnni chiroyli shahar/viloyat nomiga aylantiradi."""
    if not city_text:
        return None
    norm = normalize(city_text)
    reg = region_of(norm)
    if not reg:
        return None

    if norm in MACRO_REGIONS:
        return CANONICAL_REGION_NAMES.get(norm, norm.title())

    stripped = strip_suffix(norm)
    # Agar viloyat markazi yoki viloyat varianti bo'lsa
    if norm in ("toshkent", "tashkent", "samarqand", "samarkand", "fargona", "fergana",
                "andijon", "andijan", "namangan", "buxoro", "bukhara", "qarshi", "karshi",
                "termiz", "jizzax", "guliston", "navoiy", "navoi", "urganch", "urgench", "nukus"):
        if norm in ("qarshi", "karshi"):
            return "Qarshi"
        if norm in ("termiz",):
            return "Termiz"
        if norm in ("guliston",):
            return "Guliston"
        if norm in ("urganch", "urgench"):
            return "Urganch"
        if norm in ("nukus",):
            return "Nukus"
        return CANONICAL_REGION_NAMES.get(reg, reg.title())

    for c in BASE_REGION_CITIES.get(reg, []):
        norm_c = normalize(c)
        if norm_c == norm or norm_c == stripped:
            return c.title()

    return CANONICAL_REGION_NAMES.get(reg, reg.title())


def all_known_city_tokens() -> list[str]:
    """Parsing paytida matndan shahar nomlarini qidirish uchun token'lar ro'yxati."""
    return list(CITY_TO_REGION.keys())


# --- Google Maps Link Generators ---

def google_maps_search_url(location: str | None) -> str | None:
    """Google Maps qidiruv URL manzilini yaratadi."""
    if not location:
        return None
    query = f"{location}, Uzbekistan" if location.lower() not in ("rossiya", "moskva", "almaty", "astana", "bishkek", "dushanbe", "istanbul") else location
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.google.com/maps/search/?api=1&query={encoded}"


def google_maps_route_url(origin: str | None, destination: str | None) -> str | None:
    """Ikki nuqta o'rtasidagi Google Maps marshrut (Directions) havolasini yaratadi."""
    if not origin or not destination:
        return None
    orig_q = f"{origin}, Uzbekistan" if origin.lower() not in ("rossiya", "moskva", "almaty", "astana", "bishkek", "dushanbe") else origin
    dest_q = f"{destination}, Uzbekistan" if destination.lower() not in ("rossiya", "moskva", "almaty", "astana", "bishkek", "dushanbe") else destination
    enc_orig = urllib.parse.quote_plus(orig_q)
    enc_dest = urllib.parse.quote_plus(dest_q)
    return f"https://www.google.com/maps/dir/?api=1&origin={enc_orig}&destination={enc_dest}"

