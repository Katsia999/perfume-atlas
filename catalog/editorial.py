import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from django.conf import settings
from django.urls import reverse

from .models import Family, Fragrance, Material, Note


ADDITIONAL_ARTICLE_FILES = {
    "Чем отличаются EDT и EDP: две версии Chance Eau Tendre": "edt-and-edp.json",
    "Почему ароматы с ванилью пахнут по-разному": "vanilla-in-perfume.json",
    "Цитрусовые ноты: бергамот, мандарин и грейпфрут": "citrus-notes.json",
    "Как пахнет ветивер и с чем его сочетают": "vetiver-in-perfume.json",
    "Как выбрать парфюм: от блоттера до пробы на коже": "fragrance-testing.json",
    "Две версии Terre d’Hermès: классика и Eau Givrée": "terre-comparison.json",
    "Гардения в парфюмерии: Gucci Flora и Victoria’s Secret Tease": "gardenia-in-perfume.json",
    "Bombshell и Bombshell Intense: как меняется пион": "bombshell-comparison.json",
    "Линейка Tease: от гардении до меренги и какао": "tease-family.json",
    "Четыре Gucci Flora: гардения, жасмин, магнолия и орхидея": "gucci-flora-collection.json",
    "Что означает Intense на примере Valentino Born in Roma": "born-in-roma-intense.json",
    "Чайные ноты в парфюмерии: дым, цитрус и цветы": "tea-in-perfume.json",
    "Пион в ароматах: от граната до вишни": "peony-in-perfume.json",
    "Libre и Idôle: два цветочных аромата с разным характером": "libre-and-idole.json",
    "Гурманские ноты: какао, сливки и жареный каштан": "gourmand-cocoa-and-chestnut.json",
    "Valentino Coral Fantasy: киви и красное яблоко": "valentino-coral-fantasy.json",
}

ARTICLE_FILES = {
    "Что такое верхние ноты, сердце и база": "notes-pyramid.json",
    "Как читать колесо ароматов": "fragrance-wheel.json",
    "Из чего создают парфюмерные композиции": "fragrance-materials.json",
    **ADDITIONAL_ARTICLE_FILES,
}


def load_article(filename):
    path = settings.BASE_DIR / "data" / "articles" / filename
    return json.loads(path.read_text(encoding="utf-8"))


def editorial_article(entry):
    filename = ARTICLE_FILES.get(entry.title)
    if entry.kind != Material.Kind.ARTICLE or not filename:
        return None

    article = load_article(filename)
    for section in article["sections"]:
        for link in section.get("links", []):
            link["url"] = editorial_link(link)
    return article


def editorial_link(link):
    if link["kind"] == "fragrance":
        fragrance = Fragrance.objects.filter(
            brand__name=link["brand"], name=link["name"], version=link["version"],
            is_published=True,
        ).first()
        return reverse("fragrance-detail", args=[fragrance.pk]) if fragrance else None

    if link["kind"] == "video":
        video = Material.objects.filter(
            title=link["title"], kind=Material.Kind.VIDEO, is_published=True,
        ).first()
        return reverse("material-detail", args=[video.pk]) if video else None

    if link["kind"] == "family":
        family = Family.objects.filter(name=link["name"]).first()
        return f"{reverse('catalog')}?{urlencode({'family': family.pk})}" if family else None

    if link["kind"] == "note":
        note = Note.objects.filter(name=link["name"]).first()
        return f"{reverse('selection')}?{urlencode({'note': note.pk})}" if note else None

    raise ValueError(f"Неизвестный тип ссылки в статье: {link['kind']!r}.")


def youtube_embed_url(source_url):
    try:
        url = urlsplit(source_url)
    except ValueError:
        return None
    if url.scheme not in {"http", "https"}:
        return None

    site = url.netloc.lower()
    parts = url.path.split("/")
    video_id = ""
    if site in {"youtube.com", "www.youtube.com", "m.youtube.com"} and url.path == "/watch":
        ids = parse_qs(url.query, keep_blank_values=True).get("v", [])
        if len(ids) == 1:
            video_id = ids[0]
    elif site == "youtu.be" and len(parts) == 2:
        video_id = parts[1]
    elif site in {"youtube.com", "www.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
        if len(parts) == 3 and parts[1] == "embed":
            video_id = parts[2]

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return f"https://www.youtube-nocookie.com/embed/{video_id}"
    return None
