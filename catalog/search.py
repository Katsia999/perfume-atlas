from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import re

from django.utils import timezone

from .intent import preferred_kind
from .models import Fragrance, FragrancePerformance, FragranceWear, Material, SEASONS, WearOption
from .search_language import (
    ALTERNATIVE_LINKS, BRACKETS, EXACT_PROFILE_ALIASES, NEGATIONS, NOTE_CASES, PROFILE_ALIASES, PROFILE_FAMILIES,
    SCOPES, UNRESTRICTED, VERSION_ALIASES, WORD, Condition,
    conditions, correct_query, fold, postgres_stems, query_parts, words,
)


FRAGRANCE = "fragrance"
KINDS = (
    (FRAGRANCE, "Аромат"),
    *Material.Kind.choices,
)
PERFORMANCE_KINDS = dict(FragrancePerformance.Kind.choices)
WEAR_KINDS = dict(FragranceWear.Kind.choices)
SOURCED_FILTERS = PERFORMANCE_KINDS.keys() | WEAR_KINDS.keys()
WEIGHTS = {
    "name": 24, "note": 10, "character": 9, "family": 9, "brand": 8, "version": 6,
    **dict.fromkeys(SOURCED_FILTERS, 9),
}
MATCH_LABELS = {
    "name": "Название", "note": "Ноты", "character": "Характер", "family": "Семейство",
    "brand": "Бренд", "version": "Версия", **PERFORMANCE_KINDS, **WEAR_KINDS,
}
WEAR_ALIASES = {
    ("season", WearOption.SPRING.label): (
        "весна", "весну", "весны", "на весну", "для весны", "весной", "весною",
        "весенний", "весенняя", "весеннее", "весенние", "весеннего", "весеннее время", "весенний сезон",
    ),
    ("season", WearOption.SUMMER.label): (
        "лето", "лета", "на лето", "для лета", "летом", "летний", "летняя", "летнее", "летние",
        "летнего", "летними", "летнее время", "летний сезон",
    ),
    ("season", WearOption.AUTUMN.label): (
        "осень", "осени", "на осень", "для осени", "осенью", "осенний", "осенняя", "осеннее", "осенние",
        "осеннего", "осеннее время", "осенний сезон",
    ),
    ("season", WearOption.WINTER.label): (
        "зима", "зиму", "зимы", "на зиму", "для зимы", "зимой", "зимою", "зимний", "зимняя", "зимнее", "зимние",
        "зимнего", "зимнее время", "зимний сезон",
    ),
    ("season", WearOption.ALL_YEAR.label): (
        "круглый год", "круглогодичный", "круглогодичные", "на круглый год", "на весь год",
        "на любой сезон", "для любого сезона", "на все сезоны", "для всех сезонов", "в любое время года",
        "всесезонный", "всесезонные",
    ),
    ("time", WearOption.DAY.label): (
        "день", "днём", "на день", "для дня", "дневное время", "дневной", "дневная", "дневные",
    ),
    ("time", WearOption.EVENING.label): (
        "вечер", "вечера", "вечером", "вечерами", "на вечер", "для вечера",
        "вечернее время", "вечерний", "вечерняя", "вечерние",
    ),
}
EXACT_WEAR_PHRASES = {words(label): {key} for key, labels in WEAR_ALIASES.items() for label in labels}
WEAR_QUESTION = re.compile(
    r"\b(?:когда\s+(?:лучше\s+)?носить|на\s+какой\s+сезон|для\s+какого\s+сезона|"
    r"(?:на|в)\s+какое\s+время\s+года)\b"
)
LIGHTNESS_ALIASES = ("лёгкий", "лёгкое звучание", "воздушный", "воздушное звучание")
PERFORMANCE_ALIASES = {
    ("longevity", "Высокая"): (
        "стойкий", "долгостойкий", "очень стойкий", "высокая стойкость",
        "хорошая стойкость", "долгая стойкость", "долго держится", "долго держатся",
    ),
    ("longevity", "Средняя"): ("средняя стойкость", "умеренная стойкость"),
    ("longevity", "Низкая"): ("низкая стойкость", "слабая стойкость", "нестойкий", "быстро выветривается"),
    ("sillage", "Лёгкий"): ("лёгкий шлейф", "слабый шлейф", "деликатный шлейф", "ненавязчивый шлейф"),
    ("sillage", "Умеренный"): ("умеренный шлейф", "средний шлейф"),
    ("sillage", "Заметный"): (
        "заметный шлейф", "сильный шлейф", "интенсивный шлейф", "мощный шлейф", "выраженный шлейф",
    ),
}
UNRESTRICTED_ALIASES = {
    ("longevity",): ("любая стойкость", "стойкость любая", "стойкость не важна"),
    ("sillage",): ("любой шлейф", "шлейф любой", "шлейф не важен"),
    ("longevity", "sillage"): (
        "любая стойкость и шлейф", "любой шлейф и стойкость",
        "стойкость и шлейф любые", "шлейф и стойкость любые",
        "стойкость и шлейф не важны", "шлейф и стойкость не важны",
    ),
    ("season",): ("сезон не важен", "сезон любой", "любой сезон", "без ограничений по сезону"),
    ("time",): ("время суток не важно", "любое время суток", "время суток любое"),
}
PERFORMANCE_WORD = re.compile(r"\b(?:шлейф\w*|стойкост\w*)\b")
DURATION_HOURS = re.compile(r"\b\d+(?:[–-]\d+)?\s+час\w*\b")
MONTH = re.compile(
    r"\b(?:за\s+(?:(?:последн|прошедш)\w*\s+)?месяц|"
    r"(?:за\s+)?(?:последние\s+)?30\s+дней)\b"
)
FRESH = re.compile(r"\b(?:свеж|последн|недавн)\w*\s+(?:новост|новинк)\w*\b")
NEWS_REQUEST = re.compile(r"\bкакие\s+новые\b|\b(?:представили|выпустили|анонсировали)\b")
RECOMMENDATION = re.compile(
    r"\b(?:посоветуй(?:те)?|подбери(?:те)?|предложи(?:те)?|порекомендуй(?:те)?|подскажи(?:те)?|"
    r"ищу|ищем|предпочитаю|предпочитаем|что-нибудь)\b"
)
UNSUPPORTED_FILTERS = (
    ("стойкость в часах", DURATION_HOURS),
    ("цену", re.compile(r"\b(?:цена|цену|цены|бюджет\w*|недорог\w*|дешев\w*|дороже|рубл\w*)\b|"
                        r"\b(?:до|от)\s+\d+\b(?!\s+час)|₽")),
    ("полное отсутствие запаха", re.compile(r"\bбез\s+запаха\s*(?:$|[,.!?;]|(?:и|или|но)\b)")),
)
STOP = """
    пожалуйста покажи покажите какие какой какая мне найди найдите расскажи хочу нужен нужны
    про о об от в во на над из у для до к ко как чем что такое этот свою свой том
    с со без не и или либо но а также ещё по за последний последние прошедший месяц 30 дней
    свежие новые недавно представили выпустили анонсировали
    посоветуй посоветуйте подбери подберите назови назовите предложи предложите
    я можешь можете можно посоветовать подобрать предложить порекомендовать
    порекомендуй порекомендуйте подскажи подскажите ищу ищем предпочитаю предпочитаем
    что-нибудь какой-нибудь что-то который чтобы есть желательно что ли
"""
FILTER_WORDS = """
    нота ноты профиль характер звучание направление бренд марка концентрация версия
    запах запахом запаха запаху пахнет пахнут пахли
    носить подойдёт подойдут подходит подходят лучше сезон
"""
TYPE_WORDS = {
    FRAGRANCE: "аромат духи духов духами парфюм",
    Material.Kind.ARTICLE: "статья текст прочитать почитать",
    Material.Kind.VIDEO: "видео ролик видеоролик посмотреть",
    Material.Kind.NEWS: "новость новинка",
}
TEXT_VARIANTS = {
    "выбрать": "выбор", "выбору": "выбор", "выбора": "выбор",
    "сердца": "сердце", "сердцем": "сердце",
}
NAME_ALIASES = {
    "allure": ("Аллюр",),
    "aqua allegoria mandarine basilic": ("Аква Аллегория Мандарин Базилик",),
    "aqua allegoria nerolia vetiver": ("Аква Аллегория Неролия Ветивер", "Неролия Ветивер"),
    "belle cherie": ("Бель Шери",),
    "belle de nuit": ("Бель де Нюи",),
    "bleu de chanel": ("Блё де Шанель", "Блю де Шанель"),
    "bombshell": ("Бомбшел", "Бомбшелл"),
    "bombshell intense": ("Бомбшел Интенс", "Бомбшелл Интенс"),
    "cedrat": ("Цедрат", "Седра", "Седрат"),
    "cedre gingembre": ("Седр Жанжамбр", "Седр Женжамбр"),
    "chance eau tendre": ("Шанс О Тандр",),
    "coco": ("Коко",),
    "coco mademoiselle": ("Коко Мадемуазель",),
    "diamant": ("Диаман", "Диамант"),
    "donna born in roma": ("Донна Борн ин Рома",),
    "donna born in roma intense": ("Донна Борн ин Рома Интенс",),
    "donna born in roma coral fantasy": ("Донна Борн ин Рома Корал Фэнтези",),
    "donna born in roma green stravaganza": ("Донна Борн ин Рома Грин Страваганца",),
    "etoile": ("Этуаль",),
    "figue": ("Фиг", "Инжир"),
    "fleur de citronnier": ("Флёр де Ситронье",),
    "fleurs de cerisier": ("Флёр де Серизье",),
    "flora gorgeous gardenia": ("Флора Горджиос Гардения", "Флора Горджес Гардения", "Горджиос Гардения"),
    "flora gorgeous jasmine": ("Флора Горджиос Жасмин", "Горджиос Жасмин"),
    "flora gorgeous magnolia": ("Флора Горджиос Магнолия", "Горджиос Магнолия"),
    "flora gorgeous orchid": ("Флора Горджиос Орхид", "Горджиос Орхид"),
    "fragonard": ("Фрагонар",),
    "grain de soleil": ("Грен де Солей",),
    "grenade pivoine": ("Гренад Пивуан",),
    "guilty pour femme": ("Гилти Пур Фам",),
    "habanita": ("Абанита", "Хабанита"),
    "idole": ("Идоль",),
    "juste un baiser": ("Жюст эн Безе", "Жюст ан Безе"),
    "libre": ("Либр", "Либре"),
    "mon guerlain": ("Мон Герлен",),
    "moonlight": ("Мунлайт",),
    "neroli orchidee": ("Нероли Орхидея", "Нероли Оркиде"),
    "replica autumn vibes": ("Реплика Отэм Вайбс", "Отэм Вайбс", "Аутумн Вайбс"),
    "replica beach walk": ("Реплика Бич Уок", "Бич Уок"),
    "replica by the fireplace": ("Реплика Бай зе Файерплейс", "Бай зе Файерплейс"),
    "replica jazz club": ("Реплика Джаз Клаб", "Реплика Джаз Клуб", "Джаз Клаб", "Джаз Клуб"),
    "replica lazy sunday morning": ("Реплика Лейзи Сандей Морнинг", "Лейзи Сандей Морнинг"),
    "rose": ("Роза", "Роз"),
    "santal cardamome": ("Сантал Кардамом",),
    "santal insolent": ("Сантал Энсолан", "Сантал Инсолент"),
    "tease": ("Тис", "Тиз"),
    "tease cocoa soiree": ("Тис Какао Суаре", "Тиз Какао Суаре"),
    "tease creme cloud": ("Тис Крем Клауд", "Тиз Крем Клауд"),
    "tease glam": ("Тис Глэм", "Тиз Глэм", "Тис Глам", "Тиз Глам"),
    "tease strawberry bisou": ("Тис Строберри Бизу", "Тиз Строберри Бизу"),
    "terre d hermes": ("Тер д’Эрмес", "Терра д’Эрмес"),
    "terre d hermes eau givree": ("Тер д’Эрмес О Живре", "Терра д’Эрмес О Живре"),
    "twilly d hermes": ("Твилли д’Эрмес", "Твилли Эрмес", "Твилли"),
    "uomo born in roma coral fantasy": ("Уомо Борн ин Рома Корал Фэнтези",),
    "uomo born in roma intense": ("Уомо Борн ин Рома Интенс",),
    "un jardin sur le nil": ("Эн Жарден сюр лё Ниль", "Ун Жарден сюр ле Ниль", "Сад на Ниле"),
    "vanille": ("Ваниль",),
    "verveine": ("Вервен", "Вербена"),
}


def aliases(value):
    return tuple(label.strip() for label in value.split("|") if label.strip())


def version_labels(version):
    for canonical, variants in VERSION_ALIASES.items():
        labels = (canonical, *variants)
        if words(version) in map(words, labels):
            return (version, *labels)
    return (version,)


@dataclass
class Result:
    kind: str
    title: str
    entry: Fragrance | Material
    entities: dict
    matches: tuple[str, ...] = ()
    wear_match: bool = False

    @property
    def label(self):
        return dict(KINDS)[self.kind]

    @property
    def text(self):
        return f"{self.entry.description} {getattr(self.entry, 'body', '')}"


@dataclass
class SearchResponse:
    effective_query: str
    results: list[Result]
    since: date | None = None
    until: date | None = None
    groups: tuple[tuple[tuple[Condition, ...], ...], ...] = ()
    excluded: tuple[Condition, ...] = ()
    unknown: str = ""
    ambiguous_alternative: bool = False
    unsupported_slash: bool = False
    unsupported_brackets: bool = False
    unsupported_filters: tuple[str, ...] = ()
    contradiction: tuple[str, ...] = ()
    incompatible_kind: bool = False
    missing_performance: bool = False
    missing_wear: bool = False
    unrestricted_filters: tuple[str, ...] = ()
    wear_lookup: bool = False


def wear_keys(facts):
    for fact in facts:
        options = fact.options
        if WearOption.ALL_YEAR in options:
            options = (*options, *SEASONS)
        for option in options:
            yield fact.kind, WearOption(option).label


def documents():
    fragrances = Fragrance.objects.filter(is_published=True).select_related("brand", "family")
    for entry in fragrances.prefetch_related("notes", "character_labels", "performance", "wear"):
        name_labels = (entry.name, *NAME_ALIASES.get(" ".join(words(entry.name)), ()))
        brand_labels = (entry.brand.name, *aliases(entry.brand.aliases))
        yield Result(FRAGRANCE, str(entry), entry, {
            ("name", entry.name): name_labels,
            ("name", f"{entry.brand.name} {entry.name}"): tuple(
                f"{brand} {name}" for brand in brand_labels for name in name_labels
            ),
            ("brand", entry.brand.name): brand_labels,
            ("family", entry.family.name): (entry.family.name,),
            ("version", entry.version): version_labels(entry.version),
            **{("note", note.name): (note.name, *aliases(note.aliases)) for note in entry.notes.all()},
            **{("character", row.label): (row.label,) for row in entry.character_labels.all()},
            **{(fact.kind, fact.get_level_display()): () for fact in entry.performance.all() if fact.level},
            **dict.fromkeys(wear_keys(entry.wear.all()), ()),
        })
    materials = Material.objects.filter(is_published=True).prefetch_related("notes", "families")
    for entry in materials:
        yield Result(entry.kind, entry.title, entry, {
            ("name", entry.title): (entry.title,),
            **{("family", family.name): (family.name,) for family in entry.families.all()},
            **{("note", note.name): (note.name, *aliases(note.aliases)) for note in entry.notes.all()},
        })


def lexicon(records):
    entities = defaultdict(set)
    corpus = set()
    titles = set()
    for record in records:
        for key, variants in record.entities.items():
            entities[key].update(variants)
            if record.kind == FRAGRANCE and key[0] == "name":
                titles.update(tuple(WORD.findall(label.lower())) for label in variants)
        corpus.update(words(record.title))
        corpus.update(words(record.text))
    labels = {word for variants in entities.values() for label in variants for word in words(label)}
    spelling = {
        fold(label): label.lower()
        for (kind, _), variants in entities.items()
        if kind in {"note", "brand"}
        for label in variants
        if WORD.fullmatch(label)
    }
    spelling.update((fold(label), label) for labels in PROFILE_ALIASES.values() for label in labels)
    spelling.update((label, label) for label in EXACT_PROFILE_ALIASES)
    note_labels = {
        words(label): key
        for key, variants in entities.items()
        if key[0] == "note"
        for label in variants
    }
    cases = [forms for forms in NOTE_CASES if words(forms[0]) in note_labels]
    cases.sort(key=lambda forms: len(words(forms[0])), reverse=True)
    return entities, corpus | labels, spelling, cases, note_labels, titles


def phrase_index(entities, cases, note_labels, normalize):
    phrases = defaultdict(set)
    for key, variants in entities.items():
        for label in variants:
            phrases[normalize(label)].add(key)
            if key[0] == "family":
                phrases[normalize(f"{label} семейство")].add(key)
                phrases[normalize(f"семейство {label}")].add(key)
    for forms in cases:
        for label in forms:
            phrases[normalize(label)].add(note_labels[words(forms[0])])
    for key, variants in PERFORMANCE_ALIASES.items():
        for label in variants:
            phrases[normalize(label)].add(key)
            if len(words(label)) == 2 and words(label)[1] in {"шлейф", "стойкость"}:
                phrases[normalize(" ".join(reversed(words(label))))].add(key)
    for categories, variants in UNRESTRICTED_ALIASES.items():
        for label in variants:
            phrases[normalize(label)].update((UNRESTRICTED, category) for category in categories)

    for label in LIGHTNESS_ALIASES:
        phrases[normalize(label)].add(("lightness", WearOption.LIGHT.label))

    vanilla_phrase = normalize("ванильный")
    vanilla_keys = {("note", "Ваниль"), ("character", "Ванильный")}
    phrases[vanilla_phrase].update(vanilla_keys)
    profiles = {vanilla_phrase: "Ванильный"}
    for character, family in (*PROFILE_FAMILIES.items(), ("Фруктовый", "Фруктовое")):
        labels = (character, family, *PROFILE_ALIASES.get(character, ()))
        profile_stem = normalize(character)[0]
        keys = {
            (kind, name) for kind, name in entities
            if (kind == "character" and normalize(name) == (profile_stem,)) or
            (kind == "family" and (name == family or
                                   (character == "Фруктовый" and profile_stem in normalize(name))))
        }
        if keys:
            for label in labels:
                phrase = normalize(label)
                profiles[phrase] = character
                phrases[phrase].update(keys)
    return phrases, profiles


def matching_group_keys(group, entities):
    return set().union(*(
        condition.keys & entities.keys()
        for branch in group if all(condition.keys & entities.keys() for condition in branch)
        for condition in branch
    ))


def rank(records, terms, positive, response, kind, preferred, normalize):
    scored = []
    term_set = set(terms)
    single_note = (
        not kind and len(words(response.effective_query)) == 1
        and bool(positive) and all(category == "note" for category, _ in positive)
    )
    excluded_sourced = {key for condition in response.excluded for key, _ in condition.keys} & SOURCED_FILTERS
    wear_details = excluded_sourced & WEAR_KINDS.keys()
    if response.wear_lookup:
        wear_details.update(("season", "time"))
    for record in records:
        if kind and record.kind != kind:
            continue
        if response.since and not response.since <= record.entry.published_on <= response.until:
            continue
        if any(condition.keys.intersection(record.entities) for condition in response.excluded):
            continue
        if excluded_sourced - {category for category, _ in record.entities}:
            continue
        matched_groups = [matching_group_keys(group, record.entities) for group in response.groups]
        if not all(matched_groups):
            continue
        structured = positive.intersection(record.entities).union(*matched_groups)
        title = normalize(record.title)
        title_hits = term_set.intersection(title)
        text_hits = (term_set - title_hits).intersection(normalize(record.text))
        if not (structured or title_hits or text_hits) and (positive or terms):
            continue
        score = sum(WEIGHTS[key[0]] for key in structured) + 6 * len(title_hits) + len(text_hits)
        if len(terms) > 1 and any(title[i:i + len(terms)] == terms for i in range(len(title))):
            score += 5
        if record.kind == preferred:
            score += 3
        displayed = structured
        if wear_details and record.kind == FRAGRANCE:
            displayed = structured.union(
                (fact.kind, label) for fact in record.entry.wear.all() if fact.kind in wear_details
                for label in fact.option_labels
            )
        record.matches = tuple(
            f"{label}: {', '.join(names)}" for category, label in MATCH_LABELS.items()
            if (names := sorted(name for key, name in displayed if key == category))
        )
        record.wear_match = any(category in WEAR_KINDS for category, _ in displayed)
        publication = getattr(record.entry, "published_on", None)
        recency = publication.toordinal() if record.kind == Material.Kind.NEWS else 0
        linked_fragrance = single_note and record.kind == FRAGRANCE and bool(structured)
        scored.append((not linked_fragrance, -score, -recency, record.title.casefold(), record.entry.pk, record))
    return [item[-1] for item in sorted(scored, key=lambda item: item[:-1])]


def search(query, selected_kind="", *, autocorrect=True):
    records = list(documents())
    if not query and selected_kind in Material.Kind.values:
        results = [record for record in records if record.kind == selected_kind]
        if selected_kind in (Material.Kind.VIDEO, Material.Kind.NEWS):
            results.sort(key=lambda record: record.entry.published_on or date.min, reverse=True)
        return SearchResponse("", results)
    entities, known, spelling, cases, note_labels, titles = lexicon(records)
    fixed_vocabulary = (
        set(words(f"{STOP} {FILTER_WORDS} семейство фруктовый фруктовое")) |
        {word for pair in PROFILE_FAMILIES.items() for label in pair for word in words(label)} |
        {word for variants in PROFILE_ALIASES.values() for label in variants for word in words(label)} |
        {word for variants in PERFORMANCE_ALIASES.values() for label in variants for word in words(label)} |
        {word for phrase in EXACT_WEAR_PHRASES for word in phrase} |
        {word for label in LIGHTNESS_ALIASES for word in words(label)} |
        {"ванильный"} |
        {word for variants in UNRESTRICTED_ALIASES.values() for label in variants for word in words(label)} |
        set(EXACT_PROFILE_ALIASES) |
        set(TEXT_VARIANTS) | set(TEXT_VARIANTS.values()) |
        {word for value in TYPE_WORDS.values() for word in words(value)} |
        {word for forms in cases for label in forms for word in words(label)}
    )
    stems = postgres_stems(known | fixed_vocabulary | set(words(query)))
    brand_stems = defaultdict(set)
    for (category, name), variants in entities.items():
        if category == "brand" and len(words(name)) == 1:
            for label in variants:
                if len(words(label)) == 1:
                    brand_stems[stems[words(label)[0]]].add(stems[words(name)[0]])
    equivalents = {stem: names.pop() for stem, names in brand_stems.items() if len(names) == 1}

    def normalize(text):
        normalized = (stems[TEXT_VARIANTS.get(word, word)] for word in words(text))
        return tuple(equivalents.get(stem, stem) for stem in normalized)

    if autocorrect:
        known_stems = {stems[word] for word in known | fixed_vocabulary}
        effective = correct_query(query, stems, known_stems, spelling, cases, titles)
    else:
        effective = query

    phrases, profiles = phrase_index(entities, cases, note_labels, normalize)
    parts = list(query_parts(effective, normalize, phrases, profiles, EXACT_WEAR_PHRASES))
    positive = set().union(*(part.matches for part in parts))
    remaining = tuple(
        stem for part in parts for stem in normalize(part.text)
        if not part.matches or len(words(part.text)) == 1
        or any(key[0] not in {"name", UNRESTRICTED} for key in part.matches)
    )
    cue_stems = {kind: set(normalize(value)) for kind, value in TYPE_WORDS.items()}
    remaining_set = set(remaining)
    cues = {kind for kind, values in cue_stems.items() if values & remaining_set}
    folded = fold(effective)
    fresh = FRESH.search(folded)
    month = MONTH.search(folded)
    news_request = NEWS_REQUEST.search(folded)
    response = SearchResponse(effective, [])
    kind = selected_kind
    if kind in ("", Material.Kind.NEWS) and (
        fresh or
        (month and (kind == Material.Kind.NEWS or Material.Kind.NEWS in cues or news_request))
    ):
        kind = Material.Kind.NEWS
        response.until = timezone.localdate()
        response.since = response.until - timedelta(days=29)
        if fresh:
            positive.discard(("character", "Свежий"))

    ignored = set(normalize(STOP)).union(*cue_stems.values())
    terms = tuple(dict.fromkeys(word for word in remaining if word not in ignored))
    controls = {fold(part.text) for part in parts if not part.matches}
    material_intent = kind == Material.Kind.ARTICLE or bool(
        cues - {FRAGRANCE} or news_request or folded.startswith(("что такое ", "как выбрать ", "почему "))
    )
    wear_question = WEAR_QUESTION.search(folded)
    if wear_question and not material_intent and kind in ("", FRAGRANCE):
        requested_names = {key for key in positive if key[0] == "name"}
        response.wear_lookup = any(
            record.kind == FRAGRANCE and requested_names.intersection(record.entities) for record in records
        )
        if not response.wear_lookup and wear_question.start() == 0:
            material_intent = True
    if material_intent:
        positive = {key for key in positive if key[0] not in {*WEAR_KINDS, UNRESTRICTED}}
    matched_kinds = {key for key, _ in positive}
    unrestricted = {category for key, category in positive if key == UNRESTRICTED}
    recommendation = RECOMMENDATION.search(folded)
    filter_terms = (
        response.wear_lookup or unrestricted or controls & (SCOPES | ALTERNATIVE_LINKS) or
        matched_kinds & ({"version"} | SOURCED_FILTERS) or
        (kind in ("", FRAGRANCE) and (matched_kinds & {"character", "family"} or recommendation)) or
        (positive and (FRAGRANCE in cues or controls & ({"и", "/"} | BRACKETS))) or
        normalize("семейство")[0] in remaining_set or PERFORMANCE_WORD.search(folded)
    )
    if not material_intent and (filter_terms or positive or FRAGRANCE in cues or kind == FRAGRANCE):
        response.unsupported_filters = tuple(label for label, pattern in UNSUPPORTED_FILTERS if pattern.search(folded))
        if response.unsupported_filters:
            return response

    if kind != Material.Kind.ARTICLE and (controls & NEGATIONS or (filter_terms and not material_intent)):
        if controls & BRACKETS:
            response.unsupported_brackets = True
            return response
        if "/" in controls:
            response.unsupported_slash = True
            return response
        condition_fillers = ignored | set(normalize(FILTER_WORDS))
        if response.wear_lookup:
            condition_fillers.update(normalize(wear_question[0]))
        groups, excluded, response.unknown, response.ambiguous_alternative = conditions(parts, normalize, condition_fillers)
        if response.unknown or response.ambiguous_alternative:
            return response
        if unrestricted:
            groups = tuple(
                tuple(tuple(condition for condition in branch if not condition.unrestricted) for branch in group)
                for group in groups
            )
            groups = tuple(group for group in groups if all(group))
        response.groups, response.excluded = groups, excluded
        requested = {category for condition in excluded for category, _ in condition.keys}
        requested.update(category for group in groups for branch in group
                         for condition in branch for category, _ in condition.keys)
        response.unrestricted_filters = tuple(
            MATCH_LABELS[category].lower()
            for category in (*PERFORMANCE_KINDS, *WEAR_KINDS) if category in unrestricted - requested
        )
        banned = set().union(*(condition.keys for condition in excluded))
        for group in groups:
            blocked = [tuple(condition.label for condition in branch if condition.keys <= banned) for branch in group]
            if all(blocked):
                response.contradiction = tuple(dict.fromkeys(label for labels in blocked for label in labels))
                break
        response.incompatible_kind = kind not in ("", FRAGRANCE)
        if response.contradiction or response.incompatible_kind:
            return response
        if groups or excluded or unrestricted:
            response.results = rank(records, (), set(), response, FRAGRANCE, "", normalize)
            if not response.results:
                missing = set().union(*(
                    (requested & SOURCED_FILTERS) - {category for category, _ in record.entities}
                    for record in records if record.kind == FRAGRANCE
                ))
                response.missing_performance = bool(missing & PERFORMANCE_KINDS.keys())
                response.missing_wear = bool(missing & WEAR_KINDS.keys())
        return response

    if FRAGRANCE in cues and len(cues) > 1:
        cues.remove(FRAGRANCE)
    hinted = next(iter(cues)) if len(cues) == 1 else ""
    if not (terms or positive or hinted or response.since):
        return response
    if not (terms or positive) and not kind:
        kind = hinted
    if not (terms or positive or response.since) and hinted != kind:
        return response
    preferred = "" if kind else (preferred_kind(effective) or hinted)
    response.results = rank(records, terms, positive, response, kind, preferred, normalize)
    return response
