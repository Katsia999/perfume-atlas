from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Fragrance, FragranceNote, Note

from .import_demo import load_csv, read_date, save_entry


def save_pyramid_notes(fragrance, row):
    levels = [
        (name.strip(), level)
        for level in FragranceNote.Level.values
        if row[level]
        for name in row[level].split("|")
    ]
    names = {name for name, _ in levels}
    if not names or "" in names or len(names) != len(levels):
        raise ValueError("Укажите хотя бы одну ноту. Каждую ноту указывайте один раз.")
    for name, level in levels:
        note = Note.objects.filter(name=name).first()
        if note is None:
            note = save_entry(Note, {"name": name}, {})
        save_entry(FragranceNote, {"fragrance": fragrance, "note": note}, {"level": level})
    return len(levels)


class Command(BaseCommand):
    help = "Записать сверенные уровни пирамид для демонстрационных версий."

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = settings.BASE_DIR / "data"
        demo_entries = load_csv(
            data_dir / "demo",
            "fragrances.csv",
            "code brand name version family family_origin description source_url verified_on",
            lambda row: (row["code"], row),
        )

        def save_pyramid(row):
            code = row["fragrance_code"]
            demo = demo_entries[code]
            fragrance = Fragrance.objects.filter(
                brand__name=demo["brand"], name=demo["name"], version=demo["version"],
            ).first()
            if fragrance is None:
                raise ValueError(f"Версия {code!r} отсутствует. Сначала выполните import_demo.")
            if not row["source_url"]:
                raise ValueError("Укажите ссылку на источник уровней.")
            fragrance.pyramid_source_url = (
                "" if row["source_url"] == fragrance.source_url else row["source_url"]
            )
            fragrance.pyramid_verified_on = read_date(row["verified_on"])
            fragrance.full_clean()
            fragrance.save(update_fields=["pyramid_source_url", "pyramid_verified_on"])
            return code, save_pyramid_notes(fragrance, row)

        pyramids = load_csv(
            data_dir / "card_profiles", "pyramids.csv",
            "fragrance_code top heart base source_url verified_on",
            save_pyramid,
        )
        if not pyramids:
            raise CommandError("В pyramids.csv нет записей.")
        self.stdout.write(self.style.SUCCESS(
            f"Обработано версий: {len(pyramids)}. Нот с указанными уровнями: {sum(pyramids.values())}."
        ))
