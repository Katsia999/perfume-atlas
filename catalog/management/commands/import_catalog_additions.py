import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from catalog.models import Brand, Family, Fragrance, FragranceNote

from .import_demo import load_csv, save_entry, sourced_fields
from .import_profiles import save_character
from .import_pyramids import save_pyramid_notes


COLUMNS = (
    "code brand brand_aliases name version family family_origin description labels "
    "top heart base source_url pyramid_source_url verified_on "
    "photo_source_url image_url terms_url photo_filename photo_width photo_height evidence_note"
)
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
PHOTO_FIELDS = ("photo_source_url", "image_url", "terms_url", "photo_filename", "photo_width", "photo_height")
HTTPS_URL = URLValidator(schemes=["https"])


def validate_photo(row):
    if not any(row[field] for field in PHOTO_FIELDS):
        return
    if not all(row[field] for field in PHOTO_FIELDS):
        raise ValueError("Заполните все данные официальной фотографии.")
    filename = Path(row["photo_filename"])
    if filename.name != row["photo_filename"] or filename.stem != row["code"] or filename.suffix not in PHOTO_SUFFIXES:
        raise ValueError("Имя фото должно состоять из кода версии и расширения изображения.")
    if min(int(row["photo_width"]), int(row["photo_height"])) < 1:
        raise ValueError("Укажите положительные размеры фотографии.")
    for field in ("photo_source_url", "image_url", "terms_url"):
        HTTPS_URL(row[field])


class Command(BaseCommand):
    help = "Загрузить новые версии с характером и подтверждёнными нотами."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=Path,
            default=settings.BASE_DIR / "data" / "catalog_additions" / "fragrances.csv",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        file = options["file"]
        demo_versions = load_csv(
            settings.BASE_DIR / "data" / "demo", "fragrances.csv",
            "code brand name version family family_origin description source_url verified_on",
            lambda row: (row["code"], (row["brand"], row["name"], row["version"])),
        )
        identities = set(demo_versions.values())

        def save_fragrance(row):
            code = row["code"]
            identity = (row["brand"], row["name"], row["version"])
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", code):
                raise ValueError("Используйте латинский код версии с цифрами и дефисами.")
            if code in demo_versions or identity in identities:
                raise ValueError("Версия уже входит в исходный набор или повторяется в партии.")
            if row["family_origin"] not in ("source", "catalog"):
                raise ValueError("Допустимые значения family_origin: source и catalog.")
            has_levels = any(row[level] for level in FragranceNote.Level.values)
            if not all(row[level] for level in FragranceNote.Level.values) and not (
                row.get("notes") and row["evidence_note"]
            ):
                raise ValueError("Укажите три уровня или общий список нот и объясните неполную пирамиду.")
            validate_photo(row)
            HTTPS_URL(row["source_url"])
            if row["pyramid_source_url"]:
                HTTPS_URL(row["pyramid_source_url"])
            identities.add(identity)

            brand = Brand.objects.filter(name=row["brand"]).first()
            if brand is None:
                brand = save_entry(Brand, {"name": row["brand"]}, {"aliases": row["brand_aliases"]})
            family = Family.objects.filter(name=row["family"]).first()
            if family is None:
                family = save_entry(Family, {"name": row["family"]}, {})
            fields = sourced_fields(row)
            fragrance = save_entry(
                Fragrance, {"brand": brand, "name": row["name"], "version": row["version"]},
                {
                    **fields,
                    "family": family,
                    "family_from_source": row["family_origin"] == "source",
                    "pyramid_source_url": (
                        "" if row["pyramid_source_url"] == row["source_url"] else row["pyramid_source_url"]
                    ),
                    "pyramid_verified_on": fields["verified_on"] if has_levels else None,
                },
            )
            return code, (save_character(fragrance, row["labels"]), save_pyramid_notes(fragrance, row))

        added = load_csv(file.parent, file.name, COLUMNS, save_fragrance, optional_columns=("notes",))
        if not added:
            raise CommandError(f"{file.name}: добавьте хотя бы одну версию.")
        self.stdout.write(self.style.SUCCESS(
            f"Обработано версий: {len(added)}. Меток: {sum(labels for labels, _ in added.values())}. "
            f"Связей с нотами: {sum(notes for _, notes in added.values())}."
        ))
