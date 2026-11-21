from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Fragrance, FragranceWear

from .import_demo import load_csv, read_date, save_entry


class Command(BaseCommand):
    help = "Загрузить рекомендации по сезону и времени суток и сведения о лёгком звучании."

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

            kind = row["kind"]
            fact = save_entry(
                FragranceWear, {"fragrance": fragrance, "kind": kind},
                {
                    "options": row["options"].split("|"),
                    "basis": row["basis"],
                    "description": row["description"],
                    "source_url": row["source_url"],
                    "verified_on": read_date(row["verified_on"]),
                },
            )
            return (*identity, kind), fact

        rows = load_csv(
            options["directory"], "wear.csv", "brand name version kind options basis description source_url verified_on",
            save_row,
        )
        if not rows:
            raise CommandError("В wear.csv нет записей.")

        required = {FragranceWear.Kind.SEASON, FragranceWear.Kind.TIME}
        kinds = {}
        for (*identity, kind) in rows:
            kinds.setdefault(tuple(identity), set()).add(kind)
        for identity, supplied in kinds.items():
            if not required <= supplied:
                raise CommandError(f"Для версии {identity!r} укажите и сезон, и время суток.")

        self.stdout.write(self.style.SUCCESS(f"Загружено записей: {len(rows)}. Версий в наборе: {len(kinds)}."))
