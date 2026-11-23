import re
from collections import defaultdict
from datetime import timedelta
from html import escape
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from catalog.models import Fragrance, FragranceNote, FragrancePerformance, FragranceWear, Material, Note
from catalog.search import NAME_ALIASES, aliases
from catalog.search_language import WORD, words


RESULT_LINK = re.compile(r'<h3>\s*<a href="(/(?:fragrances|materials)/\d+/)"')
RESULT_CARD = re.compile(r'<li class="card">.*?</li>', re.DOTALL)


def urls(entries, view):
    return [reverse(view, args=[pk]) for pk in entries.values_list("pk", flat=True).distinct()]


class Command(BaseCommand):
    help = "Сверяет выдачу работающего локального сайта с ORM-выборками на демонстрационной базе."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=8000)

    def handle(self, *args, **options):
        base = f"http://127.0.0.1:{options['port']}"

        def read(path, params):
            try:
                with urlopen(f"{base}{path}?{urlencode(params, doseq=True)}", timeout=10) as response:
                    return response.read().decode("utf-8")
            except URLError as error:
                raise CommandError(f"Не удалось прочитать {base}{path}. Запустите сайт. {error}") from error

        def check(query, expected=None, *, first=None, contains=(), quiet=False, **params):
            html = read(reverse("search"), {"q": query, **params})
            links = RESULT_LINK.findall(html)
            if expected is not None and sorted(links) != sorted(set(expected)):
                raise CommandError(f"«{query}»: ссылки {links}, ожидались {expected}.")
            if first and (not links or links[0] != first):
                raise CommandError(f"«{query}»: ожидалась первая ссылка {first}, получены {links}.")
            for text in contains:
                if text not in html:
                    raise CommandError(f"«{query}»: на странице нет текста «{text}».")
            if not quiet:
                self.stdout.write(f"{query} · {len(links)}")
            return html

        fragrances = Fragrance.objects.filter(is_published=True)
        materials = Material.objects.filter(is_published=True)
        fruity = Q(character_labels__label__iexact="Фруктовый") | Q(family__name__icontains="фруктов")
        woody = Q(character_labels__label__iexact="Древесный") | Q(family__name="Древесное")
        floral = Q(character_labels__label__iexact="Цветочный") | Q(family__name="Цветочное")
        non_fruity = fragrances.exclude(fruity)
        vanilla = fragrances.filter(notes__name="Ваниль")
        sandal = fragrances.filter(notes__name="Сандал")
        vanilla_sandal = vanilla.filter(notes__name="Сандал")
        vanilla_or_sandal = fragrances.filter(notes__name__in=("Ваниль", "Сандал"))
        if not non_fruity.exists() or not fragrances.filter(fruity).exists():
            raise CommandError("Для проверки нужны опубликованные версии с фруктовым профилем и без него.")

        def fragrance_urls(entries):
            return urls(entries, "fragrance-detail")

        def material_url(title, kind):
            entry = materials.get(title=title, kind=kind)
            return reverse("material-detail", args=[entry.pk])

        check("без фруктового аромата", fragrance_urls(non_fruity), contains=(
            "фруктовый профиль", "опубликованным данным каждой версии",
        ))
        check("Я хочу аромат без фруктовых нот", fragrance_urls(non_fruity))
        if Note.objects.filter(name="Меренга").exists():
            check("аромат с безе", fragrance_urls(fragrances.filter(notes__name="Меренга")))
        check("Можешь посоветовать древесный аромат без мускуса?", fragrance_urls(
            fragrances.filter(woody).exclude(notes__name="Мускус")
        ))
        check("посоветуй что-нибудь древесное без фруктовых нот", fragrance_urls(non_fruity.filter(woody)))
        check("аромат с ванилью и сандалом, но без мускуса", fragrance_urls(
            vanilla_sandal.exclude(notes__name="Мускус")
        ), contains=("Ноты: Ваниль, Сандал",))
        check("хочу аромат с ванилью или сандалом, но без мускуса", fragrance_urls(
            vanilla_or_sandal.exclude(notes__name="Мускус")
        ), contains=(
            "Подходит любой вариант", "<li>нота «Ваниль»</li>", "<li>нота «Сандал»</li>",
            "Общий запрет</strong> — нота «Мускус».",
            "Ноты: Ваниль, Сандал",
        ))
        check("ваниль или сандал", fragrance_urls(vanilla_or_sandal))
        check("с ванилью или с сандалом", fragrance_urls(vanilla_or_sandal))
        check("с ванилью или сандалом или кедром", fragrance_urls(
            fragrances.filter(notes__name__in=("Ваниль", "Сандал", "Кедр"))
        ), contains=("<li>нота «Ваниль»</li>", "<li>нота «Сандал»</li>", "<li>нота «Кедр»</li>"))
        check("с ванилью или сандалом, но без ванили", fragrance_urls(sandal.exclude(notes__name="Ваниль")))
        neither = fragrance_urls(fragrances.exclude(notes__name__in=("Ваниль", "Сандал")))
        check("без ванили или сандала", neither, contains=("Общий запрет</strong> — нота «Ваниль», нота «Сандал».",))
        check("без ванили или без сандала", neither)
        check("с ванилью или сандалом и без мускуса", fragrance_urls(
            vanilla_or_sandal.exclude(notes__name="Мускус")
        ))
        note_links = FragranceNote.objects.filter(fragrance_id=OuterRef("pk"))
        flags = fragrances.annotate(**{
            field: Exists(note_links.filter(note__name=name))
            for field, name in (
                ("vanilla", "Ваниль"), ("sandal", "Сандал"), ("jasmine", "Жасмин"),
                ("musk", "Мускус"), ("cedar", "Кедр"),
            )
        })
        both_or_jasmine = flags.filter(Q(vanilla=True, sandal=True) | Q(jasmine=True))
        without_musk = both_or_jasmine.filter(musk=False)
        cards = check("с ванилью и сандалом или с жасмином, но без мускуса", fragrance_urls(without_musk), contains=(
            "<li>нота «Ваниль» и нота «Сандал»</li>", "<li>нота «Жасмин»</li>",
            "Общий запрет</strong> — нота «Мускус».",
        ))
        notes_by_url = {}
        for entry in without_musk:
            notes = []
            if entry.vanilla and entry.sandal:
                notes.extend(("Ваниль", "Сандал"))
            if entry.jasmine:
                notes.append("Жасмин")
            notes_by_url[reverse("fragrance-detail", args=[entry.pk])] = ", ".join(sorted(notes))
        for card in RESULT_CARD.findall(cards):
            if link := RESULT_LINK.search(card):
                if f"Ноты: {notes_by_url[link[1]]}</p>" not in card:
                    raise CommandError(f"Неверное объяснение совпадений для {link[1]}.")

        for query in (
            "с ванилью и сандалом или с жасмином без мускуса",
            "с ванилью и сандалом или с жасмином и без мускуса",
        ):
            check(query, fragrance_urls(without_musk))
        check("с ванилью или сандалом и жасмином", fragrance_urls(flags.filter(
            Q(vanilla=True) | Q(sandal=True, jasmine=True)
        )), contains=("<li>нота «Ваниль»</li>", "<li>нота «Сандал» и нота «Жасмин»</li>"))
        check("с ванилью и сандалом или жасмином и кедром или розой", fragrance_urls(flags.filter(
            Q(vanilla=True, sandal=True) | Q(jasmine=True, cedar=True) | Q(notes__name="Роза")
        )))
        check("с ванилью и сандалом или с жасмином, но без ванили", fragrance_urls(
            flags.filter(jasmine=True, vanilla=False)
        ))
        check("с ванилью и сандалом или с жасмином, но без ванили и мускуса", fragrance_urls(
            flags.filter(jasmine=True, vanilla=False, musk=False)
        ))
        check("с ванилью и сандалом или с жасмином, но без ванили и жасмина", [],
              contains=("требуется и исключается",))
        check("с ванилью или без сандала", [], contains=("Упростите условие с «или»",))
        check("с (ванилью или сандалом) и жасмином", [], contains=("без скобок",))
        check("с ванилью или", [], contains=("Укажите оба варианта с «или»",))
        check("ваниль или клубничный сироп", [], contains=("клубничный сироп». Уточните",))
        check("что-нибудь сладкое, но не фруктовое", fragrance_urls(
            non_fruity.filter(character_labels__label="Сладкий")
        ))
        check("аромат без мускуса и кедра", fragrance_urls(fragrances.exclude(notes__name__in=("Мускус", "Кедр"))))
        check("древесное семейство", fragrance_urls(fragrances.filter(family__name="Древесное")))
        for query, version in (("Герлен EDP", "Eau de Parfum"), ("Guerlain EDТ", "Eau de Toilette")):
            check(query, fragrance_urls(fragrances.filter(brand__name="Guerlain", version=version)))
        check("парфюмерная вода от Шанели", fragrance_urls(
            fragrances.filter(brand__name="Chanel", version="Eau de Parfum")
        ))
        vanilla_floral = fragrance_urls(vanilla.filter(floral))
        check("Духи с запахом ванили и цветов", vanilla_floral, contains=("цветочный профиль", "Ноты: Ваниль"))
        check("Духи с запахом ванили и цыетов", vanilla_floral,
              contains=("<strong>Духи с запахом ванили и цветов</strong>", "original=1"))
        check("Духи с запахом ванили и цыетов", [], original=1, contains=("цыетов». Уточните",))
        check("Духи с цветом", [], contains=("цветом». Уточните",))
        check("Ищу духи, которые пахнут ванилью и цветами", vanilla_floral)
        check("Я ищу парфюм с нотами ванили и сандала", fragrance_urls(vanilla_sandal))
        check("Порекомендуй духи с древесным звучанием без запаха мускуса", fragrance_urls(
            fragrances.filter(woody).exclude(notes__name="Мускус")
        ))
        check("Предпочитаю туалетную водичку марки Шанель", fragrance_urls(
            fragrances.filter(brand__name="Chanel", version="Eau de Toilette")
        ))
        check("Порекомендуй цветочный аромат марки Шанелл", fragrance_urls(
            fragrances.filter(floral, brand__name="Chanel")
        ), contains=("<strong>Порекомендуй цветочный аромат марки Шанель</strong>",))
        chance = fragrances.filter(brand__name="Chanel", name="Chance Eau Tendre")
        typo = "шанель шанс о тандер"
        check(typo, fragrance_urls(chance), contains=(
            "<strong>шанель шанс о тандр</strong>", "Название: Chanel Chance Eau Tendre", "original=1",
        ))
        check(typo, original=1, contains=("Ищем по исходному запросу", "Применить исправления"))
        check("Шанс О Тандер", fragrance_urls(chance), contains=("<strong>Шанс О Тандр</strong>",))
        check(f"{typo} EDT", fragrance_urls(chance.filter(version="Eau de Toilette")),
              contains=("<strong>шанель шанс о тандр EDT</strong>",))
        check(f"{typo} парфюмерная вода", fragrance_urls(chance.filter(version="Eau de Parfum")))
        check("Шанель Коко Мадмуазель", fragrance_urls(fragrances.filter(
            brand__name="Chanel", name="Coco Mademoiselle"
        )), contains=("<strong>Шанель Коко Мадемуазель</strong>",))
        check("Шанс О Тандр EDT", fragrance_urls(chance.filter(version="Eau de Toilette")))
        check("Chance Eau Tendre Eau de Parfum", fragrance_urls(chance.filter(version="Eau de Parfum")))
        check("Шанс О Тандр без мускуса", fragrance_urls(chance.exclude(notes__name="Мускус")))

        by_name = defaultdict(list)
        for entry in fragrances.select_related("brand"):
            by_name[entry.brand, entry.name].append(reverse("fragrance-detail", args=[entry.pk]))
        alias_count = 0
        for (brand, name), links in by_name.items():
            russian_labels = NAME_ALIASES.get(" ".join(words(name)), ())
            if not russian_labels:
                raise CommandError(f"Нет русского написания для {brand.name} {name}.")
            brand_label = next((label for label in aliases(brand.aliases) if re.search(r"[а-яё]", label, re.I)),
                               brand.name)
            for label in russian_labels:
                check(f"{brand_label} {label}", links, quiet=True)
            alias_count += len(russian_labels)

            label = russian_labels[0]
            html = check(label, quiet=True)
            if set(links) - set(RESULT_LINK.findall(html)):
                raise CommandError(f"«{label}»: без бренда найдены не все версии {brand.name} {name}.")

            longest = max(WORD.finditer(label), key=lambda word: len(word[0]))
            middle = longest.start() + len(longest[0]) // 2
            misspelled = label[:middle] + label[middle] + label[middle:]
            check(f"{brand_label} {misspelled}", links, quiet=True, contains=(
                f"<strong>{escape(f'{brand_label} {label}')}</strong>",
            ))
        self.stdout.write(f"{len(by_name)} названий · русских написаний — {alias_count} · "
                          f"{sum(map(len, by_name.values()))} карточек. Опечатка проверена для каждого названия.")

        check("аромат с ванилью и без ванили", [], contains=("требуется и исключается",))
        check("аромат без мускуса и клубничного сиропа", [], contains=("клубничного сиропа». Уточните",))

        performance = FragrancePerformance.objects.filter(fragrance_id=OuterRef("pk"))
        performance_flags = flags.annotate(
            long_lasting=Exists(performance.filter(kind="longevity", level="long")),
            light_sillage=Exists(performance.filter(kind="sillage", level="light")),
            strong_sillage=Exists(performance.filter(kind="sillage", level="strong")),
            known_sillage=Exists(performance.filter(kind="sillage")),
        )
        all_versions = fragrance_urls(fragrances)
        for query in (
            "духи с любой стойкостью и шлейфом",
            "духи с любой стойкостью и любым шлейфом",
            "духи с любым шлейфом и стойкостью",
            "стойкость и шлейф не важны",
        ):
            check(query, all_versions, contains=("Без ограничений</strong> — стойкость, шлейф.",))
        check("духи с любым шлейфом", all_versions, contains=("Без ограничений</strong> — шлейф.",))
        check("духи с любой стойкостью и шлейфом", [], kind="article")
        check("духи с ванилью и любой стойкостью и шлейфом", fragrance_urls(vanilla),
              contains=("нота «Ваниль»", "Без ограничений</strong> — стойкость, шлейф."))
        check("духи с любой стойкостью и лёгким шлейфом", fragrance_urls(
            performance_flags.filter(light_sillage=True)
        ), contains=("шлейф «Лёгкий»", "Без ограничений</strong> — стойкость."))
        check("духи с любой стойкостью и шлейфом, но без мускуса", fragrance_urls(
            fragrances.exclude(notes__name="Мускус")
        ), contains=("Общий запрет</strong> — нота «Мускус».",))
        check("с ванилью или с любым шлейфом", all_versions)
        check("с ванилью и любой стойкостью или с лёгким шлейфом", fragrance_urls(
            performance_flags.filter(Q(vanilla=True) | Q(light_sillage=True))
        ))
        check("с любым шлейфом, но без сильного шлейфа", fragrance_urls(
            performance_flags.filter(known_sillage=True, strong_sillage=False)
        ))
        exact = fragrance_urls(performance_flags.filter(vanilla=True, long_lasting=True, light_sillage=True))
        for query in (
            "хочу стойкие духи с ванилью и лёгким шлейфом",
            "Хочу духи с хорошей стойкостью, ванилью и легким шлейфом",
            "Хочу духи с ванилью и ненавязчивым шлейфом, которые долго держатся",
        ):
            check(query, exact, contains=("стойкость «Высокая»", "нота «Ваниль»", "шлейф «Лёгкий»"))
        check("подбери что-нибудь стойкое", fragrance_urls(performance_flags.filter(long_lasting=True)))
        check("духи с лёгким шлейфом", fragrance_urls(performance_flags.filter(light_sillage=True)))
        check("Духи с запахом ванили и сильным шлейфом", fragrance_urls(
            performance_flags.filter(vanilla=True, strong_sillage=True)
        ))
        check("с лёгким шлейфом или с ванилью, но без сильного шлейфа", fragrance_urls(
            performance_flags.filter(Q(light_sillage=True) | Q(vanilla=True), known_sillage=True, strong_sillage=False)
        ), contains=("Общий запрет</strong> — шлейф «Заметный».",))
        empty_hint = ("нет подходящей по всем условиям",)
        if performance_flags.filter(known_sillage=False).exists():
            empty_hint += ("Для части версий нет официальных данных",)
        check("духи с лёгким шлейфом и заметным шлейфом", [], contains=empty_hint)

        wear = FragranceWear.objects.filter(fragrance_id=OuterRef("pk"))

        def wear_option(kind, option):
            return Exists(wear.filter(kind=kind, options__contains=[option]))

        wear_flags = performance_flags.annotate(
            year_round=wear_option("season", "all_year"),
            spring=wear_option("season", "spring"),
            summer=wear_option("season", "summer"),
            autumn=wear_option("season", "autumn"),
            winter=wear_option("season", "winter"),
            day=wear_option("time", "day"),
            evening=wear_option("time", "evening"),
            light_profile=wear_option("lightness", "light"),
            vanilla_profile=Exists(fragrances.filter(pk=OuterRef("pk"), character_labels__label="Ванильный")),
        )
        summer = Q(summer=True) | Q(year_round=True)
        winter = Q(winter=True) | Q(year_round=True)
        evening_vanilla = wear_flags.filter(Q(vanilla=True) | Q(vanilla_profile=True), evening=True)
        light_summer = wear_flags.filter(summer, light_profile=True)
        for query in ("лёгкие духи на лето", "легкие духи летом", "воздушный летний аромат"):
            check(query, fragrance_urls(light_summer), contains=(
                "сезон «Лето»", "Характер звучания: Лёгкий", "#when-to-wear",
            ))
        check("ванильный аромат на вечер", fragrance_urls(evening_vanilla), contains=(
            "ванильный профиль (нота «Ваниль» или метка «Ванильный»)", "Время суток: Вечер",
        ))
        for query in ("духи днём", "духи днем", "дневные духи"):
            check(query, fragrance_urls(wear_flags.filter(day=True)), contains=("Время суток: День",))
        for query in ("духи летом", "лето", "духи в летний сезон"):
            check(query, fragrance_urls(wear_flags.filter(summer)), contains=("сезон «Лето»",))
        for query in ("подскажи, какие духи подойдут на зиму", "зимние духи", "зима"):
            check(query, fragrance_urls(wear_flags.filter(winter)), contains=("сезон «Зима»",))
        check("духи весной", fragrance_urls(wear_flags.filter(Q(year_round=True) | Q(spring=True))),
              contains=("сезон «Весна»",))
        check("духи осенью", fragrance_urls(wear_flags.filter(Q(year_round=True) | Q(autumn=True))),
              contains=("сезон «Осень»",))
        check("Порекомендуй цветочные духи на зиму", fragrance_urls(wear_flags.filter(winter, floral)),
              contains=("цветочный профиль", "сезон «Зима»", "#when-to-wear"))
        check("духи на лето или зиму", fragrance_urls(wear_flags.filter(summer | winter)),
              contains=("Подходит любой вариант", "сезон «Лето»", "сезон «Зима»"))
        check("духи на лето либо зиму", fragrance_urls(wear_flags.filter(summer | winter)))
        check("духи на лето и зиму", fragrance_urls(wear_flags.filter(summer & winter)),
              contains=("сезон «Лето» и сезон «Зима»",))
        check("духи на лето, а также на зиму", fragrance_urls(wear_flags.filter(summer & winter)))
        check("духи на весну, лето и осень", fragrance_urls(wear_flags.filter(
            Q(year_round=True) | Q(spring=True, summer=True, autumn=True)
        )))
        check("духи с ванилью для зимнего вечера", fragrance_urls(wear_flags.filter(winter, vanilla=True, evening=True)),
              contains=("сезон «Зима»", "время суток «Вечер»"))
        check("духи на лето с любой стойкостью и шлейфом", fragrance_urls(wear_flags.filter(summer)),
              contains=("Без ограничений</strong> — стойкость, шлейф.",))
        check("стойкие духи на зиму", fragrance_urls(wear_flags.filter(winter, long_lasting=True)),
              contains=("сезон «Зима»", "стойкость «Высокая»"))
        check("духи на лето с легким шлейфом", fragrance_urls(wear_flags.filter(summer, light_sillage=True)),
              contains=("сезон «Лето»", "шлейф «Лёгкий»"))
        check("сезон не важен, хочу духи с лёгким шлейфом", fragrance_urls(performance_flags.filter(light_sillage=True)),
              contains=("Без ограничений</strong> — сезон.",))
        check("сезон не важен", all_versions, contains=("Без ограничений</strong> — сезон.",))
        check("духи на зиму, но не летом", fragrance_urls(wear_flags.filter(winter=True, summer=False, year_round=False)),
              contains=("Общий запрет</strong> — сезон «Лето».", "#when-to-wear"))
        for query in ("когда лучше носить Шанель Шанс О Тандр", "шанель шанс о тандер на какой сезон"):
            check(query, fragrance_urls(chance), contains=("Сезон: Весна", "Время суток: День", "#when-to-wear"))
        check("Terre d’Hermès EDT на какое время года", fragrance_urls(fragrances.filter(
            brand__name="Hermès", name="Terre d’Hermès", version="Eau de Toilette"
        )), contains=("Сезон: Круглый год", "#when-to-wear"))
        check("свежие духи летом", fragrance_urls(
            wear_flags.filter(summer, character_labels__label="Свежий")
        ), contains=("характер «Свежий»",))
        check("духи круглый год", fragrance_urls(wear_flags.filter(year_round=True)))
        for query, option in (("на весну", "spring"), ("на лето", "summer"), ("на осень", "autumn"), ("на зиму", "winter")):
            seasonal = wear_flags.annotate(matches_season=wear_option("season", option))
            check(f"Terre d’Hermès EDT {query}", fragrance_urls(seasonal.filter(
                Q(year_round=True) | Q(matches_season=True), name="Terre d’Hermès", version="Eau de Toilette",
            )))
        check("лёгкие духи на лето или с ванилью на вечер, но без мускуса", fragrance_urls(
            wear_flags.filter((summer & Q(light_profile=True)) | Q(vanilla=True, evening=True), musk=False)
        ), contains=("Подходит любой вариант", "Общий запрет"))
        check("духи днём, но не на лето", fragrance_urls(
            wear_flags.annotate(has_season=Exists(wear.filter(kind="season"))).filter(
                day=True, has_season=True, summer=False, year_round=False,
            )
        ))
        check("духи без лёгкого звучания", [], contains=("Для части версий недостаточно сведений",))
        check("духи на лето, но без тропической жары", [], contains=("Не удалось распознать условие",))

        for entry in fragrances.prefetch_related("wear"):
            facts = {fact.kind: fact for fact in entry.wear.all()}
            if not {"season", "time"} <= facts.keys():
                raise CommandError(f"У версии {entry} отсутствует сезон или время суток.")
            html = read(reverse("fragrance-detail", args=[entry.pk]), {})
            for fact in facts.values():
                marker = f'data-wear="{fact.kind}"'
                card = html.split(marker, 1)[-1].split("</div>", 1)[0] if marker in html else ""
                expected = (
                    ", ".join(fact.option_labels), fact.get_basis_display(), fact.description,
                    fact.source_url, f"{fact.verified_on:%d.%m.%Y}",
                )
                if "Когда носить" not in html or any(escape(value) not in card for value in expected):
                    raise CommandError(f"У версии {entry} неверно показано поле {fact.kind}.")
        self.stdout.write(f"Блок «Когда носить» · {fragrances.count()} карточек со ссылками и датами.")

        for query, label in (
            ("Ищу духи с ванилью до 5000 рублей", "цену"),
            ("духи держатся 8 часов", "стойкость в часах"),
            ("Духи без запаха", "полное отсутствие запаха"),
        ):
            check(query, [], contains=(f"По данным каталога нельзя проверить {label}.",))
        check("Герлен EDT/EDP", [], contains=("Попробуйте каждый вариант отдельным запросом",))
        check("аромат с ландышем и ветивером", [], contains=("нет подходящей по всем условиям",))
        article_query = check("аромат с ванилью и сандалом", kind="article")
        if any(link.startswith("/fragrances/") for link in RESULT_LINK.findall(article_query)):
            raise CommandError("Поиск по статьям показал карточку аромата.")
        bergamot_results = check("бергамт", contains=(
            "<strong>бергамот</strong>", "original=1",
        ))
        etoile = fragrance_urls(fragrances.filter(name="Etoile"))[0]
        if etoile not in RESULT_LINK.findall(bergamot_results):
            raise CommandError("После исправления «бергамт» не найдена карточка Etoile.")
        check("бергамт", [], original=1, contains=("по исходному запросу",))
        check("с ваниль", fragrance_urls(vanilla), contains=("<strong>с ванилью</strong>", "original=1"))
        check("с ваниль", fragrance_urls(vanilla), original=1, contains=("Применить исправления",))
        check("Покажи аромат с ваниль и без мускуса", fragrance_urls(vanilla.exclude(notes__name="Мускус")),
              contains=("<strong>Покажи аромат с ванилью и без мускуса</strong>",))
        check("Что такое ноты сердца?", first=material_url("Что такое верхние ноты, сердце и база", "article"))
        check("Покажи видео о том, как выбрать аромат", [material_url("Как найти свой аромат", "video")], kind="video")
        moonlight = material_url("LOEWE представил лимитированный аромат Moonlight", "news")
        check("Moonlight", fragrance_urls(fragrances.filter(name="Moonlight")) + [moonlight])
        check("Moonlight", [moonlight], kind="news")
        until = timezone.localdate()
        since = until - timedelta(days=29)
        recent = materials.filter(kind="news", published_on__range=(since, until))
        check("Какие новые ароматы представили за месяц?", urls(recent, "material-detail"), contains=(
            f"{since:%d.%m.%Y} – {until:%d.%m.%Y}",
        ))
        check("свежие новости", urls(recent, "material-detail"), kind="news")
        for kind in Material.Kind.values:
            check("", urls(materials.filter(kind=kind), "material-detail"), kind=kind)

        note_ids = list(Note.objects.filter(name__in=("Ваниль", "Сандал")).values_list("pk", flat=True))
        selection = RESULT_LINK.findall(read(reverse("selection"), {"note": note_ids}))
        both = set(fragrance_urls(vanilla_sandal))
        either = set(fragrance_urls(fragrances.filter(notes__pk__in=note_ids)))
        if not both or set(selection[:len(both)]) != both or set(selection) != either:
            raise CommandError(f"Подбор по ванили и сандалу: найдено {selection}, ожидались {sorted(either)}.")
        self.stdout.write(f"Подбор по ванили и сандалу · {len(selection)}, с обеими нотами · {len(both)}")
        self.stdout.write(self.style.SUCCESS("Проверки локального поиска и подбора пройдены."))
