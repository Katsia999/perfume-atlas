from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from catalog.editorial import ADDITIONAL_ARTICLE_FILES, load_article, youtube_embed_url
from catalog.models import Family, Material, Note

from .import_demo import read_date


class Command(BaseCommand):
    help = "Загрузить дополнительные статьи журнала из data/articles."

    @transaction.atomic
    def handle(self, *args, **options):
        notes = Note.objects.in_bulk(field_name="name")
        families = Family.objects.in_bulk(field_name="name")
        if not notes or not families:
            raise CommandError("Сначала загрузите демонстрационные справочники командой import_demo.")

        for title, filename in ADDITIONAL_ARTICLE_FILES.items():
            try:
                article = load_article(filename)
                self.save_article(title, article, notes, families)
            except (OSError, ValueError, KeyError, ValidationError) as error:
                raise CommandError(f"{filename}: {error}") from error
        self.stdout.write(self.style.SUCCESS(f"Обработано статей: {len(ADDITIONAL_ARTICLE_FILES)}."))

    def save_article(self, title, article, notes, families):
        for source in article["sources"]:
            URLValidator(schemes=["https"])(source["url"])

        video = article.get("video")
        if video and not youtube_embed_url(video["source_url"]):
            raise ValueError("Укажите ссылку на ролик YouTube.")

        paragraphs = [article["lead"]]
        for section in article["sections"]:
            paragraphs.extend([section["heading"], *section["paragraphs"]])
        if video:
            paragraphs.extend([video["title"], video["description"]])

        fields = {
            "description": article["description"],
            "body": "\n\n".join(paragraphs),
            "source_url": article["sources"][0]["url"],
            "verified_on": read_date(article["verified_on"]),
        }
        entry, _ = Material.objects.update_or_create(
            kind=Material.Kind.ARTICLE, title=title, defaults=fields,
            create_defaults={**fields, "is_published": True},
        )
        entry.notes.set([notes[name] for name in article["notes"]])
        entry.families.set([families[name] for name in article["families"]])
