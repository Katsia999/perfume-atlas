import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import connection


WORD = re.compile(r"[^\W_]+")
RUSSIAN_WORD = re.compile(r"[а-я]{5,}")
TITLE_WORD = re.compile(r"[а-я]{2,}")
PART = re.compile(r"[^\W_]+|[,.!?;:/()\[\]{}]")
NEGATIONS = {"без", "не"}
SCOPES = NEGATIONS | {"с", "со"}
CLAUSE_END = {"но", "а", ".", "!", "?", ";", ":"}
BRACKETS = set("()[]{}")
UNRESTRICTED = "unrestricted"
ALTERNATIVE_LINKS = {"или", "либо"}

PROFILE_FAMILIES = {
    "Амбровый": "Амбровое",
    "Древесный": "Древесное",
    "Гурманский": "Гурманское",
    "Цветочный": "Цветочное",
    "Цитрусовый": "Цитрусовое",
}
PROFILE_ALIASES = {
    "Древесный": ("древесина", "древесины", "древесиной"),
    "Фруктовый": ("фрукты",),
}
EXACT_PROFILE_ALIASES = dict.fromkeys(("цветы", "цветов", "цветам", "цветами", "цветах"), "Цветочный")
VERSION_ALIASES = {
    "eau de toilette": ("EDT", "EDТ", "ЕДТ", "туалетная вода", "туалетная водичка"),
    "eau de parfum": (
        "EDP", "EDР", "ЕДП", "парфюмерная вода", "парфюмированная вода", "парфюмированная водичка",
    ),
    "parfum": ("extrait de parfum",),
}


@dataclass(frozen=True)
class QueryPart:
    text: str
    matches: frozenset = frozenset()
    profile: str = ""


@dataclass(frozen=True)
class Condition:
    keys: frozenset
    profile: str = field(default="", compare=False)

    def __str__(self):
        return self.label

    @property
    def unrestricted(self):
        return all(kind == UNRESTRICTED for kind, _ in self.keys)

    @property
    def label(self):
        if self.profile == "Ванильный":
            return "ванильный профиль (нота «Ваниль» или метка «Ванильный»)"
        if self.profile:
            return f"{self.profile.lower()} профиль"
        kind, name = min(self.keys)
        if kind == "character":
            return f"характер «{name}»"
        prefix = {
            "note": "нота", "family": "семейство", "brand": "бренд", "version": "версия",
            "longevity": "стойкость", "sillage": "шлейф",
            "season": "сезон", "time": "время суток", "lightness": "характер звучания",
        }
        return f"{prefix[kind]} «{name}»" if kind in prefix else f"«{name}»"


def query_parts(text, normalize, phrases, profiles, exact_phrases):
    tokens = list(PART.finditer(text))
    longest = max(map(len, (*phrases, *exact_phrases)), default=0)
    index = 0
    while index < len(tokens):
        for size in range(min(longest, len(tokens) - index), 0, -1):
            fragment = text[tokens[index].start():tokens[index + size - 1].end()]
            normalized = normalize(EXACT_PROFILE_ALIASES.get(fold(fragment), fragment))
            matches = None
            if len(normalized) == size:
                matches = exact_phrases.get(words(fragment)) or phrases.get(normalized)
            if matches:
                yield QueryPart(fragment, frozenset(matches), profiles.get(normalized, ""))
                index += size
                break
        else:
            yield QueryPart(tokens[index][0])
            index += 1


def conditions(parts, normalize, ignored):
    groups, excluded, unknown = [], [], []
    branches = [[]]
    scope = ""
    pending = ""
    has_condition = False
    ambiguous = False

    def finish_group():
        nonlocal branches
        if branches[0]:
            groups.append(tuple(tuple(dict.fromkeys(branch)) for branch in branches))
            branches = [[]]

    for part in parts:
        token = fold(part.text)
        if token in ALTERNATIVE_LINKS:
            token = "или"
        if not part.matches:
            if token in SCOPES or token in CLAUSE_END:
                new_scope = token if token in SCOPES else ""
                changes_sign = (scope in NEGATIONS) != (new_scope in NEGATIONS)
                if pending == "или" and token in SCOPES:
                    if changes_sign:
                        ambiguous = True
                    else:
                        scope = new_scope
                        continue
                if pending and not (pending == "и" and token in SCOPES):
                    unknown.append(pending)
                if token in CLAUSE_END or changes_sign:
                    finish_group()
                    has_condition = False
                scope = new_scope
                pending = scope
            elif token in {"или", "и"}:
                if pending or not has_condition:
                    unknown.append(token)
                pending = token
            elif set(normalize(token)) - ignored:
                unknown.append(part.text)
                pending = ""
            continue

        attributes = {key for key in part.matches if key[0] != "name"}
        condition = Condition(frozenset(attributes or part.matches), part.profile)
        if scope in NEGATIONS:
            if condition.unrestricted:
                unknown.append(part.text)
            else:
                excluded.append(condition)
        else:
            if pending == "или" and branches[-1]:
                branches.append([])
            branches[-1].append(condition)
        has_condition = True
        pending = ""

    if pending:
        unknown.append(pending)
    finish_group()
    return (
        tuple(groups),
        tuple(dict.fromkeys(excluded)),
        " ".join(unknown),
        ambiguous,
    )


NOTE_CASES = (
    ("айва", "айвой", "айвы"),
    ("амбровый аккорд", "амбровым аккордом", "амбрового аккорда"),
    ("амбра", "амброй", "амбры"),
    ("апельсин", "апельсином", "апельсина"),
    ("бергамот", "бергамотом", "бергамота"),
    ("ваниль", "ванилью", "ванили"),
    ("таитянская ваниль", "таитянской ванилью", "таитянской ванили"),
    ("ветивер", "ветивером", "ветивера"),
    ("гардения", "гарденией", "гардении"),
    ("герань", "геранью", "герани"),
    ("гиацинт", "гиацинтом", "гиацинта"),
    ("грейпфрут", "грейпфрутом", "грейпфрута"),
    ("древесный аккорд", "древесным аккордом", "древесного аккорда"),
    ("жасмин", "жасмином", "жасмина"),
    ("жасмин самбак", "жасмином самбак", "жасмина самбак"),
    ("иланг", "илангом", "иланга"),
    ("иланг-иланг", "иланг-илангом", "иланг-иланга"),
    ("имбирь", "имбирём", "имбиря"),
    ("кедр", "кедром", "кедра"),
    ("кремень", "кремнем", "кремня"),
    ("лаванда", "лавандой", "лаванды"),
    ("ландыш", "ландышем", "ландыша"),
    ("лимон", "лимоном", "лимона"),
    ("мирабилис", "мирабилисом", "мирабилиса"),
    ("можжевельник", "можжевельником", "можжевельника"),
    ("мускус", "мускусом", "мускуса"),
    ("белый мускус", "белым мускусом", "белого мускуса"),
    ("перец тимут", "перцем тимут", "перца тимут"),
    ("роза", "розой", "розы"),
    ("сандал", "сандалом", "сандала"),
    ("сандаловое дерево", "сандаловым деревом", "сандалового дерева"),
    ("слива", "сливой", "сливы"),
    ("фиалка", "фиалкой", "фиалки"),
    ("цветок апельсина", "цветком апельсина", "цветка апельсина"),
    ("флердоранж", "флердоранжем", "флердоранжа"),
    ("цитрон", "цитроном", "цитрона"),
    ("яблоко", "яблоком", "яблока"),
)


def fold(value):
    value = unicodedata.normalize("NFC", value.lower()).replace("ё", "е")
    return "".join(
        unicodedata.normalize("NFD", char)[0]
        if "LATIN" in unicodedata.name(char, "") else char
        for char in value
    )


def words(text):
    return tuple(fold(word) for word in WORD.findall(text))


def postgres_stems(vocabulary):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT word, COALESCE((ts_lexize('pg_catalog.russian_stem', word))[1], word)
            FROM unnest(%s::text[]) AS terms(word)
            """,
            (sorted(vocabulary),),
        )
        return dict(cursor.fetchall())


def one_edit(left, right):
    if len(left) > len(right):
        left, right = right, left
    if len(right) - len(left) == 1:
        return any(left == right[:i] + right[i + 1:] for i in range(len(right)))
    if len(left) != len(right):
        return False
    different = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
    if len(different) == 1:
        return True
    if len(different) == 2:
        i, j = different
        return j == i + 1 and left[i] == right[j] and left[j] == right[i]
    return False


def apply_replacements(text, replacements):
    for start, end, replacement in reversed(replacements):
        original = text[start:end]
        if original.isupper():
            replacement = replacement.upper()
        elif original[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        text = text[:start] + replacement + text[end:]
    return text


def correct_title_typos(text, query_stems, known_stems, titles):
    tokens = list(PART.finditer(text))
    values = tuple(fold(token[0]) for token in tokens)
    unknown_positions = {
        index for index, value in enumerate(values)
        if TITLE_WORD.fullmatch(value) and query_stems[value] not in known_stems
    }
    if not unknown_positions:
        return text

    suggestions = defaultdict(set)
    word_count = sum(bool(WORD.fullmatch(value)) for value in values)
    for title in titles:
        if len(title) == 1 and (word_count != 1 or len(title[0]) < 4):
            continue
        normalized_title = tuple(map(fold, title))
        for start in range(len(tokens) - len(title) + 1):
            fragment = values[start:start + len(title)]
            differences = [i for i, (typed, expected) in enumerate(zip(fragment, normalized_title)) if typed != expected]
            if len(differences) != 1:
                continue
            offset = differences[0]
            typed, expected = fragment[offset], normalized_title[offset]
            index = start + offset
            if (index in unknown_positions and len(expected) >= 3
                    and TITLE_WORD.fullmatch(expected) and one_edit(typed, expected)):
                suggestions[index].add(title[offset])

    edits = [(*tokens[index].span(), next(iter(options))) for index, options in sorted(suggestions.items())
             if len(options) == 1]
    return apply_replacements(text, edits)


def correct_query(text, query_stems, known_stems, spelling, note_cases, titles):
    text = correct_title_typos(text, query_stems, known_stems, titles)
    edits = []
    for match in WORD.finditer(text):
        word = fold(match[0])
        if not RUSSIAN_WORD.fullmatch(word) or query_stems[word] in known_stems:
            continue
        candidates = {label for candidate, label in spelling.items() if one_edit(word, candidate)}
        if len(candidates) == 1:
            edits.append((*match.span(), candidates.pop()))
    text = apply_replacements(text, edits)

    tokens = list(WORD.finditer(text))
    values = [fold(token[0]) for token in tokens]
    edits = []
    for index, prep in enumerate(values):
        if prep not in {"с", "со", "без"}:
            continue
        for forms in note_cases:
            expected = forms[2 if prep == "без" else 1]
            for form in forms:
                end = index + 1 + len(words(form))
                if tuple(values[index + 1:end]) != words(form):
                    continue
                start_pos, end_pos = tokens[index + 1].start(), tokens[end - 1].end()
                passage = text[tokens[index].end():end_pos]
                if form != expected and re.fullmatch(r"[\s\w-]+", passage):
                    edits.append((start_pos, end_pos, expected))
                break
            else:
                continue
            break
    return apply_replacements(text, edits)
