import csv
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Brand, Family, Fragrance, FragranceNote, Material, Note


def read_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError(f"Используйте формат даты ГГГГ-ММ-ДД: {value!r}.")
    return parsed


def save_entry(model, key, fields):
    entry = model.objects.filter(**key).first() or model(**key)
    for name, value in fields.items():
        setattr(entry, name, value)
    entry.full_clean()
    entry.save()
    return entry


def load_csv(directory, filename, columns, save_row):
    imported = {}
    try:
        with (directory / filename).open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            if sorted(reader.fieldnames or []) != sorted(columns.split()):
                raise CommandError(f"{filename}: ожидаются столбцы {columns}.")

            for row in reader:
                location = f"{filename}, строка {reader.line_num}"
                if None in row or None in row.values():
                    raise CommandError(f"{location}: неверное количество столбцов.")
                row = {name: value.strip() for name, value in row.items()}
                try:
                    key, entry = save_row(row)
                except KeyError as exc:
                    raise CommandError(f"{location}: неизвестная ссылка {exc.args[0]!r}.") from exc
                except (ValueError, ValidationError) as exc:
                    raise CommandError(f"{location}: {exc}") from exc
                if key in imported:
                    raise CommandError(f"{location}: повтор строки с ключом {key!r}.")
                imported[key] = entry
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CommandError(f"{filename}: {exc}") from exc
    return imported


def load_dictionary(directory, filename, model, columns):
    def save_row(row):
        name = row.pop("name")
        return name, save_entry(model, {"name": name}, row)

    return load_csv(directory, filename, columns, save_row)


def sourced_fields(row):
    return {
        "description": row["description"],
        "source_url": row["source_url"],
        "verified_on": read_date(row["verified_on"]),
        "is_published": True,
    }


def topics(value, dictionary):
    return [dictionary[name.strip()] for name in value.split("|")] if value else []


class Command(BaseCommand):
    help = "Загрузить демонстрационный каталог из CSV."

    def add_arguments(self, parser):
        parser.add_argument("--directory", type=Path, default=settings.BASE_DIR / "data" / "demo")

    @transaction.atomic
    def handle(self, *args, **options):
        directory = options["directory"]
        brands = load_dictionary(directory, "brands.csv", Brand, "name aliases")
        families = load_dictionary(directory, "families.csv", Family, "name description")
        notes = load_dictionary(directory, "notes.csv", Note, "name aliases description")

        fragrance_keys = set()

        def save_fragrance(row):
            code = row["code"]
            if not code:
                raise ValueError("Укажите код аромата для связей с нотами.")
            origin = row["family_origin"]
            if origin not in ("source", "catalog"):
                raise ValueError("Допустимые значения family_origin: source и catalog.")
            brand = brands[row["brand"]]
            identity = (brand.pk, row["name"], row["version"])
            if identity in fragrance_keys:
                raise ValueError("Эта версия аромата уже встречалась в CSV.")
            fragrance_keys.add(identity)
            fragrance = save_entry(
                Fragrance,
                {"brand": brand, "name": row["name"], "version": row["version"]},
                {
                    **sourced_fields(row),
                    "family": families[row["family"]],
                    "family_from_source": origin == "source",
                },
            )
            return code, fragrance

        fragrances = load_csv(
            directory,
            "fragrances.csv",
            "code brand name version family family_origin description source_url verified_on",
            save_fragrance,
        )

        def save_fragrance_note(row):
            fragrance = fragrances[row["fragrance_code"]]
            note = notes[row["note"]]
            link = save_entry(
                FragranceNote, {"fragrance": fragrance, "note": note}, {"level": row["level"]}
            )
            return (row["fragrance_code"], row["note"]), link

        links = load_csv(
            directory, "fragrance_notes.csv", "fragrance_code note level", save_fragrance_note
        )

        def save_material(row):
            published = row["published_on"]
            material = save_entry(
                Material,
                {"kind": row["kind"], "title": row["title"]},
                {
                    **sourced_fields(row),
                    "body": row["body"],
                    "published_on": read_date(published) if published else None,
                },
            )
            material.notes.set(topics(row["notes"], notes))
            material.families.set(topics(row["families"], families))
            return (row["kind"], row["title"]), material

        materials = load_csv(
            directory,
            "materials.csv",
            "kind title description body source_url verified_on published_on notes families",
            save_material,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано строк CSV: бренды — {len(brands)}, семейства — {len(families)}, "
                f"ноты — {len(notes)}, ароматы — {len(fragrances)}, "
                f"связи ароматов с нотами — {len(links)}, материалы — {len(materials)}."
            )
        )
