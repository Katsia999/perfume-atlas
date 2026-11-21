from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from catalog.models import Fragrance, FragrancePerformance

from .import_demo import load_csv, read_date, save_entry


class Command(BaseCommand):
    help = "Загрузить подтверждённые производителями сведения о стойкости и шлейфе."

    def add_arguments(self, parser):
        parser.add_argument("--directory", type=Path, default=settings.BASE_DIR / "data" / "card_profiles")

    @transaction.atomic
    def handle(self, *args, **options):
        def save_row(row):
            identity = (row["brand"], row["name"], row["version"])
            fragrance = Fragrance.objects.filter(
                brand__name=identity[0], name=identity[1], version=identity[2],
            ).select_for_update(of=("self",)).first()
            if fragrance is None:
                raise ValueError(f"Версия {identity!r} отсутствует. Сначала импортируйте каталог.")

            verified_on = read_date(row["verified_on"])
            checked_urls = row["checked_urls"].split("|")
            for url in checked_urls:
                URLValidator(schemes=["http", "https"])(url)
            imported = set()
            for kind in FragrancePerformance.Kind.values:
                level, description, source_url = (
                    row[f"{kind}_{field}"] for field in ("level", "description", "source_url")
                )
                if not (level or description or source_url):
                    continue
                if source_url not in checked_urls:
                    raise ValueError(f"Добавьте ссылку {source_url!r} в перечень проверенных источников.")
                save_entry(
                    FragrancePerformance, {"fragrance": fragrance, "kind": kind},
                    {"level": level, "description": description, "source_url": source_url, "verified_on": verified_on},
                )
                imported.add(kind)
            return identity, imported

        rows = load_csv(
            options["directory"], "performance.csv",
            "brand name version checked_urls verified_on review_note "
            "longevity_level longevity_description longevity_source_url "
            "sillage_level sillage_description sillage_source_url",
            save_row,
        )
        if not rows:
            raise CommandError("В performance.csv нет записей.")
        longevity = sum("longevity" in facts for facts in rows.values())
        sillage = sum("sillage" in facts for facts in rows.values())
        self.stdout.write(self.style.SUCCESS(
            f"Проверено версий по журналу: {len(rows)}. Загружено значений стойкости: {longevity}, шлейфа: {sillage}."
        ))
