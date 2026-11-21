from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Fragrance, FragranceCharacter

from .import_demo import load_csv, save_entry


def save_character(fragrance, value):
    labels = [label.strip() for label in value.split("|")]
    if not 3 <= len(labels) <= 5 or "" in labels or len(set(labels)) != len(labels):
        raise ValueError("Укажите от трёх до пяти разных непустых меток.")
    for position, label in enumerate(labels, start=1):
        save_entry(
            FragranceCharacter, {"fragrance": fragrance, "label": label},
            {"position": position},
        )
    return len(labels)


class Command(BaseCommand):
    help = "Добавить проверенные метки характера к демонстрационным версиям."

    @transaction.atomic
    def handle(self, *args, **options):
        data_dir = settings.BASE_DIR / "data"
        demo_entries = load_csv(
            data_dir / "demo",
            "fragrances.csv",
            "code brand name version family family_origin description source_url verified_on",
            lambda row: (row["code"], row),
        )

        def save_profile(row):
            code = row["fragrance_code"]
            demo = demo_entries[code]
            fragrance = Fragrance.objects.filter(
                brand__name=demo["brand"], name=demo["name"], version=demo["version"],
            ).first()
            if fragrance is None:
                raise ValueError(f"Версия {code!r} отсутствует. Сначала выполните import_demo.")
            return code, save_character(fragrance, row["labels"])

        profiles = load_csv(
            data_dir / "card_profiles", "profiles.csv", "fragrance_code labels", save_profile,
        )
        missing = demo_entries.keys() - profiles.keys()
        if missing:
            raise CommandError(f"В profiles.csv отсутствуют версии: {', '.join(sorted(missing))}.")
        self.stdout.write(
            self.style.SUCCESS(f"Обработано профилей: {len(profiles)}. Меток: {sum(profiles.values())}.")
        )
