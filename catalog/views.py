from urllib.parse import urlsplit
from uuid import uuid4

from django import forms
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .editorial import editorial_article, youtube_embed_url
from .fragrance_photos import local_bottle_photos
from .models import Brand, Family, Fragrance, FragrancePerformance, FragranceRating, Material, Note
from .search import FRAGRANCE, search


EXAMPLES = (
    "бергамот",
    "Подбери что-нибудь с запахом шоколадного десерта",
    "древесные ароматы",
    "без фруктового аромата",
    "Духи на лето или зиму",
    "Аромат с ваниль и без мускуса",
    "Что такое ноты сердца?",
    "Покажи видео о том, как выбрать аромат",
    "Какие новые ароматы представили за месяц?",
)

FAMILY_ILLUSTRATIONS = {
    "Цветочное": ("floral.webp", "Жасмин и лепестки розы"),
    "Древесное": ("wood.webp", "Щепки сандала и древесная стружка"),
    "Цитрусовое": ("fresh.webp", "Плоды бергамота"),
    "Амбровое": ("amber.webp", "Стручки ванили и кусочки смолы"),
    "Цветочно-фруктовое": ("floral.webp", "Жасмин и лепестки розы"),
    "Гурманское": ("gourmand.jpg", "Тёмный шоколад, какао и стручки ванили"),
}
FEATURED_NOTES = ("Ваниль", "Сандал", "Бергамот", "Жасмин", "Кедр", "Мускус", "Пачули", "Роза")
NOTE_GROUPS = (
    ("top", "Верхние ноты"), ("heart", "Ноты сердца"), ("base", "Базовые ноты"),
)
RATING_SESSION_KEY = "fragrance_rating_visitor"
MATERIAL_LIST_TITLES = {
    Material.Kind.ARTICLE: "Все статьи",
    Material.Kind.VIDEO: "Все видео",
    Material.Kind.NEWS: "Все новости",
}


class SearchForm(forms.Form):
    q = forms.CharField(
        label="Запрос",
        required=False,
        max_length=1500,
        widget=forms.TextInput(attrs={"placeholder": "Название, вопрос или описание своими словами"}),
    )
    kind = forms.ChoiceField(
        label="Тип результата",
        required=False,
        choices=(
            ("", "Все типы"),
            (FRAGRANCE, "Ароматы"),
            (Material.Kind.ARTICLE, "Статьи"),
            (Material.Kind.VIDEO, "Видео"),
            (Material.Kind.NEWS, "Новости"),
        ),
    )


def home(request):
    featured = list(FAMILY_ILLUSTRATIONS)[:4]
    families = Family.objects.filter(name__in=featured).in_bulk(field_name="name")
    journal = Material.objects.filter(is_published=True).order_by("-published_on", "title")
    return render(request, "catalog/home.html", {
        "form": SearchForm(),
        "examples": EXAMPLES[:3],
        "families": [
            {"entry": families[name], "image": FAMILY_ILLUSTRATIONS[name]}
            for name in featured if name in families
        ],
        "journal": [
            journal.filter(kind=Material.Kind.ARTICLE).order_by("pk").first(),
            journal.filter(kind=Material.Kind.VIDEO).order_by("pk").first(),
            journal.filter(kind=Material.Kind.NEWS).first(),
        ],
    })


class CatalogForm(forms.Form):
    family = forms.ModelChoiceField(
        label="Семейство", queryset=Family.objects.all(), required=False, empty_label="Все семейства",
    )
    brand = forms.ModelChoiceField(
        label="Бренд", queryset=Brand.objects.all(), required=False, empty_label="Все бренды",
    )


class SelectionForm(forms.Form):
    note = forms.ModelMultipleChoiceField(
        label="Ноты", queryset=Note.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
    )


class RatingForm(forms.Form):
    value = forms.TypedChoiceField(
        label="Ваша оценка",
        choices=[(value, str(value)) for value in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Выберите оценку от 1 до 5.",
            "invalid_choice": "Выберите оценку от 1 до 5.",
        },
    )


def published_fragrances():
    return Fragrance.objects.filter(is_published=True).select_related("brand", "family")


def catalog_page(request):
    form = CatalogForm(request.GET)
    entries = published_fragrances()
    if form.is_valid():
        for name, value in form.cleaned_data.items():
            if value:
                entries = entries.filter(**{name: value})
    else:
        entries = entries.none()
    entries = list(entries.prefetch_related("notes"))
    photos = local_bottle_photos(entries)
    return render(request, "catalog/catalog.html", {
        "form": form,
        "cards": [{"entry": entry, "photo": photos.get(entry.pk)} for entry in entries],
        "filtered": bool(request.GET.get("family") or request.GET.get("brand")),
    })


def selection_page(request):
    form = SelectionForm(request.GET)
    selected = list(form.cleaned_data["note"]) if form.is_valid() else []
    selected_ids = {note.pk for note in selected}
    results = []
    if selected_ids:
        matches = Note.objects.filter(pk__in=selected_ids)
        entries = published_fragrances().filter(notes__in=selected_ids).distinct().prefetch_related(
            Prefetch("notes", queryset=matches, to_attr="matched_notes")
        )
        results = sorted(entries, key=lambda entry: len(entry.matched_notes), reverse=True)

    notes = list(form.fields["note"].queryset)
    by_name = {note.name: note for note in notes}
    featured = [by_name[name] for name in FEATURED_NOTES if name in by_name]
    other = [note for note in notes if note.name not in FEATURED_NOTES]
    return render(request, "catalog/selection.html", {
        "form": form,
        "results": results,
        "selected": selected,
        "selected_ids": selected_ids,
        "featured": featured,
        "other": other,
        "other_open": any(note.pk in selected_ids for note in other),
    })


def search_page(request):
    form = SearchForm(request.GET)
    response = None
    original = request.GET.get("original") == "1"
    list_title = None
    if form.is_valid():
        query, kind = form.cleaned_data["q"], form.cleaned_data["kind"]
        list_title = MATERIAL_LIST_TITLES.get(kind) if not query else None
        if query or list_title:
            response = search(query, kind, autocorrect=not original)
    return render(request, "catalog/search.html", {
        "form": form,
        "examples": EXAMPLES,
        "query": form.cleaned_data.get("q", ""),
        "list_title": list_title,
        "response": response,
        "original": original,
    })


@require_http_methods(["GET", "HEAD", "POST"])
def fragrance_detail(request, pk):
    entry = get_object_or_404(published_fragrances(), pk=pk)
    visitor_id = request.session.get(RATING_SESSION_KEY)
    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            if visitor_id is None:
                visitor_id = request.session[RATING_SESSION_KEY] = str(uuid4())
            with transaction.atomic():
                published = published_fragrances().select_for_update(of=("self",))
                get_object_or_404(published, pk=pk)
                FragranceRating.objects.update_or_create(
                    fragrance=entry, visitor_id=visitor_id,
                    defaults={"value": form.cleaned_data["value"]},
                )
            return redirect(reverse("fragrance-detail", args=[pk]) + "#rating")

    if visitor_id is None and request.method == "GET":
        visitor_id = request.session[RATING_SESSION_KEY] = str(uuid4())
    personal_rating = (
        entry.ratings.filter(visitor_id=visitor_id).values_list("value", flat=True).first()
        if visitor_id else None
    )
    if request.method != "POST":
        form = RatingForm(initial={"value": personal_rating})

    note_links = list(entry.fragrancenote_set.select_related("note").order_by("note__name"))
    notes_by_level = {level: [] for level, _ in NOTE_GROUPS}
    unassigned_notes = []
    for link in note_links:
        if link.level:
            notes_by_level[link.level].append(link.note)
        else:
            unassigned_notes.append(link.note)
    related = Material.objects.filter(is_published=True).filter(
        Q(families=entry.family) | Q(notes__in=[link.note_id for link in note_links])
    ).distinct()
    photo = local_bottle_photos([entry]).get(entry.pk)
    performance = {fact.kind: fact for fact in entry.performance.all()}
    return render(request, "catalog/fragrance.html", {
        "entry": entry,
        "character_labels": entry.character_labels.all(),
        "wear": list(entry.wear.all().order_by("-kind")),
        "performance": [
            (label, performance.get(kind)) for kind, label in FragrancePerformance.Kind.choices
        ],
        "note_groups": [
            (level, label, notes_by_level[level]) for level, label in NOTE_GROUPS
            if notes_by_level[level]
        ],
        "unassigned_notes": unassigned_notes,
        "pyramid_source_host": (
            urlsplit(entry.pyramid_source_url).hostname
            if entry.pyramid_source_url and entry.pyramid_source_url != entry.source_url
            else None
        ),
        "rating": entry.ratings.aggregate(average=Avg("value"), total=Count("pk")),
        "rating_form": form,
        "personal_rating": personal_rating,
        "photo": photo,
        "illustration": None if photo else FAMILY_ILLUSTRATIONS.get(entry.family.name),
        "related": related,
        "source_host": urlsplit(entry.source_url).hostname,
    }, status=400 if request.method == "POST" else 200)


def material_detail(request, pk):
    queryset = Material.objects.filter(is_published=True).prefetch_related("notes", "families")
    entry = get_object_or_404(queryset, pk=pk)
    article = editorial_article(entry)
    article_video = article.get("video") if article else None
    return render(request, "catalog/material.html", {
        "entry": entry,
        "editorial": article,
        "article_video": article_video,
        "article_video_url": youtube_embed_url(article_video["source_url"]) if article_video else None,
        "video_url": youtube_embed_url(entry.source_url) if entry.kind == Material.Kind.VIDEO else None,
        "source_host": urlsplit(entry.source_url).hostname,
    })
